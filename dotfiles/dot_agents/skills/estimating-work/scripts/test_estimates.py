import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import estimates  # noqa: E402

FAKE_GH = """#!{python}
import json, os, sys, time
with open(os.environ["FAKE_GH_CALLS"], "a") as calls:
    calls.write(json.dumps({{"args": sys.argv[1:], "env": {{k: os.environ.get(k) for k in ("GH_PROMPT_DISABLED", "GH_NO_UPDATE_NOTIFIER", "NO_COLOR")}}, "stdin": sys.stdin.read()}}) + "\\n")
mode = os.environ.get("FAKE_GH_MODE", "used")
if mode == "fail":
    print("HTTP 401: login secret-login-marker, org secret-org-marker", file=sys.stderr)
    sys.exit(4)
if mode == "not_utf8":
    sys.stdout.buffer.write(b"\\xff\\xfe{{")
    sys.exit(0)
if mode == "slow":
    time.sleep(5)
premium = {{"used": {{"has_quota": True, "credits_used": float(os.environ.get("FAKE_GH_USED", "10"))}},
           "missing": {{"has_quota": True, "entitlement": 300, "quota_remaining": 288.5}},
           "no_quota": {{"has_quota": False, "credits_used": 3}},
           "slow": {{"has_quota": True, "credits_used": 1}}}}[mode]
print(json.dumps({{"quota_snapshots": {{"premium_interactions": premium}}}}))
"""


def setUpModule():
    global STUB, SAVED_ENV
    SAVED_ENV = dict(os.environ)
    STUB = tempfile.TemporaryDirectory()
    gh = Path(STUB.name) / "gh"
    gh.write_text(FAKE_GH.format(python=sys.executable))
    gh.chmod(0o755)
    os.environ["PATH"] = STUB.name + os.pathsep + os.environ["PATH"]
    os.environ["FAKE_GH_CALLS"] = str(Path(STUB.name) / "calls.jsonl")
    os.environ["ESTIMATES_LOG"] = str(Path(STUB.name) / "log.jsonl")
    os.environ["ESTIMATES_RUN"] = str(Path(STUB.name) / "run.json")


def tearDownModule():
    STUB.cleanup()
    os.environ.clear()
    os.environ.update(SAVED_ENV)


class Isolated(unittest.TestCase):
    """Every state file in a temporary folder, and the environment restored after each test."""

    def setUp(self):
        self.saved_env = dict(os.environ)
        self.dir = tempfile.TemporaryDirectory()
        os.environ["ESTIMATES_LOG"] = str(Path(self.dir.name) / "log.jsonl")
        os.environ["ESTIMATES_RUN"] = str(Path(self.dir.name) / "run.json")
        os.environ["FAKE_GH_MODE"] = "used"
        Path(os.environ["FAKE_GH_CALLS"]).unlink(missing_ok=True)

    def tearDown(self):
        self.dir.cleanup()
        os.environ.clear()
        os.environ.update(self.saved_env)


