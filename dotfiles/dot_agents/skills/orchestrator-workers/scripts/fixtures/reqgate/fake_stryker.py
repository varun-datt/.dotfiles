"""Stand-in for `stryker run`: copies the recorded report named by the tree's FAKE_STRYKER file, or fails."""
import json
import os
import shutil
import sys
import time

if os.environ.get("REQGATE_FAKE_LOG"):
    with open(os.environ["REQGATE_FAKE_LOG"], "a", encoding="utf-8") as f:
        f.write("stryker " + "\x1f".join(sys.argv[1:]) + "\n")
with open("FAKE_STRYKER", encoding="utf-8") as f:
    fixture = f.read().strip()
if len(sys.argv) > 1 and sys.argv[1].startswith("mode="):
    fixture = sys.argv[1][len("mode="):]
if fixture == "error":
    print("ERROR Stryker Unexpected error occurred while running Stryker ConfigError: no test runner", file=sys.stderr)
    sys.exit(1)
if fixture == "notests":
    print("ERROR Stryker Unexpected error occurred while running Stryker ConfigError: No tests were executed. "
          "Stryker will exit prematurely. Please check your configuration.")
    sys.exit(1)
if fixture in ("partial", "hang"):
    # Stryker's event-recorder writes one file per event as it happens; the last one may be cut off when killed.
    events = os.path.join("reports", "mutation", "events")
    os.makedirs(events, exist_ok=True)
    test = os.path.abspath(os.path.join("src", "calc.test.ts"))
    recorded = [] if fixture == "hang" else [
        ("onDryRunCompleted", {"result": {"status": "complete", "tests": [
            {"id": "1", "name": "calc adds", "fileName": test}, {"id": "2", "name": "calc keeps zero", "fileName": test}]}}),
        ("onMutantTested", {"id": "1", "fileName": os.path.abspath("src/calc.ts"), "status": "Killed", "killedBy": ["1"],
                            "coveredBy": ["1", "2"], "location": {"start": {"line": 3, "column": 1}}}),
        ("onMutantTested", {"id": "2", "fileName": os.path.abspath("src/calc.ts"), "status": "Survived", "coveredBy": ["2"],
                            "location": {"start": {"line": 3, "column": 5}}})]
    for i, (event, data) in enumerate(recorded):
        with open(os.path.join(events, f"{i:05d}-{event}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
    with open(os.path.join(events, f"{len(recorded):05d}-onMutantTested.json"), "w", encoding="utf-8") as f:
        f.write('{"id": "3", "fileName": "src/ca')
    time.sleep(60)
os.makedirs(os.path.join("reports", "mutation"), exist_ok=True)
shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), fixture), os.path.join("reports", "mutation", "mutation.json"))
