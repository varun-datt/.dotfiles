import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import session_log  # noqa: E402

SCRIPT = Path(__file__).parent / "session_log.py"
SHELL_ARGS = {"command": "npm test", "explanation": "run", "goal": "test", "mode": "sync"}
LONG_ARGS = {"command": "make lint " + "x" * 200, "explanation": "lint", "goal": "lint", "mode": "sync"}
READ_ARGS = {"filePath": "/repo/a.ts", "startLine": 1, "endLine": 9}


def event(kind, at, data):
    return {"type": kind, "timestamp": at, "data": data}


def ms(at):
    return int(datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp() * 1000)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + "\n")


class SessionLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.out = self.root / "out"
        os.environ["DISTILL_VSCODE_STORAGE"] = str(self.root / "storage")
        os.environ["DISTILL_COPILOT_HOME"] = str(self.root / "copilot")

    def tearDown(self):
        self.tmp.cleanup()
        del os.environ["DISTILL_VSCODE_STORAGE"]
        del os.environ["DISTILL_COPILOT_HOME"]

    def vscode_session(self, sid="s1"):
        workspace = self.root / "storage" / "abc"
        workspace.mkdir(parents=True)
        (workspace / "workspace.json").write_text(json.dumps({"folder": self.repo.as_uri()}))
        chat = workspace / "GitHub.copilot-chat"
        write_jsonl(chat / "transcripts" / f"{sid}.jsonl", [
            event("session.start", "2026-10-26T02:00:00Z", {"sessionId": sid}),
            event("user.message", "2026-10-26T02:00:01Z", {"content": "Never push.\nKeep going."}),
            event("assistant.message", "2026-10-26T02:00:02Z", {"content": "", "reasoningText": "I expect the tests to pass."}),
            event("tool.execution_start", "2026-10-26T02:00:03Z", {"toolCallId": "t1", "toolName": "run_in_terminal", "arguments": SHELL_ARGS}),
            event("tool.execution_complete", "2026-10-26T02:00:09Z", {"toolCallId": "t1", "success": True}),
            event("tool.execution_start", "2026-10-26T02:00:10Z", {"toolCallId": "t2", "toolName": "read_file", "arguments": READ_ARGS}),
            event("tool.execution_complete", "2026-10-26T02:00:10Z", {"toolCallId": "t2", "success": True}),
            event("tool.execution_start", "2026-10-26T02:00:11Z", {"toolCallId": "toolu_9", "toolName": "runSubagent", "arguments": {"description": "Review", "prompt": "review it"}}),
            event("tool.execution_complete", "2026-10-26T02:00:50Z", {"toolCallId": "toolu_9", "success": True}),
            event("tool.execution_start", "2026-10-26T02:00:51Z", {"toolCallId": "t3", "toolName": "run_in_terminal", "arguments": LONG_ARGS}),
            event("tool.execution_complete", "2026-10-26T02:00:55Z", {"toolCallId": "t3", "success": True}),
            event("assistant.message", "2026-10-26T02:01:00Z", {"content": "Done: one test fails.", "reasoningText": ""}),
            event("tool.execution_start", "2026-10-26T03:00:00Z", {"toolCallId": "t4", "toolName": "run_in_terminal", "arguments": SHELL_ARGS}),
            event("tool.execution_complete", "2026-10-26T03:00:05Z", {"toolCallId": "t4", "success": True}),
        ])
        write_jsonl(chat / "debug-logs" / sid / "main.jsonl", [
            {"ts": ms("2026-10-26T02:00:03Z"), "type": "tool_call", "name": "run_in_terminal", "status": "ok",
             "attrs": {"args": json.dumps(SHELL_ARGS), "result": "PASS a\nFAIL b\n1 failed, 0 errors\n2 passed, 0 failed"}},
            {"ts": ms("2026-10-26T02:00:10Z"), "type": "tool_call", "name": "read_file", "status": "ok",
             "attrs": {"args": json.dumps(READ_ARGS), "result": "const error = 1"}},
            {"ts": ms("2026-10-26T02:00:51Z"), "type": "tool_call", "name": "run_in_terminal", "status": "ok",
             "attrs": {"args": json.dumps(LONG_ARGS)[:60], "result": "lint: exit=3"}},
        ])
        write_jsonl(chat / "debug-logs" / sid / "runSubagent-default-toolu_9.jsonl", [
            {"type": "agent_response", "attrs": {"response": json.dumps(
                [{"role": "assistant", "parts": [{"type": "text", "content": "Finding 1: a race on Stop."}]}])}},
        ])
        snapshot = {"requests": [{"result": {"metadata": {"toolCallResults": {
            "t4__vscode-1": {"content": [{"$mid": 1, "value": "Tests: 1 failed\nexit=1"}]}}}}}]}
        write_jsonl(workspace / "chatSessions" / f"{sid}.jsonl", [{"kind": 0, "v": snapshot}])

    def cli_session(self, sid="c1"):
        folder = self.root / "copilot" / "session-state" / sid
        folder.mkdir(parents=True)
        (folder / "workspace.yaml").write_text(f"id: {sid}\ncwd: {self.repo}\n")
        write_jsonl(folder / "events.jsonl", [
            event("session.start", "2026-10-26T03:00:00Z", {"sessionId": sid}),
            event("user.message", "2026-10-26T03:00:01Z", {"content": "Fix the build."}),
            event("tool.execution_start", "2026-10-26T03:00:02Z", {"toolCallId": "b1", "toolName": "bash", "arguments": {"command": "make"}}),
            event("tool.execution_complete", "2026-10-26T03:00:05Z", {"toolCallId": "b1", "success": True, "result": {"content": "ok\n<exited with exit code 2>"}}),
            event("tool.execution_start", "2026-10-26T03:00:06Z", {"toolCallId": "b2", "toolName": "view", "arguments": {"path": "/repo/missing"}}),
            event("tool.execution_complete", "2026-10-26T03:00:06Z", {"toolCallId": "b2", "success": False, "error": {"message": "Path does not exist"}}),
            event("session.compaction_complete", "2026-10-26T03:10:00Z", {}),
        ])

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=self.repo)

    def digest_text(self, *args):
        result = self.run_script("digest", "--out", str(self.out), *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return "".join(p.read_text() for p in sorted(self.out.glob("chunk-*.md"))), result.stdout

    def test_vscode_digest_keeps_the_user_verbatim_and_one_line_per_tool_call(self):
        self.vscode_session()
        text, _ = self.digest_text("--session", "s1")
        self.assertIn("Never push.\nKeep going.", text)
        self.assertIn("I expect the tests to pass.", text)
        self.assertIn("Done: one test fails.", text)
        self.assertEqual(sum(" TOOL " in line for line in text.splitlines()), 5)
        self.assertIn("TOOL run_in_terminal npm test", text)
        self.assertIn("TOOL read_file /repo/a.ts:1-9", text)

    def test_vscode_digest_joins_outputs_from_the_chat_store_and_the_debug_log(self):
        self.vscode_session()
        text, out = self.digest_text("--session", "s1")
        self.assertIn("↳ FAIL b | 1 failed, 0 errors", text)
        self.assertNotIn("2 passed, 0 failed", text)
        self.assertNotIn("const error", text)
        self.assertIn("Finding 1: a race on Stop.", text)
        self.assertNotIn('"role"', text)
        self.assertIn("↳ lint: exit=3", text)
        self.assertEqual(text.count("↳ FAIL b"), 1)
        self.assertIn("↳ Tests: 1 failed | exit=1", text)
        self.assertIn("tool outputs: 4 of 5 calls still on disk", out)

    def test_reasoning_can_be_left_out(self):
        self.vscode_session()
        text, _ = self.digest_text("--session", "s1", "--no-reasoning")
        self.assertNotIn("I expect the tests to pass.", text)
        self.assertIn("Never push.", text)

    def test_small_chunks_hold_every_event_exactly_once(self):
        self.vscode_session()
        whole, _ = self.digest_text("--session", "s1")
        parts, _ = self.digest_text("--session", "s1", "--chunk-chars", "40")
        index = json.loads((self.out / "index.json").read_text())
        self.assertGreater(len(index["chunks"]), 3)
        self.assertEqual(len(list(self.out.glob("chunk-*.md"))), len(index["chunks"]))
        body = lambda t: [l for l in t.splitlines() if l and not l.startswith("# chunk-")]
        self.assertEqual(body(whole), body(parts))

    def test_find_matches_the_session_folder(self):
        self.vscode_session()
        self.cli_session()
        found = session_log.find_logs(cwd=self.repo)
        self.assertEqual(sorted(s for s, _ in found), ["copilot-cli", "vscode"])
        self.assertEqual(session_log.find_logs(cwd=self.root), [])

    def test_cli_digest_shows_failures_exit_codes_and_compactions(self):
        self.cli_session()
        text, _ = self.digest_text("--session", "c1")
        self.assertIn("Fix the build.", text)
        self.assertIn("↳ <exited with exit code 2>", text)
        self.assertIn("FAILED view: Path does not exist", text)
        self.assertIn("NOTE session.compaction_complete", text)

    def test_coverage_fails_until_every_chunk_has_a_heading_with_something_under_it(self):
        self.vscode_session()
        self.digest_text("--session", "s1", "--chunk-chars", "200")
        ids = [c["id"] for c in json.loads((self.out / "index.json").read_text())["chunks"]]
        ledger = self.root / "ledger.md"
        ledger.write_text("".join(f"## {i}\nnone\n" for i in ids[:-1]))
        result = self.run_script("coverage", "--out", str(self.out), "--ledger", str(ledger))
        self.assertEqual(result.returncode, 1)
        self.assertIn(ids[-1], result.stdout)
        ledger.write_text(ledger.read_text() + f"## {ids[-1]}\n")
        self.assertEqual(self.run_script("coverage", "--out", str(self.out), "--ledger", str(ledger)).returncode, 1)
        ledger.write_text(ledger.read_text() + "- 02:00 correction: never push\n")
        result = self.run_script("coverage", "--out", str(self.out), "--ledger", str(ledger))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_no_log_found_says_to_fall_back_to_the_context(self):
        result = self.run_script("digest", "--out", str(self.out))
        self.assertEqual(result.returncode, 1)
        self.assertIn("context window", result.stdout)


if __name__ == "__main__":
    unittest.main()
