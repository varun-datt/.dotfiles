"""Stand-in for `vitest run`: writes a recorded JSON report named by the tree's FAKE_VITEST file."""
import os
import sys

args = sys.argv[1:]
out = next(a.split("=", 1)[1] for a in args if a.startswith("--outputFile="))
target = args[args.index("run") + 1]
if os.environ.get("REQGATE_FAKE_LOG"):
    with open(os.environ["REQGATE_FAKE_LOG"], "a", encoding="utf-8") as f:
        f.write("vitest " + "\x1f".join(args) + "\n")
with open("FAKE_VITEST", encoding="utf-8") as f:
    fixture = f.read().strip()
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), fixture), encoding="utf-8") as f:
    text = f.read()
with open(out, "w", encoding="utf-8") as f:
    f.write(text.replace("__FILE__", os.path.realpath(target)))
sys.exit(1 if '"failed"' in text else 0)
