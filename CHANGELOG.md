# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [Semantic Versioning](https://semver.org/).

## [3.1.0-dev.1] — Unreleased

### Added
- Managed Hermes gateway adapter with explicit approval-request responses, model/reasoning/profile selection, persisted session/admission identities, same-owner reconnect without resubmission, and bounded cancellation cleanup.
- Terminal admission and live resource observations separate from viewer process exit. Unconfirmed execution retains `unknown` reservations; receipts explicitly do not prove termination of arbitrary external task trees.
- A standalone Hermes plugin builder and five native commands reusing canonical bilingual resources, with mandatory session-bound loading choice and existing host injection permission.
- Local fake-gateway and plugin-context regression tests; no model calls or global client configuration changes.

### Changed
- Managed Hermes requires an explicit `worker.hermes.approval` choice and empty native `args`; old configurations remain readable without implicit policy changes.
- Legacy Hermes keeps `-z` automatic approval, now documents that behavior and reports gateway execution as unknown on timeout.
- Runtime, package and plugin manifests identify this unpublished development version; generated bundles include both gateway runtime dependencies.

### Limits
- Tested protocol assumptions target Hermes 0.23.1. Native plugin activation, frontend interaction and paid model execution have not been validated by offline tests.
- Approval `deny` answers emitted requests; it does not override native grants or profile policy. Interrupted delegations without join proof remain unknown. Installation and permission changes are separate operations.

## [3.0.0] — 2026-11-14

### Added
- Five explicit lifecycle entries: `playbook`, `playbook-start`, `playbook-resume`, `playbook-handoff` and `playbook-takeover`, with English and Chinese sources under `skill-src/`.
- A standard-library Python runtime for project discovery, versioned configuration, session ownership, checkpoints, pause/resume, handoff/takeover and explicit interruption recovery on one POSIX machine.
- Managed task/attempt records, policy guards and execution reservations; successful worker exits remain reported results until acceptance is verified.
- A policy dispatcher adapter for approved worker settings and managed runtime execution.
- `scripts/build-skills.py`: standalone bundles with copied runtime scripts, references, templates and explicit-only `agents/openai.yaml`; `--check` for read-only drift detection and `--output` for staging.
- Per-skill generation manifests, preflight checks for all destinations, refusal of unsafe/local conflicts, preservation of unrelated content, and temporary-fixture packaging tests.
- Lifecycle/configuration references and a conversational first-use path covering both new projects and existing-project adoption.
- Runtime API 2: structured task specifications, contract/integrated dependencies, exclusive resource claims and read-only readiness, rechecked under the launch lock.
- Append-only acceptance receipts bound to requirements, dependency bindings, tested content and artifacts; explicit manual/independent review policy; integration begin/finish/status with associated assembled verification and branch-specific push gates.
- Partial configuration through `configure --patch`, prepared handoff withdrawal and attempt-specific cancellation requests acknowledged by the live process-group supervisor.
- Create-only `playbook-foundation.py` for minimal/standard project foundations, root README, custom paths, non-Git adoption, missing-file repair and local runtime manifests.
- Read-only `version` and running/project-copy diagnostics, offline pilot instructions, and CI for POSIX/Python regression, shell, generated-bundle and manifest checks.

### Changed
- Public plugin manifests select the five new skills and identify package version 3.0.0.
- Project policy lives in `.orchestrator/config.json`; local ownership/recovery state is shared through the Git common directory, or `.orchestrator/local/` for serial non-Git projects.
- Documentation distinguishes explicit user authorization, same-session resume, prepared handoff and takeover. It describes shared versus client-only installation without claiming identical invocation syntax across clients.
- A bare start invocation uses focused goal clarification before setup recommendations; existing projects reuse their plans, and already settled choices are not asked again.
- Shell entry points participate in managed checks for configured projects, including scaffold ownership, canonical state across linked checkouts, normalized defaults and custom planning paths; root compatibility and legacy shell paths remain available.
- Managed dispatch preserves existing logs, orders DSH launcher overlays before application arguments, and supervises the launched process group through its deadline even when the leader exits first.
- Managed worktree creation reports setup hooks as pending for the approved setup flow after the creation lock is released; unconfigured legacy hooks still run automatically.
- Interrupted configuration writes have an explicit reviewed-configuration recovery path with preserved evidence. Snapshot capture is bounded during Git patch generation and refuses unmerged indexes rather than claiming incomplete recovery data is complete.

