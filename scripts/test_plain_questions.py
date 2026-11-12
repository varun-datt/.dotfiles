import json
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "dotfiles", "dot_agents", "hooks", "plain-questions.py")


def hook(event):
    raw = event if isinstance(event, str) else json.dumps(event)
    r = subprocess.run([sys.executable, SCRIPT], input=raw, capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def ask(*texts, camel=True):
    args = {"questions": [{"header": "h", "question": texts[0], "message": " ".join(texts[1:]),
                           "options": [{"label": "1. Yes", "description": "plain"}]}]}
    if camel:
        return {"toolName": "vscode_askQuestions", "toolArgs": json.dumps(args)}
    return {"tool_name": "vscode_askQuestions", "tool_input": args}


class PlainQuestions(unittest.TestCase):
    def test_todays_jargon_question_is_refused(self):
        out = hook(ask("How should nv2's open clock be closed?",
                       "`estimates.py end` can only stamp the current time."))
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("estimates.py", out["permissionDecisionReason"])
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_each_kind_is_refused_in_either_payload_shape(self):
        for text in ("Wait with wait-exit --dots 30?", "Run lane-merge.zsh first?", "Should npm run check stay?",
                     "Then git merge main?", "Use chezmoi apply?", "Is `x` fine?"):
            for camel in (True, False):
                with self.subTest(text=text, camel=camel):
                    self.assertEqual(hook(ask(text, camel=camel)).get("permissionDecision"), "deny")

    def test_plain_words_pass(self):
        for text in ("How long should the record say nv2 took?", "Keep the full check at every merge — or not?",
                     "Is this for the merge script's re-run and the wiki's git repository?", "Notes in a node tree?"):
            with self.subTest(text=text):
                self.assertEqual(hook(ask(text)), {})

    def test_other_tools_and_bad_input_make_no_decision(self):
        self.assertEqual(hook({"toolName": "run_in_terminal", "toolArgs": json.dumps({"command": "npm run check"})}), {})
        self.assertEqual(hook("not json"), {})
        self.assertEqual(hook({"toolName": "vscode_askQuestions", "toolArgs": "{broken"}), {})


if __name__ == "__main__":
    unittest.main()
