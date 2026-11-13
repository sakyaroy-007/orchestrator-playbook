# v3 next iteration — implementation and acceptance contract

Status: implemented and locally validated. The [development validation results](v3-next-validation.md) preserve the pre-release checks and installation evidence; [release validation](v3-release-validation.md) records the final 3.0.0 preparation. Publication is recorded by the repository's versioned releases. This extends `v3-implementation.md`; it is not permission to initialize this skill repository as a managed project, publish, or call live model services.

## Authorized scope

1. Five deferred cleanups: per-verification recovery blob hash reuse; remove the redundant ordinary checkpoint state save; per-dispatch CLI help reuse; simplify adapter checks of canonical policy and remove dead `enabled` filtering; centralize outstanding-attempt predicates.
2. Pause persists the stop before checkpointing; an incomplete checkpoint does not resume dispatch. Explicit withdrawal of a prepared handoff invalidates its ID, preserves evidence, returns to paused, and races safely with takeover.
3. Separate implementation/light checks from owner-scheduled heavy verification. Reuse task IDs and attempt accounting; do not nest managed verification inside the same active dispatch/worktree.
4. A consistent, state-aware `playbook` interaction: project, state, blockers, recommended action, compact alternatives. Preserve the five entries. Native choice UI is optional; numbered text is the portable fallback. Bare invocation remains read-only. Discover reports both requested and canonical paths.
5. Explicit partial configuration updates that preserve unrelated settings and authorization. Full replacement remains available.
6. Structured task requirements, relevant content scopes, upstream evidence/dependencies and exclusive resources, with read-only readiness and lock-protected checks before dispatch.
7. Append-only acceptance evidence bound to task requirements and actual content, including relevant uncommitted changes. Manual evidence is permitted when project review policy permits it. Historical note-only conclusions remain visibly unverified by the new evidence protocol.
8. Integration records bind participants and their evidence to the actual integrated target and its verification. Code already merged is a fact separate from a passing assembled result. No automatic merge, push or cleanup authorization.
9. Cancellation by attempt ID: the current owner requests, the live supervisor stops only its own process group, terminal acknowledgement releases reservations. Lost supervisors remain unknown and need reconciliation. Cancellation is distinct from pause.
10. New-project foundations, existing-project adoption, and read-only check/create-only repair of missing collaboration files. Include a project-root README; preserve existing content and honor configured paths, Git and non-Git projects.
11. CI runs existing/new offline regressions and generated-bundle drift checks. Runtime/package version, source hashes and project-copy diagnostics are observable, without automatic upgrade.
12. An offline end-to-end pilot exercises the actual assembled scripts with fake workers, implementation/verification stages, structured evidence, integration and handoff. Provide a concrete opt-in live-client pilot recipe and measurement fields. A live paid pilot is not part of automated tests and needs a separately settled invocation scope/budget.

Out of scope remains automatic multi-machine arbitration, native chat transfer, automatic model routing, hard monetary caps, global client changes, automatic source upgrades, publication and deployment. Do not modify unrelated projects.

## Compatibility and package layout

Keep Python 3.9+ standard-library and POSIX support. Keep config/state schema 1 readable. A new optional policy field `runtime_api: 2` may gate the new cooperation protocol: old runtimes reject that unknown policy field rather than silently ignoring new constraints. Do not insert new default fields while reading an old policy, which would invalidate its stored hash. New initialization can record API 2; existing projects explicitly activate it via owner configuration, and may not silently downgrade once activated. Full replacement and reviewed recovery must preserve an already-required API marker.

Expose `version` without requiring an initialized project. Return package version `3.0.0`, runtime API, state/config schema, capability names, executing runtime path, and deterministic hashes of required runtime files. `doctor` compares the running bundle, any project copies and a project runtime manifest when present. Distinguish matching, differing, missing and unknown provenance. No file repair occurs during diagnosis. Keep development/release status explicit.

The runtime implementation may split cooperative task/evidence logic into a self-contained sibling `scripts/playbook_work.py`, loaded by an explicit path so Python `-I` remains supported. Its author owns that module and its tests. If added, it becomes a required generated and project-copied dependency. A separate `scripts/playbook-foundation.py` implements the foundation helper. Update the explicit generator allowlist and isolated-copy tests for every added dependency; include the new `PROJECT-README.md` template and both `references/work-protocol.md` / `.zh.md`. Never rely on the repository or sibling installed skills at execution time. Legacy `init-plan.sh` also copies `playbook_work.py` and names it in its staging hint.

## Core lifecycle interfaces

Preserve existing interfaces and JSON outputs, adding fields compatibly where possible.

