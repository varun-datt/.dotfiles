#!/usr/bin/env python3
"""Correct the two items whose findings came from a later round (critique B1): take the head of the item's first review in any run.

discover.py looked for a first review only inside the finding's run, so it fell back to the finding's own round. Here the first review is the
earliest review round of the item across runs (rv-<item> or <item>-review*), its head the branch's reflog entry at that round's .start time,
cross-checked against the round's own .base file or the next fix round's .base. Each map drops the tests absent at that head, and the earlier
outputs move to items/superseded/.
"""
import glob, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
ITEMS = os.path.join(OUT, "items")
sys.path.insert(0, HERE)
import discover  # noqa: E402

FIXES = {
    ("amc-2026-10-29", "insights-history"): ("amc-2026-10-28", "rv-insights-history", "amc-2026-10-28/insights-history-fix2.base"),
    ("amc-2026-11-02", "g10a-post"): ("amc-2026-11-02", "g10a-post-review2", "amc-2026-11-02/g10a-post-review2.base"),
}


def present(head, t):
    src = subprocess.run(["git", "-C", discover.AMC, "show", f"{head}:{t['file']}"], capture_output=True, text=True).stdout
    name = t["name"].split(" > ")[-1]
    return name.split("${")[0].split(" the file")[0].split(" the missing folder")[0][:50] in src


def main():
    items = json.load(open(os.path.join(OUT, "items.json")))
    os.makedirs(os.path.join(ITEMS, "superseded"), exist_ok=True)
    for i in items:
        fx = FIXES.get((i["run"], i["item"]))
        if not fx or i.get("first_review_run"):
            continue
        run, rnd, check = fx
        when = int(open(os.path.join(discover.STATE, run, f"{rnd}.start")).read().split()[0])
        head, how = discover.reflog_at(i["branch"], when)
        other = open(os.path.join(discover.STATE, check)).read().split()[0]
        assert head == other, (i["item"], head, other)
        k = f"{i['run']}__{i['item']}"
        for f in glob.glob(os.path.join(ITEMS, f"{k}.*")):
            if not f.endswith(".map.json"):
                shutil.move(f, os.path.join(ITEMS, "superseded", os.path.basename(f)))
        shutil.copy(os.path.join(ITEMS, f"{k}.map.json"), os.path.join(ITEMS, "superseded", f"{k}.map.json"))
        i.update({"later_head": i["head"], "later_head_how": i["head_how"], "head": head, "first_review_run": run, "first_review": rnd,
                  "head_how": f"{how}; first review {run}/{rnd}.start; agrees with {check}"})
        i.update(discover.item_info_files(i))
        m = json.load(open(os.path.join(ITEMS, f"{k}.map.json")))
        dropped = []
        for e in m["map"]:
            keep = [t for t in e.get("tests") or [] if present(head, t)]
            dropped += [f"MUST {e['must']}: {t['file']}::{t['name']}" for t in e.get("tests") or [] if t not in keep]
            e["tests"] = keep
            if not keep and not e.get("none"):
                e["none"] = "every mapped test was added after the first review"
        m["head"] = head
        m["notes"] = (m.get("notes") or "") + f" Remapped to the first review's head {head[:10]}: dropped tests absent there: {dropped}."
        json.dump(m, open(os.path.join(ITEMS, f"{k}.map.json"), "w"), indent=1)
        print(k, head[:10], "dropped", len(dropped))
    json.dump(items, open(os.path.join(OUT, "items.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
