# Lifecycle and shared operating rules

This is the common procedure for all five explicit entries. Read [configuration](configuration.md) before initialization or policy changes. Entry files are routes into this procedure, not separate sets of authority.

## Locate the skill and project

Resolve `PLAYBOOK_SKILL_DIR` to the directory containing the **loaded** `SKILL.md`, using the installation information supplied by the host. Resolve `PLAYBOOK_PROJECT` to the user's target project, independent of the current working directory. Quote both paths in every command. The examples assume those two variables have already been set to these resolved paths; do not copy placeholder paths literally or guess a global installation location.

Use the host's available file-reading, file-writing and command-execution facilities; no particular client's tool names are required. Read project instructions before changing files. If the target is ambiguous, perform available read-only inspection and resolve the target before mutation. Never initialize the skill repository merely because it is the current directory.

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" discover --project "$PLAYBOOK_PROJECT"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" --help
```

Commands return JSON on success. Check the exit status and parse that JSON before using IDs or claiming success. Failures need an actionable explanation; do not retry a mutation by changing identity or bypassing its checks. Use `ACTION --help` for the installed version's actual flags.

## Authority, identity and evidence

- An explicit user invocation of `playbook-start` appoints **this session**, when there is no incumbent. Do not ask for the same appointment again. This is not blanket dispatch, Git, spending or publishing permission.
- `playbook`, status, diagnosis and reading a file do not appoint anyone. Workers stay within their assigned card; they do not initialize, dispatch, change shared policy or claim ownership.
- Create a fresh identity with `session-id` for a new session. Keep the returned ID in that session's context, together with the current epoch. A continuing session may reuse its own recorded identity after compaction. Never copy an incumbent's ID from `status` to impersonate it; identical client/model names do not mean identical sessions.
- Runtime state under the shared Git common directory (or `.orchestrator/local/` without Git) is authoritative for owner, epoch and recorded attempts. `.orchestrator/config.json` is the policy source. TEAM.md and the board are readable summaries, not locks or appointment grants.
- A prepared handoff plus the user's explicit takeover invocation authorizes the designated new session to claim. Do not repeat that appointment question. An unprepared replacement requires user-directed stopping/replacement and reconciliation; elapsed time, a missing notification or an old lock is not authority.
- Preserve the user's dirty, untracked and unmerged work. Record observed facts separately from worker claims, proposed settings and unknowns. A successful child process is only `reported`, not accepted.

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" session-id --project "$PLAYBOOK_PROJECT"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
```

Set `PLAYBOOK_SESSION` from the new identity's JSON; set `PLAYBOOK_EPOCH` from a successful ownership operation. `status` includes the full config in `policy`, plus `config_path` and `project_root`; use those returned locations rather than guessing a worktree-local policy file. If ownership cannot be established, remain read-only and explain the conflict.

## Start: inspect, configure, initialize, plan

1. Run `discover` first. Inspect project instructions, existing plans, Git/worktrees and legacy `.orchestrator` files without modifying them. If the requested new directory does not yet exist, report that fact and inspect the known parent read-only; after resolving the user's target/settings, create that target directory before init. Do not silently substitute another project. Discovery is executable inventory, not a model invocation, login check or capability test.
2. If configured, read `status` and `doctor`. An existing holder is not overwritten: the same session continues through resume; another session requires takeover. Existing unconfigured files require an explicit user-requested import before `--adopt`. Preserve those files even on adoption.
3. Follow the four compact question groups in [configuration](configuration.md). Reuse settled conversation and project decisions. Recommend a small policy, obtain missing choices, and write a complete version 1 JSON proposal to a temporary file outside the project. Set `PLAYBOOK_CONFIG` to that file. Do not write global client settings or credentials.
4. Obtain a fresh session ID if needed. Set `PLAYBOOK_CLIENT` to this session's client label and `PLAYBOOK_GOAL` to the agreed, checkable stage outcome. Initialize for real:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" init --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --goal "$PLAYBOOK_GOAL" --config "$PLAYBOOK_CONFIG"
   ```

   Add `--adopt` only for the user-requested existing-project import. Initialization is idempotent for the same owner and rejects conflicts. The target directory must already exist when init runs; create a requested new project directory first. It need not be a Git repository, and init does not run `git init`. Converting an initialized non-Git project to Git is not an automatic migration: stop on the layout conflict and preserve the existing owner/state; never initialize a second owner.
5. Read `status`, retain the returned owner/epoch/revision, and confirm the stored goal and policy. Do not report a proposal as initialized if init failed. Use [bootstrap](bootstrap.md) and the foundation helper to check then create only missing README/planning/runtime files at configured paths. Select minimal or standard, preserve existing AGENTS.md, handoff, plans and code, and report conflicts instead of overwriting them. Apply enters `guard --action scaffold` with owner/epoch/active checks; explicit start metadata needs no separate permission choice. Complete the first card and its structured spec from actual facts, then inspect readiness; a generated draft is not dispatch-ready. Legacy `init-plan.sh --dry-run` remains available for the default Git layout.
6. Plan the first small task against the real baseline, with scope, acceptance and gaps. If there is an actual collaboration blocker, make that the first card; do not force a foundations wave on a project already ready. Continue within approved policy, or report the concrete missing dispatch choice. Start does not automatically launch a worker.

## Resume: same owner, no replay

Read instructions, configuration, handoff, board and settled decisions; compare them with `status` and `doctor`. Use only this session's previously retained identity and the last known epoch:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" resume --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
```