- `configure --session ID --epoch N (--config FILE | --patch FILE)`: mutually exclusive full replacement or recursive object patch. Only explicitly supplied keys change in patch mode; arrays replace only when supplied; reject unknown fields/null/unvalidated data. Hold the lock across read, merge, validation and writes. Return actual changed paths and the new revision. Preserve the existing explicit two-file recovery path.
- `handoff --session ID --epoch N --cancel`: mutually exclusive with `--to`; only the current outgoing owner in prepared state can withdraw. Retain the prior record in history, invalidate its ID, transition to paused, and preserve snapshots. A concurrent successful takeover defeats withdrawal. Repeated withdrawal should have a clear idempotent result.
- `pause`: persist paused before attempting its checkpoint. A snapshot error stays a nonzero error with paused state and an explicit incomplete-recovery record. Existing workers are not killed.
- `cancel --session ID --epoch N --attempt ID --reason TEXT`: valid for current owner in active or paused state. Persist a cancellation request rather than signalling a guessed PID from the requester. The live supervising run loop observes it and uses its own process/group handle. Preserve output, cancellation reason and attempt count; do not release resources before terminal acknowledgement. Natural exit/cancel races and repeated requests must be deterministic. Unknown/orphan attempts cannot be declared stopped.
- `discover`: include `requested_project` in addition to canonical project facts. Skill interaction resolves conflicting user intent before initializing an enclosing repository.
- Per-call hash caches must not survive subsequent checkpoint verification calls or conceal a later mutation. Existing bounded capture and tamper checks stay in place.

## Task and evidence protocol

The runtime owner finalizes exact JSON/CLI shapes and documents them here before downstream integration. Use a small protocol, not an automatic scheduler.

- Extend `task` with a structured `--spec FILE` (state defaults to reserved for a new spec if omitted); preserve ordinary reconciliation. A spec has a requirements/acceptance definition, a nonempty list of relative relevant content paths, upstream references with explicit contract-only versus integrated requirements, exclusive resource names, and any required independent-review declaration. Requirements get a deterministic digest/revision. Changes preserve history and invalidate only affected acceptance. Owner policy cannot be weakened by a task.
- Expose `readiness --task ID` as read-only. Before launch, recheck dependencies and exclusive claims while holding the existing project lock. Treat active and unknown outstanding attempts/manual reservations conservatively. Conflicting resource names use a shared project namespace across worktrees; conflicting content scopes can be reported alongside required explicit exclusive claims. No inferred automatic rebase, task dispatch or retry.
- Snapshot the spec revision and dependencies on each attempt. Record deterministic scoped content fingerprints for verification before and after execution. Ignore pure mtime changes, but include relevant bytes, modes, deletions and symlink identity without following paths outside the project. Apply bounded I/O and explicitly reject unsupported/unstable inputs. Do not read ignored secrets or generated caches merely because a broad scope was chosen; report excluded evidence accurately.
- An `evidence` operation appends an immutable receipt that names task/spec, content, source attempt or explicitly declared manual evidence, result and reviewer identity/role when required. Machine evidence must match an actual completed successful attempt and its tested content; it must not be rebound to later content at acceptance time. Hash referenced artifacts. Independent-review checks concern cooperating declarations and provenance, not cryptographic identity or proof of model independence.
- New structured tasks require applicable structured evidence for verified/integrated transitions. Legacy note-only history remains readable and explicitly distinguished. Keep all old evidence after changes and expose stale/missing/tampered evidence rather than overwriting it.
- Provide integration begin/finish/status operations or an equivalently explicit protocol. Begin records participants, accepted evidence and the actual target baseline; finish checks a successful verification of the actual resulting content/target, plus unchanged requirements/dependencies. Long verification stays outside the shared mutation lock; finish rechecks under it. Record actual merge facts separately from acceptance. A target change after verification makes that result inapplicable. Support batch integration and relevant verification scopes.
- Keep integration membership/provenance declarations explicit. Do not claim that a version/hash check proves arbitrary merge commands included every semantic change. Any unsupported proof for squash/rebase stays visible, preserving evidence rather than bypassing it.
- Push gating for a recorded required integration result must be bound to the intended integration branch and current result, without treating backup-branch pushes as release acceptance. Existing action/cadence permissions continue to apply.

### Implemented CLI/JSON protocol (runtime API 2)

Activate existing projects explicitly with `configure --patch` using `{"runtime_api":2}`. New initializations include API 2; reading legacy configurations does not add it. Optional policy `review.allow_manual` and `review.independent` are booleans, absent means false. A task may strengthen independent review, never weaken policy. Full replacement/reviewed recovery preserve an activated API floor.

