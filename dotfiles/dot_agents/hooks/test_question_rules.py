import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load("pre_tool_use", "pre-tool-use.py")
post = load("post_tool_use", "post-tool-use.py")

TABLE = "\n\n| Choice | Effect |\n|---|---|\n| a | b |"
GOOD = "Ask now: changes the owner's process. Kind: test rules." + TABLE


def question(message=GOOD, header="q1", options=None):
    return {"header": header, "question": "Which?", "message": message,
            "options": options or [{"label": "1. Keep", "recommended": True}, {"label": "2. Change"}]}


def ask(*questions):
    return hook.decide({"toolName": "vscode_askQuestions", "toolArgs": {"questions": list(questions)}})


def refused(out, text):
    return out.get("permissionDecision") == "deny" and text in out["permissionDecisionReason"]


class QuestionRulesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.dir.name, "answers.jsonl")
        self.env = mock.patch.dict(os.environ, {"QUESTION_LOG": self.log})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.dir.cleanup()

    def answer(self, q, selected, free=None):
        event = {"tool_name": "vscode_askQuestions", "tool_input": {"questions": [q]},
                 "tool_response": json.dumps({"answers": {q["header"]: {"selected": selected, "freeText": free,
                                                                        "skipped": False}}})}
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), mock.patch.object(sys, "stdout", io.StringIO()):
            post.main()

    def test_lets_a_sorted_question_with_a_table_through(self):
        self.assertEqual(ask(question()), {})

    def test_refuses_a_question_without_an_ask_now_reason(self):
        self.assertTrue(refused(ask(question("Which do you want?" + TABLE)), "Ask now"))

    def test_refuses_a_reason_outside_the_five(self):
        self.assertTrue(refused(ask(question("Ask now: it seems useful. Kind: x." + TABLE)), "Ask now"))

    def test_refuses_approving_finished_work(self):
        options = [{"label": "1. Approve as built", "recommended": True}, {"label": "2. Change something"}]
        self.assertTrue(refused(ask(question(options=options)), "finished work"))

    def test_refuses_a_non_trivial_question_without_a_table(self):
        self.assertTrue(refused(ask(question("Ask now: hard to undo. Kind: branch layout.")), "no table"))

    def test_a_fact_about_the_owners_work_needs_no_table(self):
        self.assertEqual(ask(question("Ask now: a fact about the owner's work. Kind: which repo.")), {})

    def test_refuses_several_questions_without_a_batch_label(self):
        self.assertTrue(refused(ask(question(header="a"), question(header="b")), "batch N of M"))
        self.assertEqual(ask(question(GOOD.replace("rules.", "rules. Batch 1 of 2."), header="a"), question(header="b")), {})

    def test_refuses_a_kind_taken_by_reflex_five_times(self):
        q = question()
        for _ in range(4):
            self.answer(q, ["1. Keep"])
        self.assertEqual(ask(q), {})
        self.answer(q, ["1. Keep"])
        self.assertTrue(refused(ask(q), "last 5 times"))

    def test_an_override_resets_the_streak(self):
        q = question()
        for _ in range(4):
            self.answer(q, ["1. Keep"])
        self.answer(q, ["2. Change"])
        self.answer(q, ["1. Keep"], free="but only here")
        self.assertEqual(ask(q), {})

    def test_logs_kind_and_whether_the_recommendation_was_taken(self):
        self.answer(question(), ["2. Change"])
        with open(self.log) as f:
            row = json.loads(f.readline())
        self.assertEqual((row["kind"], row["reason"], row["took_recommended"]),
                         ("test rules", "changes the owner's process", False))


if __name__ == "__main__":
    unittest.main()
