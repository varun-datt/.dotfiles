import contextlib
import io
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

    def test_a_dropped_item_counts_in_no_history_whether_open_or_finished(self):
        start = datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)
        at = lambda minutes: (start + timedelta(minutes=minutes)).isoformat()
        estimates.append({"event": "start", "id": "a", "kind": "fix", "estimate": 4, "run": "r", "at": at(0)})
        estimates.append({"event": "end", "id": "a", "at": at(0)})
        estimates.append({"event": "drop", "id": "a", "reason": "covered by b", "at": at(1)})
        estimates.append({"event": "start", "id": "c", "kind": "fix", "estimate": 4, "run": "r", "at": at(1)})
        estimates.append({"event": "drop", "id": "c", "reason": "covered by b", "at": at(2)})
        estimates.append({"event": "start", "id": "a", "kind": "fix", "estimate": 4, "run": "r2", "at": at(3)})
        estimates.append({"event": "end", "id": "a", "at": at(9)})
        estimates.append({"event": "drop", "id": "never-started", "reason": "covered by b", "at": at(9)})
        self.assertEqual([(i["id"], i["run"], i["actual"]) for i in estimates.completed(estimates.read())], [("a", "r2", 6.0)])

    def test_command_line_drop_closes_an_item(self):
        estimates.main(["start", "--id", "x", "--kind", "check", "--estimate", "4", "--method", "history"])
        self.assertEqual(estimates.main(["drop", "--id", "x", "--reason", "covered by y"]), 0)
        self.assertEqual(estimates.completed(estimates.read()), [])
        self.assertEqual(estimates.main(["end", "--id", "x"]), 1)

    def test_kind_estimate_needs_five_items(self):
        items = [{"kind": "fix", "actual": a} for a in (2, 4, 4, 5)]
        self.assertTrue(estimates.kind_estimate(items, "fix")["guess"])
        items.append({"kind": "fix", "actual": 18})
        self.assertEqual(estimates.kind_estimate(items, "fix"), {"kind": "fix", "n": 5, "p50": 4, "p90": 18, "guess": False})

    def test_forecast_divides_judged_estimates_by_judged_history(self):
        history = [{"kind": "fix", "estimate": 20, "actual": 5} for _ in range(5)]
        plan = [{"id": str(i), "kind": "fix", "estimate": 20, "method": "judged"} for i in range(6)]
        result = estimates.forecast(plan, window=60, items=history, runs=50, seed=1)
        self.assertEqual(result["total_p50"], 30.0)
        self.assertEqual(result["fit_p50"], 6)
        self.assertEqual(result["chance_all_fit"], 1.0)

    def test_history_estimates_are_not_corrected_a_second_time(self):
        history = [{"kind": "fix", "estimate": 24, "actual": 6} for _ in range(5)]
        plan = [{"id": str(i), "kind": "fix", "estimate": 6, "method": "history"} for i in range(3)]
        result = estimates.forecast(plan, window=60, items=history, runs=20, seed=1)
        self.assertEqual(result["total_p50"], 18.0)

    def test_forecast_without_history_takes_estimates_as_given(self):
        plan = [{"id": "a", "kind": "fix", "estimate": 40, "method": "rounds"}, {"id": "b", "kind": "fix", "estimate": 40, "method": "history"}]
        result = estimates.forecast(plan, window=60, items=[], runs=10, seed=1)
        self.assertEqual((result["total_p50"], result["fit_p50"], result["history"]), (80.0, 1, 0))

    def test_rounds_convert_to_minutes(self):
        self.assertEqual(estimates.rounds_estimate(5, 1.5)["estimate"], 22.5)

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

    def test_report_counts_enablers_with_the_features_they_serve(self):
        items = [
            {"kind": "feature", "estimate": 10, "actual": 10},
            {"kind": "fix", "estimate": 5, "actual": 5, "serves": "f1"},
            {"kind": "fix", "estimate": 5, "actual": 5, "serves": ""},
        ]
        self.assertEqual(estimates.report(items)["features_with_enablers_share"], 0.75)

    def test_command_line_start_end_and_estimate(self):
        estimates.main(["start", "--id", "x", "--kind", "check", "--estimate", "4", "--method", "history"])
        self.assertEqual(estimates.main(["end", "--id", "x"]), 0)
        self.assertEqual(estimates.main(["end", "--id", "missing"]), 1)
        lines = [json.loads(line) for line in Path(os.environ["ESTIMATES_LOG"]).read_text().splitlines()]
        self.assertEqual([r["event"] for r in lines], ["start", "end", "end"])
        self.assertEqual(lines[0]["method"], "history")

    def test_command_line_start_prints_a_confirmation(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            estimates.main(["start", "--id", "x", "--kind", "check", "--estimate", "4", "--method", "history"])
        printed = json.loads(out.getvalue())
        self.assertEqual({k: printed[k] for k in ("id", "kind", "estimate", "method")}, {"id": "x", "kind": "check", "estimate": 4.0, "method": "history"})
        self.assertIn("started", printed)

    def test_command_line_refuses_a_plan_item_without_a_method(self):
        plan = Path(self.dir.name) / "plan.json"
        plan.write_text(json.dumps([{"id": "a", "kind": "fix", "estimate": 5}]))
        self.assertEqual(estimates.main(["forecast", "--plan", str(plan), "--window", "60"]), 2)
        self.assertEqual(estimates.main(["estimate"]), 2)


class RunGuardTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.environ["ESTIMATES_LOG"] = str(Path(self.dir.name) / "log.jsonl")
        os.environ["ESTIMATES_RUN"] = str(Path(self.dir.name) / "run.json")
        self.at = datetime(2026, 10, 26, 2, 0, tzinfo=timezone.utc)
        self.run = {"run": "night", "until": (self.at + timedelta(hours=4)).isoformat(), "session": "chat-1", "planned": ["a", "b"]}
        self.chat = {"sessionId": "chat-1"}

    def tearDown(self):
        self.dir.cleanup()
        del os.environ["ESTIMATES_LOG"]
        del os.environ["ESTIMATES_RUN"]

    def test_blocks_the_turn_end_while_planned_items_are_open_before_the_stop_time(self):
        reason, run = estimates.guard_decision(self.run, [{"event": "end", "id": "a"}], self.at, self.chat)
        self.assertIn("1 planned items are not done (next: b)", reason)
        self.assertIn("put any question that blocks nothing in the session memory", reason)
        self.assertEqual(run["blocks"], 1)

    def test_lets_the_turn_end_when_unarmed_blocked_past_the_stop_time_or_done(self):
        records = [{"event": "end", "id": "a"}, {"event": "done", "id": "b"}]
        self.assertIsNone(estimates.guard_decision(None, [], self.at)[0])
        self.assertIsNone(estimates.guard_decision({**self.run, "blocked": "needs a secret"}, [], self.at)[0])
        self.assertIsNone(estimates.guard_decision(self.run, [], self.at + timedelta(hours=4))[0])
        self.assertIsNone(estimates.guard_decision(self.run, records, self.at)[0])
        self.assertIsNone(estimates.guard_decision(self.run, [{"event": "end", "id": "a"}, {"event": "drop", "id": "b"}], self.at, self.chat)[0])

    def test_gives_up_after_three_refusals_with_no_progress_and_counts_again_after_progress(self):
        run, reasons = self.run, []
        for _ in range(4):
            reason, run = estimates.guard_decision(run, [{"event": "start", "id": "a"}], self.at, self.chat)
            reasons.append(reason is not None)
        self.assertEqual(reasons, [True, True, True, False])
        reason, run = estimates.guard_decision(run, [{"event": "start", "id": "a"}, {"event": "end", "id": "a"}], self.at, self.chat)
        self.assertIsNotNone(reason)
        self.assertEqual(run["blocks"], 1)

    def test_holds_only_the_armed_session_never_another_agent_that_loads_the_same_hook(self):
        transcript = {"transcript_path": "/x/transcripts/chat-1.jsonl"}
        self.assertIsNotNone(estimates.guard_decision(self.run, [], self.at, transcript)[0])
        self.assertIsNone(estimates.guard_decision(self.run, [], self.at, {"sessionId": "sdk-session-9"})[0])
        self.assertIsNone(estimates.guard_decision(self.run, [], self.at, {})[0])

    def test_a_clock_stop_time_is_its_next_occurrence(self):
        late = datetime(2026, 10, 25, 23, 0, tzinfo=timezone.utc)
        self.assertEqual(estimates.until_time("06:02", late), datetime(2026, 10, 26, 6, 2, tzinfo=timezone.utc))
        self.assertEqual(estimates.until_time("23:30", late), datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc))

    def test_command_line_arms_blocks_restarts_and_disarms(self):
        plan = Path(self.dir.name) / "plan.json"
        plan.write_text(json.dumps([{"id": "a"}, {"id": "b"}]))
        estimates.main(["arm", "--run", "night", "--until", (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), "--session", "chat-1", "--plan", str(plan)])
        self.assertEqual(estimates.guard(self.chat)["hookSpecificOutput"]["decision"], "block")
        estimates.main(["block", "--reason", "waits on a sign-in only the owner can do"])
        self.assertIsNone(estimates.guard(self.chat))
        estimates.main(["start", "--id", "a", "--kind", "fix", "--estimate", "4", "--method", "history"])
        self.assertNotIn("blocked", estimates.load_run())
        self.assertEqual(estimates.guard(self.chat)["decision"], "block")
        estimates.main(["disarm"])
        self.assertIsNone(estimates.guard(self.chat))
        self.assertEqual(estimates.main(["block", "--reason", "x"]), 1)

    def test_a_broken_run_file_never_traps_the_agent(self):
        Path(os.environ["ESTIMATES_RUN"]).write_text("{not json")
        output = estimates.guard()
        self.assertNotIn("decision", output)
        self.assertIn("Run guard: not checked", output["systemMessage"])


if __name__ == "__main__":
    unittest.main()
