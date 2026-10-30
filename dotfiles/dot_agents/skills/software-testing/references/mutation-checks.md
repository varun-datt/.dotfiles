# Mutation checks

A mutation check breaks the behaviour a new test covers and confirms the test fails on its own assertion. It is the proof the rule "Prove a test can fail" in [SKILL.md](../SKILL.md) asks for; this page runs it without editing a file, so there is nothing to undo.

Python's `unittest.mock` documentation, ["Where to patch"](https://docs.python.org/3/library/unittest.mock.html#where-to-patch): "The basic principle is that you patch where an object is looked up, which is not necessarily the same place as where it is defined." In Python the same holds for a plain assignment such as `module.f = broken`.

## Procedure

1. **Write one wrapper with named mutants.** It imports the code and the test suite, replaces one function, method or constant per mutant name, runs the suite's entry point with its output captured, and prints the mutant's name, the exit code and the checks that failed. Nothing on disk changes.
2. **Run each mutant in its own process,** plus a `none` control that must pass: one mutant's patch cannot leak into the next, and a broken wrapper shows up in the control.
3. **Patch the name where it is looked up.** A module that did `from x import f` holds its own binding, so patching `x.f` does not reach it; patch the importer's name, or the module attribute its callers go through.
4. **Make each mutant the old behaviour, guards included.** A mutant that crashes the run (a missing folder, a file it deletes that it does not own) proves nothing: the check must fail on its assertion. Copy the old code's guards into the mutant and run it again.
5. **Do not swap in the old file whole** when the new tests call a new parameter or function: the run crashes on the call instead of failing the check. Patch the one behaviour the test is for.
6. **Name what a runtime patch cannot reach,** such as argument parsing or wiring done at import time: cover it with a check that runs the program in a subprocess and asserts its exit code and output, or report it as uncovered.
7. **Read which checks failed, not only the exit code.** Each mutant must fail the check written for it; other checks failing as well is fine when they depend on the same behaviour, and a mutant that fails none means the tests cannot see that bug.

Intermittent behaviour needs about 30 runs per mutant: see [flaky tests](flaky-tests.md).

Seen 2026-10-30: seven runtime mutants each failed the check written for it, while a first attempt that swapped in the old file crashed on a new keyword argument, and a mutant that left out the old code's guards crashed on a missing folder.
