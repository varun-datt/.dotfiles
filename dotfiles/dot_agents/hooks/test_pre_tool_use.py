import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("pre_tool_use", os.path.join(os.path.dirname(__file__), "pre-tool-use.py"))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def terminal(command):
    return hook.decide({"toolName": "run_in_terminal", "toolArgs": {"command": command}})


class PreToolUseTest(unittest.TestCase):
    def test_refuses_a_question_with_code_formatting(self):
        out = hook.decide({"toolName": "vscode_askQuestions", "toolArgs": {"questions": [{"question": "Run `npm test`?"}]}})
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn("Plain words", out["permissionDecisionReason"])

    def test_refuses_a_gated_step_after_a_semicolon(self):
        out = terminal("make build; git commit -m x")
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn("Gated step", out["permissionDecisionReason"])

    def test_rewrites_npx_so_it_cannot_install(self):
        out = terminal("npx tsc --noEmit")
        self.assertEqual(out["hookSpecificOutput"]["updatedInput"]["command"], "env npm_config_yes=false npx tsc --noEmit")

    def test_a_refusal_wins_over_a_rewrite(self):
        out = terminal("npx vitest run | tail -3 && git commit -m x")
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertNotIn("updatedInput", out.get("hookSpecificOutput", {}))

    def test_lets_other_calls_through(self):
        self.assertEqual(terminal("ls -la"), {})
        self.assertEqual(hook.decide({"toolName": "read_file", "toolArgs": {"filePath": "/tmp/x"}}), {})


if __name__ == "__main__":
    unittest.main()
