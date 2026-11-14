# Orchestrator Playbook

<img src="assets/icon.png" width="96" align="right" alt="Orchestrator Playbook icon">

**English** | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**One package, five explicit skills for starting, continuing and handing over a software project.**

Version 3 adds project configuration, session ownership, checkpoints and managed execution to the task-card/worktree workflow. The orchestrator plans and reviews; workers return evidence; acceptance and integration remain separate decisions. This source tree is a skill package, not a project to initialize with its own control plane.

| Entry | When to use it |
|---|---|
| `playbook` | Choose an action; inspect status, diagnose, configure or pause a project |
| `playbook-start` | Answer setup questions and start a new project or adopt an existing one |
| `playbook-resume` | Continue recorded work as the current owner session |
| `playbook-handoff` | Create a recovery checkpoint and prepare an orderly handoff |
| `playbook-takeover` | Explicitly accept a prepared handoff, or perform authorized interruption recovery |

All five use `disable-model-invocation: true` and `allow_implicit_invocation: false`. Each generated directory carries its own runtime, references and templates, so one entry can be installed without its siblings. Skill selection, command prefixes and plugin namespaces depend on the client; the names above do **not** promise identical slash syntax everywhere.

## First use

1. Install using **one** of the strategies below, then open your project directory in your client.
2. Explicitly select **playbook-start**; no prepared prompt is required. If the goal is unclear, the agent asks a few focused questions at a time, recommends a first milestone and stops once scope and acceptance are clear. You may also supply a known goal, for example: “Build CSV import with tests for malformed rows.” For a project that has **never used v3**, say “Use playbook-start to adopt this project.” It reads and preserves existing plans and work; a project following the old Playbook workflow uses this same adoption path.
3. Review a concrete recommendation: actual project path, first goal, reused files, workers/settings, concurrency/timeouts, permissions and minimal/standard foundations. Accepting its explicit choices settles them; the skill asks only about missing decisions. Worker settings default to inheriting that worker's own client configuration.
4. Start records policy and a fresh session identity when no owner conflicts. The foundation helper previews and creates only missing files, including a root README, configured planning/worker/handoff files, a first-card draft and required local runtime copies. Existing documents and differing scripts are retained. Git, non-Git and custom planning paths are supported; standard adds optional planning resources.
5. The agent fills the first card from real project facts, registers its requirements, content paths, dependencies and exclusive resources, then checks readiness before dispatch. A generated draft or unknown test command is not a ready task.

A bare **playbook** invocation shows the actual project, session role, blockers, one recommendation and up to three alternatives. It stays read-only. Ask for “check foundations” to preview missing files, or “fill missing foundations” to perform the authorized create-only operation. Choose boxes depend on the host; numbered text is the fallback, not a promise of a universal GUI. See [bootstrap](references/bootstrap.md).

You do not need to fill a directory of template placeholders to complete v3 setup. The skill turns settled choices into project-specific configuration and planning content; existing documents remain the starting point. Executable discovery does not prove login, permission or support for a requested option.

An existing `.orchestrator` directory requires an explicit adoption choice. An existing owner is a conflict to resolve through resume or takeover, even if both sessions use the same client or model. A session ID identifies a session, not a product name. Starting a new conversation does not silently inherit another conversation's role.

## Install

Choose a plugin installation, a shared skills directory, or a client-only skills directory. Avoid installing overlapping copies through several strategies: a client may discover duplicate entries. These instructions describe user-operated installation; building or testing this repository does not install anything globally or contact model services.

### Claude Code plugin

For a published revision containing v3:

```text
/plugin marketplace add sakyaroy-007/orchestrator-playbook
/plugin install orchestrator-playbook@orchestrator-playbook
```