Resume may reactivate the same owner's paused state. It does not take another owner's role, replay worker launches, rerun tests, commit or push. Inspect the changed baseline and every reserved/running/unknown task before planning new work. Missing logs are not evidence that a task never ran. If ownership or epoch conflicts, stop managed mutations and explain the takeover route; never rewrite TEAM.md to resolve the conflict.

## Checkpoint, pause and handoff

First reconcile task records with available logs, branches, dirty files and process identity. Avoid racing a snapshot with shared writes; ask cooperating workers to reach a stable point when possible. Pause does not kill them. Record anything still running or uncertain, plus unpushed commits, resources, open decisions and next steps in the configured handoff document. Project-relevant memory belongs in project files, without copying private credentials or unrelated personal notes.

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" checkpoint --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" pause --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
```

These are alternative operations as needed, not a mandatory command sequence. Pause first persists `paused` under the ownership lock, then attempts its checkpoint. If capture fails, report the nonzero result and the incomplete recovery point; new managed work remains paused, while existing workers and partial evidence are retained. A storage failure that prevented persisting the pause is not a successful pause. Checkpoint captures actual HEAD/worktrees, covered dirty and untracked source recovery copies, tasks and config without commit/push/reset. Git-ignored untracked files are excluded: explicitly archive required ignored recovery evidence into a documented, covered location before checkpoint, within its authorized content scope. Do not assume an ignored file was saved; cleanup still refuses ignored work. An unmerged index or dirty submodule is explicitly rejected; unsupported special files, oversized, unreadable or changing content can also fail the checkpoint and leave partial recovery data. Preserve that partial data, report the gap and do not announce a complete recovery point or prepared handoff. For index conflicts, first preserve every needed stage's content and resolve the conflicts before normal handoff; never discard stage contents merely to pass the check. Keep local snapshots outside normal publication.

For a handoff, finish the outgoing documentation before preparing it, then run:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" handoff --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
```

If a specific incoming **session ID** is known, append `--to "$PLAYBOOK_NEXT_SESSION"`; a client/model label is not a target session. The command makes a complete checkpoint and enters `prepared` state. On failure, do not announce a prepared handoff. On success, return its handoff ID and target to the user and stop managed mutations/dispatch, including further shared-document edits. Repeating the same handoff is idempotent. The old owner remains the recorded outgoing owner until takeover succeeds; do not preassign the new owner in TEAM.md. Commit/push is governed by policy and is not a prerequisite for local handoff.

After preparation, provide a copyable incoming instruction with the actual project path and a short account of retained work. The incoming session obtains the handoff ID from status; the user need not transcribe runtime IDs. Do not claim that preparation means a new holder has already taken over.

### Withdraw a prepared handoff

If the user changes plans before reception, the recorded outgoing owner can explicitly withdraw:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" handoff --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --cancel
```

Withdrawal invalidates the prepared ID, retains its history/checkpoint, and returns to paused. Resume or prepare a new handoff as requested. The lock resolves withdrawal/takeover races; after takeover, the former owner cannot withdraw it. Withdrawal is not a way to take another owner's identity or discard changes made since the snapshot.

### Cancel one managed execution

Pause prevents new work; it does not stop existing workers. For an explicit cancellation, select the actual attempt from status, state the reason, and request it as the current owner in active or paused mode:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" cancel --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --attempt "$PLAYBOOK_ATTEMPT" --reason "$PLAYBOOK_REASON"
```

The supervisor of that attempt observes the request and stops only its own process group. A recorded request is not yet terminal acknowledgement: inspect the subsequent result before describing processes as stopped or resources as released. Preserve logs, files, attempt counts and natural completion that wins a cancellation race. A lost supervisor/orphan remains unknown and needs explicit reconciliation; never guess a PID, kill by name or free a reservation based on elapsed time.

## Takeover: prepared or explicit recovery

