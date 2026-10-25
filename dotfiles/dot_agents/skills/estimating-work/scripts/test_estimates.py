import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import estimates  # noqa: E402


class EstimatesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.environ["ESTIMATES_LOG"] = str(Path(self.dir.name) / "log.jsonl")

    def tearDown(self):
        self.dir.cleanup()
        del os.environ["ESTIMATES_LOG"]

    def test_start_and_end_pair_into_an_actual(self):
        start = datetime(2026, 10, 25, 9, 0, tzinfo=timezone.utc)
        estimates.append({"event": "start", "id": "a", "kind": "fix", "estimate": 5, "run": "r", "at": start.isoformat()})
        estimates.append({"event": "end", "id": "a", "at": (start + timedelta(minutes=7, seconds=30)).isoformat()})
        [item] = estimates.completed(estimates.read())
        self.assertEqual(item["actual"], 7.5)
        self.assertEqual(item["kind"], "fix")

    def test_an_end_without_a_start_is_ignored(self):
        estimates.append({"event": "end", "id": "b", "at": datetime.now(timezone.utc).isoformat()})
        self.assertEqual(estimates.completed(estimates.read()), [])

    def test_kind_estimate_needs_five_items(self):
        items = [{"kind": "fix", "actual": a} for a in (2, 4, 4, 5)]
        self.assertTrue(estimates.kind_estimate(items, "fix")["guess"])
        items.append({"kind": "fix", "actual": 18})
        self.assertEqual(estimates.kind_estimate(items, "fix"), {"kind": "fix", "n": 5, "p50": 4, "p90": 18, "guess": False})

    def test_forecast_divides_estimates_by_the_history(self):
        plan = [{"id": str(i), "kind": "fix", "estimate": 20} for i in range(6)]
        result = estimates.forecast(plan, window=60, history=[4.0], runs=50, seed=1)
        self.assertEqual(result["total_p50"], 30.0)
        self.assertEqual(result["fit_p50"], 6)
        self.assertEqual(result["chance_all_fit"], 1.0)

    def test_forecast_without_history_takes_estimates_as_given(self):
        plan = [{"id": "a", "kind": "fix", "estimate": 40}, {"id": "b", "kind": "fix", "estimate": 40}]
        result = estimates.forecast(plan, window=60, history=[], runs=10, seed=1)
        self.assertEqual((result["total_p50"], result["fit_p50"], result["history"]), (80.0, 1, 0))

    def test_recent_drops_old_items(self):
        old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        new = datetime.now(timezone.utc).isoformat()
        items = [{"at": old}, {"at": new}]
        self.assertEqual(estimates.recent(items, 180), [{"at": new}])

    def test_report_counts_within_a_quarter_and_minutes_by_kind(self):
        items = [
            {"kind": "fix", "estimate": 10, "actual": 9},
            {"kind": "feature", "estimate": 40, "actual": 10},
        ]
        r = estimates.report(items)
        self.assertEqual((r["within_25_percent"], r["estimate_over_actual"]), (1, 2.63))
        self.assertEqual(list(r["minutes_by_kind"]), ["feature", "fix"])

    def test_command_line_start_end_and_estimate(self):
        estimates.main(["start", "--id", "x", "--kind", "check", "--estimate", "4"])
        self.assertEqual(estimates.main(["end", "--id", "x"]), 0)
        self.assertEqual(estimates.main(["end", "--id", "missing"]), 1)
        lines = [json.loads(line) for line in Path(os.environ["ESTIMATES_LOG"]).read_text().splitlines()]
        self.assertEqual([r["event"] for r in lines], ["start", "end", "end"])


if __name__ == "__main__":
    unittest.main()
