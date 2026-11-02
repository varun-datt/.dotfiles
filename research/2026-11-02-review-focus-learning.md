# Review focus learning: a record that steers what each review looks at

Research for task rb1, 2026-11-02. Status: draft; the graded dataset and the numbers are added in later commits.

## In short

- Keep the owner's starting table almost as it is, with three changes, and build the record from what already exists: `mine.py` fills it from the reports it already reads, `route.py` reuses its Thompson sampler to pick each review's focus blocks, and `review.sh` fills the review template's existing focus slot.
- One row per finding, per review and per escape, as JSONL in each run folder next to `routes.jsonl`, read across runs the way `route.py` already reads its history.
- A review is skipped only when no focus block clears a worth threshold and the change touches no always-reviewed area (data, approvals, folders, spend); the threshold starts strict and loosens only while escapes stay flat.
- "Is each requirement met" becomes a merge-gate script: each SHALL names a test, and the gate removes the change that test covers and checks the test then fails.
