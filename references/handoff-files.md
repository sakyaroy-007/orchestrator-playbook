# `.orchestrator/`: files that make handoffs work

The orchestrator changes hands: quota runs out, models change, tools change, people change. Good files turn a handoff into minutes; bad files force the next orchestrator to re-investigate everything.

## Layout

```text
.orchestrator/
├── PLAYBOOK.md      # this methodology instantiated for the project
├── TEAM.md          # holder, human, worker roster, authorizations
└── <agent>          # optional: a takeover note/branch name (unmerged = pending takeover)
```

## `TEAM.md`

Minimum content:

```markdown
# Team

- Human: <name>
- Current orchestrator (holder): <agent> · since <YYYY-MM-DD> · state: active / handing-over / acting
- Previous: <agent> (handed over on <YYYY-MM-DD>)
- Acting: <agent> (<from–to>, maintain only, do not expand)

## Worker roster

| Name | Channel | Default model | Sandbox | Strengths | Known pitfalls |
|---|---|---|---|---|---|
| codex | dispatch.sh codex | worker default | workspace-write | repo refactors, tests | sandbox needs the repo's .git |
| claude | dispatch.sh claude | session model | per --permission-mode | long context, review | interactive by default; needs -p |
| hermes | dispatch.sh hermes | worker default | auto-approve in one-shot | real hardware, provider | exits on a sudo password prompt |
| dsh | dispatch.sh dsh | DSH config | headless | Chinese material, research | `-m` takes provider/model |

## Dispatch channel

- What this orchestrator can actually use: dispatch.sh / subagents / human relay / chat
- Preflight: `scripts/dispatch.sh <worker> <worktree> --precheck`
- Log directory: <path>

## Authorizations

- Can dispatch directly: <who>
- Can push: <exact command, or "only the human">
- Needs the human: <privilege escalation, external accounts, irreversible operations>
```

Rules:

- **Only the human changes the holder.**
- An orchestrator may record its own takeover but may not make itself holder without appointment.
- Every change appends paragraphs from the outgoing and incoming holder; never overwrite.
- Workers read this to know whom to report to.

## `PLAYBOOK.md`

This skill's method **instantiated** for the project: roles, who gets dispatched, which models, which shared resources need locks, which files are hot. It is the first material the next orchestrator reads — not a copy of this skill.

Suggested sections:

1. Roles and holder (point to TEAM.md)
2. Dispatch channel and preflight
3. Model recommendations (high-risk vs ordinary cards)
4. Shared resources and locks (ports, daemons, hardware, credential dirs)
5. Hot files and migration rules
6. Project-specific red lines

## Handoff checklist (outgoing orchestrator)

- [ ] `HANDOFF.md` has a "handing over to <new holder>" section
- [ ] in-flight / in-review cards: branch, last commit, what remains
- [ ] unpushed commits, shared-resource lock owners, running background processes
- [ ] unanswered `questions.md` items
- [ ] **facts only in your head**: pitfalls, findings without a card, worker quirks, what to dispatch next
- [ ] project-related entries from agent-private memory copied into `docs/plan/notes/`
- [ ] `TEAM.md` holder updated, state "handing-over"
- [ ] committed and pushed

## Takeover checklist (incoming orchestrator)

- [ ] read in order: AGENTS.md → HANDOFF.md → status.md → questions.md → WORKER.md → TEAM.md
- [ ] verify live state: `git status -sb`, `scripts/wt.sh ls`, branch commits, dispatch logs, processes
- [ ] pay documentation debt (fix the board before anything else)
- [ ] check your capabilities and record them in TEAM.md
- [ ] claim the role: TEAM.md says "took over", state "active"
- [ ] send the human a one-paragraph takeover report
- [ ] do not relitigate answered decisions

## Preventing two orchestrators

- `TEAM.md`'s holder wins.
- The unrecorded party immediately drops to worker: stop writing shared docs, stop merging, hand over work in the worker report format.
- Nobody may grab the role by editing TEAM.md — that is the human's power.
- If `.orchestrator/` has an unmerged takeover note or a different holder: report it, do not self-appoint.
