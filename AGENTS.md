# AGENTS.md — maintaining this skill package

This repository **is a skill package**, not a project using that package.

- When working in another project with an installed copy, follow that project's instructions, worker contract and task card. This file does not appoint its readers as orchestrator.
- Inside this repository, maintain the package. Do not scaffold a control plane, claim a project session or dispatch project work here unless a human explicitly requests that separate task.
- Read `docs/v3-implementation.md` before changing lifecycle behavior. It is the interface and scope contract, not authorization to operate another project.

## Layout and source of truth

| Path | Purpose |
|---|---|
| `skill-src/<name>.md` / `<name>.zh.md` | Canonical sources for five lifecycle entries; the names avoid duplicate SKILL.md discovery |
| `skills/<name>/` | Generated standalone bundles; never edit copies directly |
| `SKILL.md` / `SKILL.zh.md`, `agents/openai.yaml` | Explicit-only `orchestrator-playbook` compatibility entry |
| `scripts/playbook.py`, `scripts/playbook_work.py` | Python 3.9+ standard-library runtime and required sibling task/evidence module; invoke the CLI with `python3 -I` |
| `scripts/playbook-foundation.py` | Runtime helper for read-only foundation checks and owner-guarded create-only repairs |
| `scripts/policy-dispatch.py` | Approved worker configuration adapter for managed dispatch |
| `scripts/check-manifests.py` | Repository/CI manifest checker; not a bundled runtime dependency |
| `scripts/init-plan.sh`, `wt.sh`, `dispatch.sh` | Retained shell entry paths, with a documented legacy boundary |
| `scripts/build-skills.py` | Generator; `--check` detects drift, `--output` selects a separate skills root |
| `scripts/selftest.sh`, `tests/` | Legacy adapter checks and temporary-project runtime/packaging tests |
| `references/` | On-demand documentation; `.md` English and `.zh.md` Chinese |
| `templates/` | Planning templates; some retain Chinese `【待填】` markers for legacy scaffolding |
| `README.md` / `README.zh-CN.md` | Matching installation, first-use and limitation documentation |
| `.claude-plugin/`, `.codex-plugin/`, `.agents/plugins/` | Plugin/catalog manifests; public plugin entries select the five generated skills |
| `docs/v3-implementation.md` | Current implementation contract |

The entry names are `playbook`, `playbook-start`, `playbook-resume`, `playbook-handoff` and `playbook-takeover`. Keep both language editions in sync. Entries should stay under roughly 500 lines / 5,000 tokens; put details in bundled references. All entries must remain explicitly invoked only.

## Generation and ownership of files

The generator copies exactly the runtime scripts `playbook.py`, `playbook_work.py`, `playbook-foundation.py`, `policy-dispatch.py`, `init-plan.sh`, `wt.sh` and `dispatch.sh`, plus Markdown resources from `references/` and `templates/`. Required resources include both `work-protocol` language editions and `PROJECT-README.md`. Adding a runtime dependency requires updating the allowlist and packaging tests. Never copy the whole repository, `.git`, tests, the generator or CI tools such as `check-manifests.py` into a bundle. A single installed skill must work without siblings or a link back to this checkout.

Each generated skill's `.playbook-generated.json` records managed paths, hashes and modes. Only these recorded, unmodified files can be replaced or removed on rebuild. Unknown siblings and user files are preserved; unmarked skill directories, collisions, modified generated files and symlinks fail before the batch writes. Do not delete a user's additions or reset their local edits to force a build through. The marker is provenance for a cooperating build, not a security signature.

Run `python3 -I scripts/build-skills.py` only after canonical inputs are ready, then run `--check`. Use `--output` with a fresh physical staging path for isolated work. `--check` never writes; exit 0 means current, 1 means drift, 2 means invalid/unsafe inputs. Writes are atomic per file, not transactional across the whole batch. Do not run simultaneous builders against one output tree. Installation into a user's skill roots and network publication are separate actions, not build side effects.

## Required checks

- Back up existing scripts before editing them. Run `bash scripts/selftest.sh` after script changes; it must pass and only use temporary repositories and fake worker commands.
- Run `python3 -I -m unittest discover -s tests` for runtime and packaging changes. Tests must cover external contracts and failure paths, not merely echo implementation details. Never call real LLM clients, GUIs or paid services from tests.
- After generation, run `python3 -I scripts/build-skills.py --check` and `claude plugin validate .`. Preserve the plugin icon. Missing generated directories are a validation failure, not a passing manifest check.
- Validate isolated copies of the skills. A manifest checker does not prove native Codex/DSH discovery, login, model switching or task execution; report those limits honestly.
- Keep public files portable: no host-specific absolute paths, personal forms of address, credentials, private model routing or private tool settings. Example home-relative installation roots and public repository metadata are fine.
- Preserve root compatibility and the old shell paths. Legacy unconfigured use must not be described as v3 managed operation. No automatic upgrades, multi-machine arbitration, hard spending guarantees or raw-tool interception claims.

## Reporting

Report changed files, commands actually run and their results, including skips/failures and anything still unverified. Do not claim installation, publication, native client loading or real model execution unless that separate action was authorized and performed.
