## REQUIREMENTS MAP

- MUST 1: tests/unit/order.test.ts::tab order > keeps the default groups in a customised menu: an id keeps its group, groups follow their first id, none is empty [FAIL_TO_PASS]
- MUST 1: tests/unit/order.test.ts::tab order > never gives a stray separator when the header takes a whole group [FAIL_TO_PASS]
- MUST 1: tests/unit/order.test.ts::tab order > uses the default bar until the owner moves something, and never loses an action [FAIL_TO_PASS]
- MUST 2: tests/unit/order.test.ts::tab order > says why an action is not offered, and nothing when it is [FAIL_TO_PASS]
- MUST 2: tests/e2e/app.spec.ts::a customised menu keeps its groups with separators, and the dialog mutes what this session cannot offer [FAIL_TO_PASS]
- MUST 3: tests/unit/order.test.ts::tab order > keeps the default groups in a customised menu: an id keeps its group, groups follow their first id, none is empty [FAIL_TO_PASS]
- MUST 3: tests/unit/order.test.ts::tab order > never gives a stray separator when the header takes a whole group [FAIL_TO_PASS]
- MUST 3: tests/e2e/app.spec.ts::a customised menu keeps its groups with separators, and the dialog mutes what this session cannot offer [FAIL_TO_PASS]
