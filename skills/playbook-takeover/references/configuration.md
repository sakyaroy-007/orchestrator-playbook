# Project configuration

Read [lifecycle](lifecycle.md) for path resolution, identity and ownership. `.orchestrator/config.json` is portable policy; it contains no credentials or private host configuration. Runtime state, machine/session identity, epoch, configuration revision, process records and local recovery copies live in the shared Git common directory, or `.orchestrator/local/` for non-Git, with a local ignore rule. Linked worktrees share one runtime. TEAM.md explains the policy but does not override it.

## Discover, clarify the goal, then collect missing settings

Run read-only `discover` before proposing a roster or asking setup questions. Read existing instructions, config, plans and conversation decisions. A bare `playbook-start` invocation needs no prepared project brief. If the goal is missing or vague, clarify it before presenting a complete setup recommendation:

- For an empty project, begin with the intended user and problem or desired result. Ask one to three consequential questions per round; use concrete examples or a recommended option when that helps the user decide. Do not invent a goal to fill the summary.
- Follow up only where an answer changes the first milestone: essential behavior, constraints, exclusions or how success will be checked. Recommend technical choices from available evidence; do not require the user to design the architecture or supply test commands.
- For a clear goal, ask only about actual gaps. For an existing project, read its plans and progress first, then resolve conflicting or outdated decisions and the next outcome instead of restarting a product interview.
- Stop when an agreed stage has a useful outcome, bounded scope, exclusions and observable acceptance. Save that brief in the configured plan and first task; carry unresolved nonblocking choices forward. If feasibility remains unknown, agree a bounded exploration task and its expected evidence instead of demanding a complete specification.

Then present one concrete recommendation containing the actual target, goal, reused files, minimal/standard foundation profile, workers/settings, limits and action permissions. Mark which values are already settled and which are proposed. Accepting this summary resolves its explicit choices; do not ask again about choices already accepted. The following four groups classify unresolved settings; they are not four mandatory questionnaires or a limit that forces an invented answer. Do not ask for an appointment already made by start.

1. **Outcome and boundaries.** Confirm the checkable stage goal, scope, exclusions and acceptance. Recommend the smallest useful first milestone based on the inspected project. For an existing project, confirm which existing plan/path to reuse and whether the user requested adoption of legacy state. Preserve existing files.
2. **Allowed workers and local work.** Recommend using only explicitly selected, available clients or manual work. Resolve dispatch, local verification (`permissions.verify`) and worktree creation (`permissions.worktree-create`) together as the user's local development/test/dispatch choice; save each permission once instead of asking at every command. All default to `ask` until authorized. Propose at most two agent jobs and one heavy verification job to start, adjusted to actual resources and review capacity; non-Git work stays serial. Confirm timeout/retry constraints and any cost boundary. The limits are job/attempt controls, not a hard monetary budget. A roster is not proof of permission or login.
3. **Model, effort and profile policy.** Recommend `inherit` for each worker's **own** model and effort, independent of the orchestrator, and preserve its profile where the client has a default. DSH requires an explicit profile: obtain the existing noninteractive profile name or propose `headless` explicitly for the user to choose; do not silently select it. Model/effort can inherit that chosen profile. Offer `recommend` for a proposal to resolve before dispatch, or `fixed` for an explicitly chosen supported value. Reuse settled values and explain unsupported mappings. Do not copy a profile merely because two workers have the same client.
4. **Git and retention.** Confirm each of commit, merge, push and cleanup permissions, the integration branch, merge method, push cadence and retention. Recommend authorized routine local commit/merge, manual push and retaining worktrees until verification/evidence checks pass; without approval, leave the action `ask` (or an existing `deny`). No blanket authorization follows from a Git repository existing. For non-Git, recommend serial local snapshots and no Git operations.

An explicit acceptance of a concrete recommendation resolves that choice; record it once and continue. Existing authorization persists across cards and sessions within its scope. Unresolved settings stay `ask`, denied actions stay `deny`; do not interpret silence as `allow`. Workflow metadata needed for an explicitly invoked lifecycle action does not need a duplicate permission question. Push approval does not grant publishing or deployment approval.

## Version 1 configuration

Write the agreed complete object to a temporary proposal file, set `PLAYBOOK_CONFIG` to that path, then pass it to `init` or `configure`. The following is a valid conservative baseline, **not a statement that these choices were approved**. Replace the goal/branch/paths with actual agreed values; defaults may be filled by the runtime.

