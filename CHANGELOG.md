# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [Semantic Versioning](https://semver.org/).

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
