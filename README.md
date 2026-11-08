# Orchestrator Playbook

A skill for running a software project with **one orchestrator agent + several worker agents**.

The orchestrator plans, writes task cards, dispatches them to workers running in parallel git worktrees, reviews every branch personally, and is the only one who merges. All state lives in files inside the repository, so the orchestrator can be handed off between sessions, models, or even different agent tools without losing context.

Extracted from a real project that shipped this way for months, then generalized.

## What's inside

| Path | Purpose |
|---|---|
| `SKILL.md` | Roles, the 10 rules, the session loop, the handoff process (Chinese) |
| `references/bootstrap.md` | Start a project, take over as orchestrator, per-session checklists |
| `references/handoff-files.md` | `.orchestrator/TEAM.md` / `PLAYBOOK.md`: how to hand off cleanly |
| `references/cards.md` | How to split and write task cards, spikes, anti-cheat acceptance commands |
| `references/dispatch.md` | Preflight checks, dispatch channels, worker management |
| `references/review.md` | Review checklist, mutation testing, independent review, merge pipeline |
| `references/stakeholder.md` | Decision ledger, external items, how to ask the human |
| `references/lessons.md` | 19 hard-won pitfalls |
| `templates/` | Control-plane files with `{{placeholders}}` and `【待填】` markers |
| `scripts/init-plan.sh` | Scaffold the control plane in a repo (never overwrites) |
| `scripts/wt.sh` | One worktree per card: `new` / `ls` / `path` / `rm` |
| `scripts/dispatch.sh` | Generic dispatcher for Claude / Codex / Hermes / DeepSeek Harness CLIs |
| `scripts/selftest.sh` | 68-check end-to-end test of the scripts (temp repos only) |

`templates/` and `references/` are in Chinese; the skill works the same regardless — translate them if your team needs it.

## Install

Copy (or symlink) this directory into your agent's skills directory, for example:

```bash
# Claude Code
ln -s "$PWD" ~/.claude/skills/orchestrator-playbook
# Codex / other clients that scan a shared user root
ln -s "$PWD" ~/.agents/skills/orchestrator-playbook
```

The skill is marked **explicit-invocation only** (`disable-model-invocation: true`, `agents/openai.yaml` sets `allow_implicit_invocation: false`). It should never fire on its own.

## Quick start

```bash
# 1. Scaffold the control plane inside your repo (dry-run first if you like)
bash scripts/init-plan.sh /path/to/repo --project MyProject --decider "Your Name" --orchestrator "My Agent"

# 2. Fill the blanks
grep -rn '【待填' /path/to/repo/docs/plan /path/to/repo/.orchestrator

# 3. Create the first card's worktree and follow the printed dispatch prompt
cd /path/to/repo && scripts/wt.sh new T-001 first-card

# 4. Keep improving: scripts/selftest.sh must stay green if you change anything
```

## The start gate

Reading this skill does **not** make an agent the orchestrator. Before doing anything orchestration-related, an agent must satisfy one of:

1. the human appointed it in this session;
2. `.orchestrator/TEAM.md` names it as the current holder;
3. it is explicitly taking over from a previous orchestrator.

Otherwise it is a worker (or just an assistant), and must not write the control plane, dispatch work, or merge.

## Handing off the orchestrator role

The role changes hands often — quota runs out, models change, tools change. The procedure lives in `SKILL.md` ("换总指挥") and `references/handoff-files.md`:

1. the **human** names the new holder (agents cannot self-appoint);
2. the outgoing orchestrator writes the handoff into `HANDOFF.md`, moves private memory into the repo, updates `.orchestrator/TEAM.md`, commits and pushes;
3. the incoming orchestrator reads, verifies the live state, claims the role in `TEAM.md`, and reports back.

## Model choice

This skill does not depend on any model provider, gateway, or routing service. The user chooses the models; the playbook only recommends stronger models and heavier review for high-risk cards (money, auth, isolation).

## Requirements

`git`, `bash` (macOS 3.2 works), `perl` or `timeout`, `sed`, `awk`. No network access, no sudo, no dependencies.

## Safety

- `init-plan.sh` never overwrites existing files.
- `wt.sh rm` refuses to delete unmerged or dirty worktrees unless `--force`.
- `dispatch.sh` never widens permissions for you; anything the worker CLI needs goes after `--`.
- All tests run in throwaway repos under the system temp directory.

## License

MIT. See `LICENSE`.
