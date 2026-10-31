#!/usr/bin/env bash
# Runs one read-only review as a Copilot CLI process under `timeout`, never as an in-chat subagent, through
# `route.py run`, which picks or takes the override, logs it, and launches with exactly the logged values.
#
# Usage: bash review.sh [route.py run options] <name> <worktree> [prompt-file]
#   prompt-file  default: $OW_RUN_DIR/<name>.md; when it holds {{RUBRIC}}, a copy with references/rubric.md filled in
#                is written to $OW_RUN_DIR/<name>.filled.md and launched instead. Any other {{...}} left is refused.
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
parts = re.split(r'(<!--.*?-->)', text, flags=re.S)
if any('{{RUBRIC}}' in p for p in parts[::2]):
    if os.path.realpath(src) == os.path.realpath(out):
        sys.exit(f'review.sh: {src} would be overwritten by its filled copy; rename it; nothing launched')
    if not os.path.isfile(rubric):
        sys.exit(f'review.sh: {src} needs {{{{RUBRIC}}}} but there is no rubric at {rubric}')
    with open(rubric, encoding='utf-8') as f:
        body = f.read().rstrip('\n')
    parts[::2] = [p.replace('{{RUBRIC}}', body) for p in parts[::2]]
    filled = ''.join(parts)
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