1. Read instructions, config, handoff, board and decision ledger. Run read-only `status` and `doctor`. Inspect recorded attempts, logs, branches and uncommitted work. Do not start services or rerun acceptance just to take over.
2. Use this incoming session's fresh ID. For a prepared handoff, obtain the ID from authoritative state or the outgoing result, set `PLAYBOOK_HANDOFF`, and run:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --handoff "$PLAYBOOK_HANDOFF"
   ```

   The runtime validates target, machine, revision, baseline and recovery contents under the shared lock, then increments epoch and changes owner. A changed baseline must remain visible; reconcile it rather than bypassing validation. A repeated successful claim by the same owner is idempotent.
3. Without a prepared handoff, establish the user's explicit replacement instruction and that the previous session has been stopped from further work. Check orphaned and in-flight tasks, preserve their results and make/reconcile a recovery checkpoint through the recovery path. Then use:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --recover --previous-stopped
   ```

   `--previous-stopped` records that attestation; it is not proof that raw external writes are fenced. Do not set it from age, a timeout or your own guess. If the required instruction or evidence is missing, report the specific blocker while remaining read-only. Do not delete locks or runtime state.

   Only when an interrupted/corrupt two-file `configure` update requires configuration repair, use the explicit recovery variant after the user has reviewed the complete replacement configuration. Set `PLAYBOOK_CONFIG` to that reviewed JSON file outside the project, rather than overwriting the existing config by hand:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --recover --previous-stopped --config "$PLAYBOOK_CONFIG"
   ```

   The runtime privately preserves the original config and old state as evidence before repair, records the configuration revision, then checkpoints and takes over. Report the evidence location and revision; a failed checkpoint still blocks takeover, even if configuration repair was recorded. Recovery without `--config` remains strict. Ordinary prepared takeover does not support a config override. Failed prepared validation does not authorize silently changing policy or switching to this repair path; its explicit recovery and reviewed-config prerequisites still apply.
4. After success, retain the new epoch, reconcile documents with live state and record verified capability differences. Review returned work before new dispatch. Late results from the previous epoch remain evidence and must not be discarded or automatically accepted. Report ownership, baseline changes, task uncertainties and the next permitted step.

## Working loop and policy enforcement

Review returned work before dispatching more. Choose a card with satisfied dependencies, explicit file scope, a known baseline and external acceptance criteria; see [cards](cards.md), [dispatch](dispatch.md) and [review](review.md). The orchestrator may implement a suitable card; choose independent review according to impact and project policy. Reviewer jobs consume agent slots too. Non-Git projects operate serially with local recovery snapshots; they gain no Git actions.

Use `task` to record a reconciled fact, not to wish a task away:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" task --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --id "$PLAYBOOK_TASK" --state blocked --note "$PLAYBOOK_NOTE"
```

States are `reserved`, `running`, `reported`, `verified`, `integrated`, `blocked`, `unknown`. Retain attempts, worktree, command, logs and evidence. For runtime API 2, register the spec, inspect readiness, finish implementation, then schedule heavy verification and record applicable evidence before `verified`. Independent review follows the project/task requirement. Use integration begin/associated assembly verification/finish for `integrated`; a note is not sufficient. See the exact [structured work commands](work-protocol.md). Legacy note-only records stay distinguishable. Review/integration methods, concurrency, retries, commit, merge, push cadence and cleanup follow configuration.

Short shared mutations use `guard`; long worker/reviewer/test jobs use `run`. Both verify owner and epoch. See [dispatch](dispatch.md) for runnable examples. Permission-controlled actions marked deny or `ask` must not execute; resolve a real user choice through configure, without asking again for already authorized routine actions. The `scaffold` action checks owner/epoch/active state for lifecycle metadata without an extra permission grant; it is not permission for Git actions, implementation or setup hooks. In v3, `wt.sh new` only creates under guard and reports an executable setup hook as pending. After guard returns, run the approved setup procedure: a hook that calls managed `run` must not be wrapped in another `run`; otherwise use managed verification. Verify setup before implementation dispatch. `PLAYBOOK_GUARDED=1` is set only in the guarded child for cooperating adapters; do not set it manually as a bypass.

The first version coordinates cooperating sessions on one POSIX machine. Its OS lock covers managed operations, not arbitrary editor/shell actions. There is no distributed arbitration, automatic migration, automatic publication, native-client conversation resume or guaranteed hard money budget. Never claim a model/profile/effort was applied without verified adapter support and evidence.

## Report and close

Report what changed, exact commands and actual outcomes, preserved work, skipped/blocked steps and remaining gaps. Record baseline, dirty state, scope and evidence location so a later session can verify them. Update the board and handoff while still owner; checkpoint or pause as appropriate. Retained worktrees and unpushed commits can be intentional policy outcomes. Cleanup must preserve dirty, unmerged, running, unknown and evidence-bearing work.

Unconfigured v2 shell operations remain available but are outside v3 ownership, checkpoint and managed-limit guarantees. Adopt explicitly before claiming v3 protection; do not silently migrate a legacy project.
