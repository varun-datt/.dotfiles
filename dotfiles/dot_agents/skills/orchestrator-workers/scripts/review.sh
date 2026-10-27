#!/usr/bin/env bash
# Runs one read-only review as a Copilot CLI process under `timeout`, never as an in-chat subagent.
#
# Usage: bash review.sh [--model M] [--cap N] [--timeout S] <name> <worktree> [prompt-file]
#   prompt-file  default: $OW_RUN_DIR/<name>.md
#   --model      default: $OW_REVIEW_MODEL, else gpt-6.1-sol
#   --cap        --max-ai-credits; default: $OW_REVIEW_CAP, else 80
#   --timeout    seconds; default: $OW_REVIEW_TIMEOUT, else budgets.json <name> or "review" minutes x 60, else 1800
# Output: $OW_RUN_DIR/<name>.jsonl and <name>.err; prints start, end, exit code and result.py's summary.
set -u

model="${OW_REVIEW_MODEL:-gpt-6.1-sol}"
cap="${OW_REVIEW_CAP:-80}"
secs="${OW_REVIEW_TIMEOUT:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --model) model="$2"; shift 2 ;;
    --cap) cap="$2"; shift 2 ;;
    --timeout) secs="$2"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0" | cut -c3-; exit 0 ;;
    *) break ;;
  esac
done
if [ $# -lt 2 ]; then
  echo "usage: bash review.sh [--model M] [--cap N] [--timeout S] <name> <worktree> [prompt-file]" >&2
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
nomcp=()
while IFS= read -r s; do [ -n "$s" ] && nomcp+=(--disable-mcp-server "$s"); done < <(python3 - <<'EOF'
import json, os
try:
    print('\n'.join(json.load(open(os.path.expanduser('~/.copilot/mcp-config.json'))).get('mcpServers', {})))
except (OSError, ValueError):
    pass
EOF
)
echo "start: $(date '+%Y-%m-%d %H:%M:%S')  $name  model=$model cap=$cap timeout=${secs}s"
timeout "$secs" copilot -C "$wt" -n "${OW_PREFIX:-ow-}$name" --model "$model" --max-ai-credits "$cap" \
  --no-ask-user --allow-all-tools --deny-tool 'shell(git push)' --deny-tool 'shell(git commit)' \
  --deny-tool 'shell(npm)' --deny-tool=url --disable-builtin-mcps ${nomcp[@]+"${nomcp[@]}"} --output-format json \
  -p "$(cat "$prompt")" </dev/null > "$run/$name.jsonl" 2> "$run/$name.err"
rc=$?
echo "end:   $(date '+%Y-%m-%d %H:%M:%S')  exit $rc$([ "$rc" -eq 124 ] && echo ' TIMED OUT')"
python3 "$here/result.py" "$run/$name.jsonl"
exit "$rc"
