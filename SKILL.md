---
name: orchestrator-playbook
description: Only when a human appoints you orchestrator, or .orchestrator/TEAM.md names you as holder, or you take over from a previous orchestrator. Multi-agent orchestration — one orchestrator plans, splits cards, dispatches, reviews every branch and is the only one who merges; workers run in parallel git worktrees. A dispatched worker must not act on it. 多 agent 总指挥打法：主脑计划 / 拆卡 / 派发 / 亲审 / 独家合并。
license: MIT
compatibility: Requires git, bash 3.2+, and perl (or timeout); scripts make no network calls and need no elevated privileges.
metadata:
  version: "2.0.0"
  repository: "https://github.com/sakyaroy-007/orchestrator-playbook"
  author: "Sakyaroy"
disable-model-invocation: true
---

# Orchestrator Playbook

A methodology for **one orchestrator agent plus several worker agents** on a repository project. The orchestrator plans, splits work into self-contained task cards, dispatches them to workers in parallel git worktrees, reviews every branch personally, and is the only one who merges.

Four roles: the **human decider**, one **orchestrator**, several **workers**, and the **control plane** (files in the repo). All state lives in files, so the orchestrator can change hands — another session, another model, another agent tool — without losing context.

A Chinese edition of this file is at `SKILL.zh.md`. The `references/` and `templates/` are currently in Chinese; the workflows are the same.

## §0 Start gate — read this before anything else

**You are the orchestrator only if one of these is true:**

1. the human appointed you **in this session** ("you are the orchestrator", "you run this", "dispatch the work");
2. `.orchestrator/TEAM.md` records you as the current holder **and** says to continue;
3. you are explicitly **taking over** from a previous orchestrator (the human asked for the handoff, or an unmerged `.orchestrator/<agent>` note points to you).

**If none applies, act as what you are:**

- **a dispatched worker**: read only `docs/plan/WORKER.md` and your task card; follow the worker rules. You may read this skill to understand the big picture, but you must **not** write the control plane, dispatch work, merge, or claim to be the orchestrator in any file or report;
- **a general assistant** (not dispatched, not appointed): treat this as knowledge and answer questions; do not take over the project;
- **in conflict** (TEAM.md names someone else, or `.orchestrator/` has an unmerged takeover note): report it to the human or the current holder; do not self-appoint.

⚠️ The most common failure: a worker reads this skill and starts acting as orchestrator. Two orchestrators then split the control plane. The start gate is a hard gate, not advice.

## Roles

| Role | Does | Does not |
|---|---|---|
| **Human decider** | Product / business / legal / spending decisions; external items (licenses, accounts, procurement); authorizations (dispatch, push, permissions); **appoints the orchestrator** | Relay tasks, review code (unless they want to) |
| **Orchestrator** | Inspects the codebase, plans, splits cards, dispatches; **reviews personally**; **merges and pushes exclusively**; maintains the control plane and handoff docs; turns open questions into a decision ledger | Write implementation code (by default); make the human's decisions; trust self-reports; self-appoint |
| **Worker** | Exactly the **one card** assigned: write only in its worktree, commit to its branch, add a change note, report with the template | Push / merge, edit shared docs, expand scope, guess when blocked |
| **Control plane** | Plans, board, ledger, reviews, handoff — the single source of truth | Written by workers; kept only in chat memory |

The orchestrator writes code itself only in three cases:
- core pieces where even review cannot decide correctness (then get an independent review before merging);
- interactive or privileged steps a worker cannot perform (passwords, real-hardware acceptance);
- the control plane documents themselves.

## Ten rules