The plugin manifests point at the five directories under `skills/`. Local manifest validation uses `claude plugin validate .`; validation is not a live test of skill discovery or worker execution. See [versioned releases](https://github.com/sakyaroy-007/orchestrator-playbook/releases) for published revisions.

### Codex and other clients

The repository includes `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`. Use your client's supported plugin installation flow when available. Standalone-directory discovery was checked through the installed Codex `skills/list` protocol and DSH filesystem provider without model calls. Their plugin installation flows and active conversation loading were not exercised; installation UI and invocation syntax may differ. A generic marketplace catalog points to the package, whose plugin manifest selects `skills/`.

For clients that discover standalone skills, copy the five generated directories into a supported root. A shared root such as `~/.agents/skills` is useful when the intended clients actually scan it. Use `~/.claude/skills` for a Claude-only installation; other client-only roots must be checked against that client's documentation. Keep model credentials and private client configuration outside this package.

From a reviewed checkout with generated skills, this example installs to the shared root and refuses existing destinations, including dangling symlinks:

```bash
python3 -I scripts/build-skills.py --check || exit 1
skill_root="${HOME}/.agents/skills"
for name in playbook playbook-start playbook-resume playbook-handoff playbook-takeover; do
  if [ -e "$skill_root/$name" ] || [ -L "$skill_root/$name" ]; then
    printf 'Already exists; review before replacing: %s\n' "$skill_root/$name" >&2
    exit 1
  fi
done
mkdir -p "$skill_root"
for name in playbook playbook-start playbook-resume playbook-handoff playbook-takeover; do
  cp -R "skills/$name" "$skill_root/$name" || exit 1
done
```

If a skills installer offers several discovered entries, select these five. Root `SKILL.md` is the retained `orchestrator-playbook` compatibility entry; installing the entire repository as one old-style skill does not install the five new entries. Upgrades are deliberate: review the new version and local changes, then replace your chosen installation. There is no automatic updater.

### Hermes native commands

Hermes employees do not need these orchestrator skills installed. For an orchestrator inside Hermes, build the separate native plugin with `python3 -I scripts/build-hermes-plugin.py --output /physical/staging/orchestrator-playbook`. It reuses the five canonical entries without exposing ordinary `SKILL.md` files to model discovery. Each command requires a session-bound **Load** choice; gateway/TUI instruction injection also needs an operator-reviewed host permission. See [the adapter guide](adapters/hermes/README.md) and [worker configuration](references/hermes.md). Building does not install, enable or grant permissions. This development version has offline contract tests; live plugin/frontend and paid-model execution remain unverified.

## Continuing and handing off

- **Resume:** select `playbook-resume` in the owner session. It reads recorded tasks and current differences. It does not repeat dispatches or tests just because a conversation resumed.
- **Pause:** use `playbook` to pause. It persists stopped new work before checkpointing, so a failed snapshot still leaves it paused. Report incomplete recovery separately; workers and their results are retained.
- **Handoff:** invoke `playbook-handoff` in the outgoing session. It captures current work and task records, prepares a handoff and stops the old owner's managed mutations. It returns a copyable takeover sentence containing the actual project path; the incoming agent reads the handoff ID itself. A checkpoint does not commit or push source files.
- **Withdraw / cancel:** ask `playbook` to withdraw an unreceived handoff, returning to paused and invalidating the old ID, or cancel a specific execution attempt. Cancellation is a request to the live supervisor; preserve resource claims until terminal acknowledgement. An orphan remains unknown.
- **Takeover:** explicitly invoke `playbook-takeover` in the designated new session. A valid prepared handoff and this invocation authorize claiming the role without asking the same question again. Ownership changes only after state, machine, baseline and recovery checks pass.
- **Interrupted owner:** inspect with status/diagnosis first. Recovery requires the user's direction to stop/replace the old session and explicit recovery flags. Time elapsed is never evidence of permission. Running or unknown attempts must be reconciled before any retry.

Project policy lives in `.orchestrator/config.json`. Local ownership, attempt records and recovery copies live in the **shared Git common directory**, so linked worktrees share one owner and lock. Non-Git projects use `.orchestrator/local/`, serial work and local recovery snapshots; they do not gain worktree, commit, merge or push actions. Local recovery data is not normal Git publication content and can contain copies of uncommitted work.

Checkpoints exclude Git-ignored untracked files; explicitly archive needed evidence before handoff. Current limits are 64 MiB per file, 256 MiB total and 10,000 files. Unmerged indexes, dirty submodules, special files and oversized, unreadable or changing content prevent a complete checkpoint; partial recovery data remains available rather than being reported as a successful handoff.

## Configuration and authorization

Configuration covers workers, inherited/fixed/recommended model and effort choices, agent/heavy-job limits, timeouts, attempt limits, Git preferences, review level and planning paths. See [configuration](references/configuration.md) and [lifecycle](references/lifecycle.md) for the CLI and state transitions.

Permissions are `allow`, `ask` or `deny`; missing permission is not allowance. Explicit answers can authorize routine local work once, without asking again for every task card. `ask` and `deny` do not execute the guarded action. Push permission does not authorize deployment or publication. Cleanup permission still requires checks for dirty work, unmerged changes, active workers and retained evidence.

`inherit` uses each worker's own defaults. `fixed` must map to a verified client capability. `recommend` is a proposal until resolved. The adapter supports explicit model selection and checks CLI help before passing Claude effort, Codex reasoning effort or DSH reasoning-effort overlays. Profile overrides are supported for Codex and DSH; DSH requires an explicitly selected noninteractive profile, whose model/effort settings can still be inherited. Hermes uses its public gateway protocol for model/reasoning/profile selection, with an explicit approval-response policy and durable admission tracking; [its reference](references/hermes.md) explains the completion and cancellation limits. Claude profile overrides remain unsupported. These mappings and argument tests do not prove login, model availability or actual reasoning behavior. No credentials belong in project configuration.

Partial changes use `configure --patch FILE`, for example `{"limits":{"agents":3}}`, preserving omitted settings. `--config FILE` remains deliberate full replacement. Existing schema-1 projects stay readable; explicit `runtime_api:2` activation enables the extended protocol without silently changing old policy hashes. Older runtimes reject that marker instead of ignoring its constraints.

## Tasks, evidence and integration

Register a task spec and inspect readiness before launching. Dependencies distinguish a pinned upstream contract from an integrated result present in the consumer's actual baseline. Explicit exclusive resources share a project-wide namespace across worktrees. The owner chooses ready tasks; no automatic scheduler or retries are implied.

Workers implement and run approved lightweight checks. After their dispatch ends, the owner schedules heavy tests and independent review through managed verification. An immutable receipt binds requirements, dependencies, relevant bytes/modes and artifacts to the actual verification attempt; later changes make old evidence inapplicable. Successful dispatch alone stays reported. Manual evidence requires explicit review policy and remains labelled manual.

Integration records bind verified participants to an actual target and associated assembled verification. A successful merge does not establish that the assembled result passes. The optional integration-branch push gate checks the accepted current result while preserving ordinary permissions and cadence. Declared membership and source ancestry cannot prove semantic inclusion; that limitation remains visible. See the complete [task/evidence/integration commands](references/work-protocol.md).

## Runtime diagnosis

Run `python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" version` without initializing a project. It identifies the executing path, package/runtime API/schema versions, capabilities and required file hashes. For an initialized project, `doctor --project "$PLAYBOOK_PROJECT"` compares the running bundle, local runtime copies and `.orchestrator/runtime-manifest.json`. Missing, different and unknown copies remain visible; diagnosis does not overwrite or upgrade them. This checkout reports `3.1.0-dev.1` and `release_status:development-unreleased`; the published 3.0.0 release remains separate. Compare hashes as well as version strings to identify local modifications.

## Cooperation boundary

This first version coordinates cooperating sessions on **one POSIX machine**. Managed operations check session identity and epoch under an OS lock. Short guarded mutations hold that lock while the child runs. Managed dispatch reserves an attempt and resource slot before launch; a successful process is reported work, not automatic acceptance or integration.

The protocol cannot intercept arbitrary shell/edit tools, raw Git commands, unrelated processes or a client that ignores it. `PLAYBOOK_GUARDED` only avoids adapter recursion; it is not a security boundary. A tracked `TEAM.md`, a process exit code or an old timestamp cannot prove ownership or safe takeover.

This version does not provide automatic multi-machine takeover, native conversation restoration, automatic upgrades, hard monetary limits, automatic publishing or verified model/effort parameter mappings for every client. Concurrency and timeout limits are execution controls, not a hard spending cap. Runtime tests use temporary projects and fake worker commands; native client loading and paid task execution require separate validation.

## Legacy compatibility

Root `SKILL.md` / `SKILL.zh.md`, `agents/openai.yaml` and the existing `scripts/init-plan.sh`, `scripts/wt.sh`, `scripts/dispatch.sh` paths remain available. Manual v2 scaffolding and its template-filling procedure still work for unconfigured projects. Such legacy use does **not** create v3 ownership, policy, attempt records or managed-operation guarantees. Adopt through `playbook-start` before treating that project as v3 managed.

## Development and packaging

Requires Python **3.9+** with its standard library and a POSIX platform for runtime file locks. Git is required for Git projects. Shell adapters additionally use Bash (including macOS Bash 3.2), Git, Perl or `timeout`, and standard Unix tools. Clients are optional until a real dispatch is requested; tests do not call them.

| Path | Purpose |
|---|---|
| `skill-src/<name>.md` / `.zh.md` | Canonical English and Chinese entry sources; not directly discoverable as skills |
| `skills/<name>/` | Generated, independently installable entries and complete runtime resources |
| `scripts/playbook.py`, `scripts/playbook_work.py` | Policy, lifecycle, execution, task/evidence/integration protocol and diagnosis |
| `scripts/playbook-foundation.py` | Read-only foundation inspection and guarded create-only setup/repair |
| `scripts/policy-dispatch.py` | Apply approved worker configuration before a managed dispatch |
| `scripts/build-skills.py`, `scripts/check-manifests.py` | Deterministic bundles, drift detection and local manifest checks |
| `references/`, `templates/` | Canonical documentation and planning templates |
| `tests/`, `scripts/selftest.sh`, `.github/workflows/ci.yml` | Offline regressions and CI |
| `AGENTS.md`, `docs/v3-implementation.md`, `docs/v3-next-implementation.md` | Maintainer rules and implementation contracts |

```bash
python3 -I scripts/build-skills.py
python3 -I scripts/build-skills.py --check
python3 -I scripts/check-manifests.py
python3 -I -m unittest discover -s tests
bash scripts/selftest.sh
claude plugin validate .
```

CI runs on push, pull requests and manual triggers with read-only repository permissions: Ubuntu 24.04/macOS 15 Intel × Python 3.9/3.13, plus a pinned Claude Code 2.1.323 native manifest validation job without model requests. Use the [Actions history](https://github.com/sakyaroy-007/orchestrator-playbook/actions) for remote results on a specific commit. See [release validation](docs/v3-release-validation.md) for checks on the final package, the [development report](docs/v3-next-validation.md) for earlier local checks and installation boundaries, and the [pilot procedure](docs/v3-pilot.md) for offline coverage and a separately scoped live-client proposal.

`--output` selects a separate skills root, useful for staging without changing `skills/`. Supply a physical path without symlink ancestors; on systems where the temp root is an alias, obtain its physical path with `pwd -P`. The generator copies the explicitly allowlisted runtime scripts and Markdown resources in `references/` and `templates/`, never the repository, `.git`, generator or tests.

Each generated skill has a `.playbook-generated.json` manifest of managed files, hashes and modes. Builds preflight all five destinations, refuse unmarked skill directories, symlinks, path collisions and locally modified generated files, and preserve unrelated files and siblings. An obsolete generated file is removed only when it still matches its recorded hash and mode. Edit canonical sources, not generated copies. `--check` performs no writes and exits nonzero on drift or unsafe inputs. Writes are atomic per file; a whole build is not a cross-file transaction, so an interrupted build needs inspection before rerunning.

MIT. See [LICENSE](LICENSE).
