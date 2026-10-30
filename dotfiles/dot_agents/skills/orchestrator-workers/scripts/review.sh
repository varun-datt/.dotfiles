#!/usr/bin/env bash
# Runs one read-only review as a Copilot CLI process under `timeout`, never as an in-chat subagent.
#
# Usage: bash review.sh [--model M] [--effort E] [--cap N] [--timeout S] <name> <worktree> [prompt-file]
#   prompt-file  default: $OW_RUN_DIR/<name>.md
#   --model      default: $OW_REVIEW_MODEL, else gpt-6.1-sol
#   --effort     --reasoning-effort; default: $OW_REVIEW_EFFORT, else high (max for a risk-area diff)
#   --cap        --max-ai-credits; default: $OW_REVIEW_CAP, else 80
#   --timeout    seconds; default: $OW_REVIEW_TIMEOUT, else budgets.json <name> or "review" minutes x 60, else 1800
# Output: $OW_RUN_DIR/<name>.jsonl, <name>.err and <name>.txt (the verdict line of the last message, which
# mine.py reads); prints start, end, exit code and result.py's summary.
set -u

model="${OW_REVIEW_MODEL:-gpt-6.1-sol}"
effort="${OW_REVIEW_EFFORT:-high}"
cap="${OW_REVIEW_CAP:-80}"
secs="${OW_REVIEW_TIMEOUT:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --model) model="$2"; shift 2 ;;
    --effort) effort="$2"; shift 2 ;;
    --cap) cap="$2"; shift 2 ;;
    --timeout) secs="$2"; shift 2 ;;
    -h|--help) sed -n '2,11p' "$0" | cut -c3-; exit 0 ;;
    *) break ;;
  esac
done
if [ $# -lt 2 ]; then
  echo "usage: bash review.sh [--model M] [--effort E] [--cap N] [--timeout S] <name> <worktree> [prompt-file]" >&2
  exit 2
fi
name="$1"; wt="$2"
run="${OW_RUN_DIR:?set OW_RUN_DIR to the run folder}"
prompt="${3:-$run/$name.md}"
here="$(cd "$(dirname "$0")" && pwd)"

[ -d "$wt" ] || { echo "review.sh: no worktree at $wt" >&2; exit 2; }
[ -f "$prompt" ] || { echo "review.sh: no prompt at $prompt" >&2; exit 2; }
if grep -q '{{[A-Za-z_]' "$prompt"; then
  echo "review.sh: $prompt still holds a {{PLACEHOLDER}}; fill it first" >&2
  exit 2
fi
if [ -z "$secs" ]; then
  secs=$(python3 - "$run/budgets.json" "$name" <<'EOF'
import json, sys
try:
    b = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    b = {}
m = b.get(sys.argv[2], b.get('review'))
print(int(float(m) * 60) if isinstance(m, (int, float)) else 1800)
EOF
)
fi

date +%s > "$run/$name.start"
rm -f "$run/$name.txt"
nomcp=()
while IFS= read -r s; do [ -n "$s" ] && nomcp+=(--disable-mcp-server "$s"); done < <(python3 - <<'EOF'
import json, os
try:
    print('\n'.join(json.load(open(os.path.expanduser('~/.copilot/mcp-config.json'))).get('mcpServers', {})))
except (OSError, ValueError):
    pass
EOF
)
echo "start: $(date '+%Y-%m-%d %H:%M:%S')  $name  model=$model effort=$effort cap=$cap timeout=${secs}s"
timeout "$secs" copilot -C "$wt" -n "${OW_PREFIX:-ow-}$name" --model "$model" --reasoning-effort "$effort" --max-ai-credits "$cap" \
  --no-ask-user --allow-all-tools --deny-tool 'shell(git push)' --deny-tool 'shell(git commit)' \
  --deny-tool 'shell(npm)' --deny-tool=url --disable-builtin-mcps ${nomcp[@]+"${nomcp[@]}"} --output-format json \
  -p "$(cat "$prompt"; printf '\n\nYour LAST message is the only one read: repeat every finding in it in full, even ones an earlier message gave.\n')" </dev/null > "$run/$name.jsonl" 2> "$run/$name.err"
rc=$?
echo "end:   $(date '+%Y-%m-%d %H:%M:%S')  exit $rc$([ "$rc" -eq 124 ] && echo ' TIMED OUT')"
python3 "$here/result.py" "$run/$name.jsonl"
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
