#!/usr/bin/env bash
# Runs one read-only review as a Copilot CLI process under `timeout`, never as an in-chat subagent, through
# `route.py run`, which picks or takes the override, logs it, and launches with exactly the logged values.
#
# Usage: bash review.sh [route.py run options] <name> <worktree> [prompt-file]
#   prompt-file  default: $OW_RUN_DIR/<name>.md; each bare {{RUBRIC}} (not in `code`, a fence, a > quote or a comment)
#                is filled from references/rubric.md into $OW_RUN_DIR/<name>.filled.md, launched instead. Any {{...}} left outside `code` and comments is refused.
#   options      passed to route.py run: --override "model=..,effort=..,cap=..,reason=.." (reason required),
#                --author-model M (default: read from the author round's log), --timeout S (default: budgets.json
#                <name> or "review" minutes x 60), --add-dir D, --load-wait MIN, --seed N, --no-classifier, --fresh
# Output: $OW_RUN_DIR/<name>.jsonl, <name>.err and <name>.txt (the verdict line of the last message, which
# mine.py reads); prints the decision, start, end, exit code and result.py's summary.
set -u

opts=()
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) sed -n '2,12p' "$0" | cut -c3-; exit 0 ;;
    --no-classifier|--fresh) opts+=("$1"); shift ;;
    --*) [ $# -ge 2 ] || { echo "review.sh: $1 needs a value" >&2; exit 2; }; opts+=("$1" "$2"); shift 2 ;;
    *) break ;;
  esac
done
if [ $# -lt 2 ]; then
  echo "usage: bash review.sh [route.py run options] <name> <worktree> [prompt-file]" >&2
  exit 2
fi
name="$1"; wt="$2"
run="${OW_RUN_DIR:?set OW_RUN_DIR to the run folder}"
prompt="${3:-$run/$name.md}"
here="$(cd "$(dirname "$0")" && pwd)"

[ -d "$wt" ] || { echo "review.sh: no worktree at $wt" >&2; exit 2; }
[ -f "$prompt" ] || { echo "review.sh: no prompt at $prompt" >&2; exit 2; }
prompt="$(python3 -B - "$prompt" "$here/../references/rubric.md" "$run/$name.filled.md" <<'EOF'
import os, re, sys
src, rubric, out = sys.argv[1:4]
with open(src, encoding='utf-8') as f:
    text = f.read()
masked = re.sub(r'<!--.*?-->', lambda m: re.sub(r'[^\n]', ' ', m.group()), text, flags=re.S)
slots, fence, start = [], None, 0
for line in masked.split('\n'):
    at, start, line = start, start + len(line) + 1, line.rstrip('\r')
    if fence:
        m = re.match(r' {0,3}(`{3,}|~{3,})[ \t]*$', line)
        if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
            fence = None
        continue
    m = re.match(r' {0,3}(`{3,}(?=[^`]*$)|~{3,})', line)
    if m:
        fence = m.group(1)
        continue
    if re.match(r' {0,3}>', line):
        continue
    # Spans paired as brief.py pairs them, so a slot left unfilled is one its check would also see.
    spans = [s.span() for s in re.finditer(r'`[^`]*`', line)]
    slots += [at + s.start() for s in re.finditer(r'\{\{RUBRIC\}\}', line)
              if not any(a <= s.start() < b for a, b in spans)]
if slots:
    if os.path.realpath(src) == os.path.realpath(out):
        sys.exit(f'review.sh: {src} would be overwritten by its filled copy; rename it; nothing launched')
    if not os.path.isfile(rubric):
        sys.exit(f'review.sh: {src} needs {{{{RUBRIC}}}} but there is no rubric at {rubric}')
    with open(rubric, encoding='utf-8') as f:
        body = f.read().rstrip('\n')
    filled = text
    for p in reversed(slots):
        filled = filled[:p] + body + filled[p + len('{{RUBRIC}}'):]
else:
    filled, out = text, src
visible = re.sub(r'`[^`\n]*`', '', re.sub(r'<!--.*?-->', '', filled, flags=re.S))
left = sorted(set(re.findall(r'\{\{[^{}\n]+\}\}', visible)))
if left:
    sys.exit(f'review.sh: {src} has unfilled placeholders: {" ".join(left)}; nothing launched')
if out != src:
    with open(out + '.tmp', 'w', encoding='utf-8') as f:
        f.write(filled)
    os.replace(out + '.tmp', out)
print(out)
EOF
)" || exit 2
rm -f "$run/$name.txt"
python3 -B "$here/route.py" run "$name" --kind review --run "$run" --brief "$prompt" --worktree "$wt" \
  ${opts[@]+"${opts[@]}"} </dev/null
rc=$?
python3 -B - "$here" "$run/$name.jsonl" "$run/$name.txt" <<'EOF'
import os, sys
sys.path.insert(0, sys.argv[1])
import mine
r = mine.read_round(sys.argv[2]) if os.path.exists(sys.argv[2]) else None
line = mine.verdict_line(r and r['message'])
if line:
    with open(sys.argv[3], 'w', encoding='utf-8') as f:
        f.write(line + '\n')
else:
    print('review.sh: no "Blocking: none" or "N blocking" line in the last message; no verdict written', file=sys.stderr)
EOF
exit "$rc"
