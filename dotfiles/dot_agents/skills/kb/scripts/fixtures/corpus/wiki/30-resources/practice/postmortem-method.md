---
title: Postmortem method
created: 2026-02-20
type: concept
tags: [practice, incidents, postmortem]
---
# Postmortem method

Blameless: the question is how the system allowed the failure, not who made the mistake.

Structure
1. **Summary**: two sentences, impact first.
2. **Timeline**: timestamps in one timezone, from first signal to resolution.
3. **Impact**: who and what was affected, for how long, in numbers.
4. **Contributing factors**: usually several; avoid naming a single "root cause".
5. **What went well, what was hard**.
6. **Actions**: each with an owner and a work item; prefer actions that remove a whole class of failure.

Tips
- Write it within five working days, while the logs still exist.
- Link correlation ids and dashboards from the timeline.
- Review it with people who were not on the call.
