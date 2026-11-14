# v3 implementation contract

This repository is being maintained as a skill package; do not initialize its own control plane. This document records the initial v3 implementation contract, not authorization to operate another project. The [next-iteration contract](v3-next-implementation.md) extends it with runtime API 2, partial configuration, structured acceptance/integration, cancellation, foundations and version diagnostics; where behavior is extended, use that contract and the current CLI references. The unpublished [Hermes adapter contract](hermes-adapter.md) adds a gateway employee backend and native explicit command plugin without upgrading user installations.

## Product scope

One package, five explicit-only entries: `playbook`, `playbook-start`, `playbook-resume`, `playbook-handoff`, `playbook-takeover`. The router also offers configuration, read-only status/diagnosis, and pause. Start detects a new or existing project and preserves existing files. User invocation of start appoints the current *session* only when no incumbent exists; an existing project/holder must not be overwritten. Resume never silently takes another session's role. A prepared handoff plus the user's explicit takeover invocation permits the designated new session to claim, without another identical confirmation.

The first implementation supports cooperating sessions on one POSIX machine. Locks cover managed operations, not arbitrary client shell/edit tools. Automatic multi-machine arbitration, native client conversation resumption, unverified model/effort flag mappings, automatic upgrades and automatic publishing are out of scope. Non-Git projects get serial operation and local snapshots; they do not acquire Git actions.

## Canonical sources and packaging

- Runtime: `scripts/playbook.py`, standard-library Python 3.9+, invoked with `python3 -I`.
- Skill entry sources: `skill-src/<name>.md` and `<name>.zh.md`; these are not named SKILL.md to avoid duplicate discovery.
- New deep references: `references/lifecycle.md` / `.zh.md`, `references/configuration.md` / `.zh.md`.
- `scripts/build-skills.py` builds **self-contained** `skills/<name>/` directories, including SKILL.md, Chinese edition, explicit-only agents/openai.yaml and complete required scripts/references/templates. Generated resources must match canonical sources. Individual skills must remain usable when installed without their siblings.
- Root SKILL.md / SKILL.zh.md remain an explicit-only compatibility entry named `orchestrator-playbook`; public plugin manifests point at the new skills directory. Existing low-level shell tools remain available for unconfigured v2 projects, with a clear legacy boundary.

## Runtime interface

All commands use `python3 -I scripts/playbook.py ACTION --project PATH ...` and return JSON on success; failures must have a nonzero status and an actionable message. `--help` documents actual options.

Required actions:

- `discover`: read-only project/Git/known-client executable inventory. Never runs an LLM, reads secrets, installs a client or changes global configuration. Executable presence is not login/permission/capability proof.
- `session-id`: create a fresh opaque session identity, no project mutation.
- `init --session ID --client NAME --goal TEXT [--config FILE] [--adopt]`: create a versioned config and runtime state. Idempotent for the same existing owner; fail on conflicts. Legacy `.orchestrator` files require explicit adoption and remain untouched. The skill obtains answers first and uses --adopt for a user-requested existing-project import. The target directory must already exist; the skill may create the user-requested new project directory first. Empty/new directories need not already be Git repositories. A non-Git project's later conversion to Git requires explicit migration and must not silently create a second owner.
- `status`: small authoritative current-state summary, including recorded tasks and policy; read-only.
- `resume --session ID --epoch N`: only the current owner; show changed baseline and recorded tasks without re-dispatching or re-running tests. May resume the same owner's paused state. Another owner is a conflict, not an implicit takeover.
- `configure --session ID --epoch N --config FILE`: validate and atomically replace project settings after user choices. No implicit changes to global client configuration. Preserve active ownership/tasks and record revision.
- `checkpoint --session ID --epoch N`: snapshot actual Git HEAD/worktrees/dirty and untracked work, task records and config; capture local recovery copies of uncommitted source, without git commit/push/reset. Local snapshots are outside normal Git publication. Git-ignored untracked files are excluded; needed ignored evidence must be explicitly archived before handoff, and cleanup still refuses ignored content. Oversize/unreadable/changing content, dirty submodules, unmerged indexes and special files must be reported and must not silently yield a complete checkpoint. Current limits are 64 MiB per file, 256 MiB total, and 10000 files; failed snapshots retain partial recovery data.
- `handoff --session ID --epoch N [--to SESSION]`: make a complete checkpoint, then enter prepared state. Old owner stops managed mutations/dispatch. Repeating the same handoff is idempotent. Return a handoff ID.
- `takeover --session ID --client NAME --handoff ID`: under a shared OS lock validate prepared state, target, machine, revision/baseline, and recovery content; increment epoch and change owner. Repeated success by the same owner is idempotent. Unknown or changed state must remain visible and must not trigger automatic repeated dispatch.
- Recovery after an unprepared interruption is explicit: `takeover --recover --previous-stopped ...`; this is an attestation of the user-directed stopping/replacement, not proof that raw external writes are fenced. Preserve/reconcile existing tasks and checkpoint first. Never infer replacement authority from elapsed time. If an interrupted configure leaves config and state inconsistent, an explicit `--config FILE` supplies a reviewed replacement for recovery: retain the original config/state and the selected configuration as local evidence, record a new revision, then checkpoint and claim. Do not silently adopt unknown permissions. Normal prepared takeover cannot use this option to bypass validation.
- `pause --session ID --epoch N`: stop new managed work, checkpoint and retain tasks; do not kill workers or discard files.
- `doctor`: read-only schema, ownership, paths, baseline and recorded task checks. Report unknown execution state; do not repair, migrate, delete or dispatch automatically.
- `task --session ID --epoch N --id ID --state STATE [--worktree PATH] [--note TEXT]`: explicitly record/reconcile a task. Distinguish reserved/running/reported/verified/integrated/blocked/unknown. Unknown/running work is not assumed absent. No default claim that exit 0 means acceptance.
- `guard --session ID --epoch N --action ACTION -- COMMAND...`: hold the same project OS lock across owner/policy checks **and** a short shared mutation. Actions include `commit`, `merge`, `push`, `cleanup`, `worktree-create`; no shell interpolation. The `scaffold` action is an owner/epoch/active-checked metadata operation for explicitly requested setup, without a new permission question; it does not authorize Git or dispatch. Denied/ask actions do not execute. Set `PLAYBOOK_GUARDED=1` only on the child environment for cooperating shell adapters; this is not a security boundary against a caller forging environment or invoking raw tools.
- `run --session ID --epoch N --action dispatch|verify --task ID [--worker ID] [--cwd PATH] [--config-revision N] [--timeout SECONDS] -- COMMAND...`: reserve a unique attempt and resource slot under the lock before launching an isolated process; launch while still owning the reservation, then release lock while waiting. Append its result under lock even if ownership has changed; a successful process is only reported, never automatically verified or integrated. Persist reserved/unknown state if interrupted; do not auto-relaunch it. Count dispatch/reviewer jobs against agent limits and verify jobs against heavy-job limits. Do not kill any unrelated process. Honor configured timeouts for the launched process group.

