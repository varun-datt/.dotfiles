#!/bin/sh
# Prints Tavily's plan usage and limit for the stored key, never the key itself.
set -eu
hdr=$(mktemp)
trap 'rm -f "$hdr"' EXIT
chmod 600 "$hdr"
python3 -c "import json,os;print('Authorization: Bearer '+json.load(open(os.path.expanduser('~/.tavily/config.json')))['api_key'])" > "$hdr"
curl -sf -H @"$hdr" https://api.tavily.com/usage </dev/null | python3 -c "
import json, sys
a = json.load(sys.stdin)['account']
left = (a['plan_limit'] or 0) - (a['plan_usage'] or 0)
print(f\"plan {a['current_plan']}: {a['plan_usage']} of {a['plan_limit']} used, {left} left; pay-as-you-go {a['paygo_usage']} of {a['paygo_limit']}\")"