- Pause now persists the stopped state before capture; snapshot failure cannot reopen dispatch. Router instructions show actual state, one recommendation and compact choices, reusing settled authorization and internally retrieving handoff IDs.
- Implementation and heavy verification are separate stages. Worker/card/review/handoff templates include requirements, content scope, resources and evidence applicability.
- Five deferred cleanups reuse recovery-blob hashes only within one verification, remove redundant checkpoint state persistence, cache CLI help only within one dispatch, remove duplicate canonical adapter checks/dead worker filtering, and centralize outstanding-attempt classification.
- Existing schema-1 policy remains readable without injecting new optional fields into its hash; explicit API-2 activation is preserved through replacement/recovery and rejected by older runtimes.

### Fixed during v3 validation
- Preserve supervisor deadlines while the project lock is busy, and retry API-2 initialization idempotently when its marker was initially inferred.
- Preserve implementation provenance across handoffs; retain historical dependency bindings while enforcing actual consumer baselines and current publication targets.
- Keep directory content fingerprints stable when staging/committing an existing deletion, and apply exclusions consistently to explicit scopes.
- Preserve completed machine integration evidence after approved source-worktree cleanup; explicit artifact locations and shared verification logs remain required.
- Publish complete foundation files without overwriting existing targets, normalize relative project paths before guarded execution, and retain complete managed reviewer output in authoritative logs.
- Reject conflicting native setting aliases and ambiguous manifest keys before execution or installation.

### Boundaries
- Unconfigured legacy use is still supported but does not acquire v3 guarantees.
- Managed locks coordinate cooperating same-machine sessions; they cannot intercept arbitrary client shell/edit tools or raw Git commands.
- No automatic multi-machine takeover, native conversation restoration, automatic upgrades, hard monetary cap or automatic publication.
- Model selection, Claude/Codex/DSH effort and Codex/DSH profile argument mappings are implemented; DSH requires an explicitly approved noninteractive profile. Hermes effort/profile and Claude profile overrides remain unsupported. Tests use temporary projects and fake commands, not paid model execution.
- Native client discovery and real model behavior require separate verification; packaging tests alone prove neither.
- Building or checking the source does not install skills. Installation and publication are separate, explicit operations.

## [2.0.0] — 2026-11-08

First public release.

### Added
- `SKILL.md` (English) and `SKILL.zh.md` (Chinese edition) covering the orchestrator/worker model, ten rules, start gate, change-of-orchestrator procedure, control plane, and session loop.
- `references/`: bootstrap and takeover, handoff files, card writing, dispatch, review and merge, stakeholder communication, and 19 lessons learned.
- `templates/`: WORKER.md, TEAM.md, PLAYBOOK.md, status board, task index, task card, spike card, review note, ADR, handoff doc, decision ledger, external items, change-note template.
- `scripts/init-plan.sh`: scaffolds the control plane in a repository without overwriting anything.
- `scripts/wt.sh`: one worktree per card (`new` / `ls` / `path` / `rm`, refuses to delete unmerged or dirty worktrees).
- `scripts/dispatch.sh`: dispatcher for Claude Code, Codex, Hermes, and DeepSeek Harness, with preflight, timeout, and logging.
- `scripts/selftest.sh`: 73-check end-to-end test suite for the scripts (temp repos only).
- Plugin manifests for Claude Code (`.claude-plugin/`), Codex (`.codex-plugin/`), and generic agent marketplaces (`.agents/plugins/`).
- Explicit-invocation enforcement: `disable-model-invocation`, `allow_implicit_invocation: false`, and a prose start gate in `SKILL.md`.

### Notes
- The skill is model-agnostic and has no provider or gateway dependency.
- `references/` and `templates/` are currently in Chinese; contributions with translations are welcome.

## Pre-release history

- **1.x (internal)**: the workflow was developed and validated on a real multi-agent project before being generalized into this skill.
