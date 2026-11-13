# Files and evidence for handoffs

Follow [lifecycle](lifecycle.md) for the actual ownership transition. Files explain the project; editing them cannot appoint an owner. Config paths override the example planning paths below.

## Sources of truth

| Location | Purpose |
|---|---|
| `.orchestrator/config.json` | Portable, versioned project goal, worker and action policy |
| Shared Git common directory runtime, or `.orchestrator/local/` without Git | Machine/session identity, epoch, config revision, owner, attempts and recovery snapshots |
| `.orchestrator/TEAM.md` | Readable roster and ownership observation with observation time/revision |
| `.orchestrator/PLAYBOOK.md` | Project-specific workflow, resource constraints and policy references |
| Configured plan/card/worker/handoff files | Intent, bounded scope, decisions, evidence and next steps |
| Task logs and change/review notes | Actual commands/results and independent acceptance |

Use a local ignore rule for runtime/recovery data. Linked worktrees must share state, not create one owner per worktree. Tracked TEAM.md, old takeover notes and lock age cannot arbitrate ownership. Keep existing legacy files on explicit adoption; they remain history, not v3 runtime state.

## TEAM.md and PLAYBOOK.md

TEAM records the human, observed holder **session ID** and client, epoch, config revision, date, previous handoff and worker IDs. A roster distinguishes executable discovery, verified options, authentication readiness and observed execution. Record each worker's own inherited defaults or explicit settings; a recommendation remains a proposal. Do not write credentials or copy private profiles into it.

PLAYBOOK points to config and records the project's approved dispatch channel, integration/retention choices, hot files, resource locks, test approach and red lines. Reuse the shared procedure rather than copying the whole skill. The runtime is authoritative when a summary disagrees; investigate the difference instead of changing the holder line to win it.

## Outgoing handoff evidence

Before calling `handoff`, record:

- Goal, completed scope, active wave and the exact next task recommendation.
- Baseline HEAD/branch/worktrees (or non-Git description), dirty/untracked/ignored facts, unpushed commits and local recovery location. Git-ignored untracked files are not checkpointed; explicitly archive required ignored evidence within authorized scope into a covered location first. An unmerged index or dirty submodule is rejected; special files and size/read failures can also leave partial recovery data. Preserve and report it, not as complete. Save the needed contents of every conflict stage and resolve conflicts before normal handoff; never erase stage contents just to pass checkpoint validation. A path alone does not prove snapshot completeness.
- Every reserved/running/reported/unknown task: ID, attempt, worker, branch/worktree, last commit, command, log, process identity if known and remaining work.
- Verification: command, cwd, baseline, exit status, actual output, scope covered, failed/skipped checks and gaps. Expected output belongs in acceptance, not as a substitute for actual results.
- Shared resources, background services, lock ownership evidence, open decisions and settled decisions that must not be asked again.
- Project-relevant memory needed by the next session, excluding secrets and unrelated personal information.

Write intention and observed facts before preparing; do not prematurely mark the new owner active. After success, return handoff ID/target and stop managed writes. The ID and complete checkpoint live in authoritative runtime state; do not alter the checkpointed files merely to insert that new ID. A failed/incomplete snapshot is not a prepared handoff. Commit/push is a project policy choice, not a mandatory handoff step.

## Incoming checklist

1. Read project instructions, configured handoff, plan, board, decision ledger, worker rules and config.
2. Read runtime `status`/`doctor`, then inspect live baseline, logs, dirty work and process identity. Unknown is not absent. Do not automatically relaunch services, workers or tests.
3. Claim through the prepared takeover or explicit recovery procedure in lifecycle. User invocation for a prepared handoff does not need a repeated appointment question. Recovery needs user-directed stopping/replacement; keep tasks and make/reconcile a recovery checkpoint first.
4. After success, record the new owner/epoch and capability differences in readable summaries. Keep late worker results and reconcile them before dispatching again.
5. Report what is ready, running, uncertain, blocked and intentionally retained. Do not claim native-client conversation resume or cross-machine locking.

## Conflict and preservation

Conflicting sessions stop managed mutations; runtime owner/epoch is the authority. Nobody acquires the role by editing TEAM.md, deleting a lock, copying an ID or waiting long enough. The OS lock protects cooperating managed operations on one machine, not raw shell/editor writes.

Cleanup depends on policy **and** evidence: dirty, untracked, ignored, unmerged, running, unknown or evidence-bearing work is retained. Legacy force options do not bypass v3 safety checks. If a squash merge prevents the tool from proving integration, keep the worktree for explicit reconciliation. Report retained work as retained, not as a failed handoff.
