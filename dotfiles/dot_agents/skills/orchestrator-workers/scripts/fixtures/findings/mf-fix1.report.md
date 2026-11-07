Both findings are fixed in commit f194172 on `ow/mf`, and every check passes (VERIFIED). The work ran 19:27–19:29 and 20:38–20:44; the gap was the Mac sleeping.

**Finding 1: deciding a resumed round by numbers** (VERIFIED)
- **Fix:** whether a round continued a session now comes only from provenance: its own session id matching an earlier round's, a `-resume<N>` name, or a `resumes` launch record.
  - In `mine.py`, `decumulate()` gives a round with no session id its own session when its launch record says it was fresh. It also records on each round whether it continued its session and whether the running total fell; the existing rule that a fall resets the total is unchanged.
  - `result.py` `usage_line()` now uses those flags and no longer compares figures.
- **Test** (`test_mine.py`): `RoundCreditsTest.test_a_fresh_round_without_a_session_id_stands_alone_by_its_launch_record`
  - Fails on 1498bbb: `['premium_requests=30 ai_credits=760.6 session_premium_reque…al)'] != ['premium_requests=45 ai_credits=981.4']`
  - Passes on f194172: OK
- **Test:** `RoundCreditsTest.test_a_resumed_round_after_a_zero_round_or_a_fall_prints_its_known_figure`. It covers a predecessor that spent 0, growth of 0.0 shown with the session total, and a fall that prints the round's own figure.
  - Fails on 1498bbb: `["session_premium_requests=45 session_ai_c…wn)"] != ['premium_requests=45 ai_credits=981.4 ses…al)']`
  - Passes on f194172: OK
- The four real p1b rounds still print 220.7, 274.2 with 981.4, and 102.7 with 1084.1. A resumed round with no earlier round in the folder keeps its "session running total" label. The existing tests pin both.

**Finding 2: result.py and mine.py disagreeing on a round** (VERIFIED)
- **Fix:** `round_in_folder()` now returns the round exactly as `mine.load_rounds(run)` computes it over the whole folder. The name filter and `load_rounds`' `keep` parameter are gone.
- **Test:** `RoundCreditsTest.test_a_round_outside_the_naming_scheme_gets_the_figure_mine_gives_and_a_review_stands_alone`. It uses a copy of the real fix4 log renamed `p1b-report2`, and a review that is still computed alone.
  - Fails on 1498bbb: `'premium_requests=60 ai_credits=1084.1' != 'premium_requests=15 ai_credits=102.7 session_premium_reque…tal)'`
  - Passes on f194172: OK
- I removed my earlier test `test_only_the_items_own_worker_logs_are_read`, because this finding overturns what it checked.

**Mutation check:** runtime patches killed 5 of 5, none invalid (VERIFIED; harness `.gates/mutate-fix.py`, log `.gates/mutate-fix.log`). The mutants were: launch provenance dropped, the figure comparison restored, a fall labelled "share unknown", a zero predecessor treated as not continued, and the name filter restored.

**Same kind, not fixed**
- `mine.py` near line 368: a round with no session id and no launch record (a hand-run round, or a folder without `routes.jsonl`) still joins its item's session. That is the existing rule, and there is no provenance to decide otherwise. INFERRED.
- `mine.py` near line 391: the fall reset is unchanged, as NOT TO CHANGE says.
- TD-18 (concurrent `--findings` rebuilds) is not touched.

**Checks** (from `scripts/`, VERIFIED)

| Command | Result |
|---|---|
| `python3 -B -m unittest test_mine test_runqueue -v </dev/null > ../../../../../.gates/fix-mf.log 2>&1; echo $?` | exit 0, 109 tests OK |
| `python3 -B -m unittest discover -p 'test_*.py' </dev/null > ../../../../../.gates/suite.log 2>&1; echo $?` | exit 0, 541 tests OK |
| `python3 -B result.py --help` | exit 0 |
| `pgrep -x yes \| wc -l` | 0 |

**Could not do:** I did not time `result.py` on the real 54-log folder now that it reads every log; the brief leaves that re-timing to you (OPEN). `REVIEW-DIFF.patch` and `REVIEW-REPORT.md` are left uncommitted.

**REQUIREMENTS MAP**
- MUST 3: dotfiles/dot_agents/skills/orchestrator-workers/scripts/test_mine.py::RoundCreditsTest.test_a_fresh_round_without_a_session_id_stands_alone_by_its_launch_record FAIL_TO_PASS
- MUST 3: dotfiles/dot_agents/skills/orchestrator-workers/scripts/test_mine.py::RoundCreditsTest.test_a_resumed_round_after_a_zero_round_or_a_fall_prints_its_known_figure FAIL_TO_PASS
- MUST 3: dotfiles/dot_agents/skills/orchestrator-workers/scripts/test_mine.py::RoundCreditsTest.test_a_round_outside_the_naming_scheme_gets_the_figure_mine_gives_and_a_review_stands_alone FAIL_TO_PASS