1. **The control plane is the only source of truth.** Plans, cards, board, ledger live in repo files; only the orchestrator writes them. Chat messages and agent memory do not count until written back: sessions end, context compacts, orchestrators change; files do not.
2. **One card, one worktree, one branch.** Workers write only in `<repo>-wt/<card>` and commit only to `t/<number>-<slug>`. The integration branch (`main`) is merged by the orchestrator only (`--no-ff`), and only the orchestrator pushes.
3. **Cards must be self-contained and verifiable.** A worker needs only WORKER.md, the card, and the files the card lists. Acceptance is "command + expected output", never "make it better". The dispatch prompt is always one sentence pointing at files; never paste the card into chat.
4. **Do not trust self-reports.** For every returned card, the orchestrator re-runs the acceptance commands, reads the full diff, and checks for scope creep, fake tests, leaked secrets, and irreversible operations. Every "updated" claim in the change note gets verified.
5. **Review is the bottleneck, not writing.** Keep at most four implementation cards in flight. Prefer smaller cards and deeper review. High-risk cards get line-by-line review plus mutation testing: break the code on purpose and confirm the tests catch it.
6. **What you write, someone else reviews.** Before merging a card the orchestrator wrote, spawn an independent reviewer that does **not** see the orchestrator's conclusions — only the spec and the code.
7. **Decisions belong to the human.** Product, business, legal, irreversible operations, and privilege escalation go to the decision ledger with evidence, recommendation, and impact. Reversible items may proceed on the recommendation marked "pending confirmation"; irreversible ones wait. When the human changes their mind, open a new entry that supersedes the old one.
8. **Worktrees isolate files, not runtime.** Ports, daemons, real hardware, credentials, and global config are shared: serialize shared resources behind a lock, allocate ports per card, use temporary databases. A hot file belongs to one card at a time.
9. **Out-of-scope findings become new cards.** A worker who hits ambiguity, needs a product decision, or fails the same problem twice stops and reports `blocked` with the preferred option — no guessing. Two failures on the same problem means a different agent or a different model.
10. **After merging, sync docs and push immediately.** Update the board, handoff doc, README tree, ledger, and ADRs in the same session; run `git status -sb` after every merge and never leave it showing "ahead". The handoff doc must let a brand-new agent pick up in five minutes.

## Changing the orchestrator (first-class process)

The orchestrator will change: quota runs out, models change, tools change, people change. **Only the human may appoint**; an agent cannot self-appoint, and cannot delegate the appointment.

### One place records the holder

`.orchestrator/TEAM.md`, containing at least:

```markdown
# Team
- Human decider: <name>
- Current orchestrator (holder): <agent> · since <date> · state: active / handing over / acting
- Previous: <agent> (handed over on <date>)
- Worker roster: <name> | channel | default model | sandbox | strengths | known pitfalls
- Dispatch channel: <what this orchestrator can actually use>
- Authorizations: <who can be dispatched / what can be pushed / what needs the human>
```

Rules:
- **Only the human changes the holder.**
- An orchestrator may record its own takeover, but may not make itself holder without the human's appointment.
- Every change appends a paragraph from the outgoing and incoming holder; never overwrite.
- Workers read this to know whom to report to.

### Handoff ritual (outgoing orchestrator, on main)

1. **Write the handoff** in `HANDOFF.md` under "Handing over to <new holder>":
   - current wave; in-flight / in-review cards with branches and last commits;
   - unpushed commits, shared-resource lock owners, running daemons;
   - open decisions from `questions.md`;
   - **facts only in your head**: pitfalls, findings without a card, worker quirks, what to dispatch next.
2. **Move agent-private memory into the repo.** Anything in your own memory/notes that the next orchestrator needs goes into `docs/plan/notes/` (or a "project memory" section in the handoff). Agents do not share private memory; **the repo is the only shared medium**.
3. **Update TEAM.md**: holder = new holder, state "handing over".
4. **Commit and push.** An unpushed commit is an unfinished handoff.

### Takeover ritual (incoming orchestrator)

1. **Read in order**: `AGENTS.md` → `HANDOFF.md` → `docs/plan/status.md` → `docs/plan/questions.md` → `docs/plan/WORKER.md` → `.orchestrator/TEAM.md`.
2. **Verify the live state** (docs may lag):
   ```bash
   git log --oneline -15; git status -sb
   scripts/wt.sh ls
   git -C <worktree> log --oneline <main>..HEAD   # new commits on in-flight / in-review cards
   ls -t <dispatch log dir> | head                # recent dispatches and exit codes
   ```
   Check shared-resource lock owners, running processes, daemons.
