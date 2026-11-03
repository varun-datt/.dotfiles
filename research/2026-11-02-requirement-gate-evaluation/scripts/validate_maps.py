#!/usr/bin/env python3
"""Check each INFERRED map: every brief MUST present, every named test's title found in its file at the head."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
ITEMS = os.path.join(OUT, "items")
AMC = os.path.expanduser("~/sandbox/personal/agent-mission-control")
sys.path.insert(0, os.path.expanduser("~/worktrees/chezmoi/r3/dotfiles/dot_agents/skills/orchestrator-workers/scripts"))
from brief import must_items  # noqa: E402


def show(ref, path):
    p = subprocess.run(["git", "-C", AMC, "show", f"{ref}:{path}"], capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def main():
    items = json.load(open(os.path.join(OUT, "items.json")))
    bad = 0
    for i in items:
        k = f"{i['run']}__{i['item']}"
        mp = os.path.join(ITEMS, f"{k}.map.json")
        if not os.path.exists(mp):
            continue
        m = json.load(open(mp))
        musts = [str(x[0]) for x in must_items(open(os.path.expanduser(i["brief"])).read().splitlines())]
        have = [str(e["must"]) for e in m["map"]]
        issues = []
        if sorted(musts, key=int) != sorted(have, key=lambda x: int(x) if x.isdigit() else 0):
            issues.append(f"MUSTs brief={musts} map={have}")
        cache = {}
        for e in m["map"]:
            for t in e.get("tests") or []:
                src = cache.setdefault(t["file"], show(i["head"], t["file"]))
                if src is None:
                    issues.append(f"missing file {t['file']}")
                    continue
                leaf = t["name"].split(" > ")[-1]
                if leaf not in src and leaf.replace("'", "\\'") not in src:
                    issues.append(f"title not found: {t['file']}::{leaf[:70]}")
        if issues:
            bad += 1
            print(k, *issues, sep="\n  ")
    print("maps with issues:", bad)


if __name__ == "__main__":
    main()
