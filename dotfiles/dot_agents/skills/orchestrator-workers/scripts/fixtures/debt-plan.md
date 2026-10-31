# Plan

| Date | Decision | By |
| --- | --- | --- |
| 2026-01-02 | A stray line that mentions known gaps: not an item | human |

## Items

1. Widget search (owner, 2026-01-01): built and merged. Known gaps (review, not blocking): a widget
   renamed during a search keeps its old name; the cache is read once until a restart; a query that
   starts with `--` is read as an option. The owner tried it live.
2. Gadget view, merged 2026-01-03 (abc1234; gated as def5678). Known gaps (review, not blocking): a
   root set by hand with a trailing `/` or `/.` is still followed (fixed later in 1111111; reverted
   in 2222222); a folder swapped for a link between the check and the read. Clusters built after.
3. Sprocket export. Known gap: names saved before that change can still be reused.
4. Attachments. Known gaps (review rounds): an attachment is read whole with no binary check; a
   literal `>>>; <<<` in an attachment becomes `>>`. Fixed 2026-01-05 (merge 3333333): the fence.
5. Thread markers. Known gap, accepted by the owner on 2026-01-04: a thread on a deleted first line
   shows a stray number.
6. Nothing known here, and no gaps worth a row.