3. **Pay the documentation debt first**: if the board disagrees with reality, fix the board before anything else.
4. **Check your own capabilities**: whom you can dispatch, through which channel, whether you can push, what the default model is. Differences from the previous holder go into TEAM.md.
5. **Claim the role**: TEAM.md says "<date> took over", state "active".
6. **Send the human a one-paragraph takeover report**: current wave, cards in review, blockers, decisions needed. Then enter the main loop.
7. **Do not relitigate settled decisions.** Everything marked "answered" in `questions.md` is binding.

### Acting orchestrator

- If the holder is unavailable (quota, crash, offline), the human may appoint an acting orchestrator: TEAM.md state "acting", with an end date.
- An acting orchestrator **maintains, does not expand**: finish in-flight reviews, start no new wave, change no ADR, perform no irreversible operation.
- When the holder returns, the acting orchestrator hands back and appends "what happened while acting".

### When two agents both claim to be orchestrator

1. `.orchestrator/TEAM.md` decides.
2. The unrecorded one **immediately drops to worker**: stop writing shared docs, stop merging, hand over current work in the worker report format.
3. Nobody may grab the role by editing TEAM.md — that is the human's power.

## Control plane

| File | Contents | Written by |
|---|---|---|
| `.orchestrator/TEAM.md` | Human, current holder, previous/acting, worker roster, dispatch channel, authorizations | Human changes the holder; orchestrator writes the rest |
| `.orchestrator/PLAYBOOK.md` | This methodology instantiated for the project (roles, channels, model recommendations, shared-resource locks, hot files) | Orchestrator |
| `docs/plan/README.md` | Master plan: one-pager, inspection findings, definition of done, ADR summary, epics, waves and critical path, collaboration protocol, risks | Orchestrator |
| `docs/plan/WORKER.md` | Worker rules: start steps, boundaries, quality rules, commits, report template, shared resources | Orchestrator |
| `docs/plan/tasks.md` | One-line index of all cards (owner / dependencies / size / flags / expanded?) | Orchestrator |
| `docs/plan/tasks/T-NNN.md` | Dispatchable card, with the dispatch prompt at the top | Orchestrator |
| `docs/plan/status.md` | Board, roster and dispatch rules, hot-file lock, shared-resource lock, wave exit criteria | Orchestrator |
| `docs/plan/questions.md` | Decision ledger (waiting on the human) | Orchestrator writes, human answers |
| `docs/plan/external.md` | Human's external items: lead time, latest start, what we do meanwhile, fallback | Orchestrator |
| `docs/plan/decisions/ADR-NNN-*.md` | Architecture decisions; ADR-001 is always "collaboration and branching" | Orchestrator |
| `docs/plan/reviews/T-NNN-rN.md` | Review findings, used for rework | Orchestrator / independent reviewer |
| `docs/plan/templates/` | Snapshots of card / spike / review / ADR templates, so the project does not depend on this skill | — |
| `docs/changes/T-NNN.md` | Change note: worker writes it, orchestrator syncs shared docs from it | Worker |
| Handoff doc (e.g. `HANDOFF.md`) | Current state, five-minute pickup, handoff section, known risks and unverified items, environment pitfalls | Orchestrator |
| `AGENTS.md` / `CLAUDE.md` | Stable rules: red lines, environment facts, "workers read WORKER.md first" | Orchestrator (rarely) |

- **Card states**: proposed → ready → in progress → in review → (rework → in review) → merged. Any state can become "blocked".
- **Flags**:
  - 🔴 money / auth / isolation / data safety: heavier review; tests must cover idempotency, concurrency, and authorization;
  - 🔒 shared resource: globally serialized;
  - 🏛 external item: the human handles it.
- **Sizes**: S ≤ half a day, M ≈ one day, L ≈ two days. Anything larger must be split.
- **Small projects can trim**: TEAM.md, WORKER.md, status.md, `tasks/`, `docs/changes/`, and a handoff doc are the minimum; the master plan, ledger, external items, and ADRs as needed.

## Session loop

0. **Confirm how you can dispatch here**: see the "dispatch channel" in `.orchestrator/TEAM.md`. If the machine already has its own scheduler, prefer it (record it in TEAM.md); otherwise use `scripts/dispatch.sh` or your own subagent tool.
1. **Start**: pass the §0 gate, then read TEAM.md, the handoff doc, `status.md`, `questions.md`, and verify the live state:
   - `git status -sb`: anything unpushed;
   - `scripts/wt.sh ls`: which cards are active;
   - new commits on in-flight / in-review branches; dispatch logs.
   If docs disagree with reality, fix the docs first.
