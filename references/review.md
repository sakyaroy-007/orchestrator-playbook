# Review, acceptance and integration

A worker's `done` or exit 0 is a report, not acceptance. Follow project `review` policy and the actual impact of the change. [Lifecycle](lifecycle.md) defines ownership; [dispatch](dispatch.md) defines managed verify/guard commands. Do not turn every reversible documentation change into a full-suite or independent-agent review.

## Produce review evidence

1. Record the reviewed baseline, current HEAD, branch/work directory, configuration revision and dirty/untracked state. Distinguish pre-existing changes from the card's patch; never erase dirty work to obtain a clean screenshot.
2. Read the full scoped diff and change note, including uncommitted delivery if commits were not authorized. Check each claimed update against the files.
3. Run the card's relevant acceptance commands against the actual result, with cwd, exit status, observed output and covered scope. If acceptance is stale, explain and revise it within authorized scope instead of inventing a pass. Run broader tests only when shared behavior or unresolved concerns justify them; honor required project checks.
4. Where shared state, test isolation or order dependencies matter, run affected tests alone or in reversed/randomized order. There is no universal requirement to reverse every test suite after every change.
5. Examine scope creep, bypassed failures, weakened assertions, expectations copied from outputs, secret residue and destructive defaults. Test counts alone do not establish coverage. Document/research cards need accurate claims and working references, not arbitrary section-count quotas.
6. For money/auth/isolation/data safety or comparable impact, inspect trust/transaction boundaries and relevant failure, retry, authorization, concurrency and idempotency paths. Use targeted mutation testing when it materially checks the oracle; isolate and restore mutations, and prove restoration. Not every feature has all of these behaviors.
7. Classify findings with location, trigger, actual/expected behavior and evidence. Mark untested concerns as unverified, not reproduced. Out-of-scope findings become separate cards or explicit decisions.

## Bind evidence to the result

For structured tasks, record acceptance through the runtime evidence protocol. An immutable receipt identifies the task/spec revision, requirements digest, relevant content fingerprint, verification attempt or explicitly declared manual source, conclusion and reviewer declaration when required. Include the actual evidence artifact and its digest. Do not replace an old receipt with a later verdict.

A passing verification attempt is usable only for the requirements and content it actually tested. The runtime records relevant content before/after verification; later code or relevant uncommitted changes make that result inapplicable. A pure mtime change does not change content. Inspect the scope: a fingerprint does not prove that omitted files, ignored outputs or untested behavior were covered. Missing/tampered artifacts and legacy note-only acceptance remain visibly unresolved. Configuration changes unrelated to a task's requirements do not automatically invalidate every task.

Manual review can be appropriate for a low-impact card. Record it as manual evidence against the actual content, not as an executed test. When independent review is required, identify the participant and implementation relationship and link the review to that same result. Cooperating identity declarations are not cryptographic identity or proof that model judgments are independent.

## Verdict and independence

- **Pass**: record why acceptance covers the scoped change and what remains unverified. Mark the task `verified` only with that evidence.
- **Fix, then review**: write a bounded review note from the template and continue the existing work after checking its current state.
- **Change approach**: explain the failed assumption, preserve current results and revise scope/worker/settings only within policy and user authority.

The orchestrator may implement a card. Use independent review for substantial self-authored work, higher-impact changes or unresolved uncertainty according to project policy. Give the reviewer specification and code, not your conclusions. It consumes an agent slot and needs an approved dispatch route. Reproduce/assess its findings rather than accepting them by status alone. If independent review is required but unavailable, report that gate as unmet.

## Integrate under project policy

Confirm current owner/epoch and the exact accepted baseline before shared mutation. Use `guard --action merge` with the configured integration branch and merge method. A `merge`, squash, rebase or fast-forward policy is a project choice; no global `--no-ff` mandate applies. Do not replace it with the reviewer's preference. For a non-Git project, record the serial file integration and local snapshot instead of a Git operation.

Begin a structured integration record for the selected participants/evidence and actual target baseline before the authorized integration work. After actual integration, run the required affected checks against the assembled result and finish its record with the corresponding verification. Long verification runs outside the shared mutation lock; final registration rechecks the target and evidence under the lock. The resulting commit or non-Git content must match what was tested. A target that advanced after verification cannot reuse that old pass.

Record already-merged code separately from overall acceptance. When A and B passed individually but their combination fails, retain the actual integration and failed evidence, then fix within scope; do not automatically reset work or mark the combination passing. Batch integration can validate the final assembly instead of mechanically rerunning every full suite after each merge. Membership/provenance declarations remain explicit: hashes and passing tests do not prove that arbitrary merge commands included every semantic change. Preserve unsupported squash/rebase proof gaps. Mark tasks integrated only with applicable integration evidence.

Update the board, task index, handoff and relevant decisions from real evidence while still owner. Commit those updates only when authorized. Push only when both permission and cadence permit it; local success and a documented unpushed commit are valid outcomes. Push does not authorize publication/deployment.

Cleanup is separate from acceptance. Respect retention and checks for dirty, untracked, ignored, unmerged, running, unknown and evidence-bearing work. Use the managed cleanup path only when safe. If a squash result cannot be proved integrated, retain its worktree for reconciliation. Legacy force flags cannot waive these checks.

## Rework note

Use `templates/review.md` for the verdict, reviewed baseline/config revision, actual commands/results, must-fix reproductions, unverified concerns, accepted scope and skipped checks. A review note may narrow a card; it cannot grant new permissions or override project policy. Follow configured retry limits; changing task IDs does not make repeated failures disappear.