```json
{
  "schema_version": 1,
  "goal": "Deliver the agreed, checkable first milestone",
  "workers": [],
  "limits": {"agents": 2, "heavy_jobs": 1, "timeout_seconds": 7200, "max_attempts": 2},
  "permissions": {"dispatch": "ask", "verify": "ask", "worktree-create": "ask", "commit": "ask", "merge": "ask", "push": "ask", "cleanup": "ask"},
  "git": {"integration_branch": "main", "merge_method": "merge", "push_cadence": "manual", "cleanup_mode": "retain"},
  "review": {"level": "adaptive"},
  "paths": {"plan": "docs/plan/README.md", "worker": "docs/plan/WORKER.md", "cards": "docs/plan/tasks", "handoff": "HANDOFF.md"}
}
```

Use relative project paths for portable configuration. Follow the installed runtime's validation for supported enum values and bounds; a setting rejected by validation has not been applied. Never repair a rejection by silently dropping the user's requirement. Preserve existing policies and custom paths when updating only one choice.

The optional `runtime_api: 2` policy marker activates the extended cooperation protocol. New initialization records it; an existing project activates it through an explicit owner configuration update, for example a patch containing `{"runtime_api": 2}`. Reading an older policy does not insert this field or change its stored hash. Once activated, replacement/recovery must not silently remove the requirement. Older runtimes reject this unknown field, exposing incompatibility instead of running without the new constraints. Schema version and runtime API are different concepts. Inspect `version`/`doctor` and preserve differing project copies; activation is not an automatic source upgrade.

Optional review booleans `allow_manual` and `independent` default to false when absent. `allow_manual:true` permits explicitly labelled manual acceptance artifacts; it does not make a note equivalent to a successful test. `independent:true` requires cooperating reviewer declarations distinct from recorded implementation participants. A task may strengthen independent review, not weaken project policy. These declarations are not cryptographic identity. Existing policies retain their hash when these optional fields are absent. See [structured work and acceptance](work-protocol.md) for receipt and integration applicability.

Worker records have a unique `id`, a `client` from `claude`, `codex`, `dsh`, `hermes`, `manual`, and model/effort objects such as `{"mode":"inherit"}`. A `fixed` or `recommend` object also supplies its selected/proposed `value`. Optional `profile` and per-invocation `args` (an array of strings) must use the installed adapter's verified options. The adapter consumes args/profile/model/effort; unknown mappings block the launch instead of being dropped. Multiple records may use the same client but have different identities. Do not store credentials, authentication dumps or private machine settings in these records.

```json
{
  "id": "implementation",
  "client": "codex",
  "model": {"mode": "inherit"},
  "effort": {"mode": "inherit"},
  "args": []
}
```

| Mode | Meaning | Before launch |
|---|---|---|
| `inherit` | Keep this worker's own configured default | Do not copy the orchestrator's model or invent an override |
| `recommend` | A proposed model/effort value | Resolve the proposal within existing user authority; it is not yet applied |
| `fixed` | An explicit supported per-invocation value | Verify the adapter mapping and report unsupported values as a launch blocker |

Model and effort modes are independent. `profile` is a string: it may be absent for clients that have their own default, but managed DSH requires it because its launcher has no default profile. A missing DSH profile blocks launch before any model call. Use dedicated fields for model/effort/profile instead of conflicting `args` overrides. The example roster entry is not authorization to launch it. Do not invent equivalence among providers' reasoning levels, turn recommendations into flags, or alter global files to make a launch work.

The current validating dispatcher passes fixed models through the existing `-m` adapter. After checking the installed client's help, it supports Claude `--effort`, Codex `--config model_reasoning_effort=...`, and a one-run DSH `agent-default-model.reasoningEffort` patch. Fixed Hermes effort is unsupported. Explicit profiles are supported for Codex and DSH; Claude/Hermes profile overrides are rejected. These are argument mappings, not proof of login, model availability or effective reasoning behavior. Unsupported options and unresolved `recommend` values block launch. DSH's profile must be explicitly selected; inheritance preserves the chosen profile's model/effort and does not automatically select legacy `headless`.