class CreditsTest(Isolated):
    def test_a_normal_read_takes_credits_used(self):
        self.assertEqual(estimates.read_credits(), (10.0, None))

    def test_gh_gets_exact_arguments_no_prompt_env_no_shell_and_closed_stdin(self):
        real_run = estimates.subprocess.run
        seen = []
        with mock.patch.object(estimates.subprocess, "run", side_effect=lambda *a, **k: seen.append((a, k)) or real_run(*a, **k)):
            estimates.read_credits()
        [(args, kwargs)] = seen
        self.assertEqual(args[0], ["gh", "api", "/copilot_internal/user"])
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        [call] = [json.loads(line) for line in Path(os.environ["FAKE_GH_CALLS"]).read_text().splitlines()]
        self.assertEqual(call, {"args": ["api", "/copilot_internal/user"], "env": {"GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "NO_COLOR": "1"}, "stdin": ""})

    def test_a_missing_credits_used_is_unknown_never_derived_from_entitlement(self):
        os.environ["FAKE_GH_MODE"] = "missing"
        self.assertEqual(estimates.read_credits(), (None, "no-figure"))

    def test_parse_refuses_no_quota_and_a_bad_figure(self):
        premium = lambda p: {"quota_snapshots": {"premium_interactions": p}}
        self.assertEqual(estimates.parse_credits(premium({"has_quota": True, "credits_used": -1})), (None, "no-figure"))
        self.assertEqual(estimates.parse_credits(premium({"credits_used": float("inf"), "entitlement": 5, "quota_remaining": 2})), (None, "no-figure"))
        self.assertEqual(estimates.parse_credits(premium({"has_quota": True, "credits_used": True})), (None, "no-figure"))
        self.assertEqual(estimates.parse_credits({}), (None, "no-quota"))
        self.assertEqual(estimates.parse_credits(premium({"credits_used": 0})), (0, None))

    def test_has_quota_false_is_unknown(self):
        os.environ["FAKE_GH_MODE"] = "no_quota"
        self.assertEqual(estimates.read_credits(), (None, "no-quota"))

    def test_a_non_zero_exit_is_a_code_and_never_stores_or_prints_gh_stderr(self):
        os.environ["FAKE_GH_MODE"] = "fail"
        self.assertEqual(estimates.read_credits(), (None, "gh-exit-4"))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            estimates.main(["start", "--id", "s", "--kind", "fix", "--estimate", "4", "--method", "rounds"])
            estimates.main(["end", "--id", "s"])
            estimates.main(["report"])
        everything = out.getvalue() + err.getvalue() + Path(os.environ["ESTIMATES_LOG"]).read_text()
        self.assertNotIn("marker", everything)
        self.assertEqual(estimates.completed(estimates.read())[0]["credits_unknown"], "start:gh-exit-4 end:gh-exit-4")

    def test_output_that_is_not_utf8_is_bad_json_and_never_stops_end(self):
        os.environ["FAKE_GH_MODE"] = "not_utf8"
        self.assertEqual(estimates.read_credits(), (None, "bad-json"))
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["start", "--id", "b", "--kind", "fix", "--estimate", "4", "--method", "rounds"])
            self.assertEqual(estimates.main(["end", "--id", "b"]), 0)
        self.assertEqual(estimates.completed(estimates.read())[0]["credits_unknown"], "start:bad-json end:bad-json")

    def test_gh_missing_from_path_is_unknown(self):
        os.environ["PATH"] = self.dir.name
        self.assertEqual(estimates.read_credits(), (None, "gh-missing"))

    def test_a_timeout_is_unknown_and_never_blocks_start_or_end(self):
        os.environ["FAKE_GH_MODE"] = "slow"
        saved, estimates.CREDITS_TIMEOUT = estimates.CREDITS_TIMEOUT, 0.5
        try:
            self.assertEqual(estimates.read_credits(), (None, "timeout"))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(estimates.main(["start", "--id", "t", "--kind", "fix", "--estimate", "4", "--method", "rounds", "--credits", "2"]), 0)
                self.assertEqual(estimates.main(["end", "--id", "t"]), 0)
        finally:
            estimates.CREDITS_TIMEOUT = saved
        [item] = estimates.completed(estimates.read())
        self.assertIsNone(item["credits_actual"])
        self.assertEqual(item["credits_unknown"], "start:timeout end:timeout")

    def test_start_and_end_read_the_figure_and_store_the_delta(self):
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["start", "--id", "c", "--kind", "fix", "--estimate", "4", "--method", "rounds", "--credits", "3"])
            os.environ["FAKE_GH_USED"] = "12.5"
            estimates.main(["end", "--id", "c"])
        start, end = estimates.read()
        self.assertEqual((start["credits_estimate"], start["credits_at_start"], end["credits_at_end"], end["credits_actual"]), (3.0, 10.0, 12.5, 2.5))
        [item] = estimates.completed(estimates.read())
        self.assertEqual((item["credits_estimate"], item["credits_actual"]), (3.0, 2.5))
        self.assertNotIn("credits_unknown", item)

    def test_a_failed_read_at_start_marks_the_item_unknown_but_stamps_it(self):
        os.environ["FAKE_GH_MODE"] = "fail"
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["start", "--id", "u", "--kind", "fix", "--estimate", "4", "--method", "rounds"])
        os.environ["FAKE_GH_MODE"] = "used"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(estimates.main(["end", "--id", "u"]), 0)
        [item] = estimates.completed(estimates.read())
        self.assertEqual((item["actual"] >= 0, item["credits_actual"]), (True, None))
        self.assertEqual(item["credits_unknown"], "start:gh-exit-4")

    def test_a_second_end_appends_a_record_and_exits_zero_as_before(self):
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["start", "--id", "d", "--kind", "fix", "--estimate", "4", "--method", "rounds"])
            self.assertEqual(estimates.main(["end", "--id", "d"]), 0)
            self.assertEqual(estimates.main(["end", "--id", "d"]), 0)
        self.assertEqual([r["event"] for r in estimates.read()], ["start", "end", "end"])
        self.assertNotIn("credits_at_end", estimates.read()[2])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(estimates.main(["end", "--id", "never-started"]), 1)

    def test_free_text_in_a_start_record_never_reaches_the_end_record_or_the_report(self):
        estimates.append({"event": "start", "id": "f", "kind": "fix", "estimate": 4, "run": "r", "credits_at_start": None, "credits_unknown": "at start: gh exited 4: login secret-login-marker", "at": datetime.now(timezone.utc).isoformat()})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(estimates.main(["end", "--id", "f"]), 0)
            estimates.main(["report", "--run", "r"])
        self.assertEqual(estimates.read()[1]["credits_unknown"], "start:unknown")
        self.assertNotIn("marker", out.getvalue())
        self.assertEqual(estimates.known_reasons("start:timeout end:gh-exit-4"), "start:timeout end:gh-exit-4")
        self.assertEqual(estimates.known_reasons("end: secret-org-marker"), "unknown")

    def test_an_id_started_then_added_is_not_running_and_marks_no_later_item(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=30)
        at = lambda minutes: (start + timedelta(minutes=minutes)).isoformat()
        estimates.append({"event": "start", "id": "s", "kind": "fix", "estimate": 5, "run": "r1", "at": at(0)})
        estimates.main(["add", "--id", "s", "--kind", "fix", "--estimate", "5", "--actual", "4", "--method", "rounds", "--run", "r1", "--at", at(4)])
        estimates.append({"event": "start", "id": "later", "kind": "fix", "estimate": 5, "run": "r1", "at": at(10)})
        estimates.append({"event": "end", "id": "later", "credits_actual": 1, "at": at(15)})
        self.assertEqual(estimates.running(estimates.read(), datetime.now(timezone.utc)), [])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            estimates.main(["report", "--run", "r1"])
        rows = {r["id"]: r for r in json.loads(out.getvalue())["credits"]["items"]}
        self.assertNotIn("overlaps", rows["later"])

    def test_an_item_overlapping_one_still_open_is_marked(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=10)
        at = lambda minutes: (start + timedelta(minutes=minutes)).isoformat()
        for r in [
            {"event": "start", "id": "a", "kind": "fix", "estimate": 5, "run": "r1", "at": at(0)},
            {"event": "start", "id": "b", "kind": "fix", "estimate": 5, "run": "r1", "at": at(2)},
            {"event": "end", "id": "a", "credits_actual": 1, "at": at(5)},
        ]:
            estimates.append(r)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            estimates.main(["report", "--run", "r1"])
        credits = json.loads(out.getvalue())["credits"]
        self.assertEqual([(r["id"], r.get("overlaps")) for r in credits["items"]], [("a", ["b"])])

    def test_report_for_one_run_marks_an_overlap_with_another_runs_item(self):
        at = lambda minutes: datetime(2026, 10, 28, 9, minutes, tzinfo=timezone.utc).isoformat()
        for r in [
            {"event": "start", "id": "mine", "kind": "fix", "estimate": 5, "run": "r1", "at": at(0)},
            {"event": "start", "id": "theirs", "kind": "fix", "estimate": 5, "run": "r2", "at": at(2)},
            {"event": "end", "id": "mine", "credits_actual": 1, "at": at(5)},
            {"event": "end", "id": "theirs", "credits_actual": 1, "at": at(7)},
        ]:
            estimates.append(r)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            estimates.main(["report", "--run", "r1"])
        credits = json.loads(out.getvalue())["credits"]
        self.assertEqual([(r["id"], r["overlaps"]) for r in credits["items"]], [("mine", ["theirs"])])
        self.assertEqual(credits["items_overlapping"], 1)

    def test_report_shows_credits_beside_minutes_and_marks_overlapping_items(self):
        at = lambda minutes: datetime(2026, 10, 28, 9, minutes, tzinfo=timezone.utc).isoformat()
        records = [
            {"event": "start", "id": "a", "kind": "fix", "estimate": 5, "credits_estimate": 2, "credits_at_start": 10, "at": at(0)},
            {"event": "start", "id": "b", "kind": "fix", "estimate": 5, "credits_estimate": 1, "credits_at_start": 11, "at": at(4)},
            {"event": "end", "id": "a", "credits_at_end": 14, "credits_actual": 4, "at": at(6)},
            {"event": "end", "id": "b", "credits_at_end": 15, "credits_actual": 4, "at": at(8)},
            {"event": "start", "id": "c", "kind": "feature", "estimate": 5, "credits_estimate": 3, "credits_at_start": 15, "at": at(8)},
            {"event": "end", "id": "c", "credits_actual": None, "credits_unknown": "end:gh-missing", "at": at(10)},
        ]
        for r in records:
            estimates.append(r)
        credits = estimates.report(estimates.completed(estimates.read()))["credits"]
        rows = {r["id"]: r for r in credits["items"]}
        self.assertEqual((rows["a"]["overlaps"], rows["b"]["overlaps"]), (["b"], ["a"]))
        self.assertNotIn("overlaps", rows["c"])
        self.assertEqual((rows["a"]["minutes_actual"], rows["a"]["credits_estimate"], rows["a"]["credits_actual"]), (6.0, 2, 4))
        self.assertEqual(rows["c"]["credits_unknown"], "end:gh-missing")
        self.assertEqual({k: credits[k] for k in ("estimated", "actual", "items_estimated", "items_measured", "items_overlapping")}, {"estimated": 6, "actual": 8, "items_estimated": 3, "items_measured": 2, "items_overlapping": 2})