A spec file contains the following shape (paths are relative to the task worktree root, including when a command runs in a subdirectory). Requirements and acceptance are nonempty arrays of strings. Paths are a nonempty array; `.` is allowed. Dependency kinds are `contract` (bind the upstream spec revision/hash only) and `integrated` (also require an intact historical upstream integration result and its actual consumer baseline). Resources share one project namespace. Cycles and unknown fields are rejected.

```json
{
  "requirements": ["Return a stable identifier for each record"],
  "acceptance": ["Offline unit checks cover duplicate identifiers"],
  "paths": ["src", "tests"],
  "dependencies": [{"task": "contract-1", "kind": "contract"}],
  "resources": ["fixture-database"],
  "review": {"independent": true}
}
```

```sh
python3 -I scripts/playbook.py task --project . --session OWNER --epoch 1 --id T1 --spec /tmp/task-spec.json --worktree /tmp/project-worker
python3 -I scripts/playbook.py readiness --project . --task T1
python3 -I scripts/playbook.py run --project . --session OWNER --epoch 1 --action dispatch --task T1 --worker implementer -- python3 -I /tmp/fake-worker.py
python3 -I scripts/playbook.py run --project . --session OWNER --epoch 1 --action verify --task T1 --reviewer independent-reviewer --role reviewer -- python3 -I /tmp/offline-check.py
python3 -I scripts/playbook.py evidence --project . --session OWNER --epoch 1 --task T1 --attempt VERIFY_ATTEMPT --reviewer independent-reviewer --role reviewer --note 'Offline acceptance checked'
python3 -I scripts/playbook.py evidence --project . --operation status --task T1
python3 -I scripts/playbook.py task --project . --session OWNER --epoch 1 --id T1 --state verified
```

`task --spec` defaults the state to reserved. Spec changes increment `spec_revision`, retain `spec_history` and prior receipts, and remove the current acceptance/integration pointer. `readiness --action dispatch|verify [--worker ID]` defaults to dispatch and returns `action`, `ready`, `blockers`, `dependencies`, `spec_hash`, `spec_revision`, advisory `content_conflicts`, and `dispatch_state_ready`. Readiness includes project mode, permission, task state, worktree occupancy and resource capacity; it does not reserve work or choose a worker. A reserved typed task holds its explicit resources; running/unknown attempts and manual reservations block conflicting launches. Attempt records snapshot dependencies/resources/spec and verification content before/after execution. All launches recheck under the shared lock. Integrated dependencies check the actual consumer worktree: committed upstream results require the accepted result commit in its ancestry; uncommitted results additionally require matching accepted scoped content. Task receipts repeat the consumer check so losing the baseline cannot retain acceptance. Successful integrations freeze `result_committed` at finish and pin the original dependency IDs; historical dependency validation verifies retained records/logs/specs without requiring the old target or worker checkout to remain unchanged. Current integration status and push gating still require the exact accepted target HEAD/branch/content and its dependencies. This permits ordinary downstream integration and later batches without rewriting history or forming pointer cycles. Missing `result_committed` is treated conservatively as uncommitted. The uncommitted-content rule is conservative about overlapping downstream edits; explicit contract-only dependencies remain distinct.

Only a completed successful **verify** attempt can produce passing machine evidence; dispatch exit zero remains a report. `run --reviewer/--role` freezes cooperating review declarations before verification; receipt declarations must match. Independent review requires a reviewer distinct from retained task-owner/implementation-worker provenance. Task updates and handoffs retain owner history; verification attempts freeze their implementation sources before execution, so the same rejected self-review cannot become independent after a handoff. Manual evidence uses `evidence --manual --reviewer NAME --role reviewer --artifact relative/path --note TEXT`, requires `review.allow_manual:true`, and is explicitly labelled manual. `--result passed|failed` defaults to passed. Each receipt has a fresh ID, is exclusively created in local runtime `evidence/ID.json`, and has a SHA256 pointer in state. Complete runtime verification logs are hashed at attempt completion and rechecked at receipt creation and applicability checks. Managed adapter verify streams full stdout/stderr there, including quiet mode; external user logs are separate copies. A completed integration with empty artifact lists does not require cleaned-up source worktrees; explicit artifact paths still must exist and match. Checkpoints also copy receipt files and referenced verification logs within the existing aggregate snapshot budget and retain the integration/evidence ledger in their manifests. There is no replace/delete CLI. `evidence --operation status` reports individual applicability/errors; legacy tasks are labelled `legacy-note-only`. Accepted machine results cannot be rebound to later content, requirements or dependencies. Artifact bytes/modes are hashed; missing or altered artifacts invalidate applicability. Explicit artifact paths may include intentionally archived ignored evidence, but must name regular files without symlink ancestors.

