#!/usr/bin/env python3
"""Print items.json one line per item: set, run, item, commits, counts, problems, finding rounds."""
import json, os, sys

items = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "items.json")))
for i in items:
    if i["set"] == "control-ineligible" and "-a" not in sys.argv:
        continue
    rounds = sorted({(f["round"], (f["round_head"] or "-")[:8], (f["round_reflog_head"] or "-")[:8]) for f in i.get("findings", [])})
    print(i["set"][:9], i["run"][4:], i["item"], i.get("branch"), i["review"], i["repo"], len(i["musts"]),
          (i["head"] or "-")[:8], (i.get("reflog_head") or "-")[:8], len(i.get("tests", [])), len(i.get("new_tests", [])),
          len(i.get("sources", [])), i["problems"], rounds)
