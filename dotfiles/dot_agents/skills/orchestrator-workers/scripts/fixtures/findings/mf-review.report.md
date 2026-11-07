5 blocking

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
