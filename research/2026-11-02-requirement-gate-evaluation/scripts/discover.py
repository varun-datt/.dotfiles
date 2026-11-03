#!/usr/bin/env python3
"""Find each past item's build base and the head its first review saw; write items.json.

Scope: blocking findings with focus requirement (not critique rounds) or focus test, from
findings.csv; controls: first reviews with neither, sampled with a fixed seed.
"""
import csv, json, os, random, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
RF = os.path.join(OUT, "..", "2026-11-02-review-focus-learning")
STATE = os.path.expanduser("~/.local/state/orchestrator-workers")
AMC = os.path.expanduser("~/sandbox/personal/agent-mission-control")
GATE = os.path.expanduser("~/worktrees/chezmoi/r3/dotfiles/dot_agents/skills/orchestrator-workers/scripts")
sys.path.insert(0, GATE)
from brief import brief_lines, must_items  # noqa: E402

SEED = 20261102
TEST_FILE = re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$")
JS = re.compile(r"\.[cm]?[jt]sx?$")


def git(*a):
    p = subprocess.run(["git", "-C", AMC, *a], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout.strip()


def read(p):
    return open(p, encoding="utf-8", errors="replace").read().strip() if p and os.path.exists(p) else None


def load():
    rows = list(csv.DictReader(open(os.path.join(RF, "findings.csv"))))
    b = [r for r in rows if r["block_reviewer"] == "yes"]
    req = [r for r in b if r["focus"] == "requirement" and r["round_kind"] != "critique"]
    tst = [r for r in b if r["focus"] == "test"]
    return rows, req, tst


def first_review(rows, run, item):
    rounds = [r["round"] for r in rows if r["run"] == run and r["item"] == item and r["round_kind"] == "review"]
    return rounds[0] if rounds else None


def reflog_at(branch, when):
    code, out = git("reflog", "show", "--date=unix", "--format=%H %gd", branch)
    if code or not out:
        return None, f"no reflog for {branch}"
    best = None
    for line in out.splitlines():
        sha, sel = line.split(" ", 1)
        t = int(re.search(r"\{(\d+)\}", sel).group(1))
        if t <= when and (best is None or t > best[1]):
            best = (sha, t)
    if not best:
        return None, f"no reflog entry of {branch} before {when}"
    return best[0], f"reflog of {branch}: last entry at {best[1]} <= review start {when}"


def round_head(d, rnd, branch):
    """(head, how, reflog head, reflog how) for a review round: its .base file, checked against the branch reflog at its .start."""
    head = how = rsha = rhow = None
    rb = read(os.path.join(d, rnd + ".base"))
    if rb:
        head, how = rb, f"{os.path.basename(d)}/{rnd}.base (the head the round was launched on)"
    st = read(os.path.join(d, rnd + ".start"))
    if st:
        rsha, rhow = reflog_at(branch, int(st))
        if not head and rsha:
            head, how = rsha, rhow
    return head, how, rsha, rhow


def item_info(run, item, review):
    d = os.path.join(STATE, run)
    runs = [r for r in sorted(os.listdir(STATE)) if r.startswith("amc-") and r <= run][::-1]
    brief = next((os.path.join(STATE, r, item + s) for r in runs for s in (".prompt.md", ".body.md")
                  if os.path.exists(os.path.join(STATE, r, item + s))), None)
    info = {"run": run, "item": item, "review": review, "brief": brief}
    text = read(brief) or ""
    m = re.search(r"^TASK:.*$", text, re.M)
    task = m.group(0) if m else ""
    bm = re.search(r"branch `(ow/[^`]+)`", text)
    branch = info["branch"] = bm.group(1) if bm else f"ow/{item}"
    info["repo"] = "dotfiles" if re.search(r"chezmoi|dotfiles", task) and "agent-mission-control" not in task else "amc"
    info["musts"] = [n for n, _, _ in must_items(brief_lines(text))]
    info["base"], info["base_how"] = None, None
    for r in runs:
        if read(os.path.join(STATE, r, item + ".base")):
            info["base"], info["base_how"] = read(os.path.join(STATE, r, item + ".base")), f"{r}/{item}.base"
            break
    head = how = None
    if review:
        head, how, rsha, rhow = round_head(d, review, branch)
        info["reflog_head"], info["reflog_how"] = rsha, rhow
    info["head"], info["head_how"] = head, how
    probs = []
    for k in ("base", "head"):
        if not info[k]:
            probs.append(f"no {k} found")
        elif git("cat-file", "-e", info[k] + "^{commit}")[0]:
            probs.append(f"{k} {info[k][:10]} not in the AMC repository")
    info["problems"] = probs
    if not probs:
        info.update(item_info_files(info))
    return info


def item_info_files(info):
    probs = info["problems"]
    if not probs:
        if git("merge-base", "--is-ancestor", info["base"], info["head"])[0]:
            probs.append("base is not an ancestor of head")
        _, merges = git("rev-list", "--first-parent", "--merges", "--parents", f"{info['base']}..{info['head']}")
        info["build_base"] = info["base"]
        if merges:
            newest = merges.splitlines()[0].split()
            info["base"] = newest[2]
            info["base_how"] += f"; the branch merged main {len(merges.splitlines())} time(s), so the base is the main commit of its newest merge ({newest[0][:10]}^2)"
        _, names = git("diff", "--name-status", "--no-renames", info["base"], info["head"])
        files = [ln.split("\t") for ln in names.splitlines() if ln]
        info["changed"] = [f"{s}\t{p}" for s, p in files]
        info["tests"] = [p for s, p in files if s != "D" and TEST_FILE.search(p)]
        info["new_tests"] = [p for s, p in files if s == "A" and TEST_FILE.search(p)]
        info["sources"] = [p for s, p in files if s != "D" and JS.search(p) and not TEST_FILE.search(p)
                           and not p.startswith(("tests/", "e2e/"))]
        info["new_sources"] = [p for s, p in files if s == "A" and p in info["sources"]]
    return info


def main():
    rows, req, tst = load()
    items = {}
    for r in req + tst:
        items.setdefault((r["run"], r["item"]), []).append(r)
    out = []
    for (run, item), fs in sorted(items.items()):
        info = item_info(run, item, first_review(rows, run, item))
        if (run, item) == ("amc-2026-10-27", "diagram") and not info["head"]:
            # ow/diagram was deleted; its first-parent commits survive under 78edfd7^1 ("Merge branch 'main' into ow/diagram").
            info["head"] = "5fdc5216aed3298e23e249878f12915061a9db16"
            info["head_how"] = ("INFERRED: newest first-parent commit of 78edfd7^1 not in the build base whose committer time "
                                "(1793147278) is before rv-diagram.start (1793148421); the branch and its reflog are gone")
            info["problems"] = [p for p in info["problems"] if p != "no head found"]
            info.update(item_info_files(info))
        info["set"] = "finding"
        info["findings"] = [{k: f[k] for k in ("round", "n", "round_kind", "focus", "cause", "test_would_catch", "ruling", "summary")} for f in fs]
        for f in info["findings"]:
            h = round_head(os.path.join(STATE, run), f["round"], info.get("branch", f"ow/{item}"))
            f["round_head"], f["round_head_how"], f["round_reflog_head"] = h[0], h[1], h[2]
        if not info["head"]:
            firsts = [f for f in info["findings"] if f["round_head"]]
            if firsts:
                info["head"], info["head_how"] = firsts[0]["round_head"], firsts[0]["round_head_how"] + " (no first review round; the finding's own round)"
                info["problems"] = [p for p in info["problems"] if p != "no head found"]
                info.update({k: v for k, v in item_info_files(info).items()})
        out.append(info)
    # Controls: items whose first review found no blocking requirement or test finding (any round of the item).
    flagged = {item for _, item in items}
    firsts = {}
    for r in rows:
        if r["round_kind"] == "review" and r["run"].startswith("amc-"):
            firsts.setdefault((r["run"], r["item"]), r["round"])
    pool = []
    for (run, item), rv in sorted(firsts.items()):
        if item in flagged:
            continue
        fs = [r for r in rows if r["run"] == run and r["item"] == item and r["round"] == rv]
        if any(r["focus"] in ("requirement", "test") and r["block_reviewer"] == "yes" for r in fs):
            continue
        info = item_info(run, item, rv)
        if info["repo"] != "amc" or info["problems"] or not info.get("tests"):
            info["set"] = "control-ineligible"
        else:
            info["set"] = "control-pool"
        info["first_review_findings"] = len(fs)
        pool.append(info)
    eligible = [p for p in pool if p["set"] == "control-pool"]
    random.Random(SEED).shuffle(eligible)
    for i, p in enumerate(eligible):
        p["set"] = "control" if i < 12 else "control-spare"
        p["sample_rank"] = i
    json.dump(out + pool, open(os.path.join(OUT, "items.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
