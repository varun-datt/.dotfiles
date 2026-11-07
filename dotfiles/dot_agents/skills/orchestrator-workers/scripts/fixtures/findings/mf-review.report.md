5 blocking

**Blocking.**

B1. [Major] COR L2/I2 FAIL: Missing intermediate logs inflate the next round’s cost.

Class: incomplete checkpoint history. When `p1b-fix3.jsonl` is missing but its `.start`, the build and resume logs remain, [result.py:40](dotfiles/dot_agents/skills/orchestrator-workers/scripts/result.py#L40) reports fix4 as `ai_credits=377.0 premium_requests=30`, including fix3’s spend. **VERIFIED:** read-only `usage_line()` probe hiding that filename through `os.listdir`. L2: missing logs during recovery; I2: wrong ledger figures, contrary to MUST 3. **WHY NOW:** inflated round costs reach the owner’s records. Fix: detect intervening missing checkpoints and label the round’s share unknown.

B2. [Major] COR L2/I2 DESIGN: Filename filtering discards legitimate session predecessors.

Class: filename-derived session identity. A resumed round named `p1b-report2` shares the recorded session, but [mine.py:347](dotfiles/dot_agents/skills/orchestrator-workers/scripts/mine.py#L347) isolates it by filename. **VERIFIED:** read-only fixture-alias probe produced 274.2 through `mine.load_rounds()`, versus 981.4 through `result.usage_line()`. The existing `test_an_unknown_suffix_inside_a_session_is_other` establishes this supported naming case. L2: older/custom resume names; I2: wrong costs and unmet MUST 3. **WHY NOW:** the new optimization defeats the reused helper’s session grouping. Fix: scope reads by actual session provenance, not inferred item names.

B3. [Major] COR L2/I2 DESIGN: Credit inequality substitutes for session provenance.

Class: numeric proxies for known versus unknown history. At [result.py:40–43](dotfiles/dot_agents/skills/orchestrator-workers/scripts/result.py#L40), a known zero predecessor or counter reset is labelled “earlier rounds are not in this folder,” withholding known round figures. Conversely, a fresh round interrupted before `result` can inherit the previous session’s identity and print a false delta. **VERIFIED:** read-only probes showed known 30.0 reset credits labelled unknown, and an unfinished fresh round printing 274.2 instead of its 981.4 total even with `resumed()` false. Original logs have no top-level session identity before `result`. L2: reset or CLI failure; I2: wrong figures/availability under MUST 3. **WHY NOW:** recovery summaries become unreliable. Fix: use explicit launch/provenance metadata rather than `credits < cum_credits`; cover both directions.

B4. [Major] COMP L1/I2 ADJ: Literal case placeholders prevent the re-review from launching.

Class: generated literals reinterpreted as template slots. When an after-“Done when” Cases list quotes `{{FINDING_1}}`, [reviewprep.py:244](dotfiles/dot_agents/skills/orchestrator-workers/scripts/reviewprep.py#L244) preserves it, but [review.sh:100–103](dotfiles/dot_agents/skills/orchestrator-workers/scripts/review.sh#L100) and `brief.problems()` reject it as unfilled. **VERIFIED:** generated-template probe returned both placeholder errors; the base parser dropped this after-“Done when” list. This newly exposes the existing TD-11 limitation. L1: literal template examples are a named normal input; I2: re-review cannot launch. **WHY NOW:** MUST 2’s literal case passes the new test but breaks the real flow. Fix: preserve literal provenance through both validators without permitting genuine unfilled slots; test the launch boundary.

B5. [Major] REL L2/I2 ORDER: A runner restart during settling causes a false wake.

Class: stale news decisions across a wait. When an exit is initially new, then the runner restarts during the default settling delay, [runqueue.py:909–914](dotfiles/dot_agents/skills/orchestrator-workers/scripts/runqueue.py#L909) correctly removes that exit but still returns 0. **VERIFIED:** read-only `wait()` probe changing runner start from 100 to 300 around an exit at 200 printed only “not news” and returned 0. L2: restart during settling; I2: MUST 5 explicitly requires the no-news return. **WHY NOW:** past exits still wake the orchestrator and consume attention/credits. Fix: continue waiting when the settled fresh-news list is empty.

**Check.**

None.

**Minor.**

None.

**Pre-existing.**

P1. VERIFIED VERIF L2/I2 PRE: An unindented standalone `Cases:` truncates `FIX THESE`, hiding later findings, [reviewprep.py:211](dotfiles/dot_agents/skills/orchestrator-workers/scripts/reviewprep.py#L211); class: section-delimiter collision. The same real brief reformatted this way yields one finding on both base and branch.

**Corrections.**

VERIFIED: MUSTs 1 and 4 are met at [route.py:1021–1039](dotfiles/dot_agents/skills/orchestrator-workers/scripts/route.py#L1021) and the preambles; MUSTs 2, 3 and 5 are only partly met above. [REVIEW-REPORT.md](REVIEW-REPORT.md) also says the base tail is added after argv construction; it is supplied during construction. Its base log contains 12 distinct failing test methods and 14 failure events, not 14 failing methods.

Nits: 0

**Not checked.**

Full suites and mutation controls were not rerun because they write files; their supplied logs show 539 tests passing and 38 valid kills. **VERIFIED:** all four help gates were rerun successfully. The 54-log performance claim remains **OPEN**: only four real worker logs, totalling 15.9 MB, were supplied. Exact CLI 1.0.106 behaviour was not live-tested; installed 1.0.107 help was read. Unexplained denial causes remain **OPEN**.

```json
{
  "version": "2.1.0",
  "runs": [{
    "results": [
      {
        "ruleId": "FAIL",
        "level": "error",
        "message": {"text": "Missing intermediate logs inflate the next round's cost"},
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "dotfiles/dot_agents/skills/orchestrator-workers/scripts/result.py"},
            "region": {"startLine": 40}
          }
        }],
        "properties": {
          "n": "B1", "grade": "Major", "area": "COR",
          "likelihood": "L2", "impact": "I2",
          "class": "incomplete checkpoint history"
        }
      },
      {
        "ruleId": "DESIGN",
        "level": "error",
        "message": {"text": "Filename filtering discards legitimate session predecessors"},
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "dotfiles/dot_agents/skills/orchestrator-workers/scripts/mine.py"},
            "region": {"startLine": 347}
          }
        }],
        "properties": {
          "n": "B2", "grade": "Major", "area": "COR",
          "likelihood": "L2", "impact": "I2",
          "class": "filename-derived session identity"
        }
      },
      {
        "ruleId": "DESIGN",
        "level": "error",
        "message": {"text": "Credit inequality substitutes for session provenance"},
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "dotfiles/dot_agents/skills/orchestrator-workers/scripts/result.py"},
            "region": {"startLine": 40}
          }
        }],
        "properties": {
          "n": "B3", "grade": "Major", "area": "COR",
          "likelihood": "L2", "impact": "I2",
          "class": "numeric proxies for known versus unknown history"
        }
      },
      {
        "ruleId": "ADJ",
        "level": "error",
        "message": {"text": "Literal case placeholders prevent the re-review from launching"},
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "dotfiles/dot_agents/skills/orchestrator-workers/scripts/reviewprep.py"},
            "region": {"startLine": 244}
          }
        }],
        "properties": {
          "n": "B4", "grade": "Major", "area": "COMP",
          "likelihood": "L1", "impact": "I2",
          "class": "generated literals reinterpreted as template slots"
        }
      },
      {
        "ruleId": "ORDER",
        "level": "error",
        "message": {"text": "A runner restart during settling causes a false wake"},
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "dotfiles/dot_agents/skills/orchestrator-workers/scripts/runqueue.py"},
            "region": {"startLine": 909}
          }
        }],
        "properties": {
          "n": "B5", "grade": "Major", "area": "REL",
          "likelihood": "L2", "impact": "I2",
          "class": "stale news decisions across a wait"
        }
      },
      {
        "ruleId": "PRE",
        "level": "note",
        "message": {"text": "An unindented standalone Cases label truncates the findings list"},
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "dotfiles/dot_agents/skills/orchestrator-workers/scripts/reviewprep.py"},
            "region": {"startLine": 211}
          }
        }],
        "properties": {
          "n": "P1", "grade": "Pre-existing", "area": "VERIF",
          "likelihood": "L2", "impact": "I2",
          "class": "section-delimiter collision"
        }
      }
    ]
  }]
}
```
