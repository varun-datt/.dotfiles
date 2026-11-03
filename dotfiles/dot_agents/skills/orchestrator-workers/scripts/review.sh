#!/usr/bin/env bash
# Runs one read-only review as a Copilot CLI process under `timeout`, never as an in-chat subagent, through
# `route.py run`, which picks or takes the override, logs it, and launches with exactly the logged values.
#
# Usage: bash review.sh [route.py run options] <name> <worktree> [prompt-file]
#   prompt-file  default: $OW_RUN_DIR/<name>.md; each bare {{RUBRIC}} (not in `code`, a fence, a > quote or a comment)
#                is filled from references/rubric.md into $OW_RUN_DIR/<name>.filled.md, launched instead; a prompt
#                with no {{RUBRIC}} gets the scope line and the rubric's Scope rule appended there. Any {{...}} left outside `code` and comments is refused.
#   options      passed to route.py run: --override "model=..,effort=..,cap=..,reason=.." (reason required),
#                --author-model M (default: read from the author round's log), --timeout S (default: budgets.json
#                <name> or "review" minutes x 60), --add-dir D, --load-wait MIN, --seed N, --no-classifier, --fresh
#   --project D  a research critique (a prompt opening "You are a read-only critic") reads the run folder, and D, the
#                project repository, when given; without it the critic reads the run folder only, said on stderr
#   --scope S    product or tool, the rubric's blocking scope, filled in after the rubric, and wins over the default.
#                Default: tool when every changed file in <worktree>/REVIEW-DIFF.patch is under
#                dotfiles/dot_agents/skills/*/scripts/, else product (no patch, or a mixed diff, whose check-tool files
#                the line lists to be graded as tool)
# Refuses (exit 2) when started under caffeinate, which this Mac kills within seconds.
# Output: $OW_RUN_DIR/<name>.jsonl, <name>.err and <name>.txt (the verdict line of the last message, which
# mine.py reads); prints the decision, start, end, exit code and result.py's summary.
set -u

opts=(); project=; scope=
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) sed -n '2,20p' "$0" | cut -c3-; exit 0 ;;
    --no-classifier|--fresh) opts+=("$1"); shift ;;
    --project) [ $# -ge 2 ] && [ -d "$2" ] || { echo "review.sh: --project needs a folder" >&2; exit 2; }
      project="$(cd "$2" && pwd)"; shift 2 ;;
    --scope) case "${2:-}" in product|tool) scope="$2"; shift 2 ;;
      *) echo "review.sh: --scope takes product or tool" >&2; exit 2 ;; esac ;;
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

python3 -B -c 'import sys; sys.path.insert(0, sys.argv[1]); import runqueue; r = runqueue.caffeinate_refusal()
r and print("review.sh: " + r, file=sys.stderr); sys.exit(2 if r else 0)' "$here" </dev/null || exit 2
[ -d "$wt" ] || { echo "review.sh: no worktree at $wt" >&2; exit 2; }
[ -f "$prompt" ] || { echo "review.sh: no prompt at $prompt" >&2; exit 2; }
prompt="$(python3 -B - "$prompt" "$here/../references/rubric.md" "$run/$name.filled.md" "$here" "$wt" "$scope" <<'EOF'
import os, re, sys
src, rubric, out, here, wt, given = sys.argv[1:7]
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
if os.path.realpath(src) == os.path.realpath(out):
    sys.exit(f'review.sh: {src} would be overwritten by its filled copy; rename it; nothing launched')
sys.path.insert(0, here)
import route
patch = os.path.join(wt, 'REVIEW-DIFF.patch')
diff = open(patch, encoding='utf-8', errors='replace').read() if os.path.isfile(patch) else None
scope, tools, note = route.review_scope(diff)
if given:
    scope, tools, note = given, [], 'given by --scope'
elif diff is None:
    print(f'review.sh: no REVIEW-DIFF.patch in {wt}, so the review is graded at scope product', file=sys.stderr)
listed = ' Graded as tool whatever the scope, being check tools: ' + ', '.join(tools) + '.' if scope == 'product' and tools else ''
rule = ''
if os.path.isfile(rubric):
    with open(rubric, encoding='utf-8') as f:
        body = f.read().rstrip('\n')
    rule = next((l[len('- **Scope.** '):] for l in body.split('\n') if l.startswith('- **Scope.** ')), '')
if slots:
    if not os.path.isfile(rubric):
        sys.exit(f'review.sh: {src} needs {{{{RUBRIC}}}} but there is no rubric at {rubric}')
    body += f'\n\nScope of this change: {scope} ({note}). Grade with the Scope rule in section 4.' + listed
    filled = text
    for p in reversed(slots):
        filled = filled[:p] + body + filled[p + len('{{RUBRIC}}'):]
else:
    filled = text.rstrip('\n') + f'\n\nScope of this change: {scope} ({note}).' + listed + \
        (f" Grade with the review rubric's Scope rule: {rule}" if rule else '') + '\n'
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
critic="$(python3 -B -c 'import sys; sys.path.insert(0, sys.argv[1]); import brief
t = open(sys.argv[2], encoding="utf-8").read()
print(next((l for _, l in brief.outside_fences(brief.brief_lines(t)) if l.strip()), "").startswith("You are a read-only critic"))' \
  "$here" "$prompt" </dev/null)"
if [ "$critic" = True ]; then
  opts+=(--add-dir "$(cd "$run" && pwd)")
  [ -n "$project" ] || echo "review.sh: no --project given, so the critic reads the run folder only" >&2
fi
[ -z "$project" ] || opts+=(--add-dir "$project")
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
