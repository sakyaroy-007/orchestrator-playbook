# AGENTS.md — for agents working on this repository

This repository **is a skill**, not a project that uses the skill.

- If you installed this skill elsewhere and are working in some other repository, this file does not apply to you. Go read `docs/plan/WORKER.md` and the task card you were given.
- If you are working **inside this repository** (editing the skill itself), you are a maintainer here — not an orchestrator of this repo. Do not scaffold a control plane, dispatch work, or write `.orchestrator/TEAM.md` unless a human explicitly asks you to run this repository as a project.

## Layout

| Path | What it is |
|---|---|
| `SKILL.md` | The skill itself (English). `SKILL.zh.md` is the Chinese edition; clients load only `SKILL.md`. |
| `README.md` / `README.zh-CN.md` | English and Chinese READMEs; keep both in sync when changing install steps. |
| `references/` | Deep-dive documentation, loaded on demand. `*.md` are English; `*.zh.md` are the Chinese editions. |
| `templates/` | Control-plane files with `{{placeholders}}` and `【待填】` (to-fill) markers; still Chinese. |
| `scripts/` | `init-plan.sh`, `wt.sh`, `dispatch.sh`, `selftest.sh`. |
| `.claude-plugin/` | Claude Code plugin + marketplace manifests. |
| `.codex-plugin/` | Codex plugin manifest. |
| `.agents/plugins/` | Generic marketplace manifest. |

## Before you change anything

- **Scripts**: back up, edit, then run `scripts/selftest.sh` — all checks must pass. It creates throwaway repos under the system temp directory only.
- **Plugin manifests**: run `claude plugin validate .` and keep it passing (an icon warning is acceptable).
- **SKILL.md**: keep it under ~500 lines / 5,000 tokens; move detail into `references/`. If you change behavior, update both the English `SKILL.md` and `SKILL.zh.md`.
- **No host-specific content**: no absolute paths, no personal accounts, no private tooling. The repository must be usable by a stranger.

## Reporting

If you are an agent asked to modify this repository, report with: what changed, commands run and their output, and anything you could not verify.