Runtime may offer additional flags needed for validated operation, but must update this contract and the CLI references if its interface differs. Component owners should communicate API changes to the parent before downstream integration.

## Configuration

`.orchestrator/config.json` is the portable policy source. Runtime ownership, process records and recovery copies live in the **shared Git common directory** (for all linked worktrees) or `.orchestrator/local/` for non-Git, with a local ignore rule. Do not create runtime copies per worktree. Store project ID, machine identity, session/client, monotonically increasing epoch and configuration revision. Use atomic replacement and an OS file lock (fail clearly when unsupported). Do not treat a tracked TEAM.md or lock age as a distributed lock.

Version 1 config minimum shape (runtime validates and fills missing defaults):

```json
{
  "schema_version": 1,
  "goal": "A checkable stage outcome",
  "workers": [],
  "limits": {"agents": 2, "heavy_jobs": 1, "timeout_seconds": 7200, "max_attempts": 2},
  "permissions": {"dispatch": "ask", "verify": "ask", "worktree-create": "ask", "commit": "ask", "merge": "ask", "push": "ask", "cleanup": "ask"},
  "git": {"integration_branch": "main", "merge_method": "merge", "push_cadence": "manual", "cleanup_mode": "retain"},
  "review": {"level": "adaptive"},
  "paths": {"plan": "docs/plan/README.md", "worker": "docs/plan/WORKER.md", "cards": "docs/plan/tasks", "handoff": "HANDOFF.md"}
}
```

Permission values: `allow`, `ask`, `deny`. Missing authorization is not allowance. Explicit user answers can authorize routine local actions once; do not ask again per card. Workflow/metadata operations needed for an explicitly invoked lifecycle command do not require redundant prompts. Push authorization does not grant publish/deploy authority. Allowing cleanup does not bypass dirty/unmerged/running/evidence checks. Cadence/retention policy remains relevant even when permission is allow.

A worker record includes `id`, `client` (`claude`, `codex`, `dsh`, `hermes`, `manual`), model and effort objects with `mode` (`inherit`, `fixed`, `recommend`) and optional `value`, optional profile, and per-invocation `args`. Default inherit means that worker's own configuration. Recommendations are proposals until resolved; no invented flag mappings. Existing dispatcher can preserve config or pass an explicitly chosen model; richer effort/profile mappings are only advertised when verified. Unsupported requested settings block that launch instead of silently being dropped. No credentials belong in config.

## Shell integration (parent-owned)

The parent integrates existing `wt.sh`, `dispatch.sh`, `init-plan.sh` and `selftest.sh`. On configured projects, managed mutations must use runtime owner/policy checks. Unconfigured legacy calls retain existing behavior and are explicitly documented as outside v3 guarantees. `init-plan.sh` must copy the runtime alongside a newly copied wt.sh when necessary, include it in the staging hint, and guard configured writes with `scaffold` while keeping `--dry-run` read-only. Worktree/dispatch helpers detect shared runtime state and consume its canonical policy; the primary checkout need not contain the config. Managed `wt.sh new` reports setup hooks as pending and releases the creation lock before the approved setup/verification flow runs; legacy hooks retain automatic execution. A hook that already invokes managed run is not wrapped in another run. Dispatch preserves caller-relative log paths and exclusively creates managed logs. A guard environment marker only prevents recursion; never describe it as enforcement against an uncooperative client.

## Acceptance

- Existing script selftest remains green; plugin manifests validate.
- Runtime tests use only temporary projects, local Git commits and fake child commands, no paid model calls or network.
- Cover new init, dirty existing adoption, duplicate init, same-client/different-session conflicts, valid handoff/takeover, repeated calls, stale epoch rejection, checkpoint failure, unprepared recovery, late worker results, attempt deduplication, limits, timeout, denied push, config validation, non-Git and shared worktree state.
- Bundle tests confirm five distinct explicit-only entries, resource completeness, isolated copy operation, no host paths, synchronized generated resources and compatibility root.
- Review actual implementation and UI instructions independently, fix confirmed issues, and report limitations precisely. Do not claim native-client task execution, model switching, cross-machine locks, hard monetary budgets, publication or installation unless actually performed and verified.
