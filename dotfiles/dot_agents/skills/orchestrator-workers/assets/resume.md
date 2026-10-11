<!-- Resume prompt, sent with `copilot -r <prefix><item>` and the same flags as the original launch,
to a session that stopped without finishing: a stall, a CLI-wide stop, sleep, an editor quit, or a
background-task timeout. Name the run <item>-resume<N> so status.py treats the old run as superseded.
Keep it short: the session still has its own context. -->
Your previous run {{WHAT_HAPPENED}} at {{TIME}}; nothing you did caused it. Your commits up to {{LAST_COMMIT}} are intact, and {{TREE_STATE}}.

Continue from where you stopped. {{NARROWED_SCOPE_OR_DELETE}} Commit each piece as soon as it passes, with explicit paths. Then run every gate on the final tree, in the foreground, {{ENVIRONMENT_NOTE_OR_DELETE}} and give the full report your task asked for, marking every claim VERIFIED, INFERRED or OPEN.

<!-- Examples for {{WHAT_HAPPENED}}:
  "stalled for 25 minutes inside a single model call after the editor window reloaded, so it was stopped"
  "was cut off by a Copilot CLI failure (\"Cannot invoke native session after disposal has started\")"
  "ended when the machine slept and the model call failed five times"
  "was ended by the CLI because a background task was still running when you ended your turn"
  "ran past 2.5x its time budget, so it was stopped"   (then fill NARROWED_SCOPE)
Examples for {{TREE_STATE}}: "the working tree is clean" / "your uncommitted edits are still in the tree". -->
