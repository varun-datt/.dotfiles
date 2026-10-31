#!/usr/bin/env bash
# Runs one read-only review as a Copilot CLI process under `timeout`, never as an in-chat subagent, through
# `route.py run`, which picks or takes the override, logs it, and launches with exactly the logged values.
#
# Usage: bash review.sh [route.py run options] <name> <worktree> [prompt-file]
#   prompt-file  default: $OW_RUN_DIR/<name>.md
#   options      passed to route.py run: --override "model=..,effort=..,cap=..,reason=.." (reason required),
#                --author-model M (default: read from the author round's log), --timeout S (default: budgets.json
#                <name> or "review" minutes x 60), --add-dir D, --load-wait MIN, --seed N, --no-classifier, --fresh
# Output: $OW_RUN_DIR/<name>.jsonl, <name>.err and <name>.txt (the verdict line of the last message, which
# mine.py reads); prints the decision, start, end, exit code and result.py's summary.
set -u

opts=()
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) sed -n '2,11p' "$0" | cut -c3-; exit 0 ;;
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