Content fingerprints are bounded to the existing per-file/total/entry limits and compare bytes, modes, deletion and symlink identity, not mtime. Directory symlinks are not followed. Git scopes include tracked and nonignored untracked content; ignored untracked data and conventional untracked cache/`.env` paths are excluded and reported. Non-Git scopes exclude conventional caches, `.env` paths and conservative root `.gitignore` matches; negation does not re-include excluded files. Scope hashes are not a claim that ignored or excluded files were tested.

```sh
python3 -I scripts/playbook.py integration --project . --session OWNER --epoch 1 --operation begin --id batch-1 --tasks T1 T2 --target /tmp/project-main --paths integration-tests --require-push
# Execute separately authorized merge commands; begin does not merge or grant permissions.
python3 -I scripts/playbook.py run --project /tmp/project-main --session OWNER --epoch 1 --action verify --task assembled-batch-1 --integration batch-1 --reviewer integration-reviewer --role reviewer -- python3 -I /tmp/assembly-check.py
python3 -I scripts/playbook.py integration --project . --session OWNER --epoch 1 --operation finish --id batch-1 --attempt ASSEMBLY_ATTEMPT --note 'Declared T1 and T2 membership; assembled checks passed'
python3 -I scripts/playbook.py integration --project . --operation status --id batch-1
```

Begin requires currently verified participants and applicable receipts. Its scopes union all participant paths with optional extra `--paths`; scopes cannot silently narrow acceptance. Finish requires a successful explicitly associated assembly attempt, unchanged requirements/dependencies, and matching actual verification-before/after/current content plus target HEAD/branch. Finish also rejects outstanding execution in the target worktree. Every assembly attempt appends an `observations` entry with its real return code, target identity and merge ancestry, including failed or cancelled checks; status reports current `observed_target`/`observed_merge_facts` separately from acceptance. Successful finish records `result_hash`, `result_target`, `result_content` and `merge_facts`, then marks participants integrated. Merge facts separately report source-commit ancestry; `membership:declared` and `semantic_inclusion_proven:false` explicitly preserve the limitation for dirty changes and squash/rebase. No hash or ancestry claim proves arbitrary semantic inclusion.

`--require-push` is valid only for the configured integration branch, persists a branch-specific gate, and needs a current successful result before publishing that branch. With a gate recorded, guarded push accepts explicit `git push REMOTE SOURCE:DESTINATION` argv; wrappers, force/deletion/default/wildcard refspecs fail closed. The source commit must equal the accepted result and its target worktree must be clean. Explicit backup-branch destinations do not confer or require release acceptance; existing permission and cadence checks still apply.

## Foundation helper contract

`python3 -I scripts/playbook-foundation.py check|apply --project PATH [--profile minimal|standard] [--session ID --epoch N]`

`check` is read-only; `apply` uses `guard --action scaffold` with current owner/epoch. Both return structured create/retain/conflict/readiness information. Apply must preflight all targets and use exclusive creation so a concurrent existing file is never overwritten. Refuse escaping/symlink target paths and ambiguous path collisions. Preserve existing README, AGENTS, plans, handoff and source. Existing files needing changes are reported, not rewritten.

Minimal foundations include a truthful root README, configured plan/worker/handoff files and a first task-card draft/template at the configured cards path. Reflect the known goal and policy reference; unknown build/test commands and acceptance details remain explicitly pending. Do not report a draft as dispatch-ready. The agent completes the first concrete card/spec using actual project facts. Standard adds the existing board/decision/review resources as appropriate. Do not always create every optional document.

Project copies of required runtime dependencies are create-only and have a source/hash manifest for diagnostics; differing existing helpers are retained and reported. The helper works without Git. The old `init-plan.sh` path stays compatible for legacy/default Git layouts; v3 instructions prefer the new helper and configured paths. README creation is explicitly part of user-requested start/repair, not bare `playbook` discovery.

## Interaction and documentation

Update both languages, root compatibility entry, templates and CLI examples against the actual completed implementation. Provide examples for bare entry, default recommendation acceptance, same-owner resume, prepared takeover, unprepared owner conflict, requested/canonical path mismatch, partial configuration, handoff withdrawal, attempt cancellation, foundation check/repair and staged verification. User-facing names can be localized, while existing skill names stay stable.