2. **Collect before dispatching**: review cards in review first (`references/review.md`). Merge, sync docs, push, remove the worktree; or write `reviews/T-NNN-rN.md` and send it back to the original worker.
3. **Then dispatch**: pick cards from `tasks.md` (dependencies met, no hot-file collision, under the in-flight limit) → expand into a complete card (`references/cards.md`) → `scripts/wt.sh new <card> <slug>` → preflight → dispatch (`references/dispatch.md`) → mark "in progress".
4. **While waiting**: run dispatches in the background; do not poll. Write the next batch of cards, tidy the ledger, fold spike results into ADRs, prepare the list for the human.
5. **When a decision is needed**: write it in `questions.md`, batch them, at most three at a time, each with options and a recommendation (`references/stakeholder.md`).
6. **Wrap up**: every board row accurate; handoff doc updated; answered questions folded back; `git status -sb` not showing "ahead"; merged cards' worktrees removed.

## Bootstrap and takeover

**First use on a new project**:

1. Inspect first: run the tests yourself, each one alone and then in reverse order; read the critical paths for trust boundaries; list hard gaps with `file:line`.
2. Then scaffold the control plane:
   ```bash
   bash scripts/init-plan.sh <repo> \
        --project <name> --decider <human> --orchestrator <your name>
   ```
   The script never overwrites existing files. Before dispatching the first card, every `【待填】` (to-fill) marker in WORKER.md and status.md must be gone. See `references/bootstrap.md`.
3. Wave 0 is only "make parallel development safe".

**Taking over as orchestrator**: follow the takeover ritual above; details in `references/bootstrap.md`.

## Models and configuration (user's choice; this skill only recommends)

This skill assumes no provider, gateway, or routing service. The user chooses the models.

Recommendations:
- **High-risk cards (money / auth / isolation / data safety)**: use the strongest model you have, and review hardest (line-by-line + mutation testing). A weaker model is not disqualifying — split the card smaller, make acceptance harder, review deeper.
- **Ordinary cards**: the worker's default model is fine; no need to specify one per card.
- **With an automatic model router**: it may classify a high-risk card as easy and silently downgrade it. When unsure, specify the model explicitly.
- **Changing the model is cheaper than changing the agent**: after two failed attempts, try a different model or a different agent before rewriting the card.

## File index

| File | When to read |
|---|---|
| `references/bootstrap.md` | New project, takeover, per-session start/end checklists |
| `references/handoff-files.md` | How to write `.orchestrator/*`; handoff file checklists |
| `references/cards.md` | Splitting and writing cards, spikes, contracts, locks, rolling expansion, anti-cheat acceptance commands |
| `references/dispatch.md` | Preflight, dispatch channels, models and division of labor, collecting results |
| `references/review.md` | Review checklist, mutation testing, independent review, merge pipeline, rework notes |
| `references/stakeholder.md` | Decision ledger, external items, how to ask, reporting cadence |
| `references/lessons.md` | 19 pitfalls; skim before dispatching and before merging |
| `templates/*` | `init-plan.sh` fills the placeholders and writes them into the project; card / spike / review / ADR templates also go to `docs/plan/templates/` |
| `scripts/init-plan.sh` | Scaffold the control plane (create-only; `--dry-run` previews) |
| `scripts/wt.sh` | Worktree management: `new` / `ls` / `path` / `rm` (refuses to delete unmerged work) |
| `scripts/dispatch.sh` | Dispatcher for claude / codex / hermes / dsh: worktree, timeout, log, `--precheck` |
| `scripts/selftest.sh` | End-to-end script tests (temp repos only). Must pass after script changes |

## Improving this skill

- A **general** pitfall (any project would hit it) goes into `references/lessons.md`, one line plus the countermeasure.
- Project-specific facts belong in that project's AGENTS.md or handoff doc, not here.
- The original copy lives at `~/.agents/skills/orchestrator-playbook/` (or wherever you installed it). Back up to `~/.agents/skill-install-state/backups/` before changing scripts, then run `scripts/selftest.sh` — it must stay green.