Supported Git values are `merge|squash|rebase|ff-only` for merge method, `manual|after-merge|stage|never` for cadence, and `retain|after-merge|manual` for cleanup. The current managed push path refuses `manual` and `never`; configure an authorized `stage` or `after-merge` cadence before a managed push. `retain` blocks cleanup even with cleanup permission set to allow.

## Discovery, capability and authentication are separate

- **Discovery** finds project/Git facts and known executables. It does not run an LLM, read secrets, install software, test login or modify global configuration.
- **Capability evidence** comes from the installed client's documented/help options and a verified adapter. Record the version, inspected option and supported mapping. Reading help does not prove that a real request will succeed.
- **Authentication/readiness** requires an authorized check appropriate to that client or evidence from an authorized run. Unknown stays unknown; never inspect secret values or start a paid job merely to make discovery look complete.
- **Observed execution** includes the actual command, worker ID, cwd, reported model/effort if available, log and exit status. If the client does not report a setting, say the effective value is unverified. An executable on PATH or a recommendation in TEAM.md is not evidence that it ran.

## Apply and verify

For initialization, use the start procedure in [lifecycle](lifecycle.md). For “change this setting, keep everything else”, write only the agreed change into a temporary JSON patch, e.g. `{"limits":{"agents":3}}`, then use the current owner:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" configure --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --patch "$PLAYBOOK_CONFIG"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
```

Patch objects are merged into the current canonical policy under the lock; omitted fields remain unchanged, and arrays replace only when explicitly supplied. Invalid fields or values reject the update. Report returned changed paths and revision, not just the proposed object. For an intentional complete policy replacement use mutually exclusive `--config FILE` instead; its omitted ordinary fields retain the documented defaulting semantics. Never submit a partial object through full replacement to satisfy “other settings unchanged”.

The runtime validates policy and atomically replaces each file, retaining ownership/tasks and recording a configuration revision. The config and runtime state are two files: interruption can leave them inconsistent, so do not describe the pair as one atomic transaction. Report the stored revision and effective choices from successful output, plus pending recommendations and unsupported settings. Do not treat a written proposal as applied configuration. A new session cannot use configure as takeover. Prepared handoffs must not be invalidated by uncoordinated edits.

For an interrupted/corrupt two-file configure update, follow the explicit recovery procedure in [lifecycle](lifecycle.md). After user-directed stopping/replacement and the user's review of the complete configuration, an incoming session may use `takeover --recover --previous-stopped --config FILE`. The runtime first privately preserves the original config and old state as evidence, records the repaired configuration revision, then checkpoints and takes over. Keep that evidence and report a checkpoint failure as a blocked takeover, even if repair was already recorded. Recovery without `--config` stays strict; ordinary prepared takeover does not allow a config override. A failed prepared validation is not permission for silent policy repair.

## Permission and preservation checks

- `allow` permits an action within the agreed scope and current policy; `ask` requires a real unresolved choice; `deny` prohibits it. Do not repeatedly ask for routine actions already approved, or bypass a denied action through raw shell.
- `guard` holds the shared OS lock over a short owner/policy check and mutation. Its `scaffold` action checks owner/epoch/active state for lifecycle metadata; explicit start metadata needs no extra permission grant or new config permission field. Configured `init-plan.sh` writes use it; `--dry-run` stays read-only. `run` reserves a unique attempt and resource slot before launch. See [dispatch](dispatch.md). They protect cooperating operations on one machine, not arbitrary tools or a forged environment variable.
- Concurrency follows `limits.agents` for worker/reviewer jobs and `limits.heavy_jobs` for verification jobs. Interrupted reserved/unknown jobs remain visible and need reconciliation before another attempt. Honor timeouts and `max_attempts`, counted per task and action so dispatch and subsequent verify keep distinct attempt budgets; do not reset task IDs just to escape limits.
- Merge method, push cadence and cleanup retention still apply even when permissions are `allow`. Cleanup also needs proof of integration and checks for dirty, untracked, ignored, running, unknown and evidence-bearing work. Legacy force flags cannot bypass v3 checks; retain a squash-integrated branch when the tool cannot prove integration.
- Non-Git projects use serial operations and local snapshots. Do not create branches, commits or remotes as an incidental setup step.
- No automatic client installation, host reconfiguration, upgrade, publication or deployment is included. Unsupported requested settings block the launch; they are not silently ignored.
