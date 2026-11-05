# Case lists

Before writing code, list the cases a change must survive, then give each a test. A reviewer who blocks a branch usually asks one question the builder never asked: "what about the other send path?", "what if Stop lands here?". These lists are those questions, taken from 264 review findings on agent builds over four runs (2026-10-27 to 10-30), most frequent first. Each list stays short on purpose: targeted questions catch more than a long generic checklist ([Porter, Votta and Basili](https://www.cs.umd.edu/users/basili/publications/technical/T101.pdf): reviewers with scenarios found more faults, and reviewers with a generic checklist did no better than ad hoc ones).

## How to use them

1. **Assume the review already failed.** Write two or three sentences on why, before reading the lists. Imagining that a failure has happened "increases the ability to correctly identify reasons for future outcomes by 30%" ([Klein, HBR 2007](http://homepages.se.edu/cvonbergen/files/2013/01/Performing-a-Project-Premortem.pdf), citing Mitchell, Russo and Pennington).
2. **Take every list your task's RISK names, plus "Every change".** Answer each question for each entry of your impact map.
3. **Each answer is a test or a reason.** "Cannot happen" needs evidence (a file:line, a type, a probe). Thinking it over again without new evidence does not count: models rarely correct themselves without an outside signal such as a failing test ([Kamoi et al., TACL 2024](https://arxiv.org/html/2406.01297)).
4. **Prove each test can fail** ([mutation checks](mutation-checks.md)); drive orderings on purpose ([event orders](event-orders.md)).
5. **Put the table in the report.** The reviewer checks it.

## Every change

- **Who else reads or writes this?** Every caller; every reader of a stored field, route, setting, environment variable or CSS class; the other implementation of the same job (a second engine or adapter, the other send, save or open path, the copy or fork path). Missed in 25 of 133 accepted blocking findings.
- **Which library, platform or vendor behaviour am I relying on?** Read its source or docs, or probe it. Unchecked facts caused 20 of 133: a view state that also restores folds, a search box whose blur moves focus, `lstat` following a trailing slash, an SDK schema that drops a field, an id that is only a snapshot position.
- **What does each awaited call do when it fails, times out or half-succeeds?** Handle it, show it as unknown rather than as fine, and test it. In one study, 92% of catastrophic failures came from mishandled non-fatal errors ([Yuan et al., OSDI 2014](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf)).
- **Edge values:** empty, one, many, very large (the owner's real data sizes); the first and last line, line 0; today, midnight, a span across midnight; an unknown enum value; non-UTF-8 text; text that contains markup, quotes or fences.
- **Records written by an older version:** a stored row, log line or file without the new field.
- **Existing tests and specs that touch what changed:** find them through the impact map and run them; a spec still expecting the old menu fails at the merge gate otherwise.
- **Stored or derived?** Store the least state and derive the rest; two stored values that can disagree will ([react.dev, "Choosing the state structure"](https://react.dev/learn/choosing-the-state-structure)). Identity comes from the thing itself, never from its position in a list.

## host-state: turns, runs, sessions, queues

Event orders were 9 of the 24 accepted findings on these items.

- **Stop, then a late event:** a delta, echo, refusal, tool request or callback after Stop.
- **The engine ends the turn on its own** (idle, aborted, error) while something waits on it.
- **A restart between two steps:** the answer is stored but its action has not run, or the action ran but its record says not. Rebuild from the stored data and check both.
- **A second round of the same thing:** a stale timer or callback from round 1 lands in round 2; a finished answer replays after a restart. Tag work with its round and check the tag after every `await`.
- **Two at once:** a double press, two sends in flight, End during a merge. Serialize through one queue, or refuse with a reason.
- **Keys and scope:** ids that restart at 1 per run, session or worker collide across them.
- **Delivered is not resolved:** read what the callee returns before treating a send as done.

## boundary: outside input, files, paths, secrets

- **Every place outside text reaches a model or a log:** fence each one with the existing helper, and list them by search, not memory (10 findings across 6 items).
- **Paths go through the one containment helper:** symlinks at the root, a parent and the leaf; `..` after a symlink; a trailing `/` or `/.`; hard links.
- **Check, then use:** open once and check the open descriptor, rather than checking a path and opening it again (9 findings across 7 items).
- **Other content types and entry points:** a guard on HTML also on SVG; a guard in the frame also on the directly opened page.
- **Secrets and account text** never reach the UI or a log: no raw error output, environment values or tokens; use fixed reason codes.
- **Arguments:** a value starting with `-` is read as an option unless it follows `--`.

## data: caches, histories, imports, stores

- **The owner's real scale:** measure sizes, not contents, and test at that size; parse large inputs off the main thread.
- **One source fails while the others answer:** keep the failed source's state, and show it as unreadable rather than empty.
- **Cache lifecycle:** invalidate on detach, on source removal and on a configuration change.
- **Provenance:** each cached or derived item records where it came from, and is reused only where all its sources are allowed.
- **Old names and formats** in real data: try the change read-only against a copy of real records.

## UI

- **Every input path gives the same result:** mouse, keyboard, drag and menu each announce and keep focus the same way.
- **Focus after a change:** when the focused element is removed, disabled or hidden, move focus to a stable control; keep DOM focus and the component's own focus together.
- **Library defaults:** read what the component does on blur, on keys and on re-render before relying on it, and check it against the WAI-ARIA pattern.
- **Contrast is computed, not judged by eye:** every text colour on every background in every theme, WCAG AA 4.5:1.
- **Nothing moves when something loads late:** reserve its space, and give each lazy part an error state.
- **Global names:** search for a CSS class before adding one.
- **One colour, one meaning; the normal state is quiet;** a chart says what its bars measure.
- **Browser tests own their data:** a test creates and finds its own rows by id and passes in any order.

## dotfiles and scripts

- **Run it read-only against the real folders or a copy:** older naming schemes, resumed sessions with idle gaps, records counted twice.
- **Every record kind that opens or closes something** (start, end, drop, add) is handled.
- **The owner's own commands still work** with optional settings unset.
- **The documentation that names the behaviour** (SKILL.md, README, plan lines) changes with it.

## config edits: YAML, pipeline files, CODEOWNERS, branch filters

From one migration skill's five review rounds (2026-11-02 to 11-03), where editing YAML as text and judging branch-filter coverage each caused several blocking findings.

- **Every way the same value can be written:** quoted and unquoted, a folded or literal block (`>-`, `|`) over several lines, a trailing comment, CRLF line ends, a UTF-8 BOM. Text inserted before a BOM moves it into the next key, which then parses as `\ufefftrigger` with no error.
- **YAML indicators in generated values:** a bare `*` starts an alias and `&` an anchor, so a generated `- *` does not parse. Quote every generated scalar.
- **Order semantics:** in CODEOWNERS the last matching line wins, so removing a duplicate keeps its last occurrence.
- **One pattern covering another is not a glob match:** `fnmatch('release/*', 'release/?')` is true because `?` matches the literal `*`, and an exclude removes coverage an include gave. Decide coverage from the patterns' structure, and treat what cannot be proved as uncovered.

## test-suite: guards, harnesses, flaky-test fixes

- **A guard parses; it does not pattern-match.** Use the language's own scanner: a regular expression matches comments and misses variants.
- **Configuration is in scope:** a guard over `tests/` misses the config file that sets the default.
- **Removing coverage to fix a flake** needs a replacement test for what it covered.
- **Meters and counters see every call,** including calls the system makes on its own (titles, retries).
- **The test reaches the path at risk.** Starting an app misses what it sets up on first use (a connection pool, a Kerberos login): call something that uses it. A harness whose settings switch the risky part off (security off, an unencrypted broker) proves nothing about it; a smoke test on a local plaintext Kafka reported healthy while the encrypted broker failed in the cluster.

## Keeping the lists true

After each run, add its accepted findings to the defect log, tagged with a cause and a class, and change a list only where a class recurs or one costly miss shows a gap. The Personal Software Process keeps review checklists the same way: engineers "update their personal review checklists to help them find and fix similar defects in the future" ([Humphrey, CMU/SEI-2000-TR-022](https://sei.cmu.edu/library/the-personal-software-process-psp)).
