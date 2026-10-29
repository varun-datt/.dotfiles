# Reading a Terraform repo for an explanation

The goal is a table you could defend line by line: for each account and environment, what is created, its name pattern, what it is for, who uses it, who else may reach it, and the source of each fact.

## 1. Find the shape

- **Roots and accounts.** List the root modules (folders with a `backend` block) and the per-account inputs: `*.tfvars`, `backends/*`, workspace names, or the CI matrix that runs `plan` and `apply`. The CI matrix is the truest list of accounts actually deployed.
- **What the code says about accounts.** Search the shared code for account names, environment names, 12-digit numbers and literal ARNs (`rg -n '"(dev|prod|test)[^"]*"|[0-9]{12}|arn:aws' <root>`). Each hit is either a per-account fact living in the wrong place or a constant; say which.
- **Guards.** Conditions such as `var.environment == "dev" ? {...} : {}` or `count = var.x ? 1 : 0` decide what exists where. List each with the inputs that flip it.

## 2. Inventory what is created

- **Per environment, from the maps.** For every `module` and `resource` block, write down its `for_each` or `count` source and expand it with the real inputs. Multiply by environments; do not count blocks.
- **Inside each module.** Open the module at the exact version pinned in `source` (`?ref=v1.2.3`, a registry `version`, or a commit); `gh api -H 'Accept: application/vnd.github.raw' 'repos/OWNER/REPO/contents/PATH?ref=TAG'` reads one file at a tag without cloning. Note what it creates besides the obvious (keys, policies, roles, log buckets), its defaults (versioning, logging, encryption, deletion protection) and how it builds names (random suffix, region, environment).
- **Settings that differ.** Retention days, sizes, feature switches: collect them per account in one table, with the file and line for each value.
- **Outputs and consumers.** Outputs show what other code is meant to use. Then search the services that run against these resources for the names and ARNs (Helm values, app settings, test settings). Hard-coded names mean a rename is a breaking change for them.

## 3. Who else can reach it

- **Grants come in pairs.** Another account's role needs both the resource policy (bucket, key, queue, event bus) and its own IAM policy. Collect every principal that is not the service's own role, with its actions.
- **Name each one as what it is,** not as a team: "Windows EC2 test agents through role X", "a Lambda in the analytics account through role Y", "an event bus in account Z". Read the other side's code to find out what the principal is and whether it uses the grant; say "unused today" only with that evidence.
- **Event flows.** Follow notifications and rules to their targets: bucket notification settings, EventBridge rules and targets, dead-letter queues, retry settings. Read the receiving side far enough to show where its workflow starts, and which of its schedules are switched on.

## 4. Check it live (read-only)

- Use the account's read-only role and `list`/`get`/`describe` calls only. Prove the credentials work with a control that must be non-empty first; expired single sign-on often returns empty lists or a token error that is easy to miss.
- Useful checks: the bucket list against the code's names; `get-bucket-notification-configuration`; `get-bucket-lifecycle-configuration` and `get-bucket-versioning`; `kms list-aliases` counted against the code; `events list-targets-by-rule`; CloudWatch metrics for invocations and failures.
- Access logs answer "does anyone use this grant", but they are large: sample every Nth log file with a short script rather than syncing a bucket, and report the sample size beside the result.

## 5. What a re-creation would mean

For each change you might propose, write: re-created or not, the new name if it is, who breaks (consumers found in step 2), and whether data is lost. A bucket that still holds files refuses to be destroyed unless `force_destroy` is set; a table is deleted with its items unless deletion protection is on; a key is scheduled for deletion after a waiting period of 7 to 30 days, after which nothing encrypted with it can be read. `moved` blocks change addresses without re-creating.
