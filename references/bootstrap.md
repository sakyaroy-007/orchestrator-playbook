# Bootstrap, takeover, and session checklists

## A. Starting a new project

Do these in order, and keep evidence for each step.

### 1. Get the starting decisions (Q-00)

Ask the human four things and record them as Q-00 in `questions.md`, marked answered:

- **Goal**: what counts as "done", in one sentence, and who signs off.
- **Red lines**: what will never be done, for any reason.
- **Version control**: is there a remote, private or public, who may push.
- **Dispatch**: does the orchestrator dispatch directly (which commands are allowed), or does the human relay?

Do not re-ask what the conversation or existing docs already answer; cite them instead.

### 2. Inspect (verify everything yourself; do not copy old docs)

- **Tests**: run the full suite, then **each test alone**, then **in reverse order**. Order dependencies make parallel work fail at random. The source project had 19 of 52 tests fail when run alone.
- **Build, start, smoke**: does it come up from zero? Record the real commands.
- **Credentials**: scan history for secrets, e.g. `git log -p | grep -iE 'secret|token|password|BEGIN .*PRIVATE'` (adapt the pattern). Check that credential files are gitignored.
- **Trust boundaries**: read the critical paths. Who can call this endpoint? Who supplies durations, amounts, identities?
- **Environment facts**: do workers have sandboxes, what are the default models, what is missing on this machine? These determine how cards are written.
- **Output**: write section 1 of the master plan with two parts:
  - "solid, keep" list;
  - "hard gaps" table: `# | gap | evidence (file:line / command output) | owning card`.

### 3. Scaffold the control plane

```bash
bash scripts/init-plan.sh <repo> \
     --project <name> --decider <human> --orchestrator <orchestrator> \
     [--wt-base <dir>] [--main <branch>] [--handoff <handoff file>] [--agents-md AGENTS.md] [--dry-run]
```

1. Run with `--dry-run` first. Existing files are never overwritten; if the project already has a handoff doc, point `--handoff` at it.
2. Add the printed snippet to `AGENTS.md` (or let `--agents-md` do it). Worker clients read it and learn to read WORKER.md first.
3. Fill every `【to fill】` marker:
   - **Before the first card**, WORKER.md and status.md must have none left: `grep -rn '【' docs/plan/WORKER.md docs/plan/status.md`;
   - the important ones are WORKER.md §2 "do not touch" (credential dirs, daemons, real hardware) and §3 test commands.
4. If each worktree needs its own environment (venv, node_modules, build dir), write an executable `scripts/wt-setup.sh <worktree>`; `wt.sh new` calls it automatically.
5. Commit: `docs(plan): scaffold the control plane`.

### 4. Write the master plan (`docs/plan/README.md`)

- **One page**: how far from the goal; the critical path (often external licenses, accounts, approvals, not code); rough schedule; acceptance gates.
- **Definition of done**: golden paths end-to-end; bottom lines for money / security / recoverability / compliance, each one verifiable; and an explicit **not doing** list.
- **ADRs**: only decisions that constrain multiple cards. ADR-001 is always "collaboration and branching": integration line, worktree layout, shared resources, hot files, migration rules.
- **Then**: epics (goal, exit criteria, main worker, card count), waves, critical path, risk register (trigger, mitigation, owner).

### 5. Split cards

- Put every card in `tasks.md` as one line; expand only the current wave into full cards (see `references/cards.md`).
- **Wave 0 is foundations only**: test isolation, CI, configuration, migrations, worktree tooling. The point is to make parallel work safe. Do not stack features on a red baseline.
- External items go to `external.md`; start everything that can start in week one.

### 6. Open the wave

Give the human one page: plan summary plus this week's list (unanswered questions and external items, in order). Start W0 once dispatch is authorized.

## B. Taking over as orchestrator (new agent / new session / after compaction)

1. **Read in order**: `AGENTS.md` → handoff doc → `docs/plan/README.md` §0 and the collaboration section → `status.md` → `questions.md` (everything answered is binding; do not relitigate) → `WORKER.md` → `.orchestrator/TEAM.md`.
2. **Verify the live state**; docs may lag:
   ```bash
   git log --oneline -15; git status -sb        # unpushed / uncommitted work
   scripts/wt.sh ls                             # active cards, ahead/behind, dirty worktrees
   git -C <worktree> log --oneline main..HEAD   # new commits on in-flight / in-review cards
   ls -t <dispatch log dir> | head              # recent dispatches and exit codes
   ```
   Also check shared-resource lock owners and running services.
3. **Pay documentation debt first**: if the board disagrees with reality, fix the board before anything else.
4. **Check your own capabilities**: dispatch channel; permissions (direct dispatch? push? a single exact command?); model. Record differences from the previous holder in `status.md` and `TEAM.md`.
5. **Send the human a one-paragraph takeover report**: current wave, cards in review, blockers, decisions needed. Then enter the session loop.

## C. Every session

**Start**: handoff doc → board → decision ledger → verify the live state → review before dispatching.

**Wrap-up checklist**:

- [ ] every row in `status.md` matches reality: state, commit, log path, key acceptance numbers in the note
- [ ] handoff doc "current state" and "next steps" updated with absolute dates
- [ ] today's decisions folded back into ADRs, cards, and the ledger
- [ ] `git status -sb` does not show "ahead"; control-plane changes committed
- [ ] merged cards' worktrees removed with `wt.sh rm`
- [ ] background processes you started are stopped or recorded in the handoff doc