class WorkerImportTest(Isolated):
    ROUNDS = [
        {"name": f"item{n}", "kind": "build", "start": f"2026-10-28T09:{n:02d}:00+00:00", "wall_min": 10.0 + n, "credits": 100.5 + n}
        for n in range(6)
    ] + [
        {"name": "item0-review", "kind": "review", "start": "2026-10-28T10:00:00+00:00", "wall_min": 6.0, "credits": 20.0},
        {"name": "item0-fix", "kind": "fix", "start": "2026-10-28T10:10:00+00:00", "wall_min": 8.0, "credits": None},
        {"name": "item0-merge", "kind": "merge", "start": "2026-10-28T10:30:00+00:00", "wall_min": 1.0, "credits": 1.0},
    ]

    def stub_mine(self):
        path = Path(self.dir.name) / "mine.py"
        path.write_text("import json, sys\nprint(json.dumps({'rounds': %r}))\n" % (self.ROUNDS,))
        os.environ["MINE_PY"] = str(path)
        return Path(self.dir.name) / "run-a"

    def test_import_logs_worker_kinds_with_credits_from_the_workers_log(self):
        run = self.stub_mine()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(estimates.main(["import-run", str(run)]), 0)
        self.assertEqual(json.loads(out.getvalue())["imported"], 8)
        items = estimates.completed(estimates.read())
        self.assertEqual({i["kind"] for i in items}, {"worker-build", "worker-review", "worker-fix"})
        build = next(i for i in items if i["id"] == "item1")
        self.assertEqual((build["actual"], build["credits_actual"], build["run"]), (11.0, 101.5, "run-a"))
        fix = next(i for i in items if i["id"] == "item0-fix")
        self.assertIsNone(fix["credits_actual"])
        self.assertEqual(fix["credits_unknown"], "not-read")

    def test_importing_twice_adds_nothing(self):
        run = self.stub_mine()
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["import-run", str(run)])
            estimates.main(["import-run", str(run)])
        self.assertEqual(len(estimates.completed(estimates.read())), 8)

    def test_estimate_for_a_worker_kind_answers_from_imported_history_apart_from_in_chat_kinds(self):
        run = self.stub_mine()
        estimates.append({"event": "done", "id": "chat", "kind": "fix", "estimate": 5, "actual": 4, "method": "history", "at": "2026-10-28T09:00:00+00:00"})
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["import-run", str(run)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            estimates.main(["estimate", "--kind", "worker-build", "--days", "100000"])
        answer = json.loads(out.getvalue())
        self.assertEqual((answer["n"], answer["guess"], answer["p50"]), (6, False, 12.0))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            estimates.main(["estimate", "--kind", "fix", "--days", "100000"])
        self.assertEqual(json.loads(out.getvalue())["n"], 1)

    def test_import_logs_active_minutes_as_the_actual_and_keeps_wall_minutes(self):
        self.ROUNDS = [{"name": "slow", "kind": "build", "start": "2026-10-28T09:00:00+00:00", "wall_min": 500.0, "active_min": 40.0, "credits": 1.0}]
        run = self.stub_mine()
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["import-run", str(run)])
        item = estimates.completed(estimates.read())[0]
        self.assertEqual((item["actual"], item["wall_min"]), (40.0, 500.0))

    def test_an_imported_id_replaces_its_hand_logged_row_but_keeps_its_estimate(self):
        self.ROUNDS = [{"name": "item1", "kind": "build", "start": "2026-10-28T09:00:00+00:00", "wall_min": 30.0, "active_min": 30.0, "credits": 1.0}]
        run = self.stub_mine()
        estimates.append({"event": "done", "id": "item1", "kind": "worker-build", "estimate": 25, "actual": 90, "method": "history", "at": "2026-10-28T12:00:00+00:00"})
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["import-run", str(run)])
        items = estimates.completed(estimates.read())
        self.assertEqual([(i["id"], i["actual"], i["estimate"], i.get("imported")) for i in items], [("item1", 30.0, 25, True)])

    def test_report_labels_log_credits_and_never_marks_them_overlapping(self):
        run = self.stub_mine()
        with contextlib.redirect_stdout(io.StringIO()):
            estimates.main(["import-run", str(run)])
        items = estimates.completed(estimates.read())
        credits = estimates.report(items)["credits"]
        self.assertEqual(credits["items_overlapping"], 0)
        self.assertEqual({r["credits_source"] for r in credits["items"]}, {"log"})

    def test_account_counter_items_are_labelled_as_such(self):
        estimates.append({"event": "done", "id": "x", "kind": "fix", "estimate": 5, "actual": 5, "credits_actual": 3, "at": "2026-10-28T09:00:00+00:00"})
        row = estimates.report(estimates.completed(estimates.read()))["credits"]["items"][0]
        self.assertEqual(row["credits_source"], "account counter")


