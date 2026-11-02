"""Stand-in for `stryker run`: copies the recorded report named by the tree's FAKE_STRYKER file, or fails."""
import os
import shutil
import sys

if os.environ.get("REQGATE_FAKE_LOG"):
    with open(os.environ["REQGATE_FAKE_LOG"], "a", encoding="utf-8") as f:
        f.write("stryker " + "\x1f".join(sys.argv[1:]) + "\n")
with open("FAKE_STRYKER", encoding="utf-8") as f:
    fixture = f.read().strip()
if fixture == "error":
    print("ERROR Stryker Unexpected error occurred while running Stryker ConfigError: no test runner", file=sys.stderr)
    sys.exit(1)
os.makedirs(os.path.join("reports", "mutation"), exist_ok=True)
shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), fixture), os.path.join("reports", "mutation", "mutation.json"))
