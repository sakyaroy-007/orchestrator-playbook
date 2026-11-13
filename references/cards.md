# Writing bounded task cards

Use `templates/task-card.md` or `templates/spike-card.md`. Projects may keep template snapshots; configured paths and [configuration](configuration.md) take precedence. A card narrows scope and permissions; it cannot appoint an owner, authorize a new worker, grant Git rights, override a red line or change project policy.

## Split along contracts

One card produces a contract that another consumes: function signature, schema, endpoint or file format. Before an upstream result is integrated, downstream work uses an explicitly agreed contract/mock or records the dependency and exact starting branch. Do not treat an unmerged promise as implemented behavior.

Keep cards small enough to review independently. Suggested sizes are S (half day), M (about a day) and L (about two days); split larger work and state a fallback split point. Separate money/auth/isolation work from unrelated UI or refactors. Number by epic where useful, with S-NN for spikes. Out-of-scope findings become new cards linked to their source.

Keep one-line backlog entries and expand only the next ready wave. Re-check existing cards against current paths, contracts and baseline before dispatch; old line numbers are not evidence of current behavior. A foundations wave is needed only for actual blockers.

## Card content

| Field | Required information |
|---|---|
| Dispatch prompt | Read worker rules and this one card, use explicit working directory/branch, report using the template; append only narrower restrictions |
| Policy | Config path/revision, decision evidence and approved worker ID; unresolved settings/permissions block the affected action |
| Baseline | HEAD/branch or non-Git snapshot, dirty/untracked facts, relevant pre-existing failures |
| Goal and background | Checkable result and measured reason for this work, with command/output or file evidence |
| Reading and contract | Specific files, ADR sections and externally consumed names/behavior |
| Scope | Allowed files/operations, explicit exclusions and shared-resource reservation |
| Dependencies | Required integration commits/contracts, or a documented upstream starting branch |
| Acceptance | Actual runnable commands, cwd, expected external behavior, failures that must be caught and relevant coverage limits |
| Report | Actual commands/exit/output, covered scope, gaps, preserved work and out-of-scope findings |

Use project-resolved absolute paths in a live dispatch prompt so workers do not guess cwd. Keep public templates portable placeholders. A card that cannot be completed inside scope returns `blocked` with evidence and a recommendation; it does not grant itself an exception.

## Register the executable task contract

Complete and register a structured spec before dispatching a new card. It records requirements/acceptance, relevant relative content scopes, upstream task/evidence references with contract-only versus integrated requirements, exclusive resource names, and required review declarations. The runtime stores the requirements revision/digest and retains prior records. Keep this machine-readable contract aligned with the human card; a draft or an unregistered markdown promise does not satisfy readiness.

Use the read-only readiness operation for the actual intended worktree. It explains missing dependencies or occupied resources; run checks again under the same reservation lock before launching. A required upstream integration must be present at the consumer's actual starting point, not merely mentioned in a note. Explicitly agreed contract-only work pins the upstream spec revision/hash; it requires neither an integrated implementation nor a claim that the code was accepted. Reconcile a changed upstream result before downstream acceptance/integration. Contract-only bindings track the spec. Integrated dependencies bind an intact historical result and check the consumer's actual baseline. An upstream target advancing normally does not erase that history; publishing the changed target still needs current assembled verification bound to its HEAD/branch and scope.

Exclusive names use one project-wide namespace across worktrees, such as `port:3000`, `database:integration` or `file:package-lock.json`. Declare shared hot-file ownership explicitly; matching literal scopes are not a substitute for semantic resource planning. Active/unknown claims stay occupied until their execution has actually ended or been explicitly reconciled. Readiness is not authority to dispatch, and a resource declaration is not permission to access it. The owner still chooses ready cards; no automatic scheduler/rebase/retry is implied.

## Acceptance that checks behavior

- Define observable success and meaningful failure paths. Test a violated contract, not only the implementation's own output or an arbitrary count of assertions.
- Preserve the intent of existing tests. Explain any changed/deleted expectation; do not hide failures with skips, relaxed comparisons or copied actual outputs.
- For state-sharing, isolation or order-sensitive changes, include focused independent/reversed/randomized runs where relevant. Do not require all tests in all orders for every card.
- Choose money/auth/data-safety checks relevant to the behavior: authorization, retries/idempotency, partial failure, concurrency, persistence. Review depth and targeted mutation follow impact and project policy.
- Documentation/research acceptance checks claim accuracy, source dates, references and usable instructions. Unsupported claims stay unverified; a heading count is not a proof.
- Distinguish expected output in the card from observed output in the report. Record baseline and dirty state so later results can be reproduced.

## Isolation and preservation

For Git parallel work, one card normally gets one worktree/branch created through the managed path. Non-Git stays serial with an explicit directory and local snapshots. The orchestrator may implement a card and arranges independent review when impact/policy requires it.

Hot files have one active writer; reserve them in the board and card. Worktrees do not isolate ports, services, databases or credentials. Record the concrete shared resource and coordination mechanism; do not infer a free lock from its age. Migration numbering and head topology follow the project's migration contract, not a universal one-revision rule.

A shared-resource card lists each already-authorized operation, backup/recovery evidence and restoration check. The card alone cannot expand policy. Retain backups until restoration is verified and retention permits cleanup. Interactive or privileged steps remain with an appropriately authorized operator; no automatic permission changes.

## Spikes and upstream branches

Spikes answer questions that affect architecture, within a timebox and explicit operations. Deliver findings with measured evidence, cited source evidence clearly distinguished, limitations, recommendation and restoration facts. Unrun experiments remain unverified. Keep product changes out unless separately scoped. Fold accepted findings into decisions and create follow-up cards.

For a card based on an unmerged branch, record the exact starting point and dependency. Before integration, reconcile with the upstream's final result and rerun the affected acceptance. Never silently reset or discard the downstream work.