Avoid claims of an interactive GUI on every client. Show state-aware actionable choices and use a host choice tool only when a real unresolved choice exists. Standard actions stay inside the total entry; no sixth Skill. Existing authorization is reused within its scope. Entry-loaded, configured, scaffolded, dispatch-ready, dispatched, verified and integrated are different facts.

## Required validation

- Existing regressions remain meaningful; change expectations only for an intentional documented contract change.
- Add failure and race tests for pause snapshot failure, handoff cancel/takeover race, patch preservation, targeted cancellation and natural-exit races, stale evidence including dirty contents, dependency/resource gating, changed integration targets, historical/legacy compatibility, runtime-copy diagnostics and create-only foundations.
- Demonstrate two fake workers in isolated Git worktrees, then non-overlapping managed heavy verification, evidence acceptance and final integration verification; include a prepared handoff to a simulated new owner. Test non-Git foundations separately. Preserve command receipts and known exclusions.
- CI uses no credentials or paid model calls. Include macOS and Linux POSIX runners, supported Python versions, shell syntax/selftest, unittest discovery, generated bundle `--check`, and manifest checks. Native plugin validation may be a separately explicit pinned CLI validation job; do not treat missing validators as passing.
- Build final bundles only after canonical sources settle. Validate standalone copies with every new dependency present. Shared installed updates require external staging, review, backup, helper reconciliation and actual discovery checks under the standing installation rules.
- No commit, push, release, remote CI execution or deployment without the corresponding user request.

## Final runtime CLI interface appendix

Lifecycle additions preserve existing flags and JSON fields:

```sh
python3 -I scripts/playbook.py version
python3 -I scripts/playbook.py discover --project /tmp/project/subdirectory
python3 -I scripts/playbook.py configure --project . --session OWNER --epoch 1 --patch /tmp/policy-patch.json
python3 -I scripts/playbook.py pause --project . --session OWNER --epoch 1
python3 -I scripts/playbook.py cancel --project . --session OWNER --epoch 1 --attempt ATTEMPT_ID --reason 'Work superseded'
python3 -I scripts/playbook.py handoff --project . --session OWNER --epoch 1 --cancel
python3 -I scripts/playbook.py doctor --project .
```

A patch such as `{"limits":{"heavy_jobs":2}}` changes only the supplied leaf. Arrays replace when supplied; null and unknown fields fail. Full `--config` replacement remains mutually exclusive with `--patch`. Both return `changed_paths` and the normal configuration revision. Patch read/merge/validation/write occurs under the project lock; incomplete full writes still use explicit reviewed recovery.

Pause first saves `mode:paused` and an incomplete-recovery marker, then attempts the checkpoint. Errors remain nonzero and leave dispatch stopped. Handoff withdrawal is mutually exclusive with `--to`; it preserves snapshots, appends `handoff_history`, returns `cancelled_handoff`/`already_cancelled`, invalidates the prepared token and leaves paused. Owner and epoch checks serialize withdrawal with takeover.

Cancellation returns `status:requested|unknown|terminal`, `requested` and the attempt record. Requests preserve the first reason. Only the still-live supervisor reads them and acts on its own unreaped process-group leader; the requester never signals recorded PID/PGID values. Terminal supervisor records include `cancelled` and, when requested, `cancel_acknowledgement.outcome:cancelled|completed-before-cancel|timed-out`. Cancelled run exits 125; attempts and logs remain. A lost supervisor remains unknown and continues consuming reservations until explicit reconciliation. Natural group exit observed before cancellation wins as terminal completion.

`discover` returns `requested_project` and canonical `project`. `version` does not require `--project` and returns `package_version:3.0.0`, `runtime_api:2`, `schema_version:1`, explicit state/config schema versions, `release_status:released`, `capabilities`, `runtime_path`, `files` (sibling filename to SHA256) and `missing_files`. The required copy list is `playbook.py`, `playbook_work.py`, `policy-dispatch.py`, `playbook-foundation.py`, `wt.sh`, and `dispatch.sh`; legacy `init-plan.sh` remains packaged separately.

`doctor.runtime_diagnostics` contains `running`, `manifest` and `project_copies`. The project manifest path is `.orchestrator/runtime-manifest.json`. Foundation's portable manifest shape is `{"package_version":"3.0.0","runtime_api":2,"source_runtime":"orchestrator-playbook/scripts/playbook.py","files":{"scripts/playbook.py":{"sha256":"...","mode":493}}}`. Diagnostics also understand a full `version` object under `source`/`source_version`; no declared source is `unknown`. Each project copy reports manifest `status:matching|differing|missing|unknown`, running-copy `comparison` and `provenance`. A declared source is diagnostic provenance, not a signature. Missing/changed copies are never overwritten or upgraded by diagnosis.