class EstimatesTest(Isolated):
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

    def test_a_time_with_no_zone_is_local_and_compares_with_zoned_ones(self):
        estimates.main(["add", "--id", "n", "--kind", "fix", "--estimate", "4", "--actual", "5", "--method", "history", "--at", "2026-10-27T13:06:00"])
        estimates.append({"event": "done", "id": "m", "kind": "fix", "estimate": 4, "actual": 6, "method": "history", "at": "2026-10-27T13:25:00"})
        estimates.append({"event": "done", "id": "z", "kind": "fix", "estimate": 4, "actual": 7, "method": "history", "at": datetime.now(timezone.utc).isoformat()})
        self.assertIsNotNone(datetime.fromisoformat(estimates.read()[0]["at"]).tzinfo)
        self.assertEqual(len(estimates.recent(estimates.completed(estimates.read()), 100000)), 3)

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

    def test_forecast_skips_logged_items_without_an_estimate(self):
        history = [{"kind": "fix", "estimate": 20, "actual": 5} for _ in range(5)] + [{"kind": "fix", "estimate": None, "actual": 7}]
        plan = [{"id": "a", "kind": "fix", "estimate": 20, "method": "judged"}]
        result = estimates.forecast(plan, window=60, items=history, runs=10, seed=1)
        self.assertEqual(result["total_p50"], 5.0)

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


class RunGuardTest(Isolated):
    def setUp(self):
        super().setUp()
        self.at = datetime(2026, 10, 26, 2, 0, tzinfo=timezone.utc)
        self.run = {"run": "night", "until": (self.at + timedelta(hours=4)).isoformat(), "session": "chat-1", "planned": ["a", "b"]}
        self.chat = {"sessionId": "chat-1"}

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
