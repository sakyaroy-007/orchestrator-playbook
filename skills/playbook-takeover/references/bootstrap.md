# Bootstrap and session checklists

Use [lifecycle](lifecycle.md) for authority and commands, and [configuration](configuration.md) for the four setup question groups. Bootstrap follows successful runtime initialization; it does not appoint a holder by writing files.

## Inspect an existing or new project

Start with read-only discovery and project instructions. Record the actual Git HEAD/branch/worktrees and dirty/untracked state, or a non-Git baseline description. Read existing plans and settled decisions before asking anything. Keep the evidence split into observed facts, unverified claims and gaps.

Choose initial checks according to the intended change and project policy:

- Run the relevant baseline tests/build/smoke checks only when authorized; record exact commands, cwd, exit status and actual output. A failed baseline remains visible.
- Test isolation/order when tests share state, parallel work is planned, or evidence suggests a dependency. Run affected tests alone or in reversed/randomized order as justified; do not require every test in every order for every project.
- Inspect the relevant trust and transaction boundaries. Check whether credential paths are ignored without printing their values or dumping secret-bearing history.
- Distinguish discovered client executables, verified adapter capability and authentication readiness. A capability recommendation is not an observation.

Write the plan's findings as “keep” and “gaps”, each with evidence location and a proposed owning card. Unrun checks are listed as gaps, never passes.

## Create or repair only missing foundations

After successful `init`, use normalized configuration `paths` for the plan, worker rules, cards and handoff. Existing-project adoption first identifies which files to reuse and any conflicting conventions. Preserve existing README, AGENTS, plans, handoff and source. Existing content needing changes becomes scoped follow-up work, not an implicit replacement.

Use the bundled foundation helper for both Git and non-Git projects, including custom paths. `minimal` is the default: a truthful project-root README, configured planning/worker/handoff files, first-card draft and required runtime copies. `standard` adds the board, decisions and review resources. Choose standard only when useful to the project; the number of files does not establish readiness.

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook-foundation.py" check --project "$PLAYBOOK_PROJECT" --profile minimal
```

Report create/retain/conflict results, including differing existing helpers. A new independent project inside another Git repository must not silently become that enclosing repository. Resolve the target before applying. For explicit start or a requested missing-file repair, use this session's retained identity/epoch:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook-foundation.py" apply --project "$PLAYBOOK_PROJECT" --profile minimal --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
```

Apply enters the runtime scaffold guard. It checks current ownership and active state, preflights targets and only creates missing files. It never overwrites a file that appeared after preview. Symlink escapes and conflicting targets are blockers. The runtime source/hash manifest supports version diagnosis; it is not permission to upgrade an existing copy. Do not set recursion markers manually. Scaffold metadata for explicit start/repair needs no duplicate permission prompt and grants no dispatch, dependency-installation or Git permission.

The same `check`/`apply` flow supports “check collaboration files” and “fill missing files” from the main entry. Check is read-only and does not appoint a session. An uninitialized project must start/adopt first. A paused/prepared or different-owner project follows the lifecycle rules before writing. The old `init-plan.sh --dry-run` and create-only path remain available for legacy/default Git layouts; do not use `--agents-md` to rewrite instructions during adoption.

Generated first-card content is a draft. Complete the real goal, acceptance criteria, content scope, dependencies, exclusive resources, actual commands, current baseline, policy reference and reporting destination. Explicitly assign lightweight checks to the implementation worker and heavy/shared checks to owner-scheduled verify after dispatch ends. Register the completed structured spec and check readiness. Unknown commands or unresolved placeholders remain blockers; do not invent results to remove them.

A configured `wt.sh new` only creates the worktree inside guard; executable `scripts/wt-setup.sh` is reported as `setup pending`. After guard returns, follow the approved setup procedure in [dispatch](dispatch.md), without nested managed runs, and verify completion before implementation dispatch. Installing dependencies or starting services is not an implicit bootstrap action.

## Plan the first useful work

- Write a short goal/definition of done and an explicit scope boundary. Reuse the configured plan path and existing decisions.
- Use ADRs only for choices spanning cards; record collaboration/branching policy where needed without overriding config.
- Keep a one-line backlog, expand only the next ready cards against the current code, and name their contract/acceptance; see [cards](cards.md).
- Make collaboration foundations the first card only when they block safe progress. Existing red tests need a recorded cause and disposition; do not claim the baseline is green or blindly stack dependent work on it.
- Non-Git projects use one active operation and local snapshots, not fake branch/worktree instructions. The orchestrator may implement a bounded task; choose review according to impact and policy.

## Resume, takeover and close

Resume is only for the same owning session; takeover follows prepared handoff or explicit recovery. Read the configured handoff, board, ledger and worker rules, then compare with runtime `status`/`doctor`. Check orphaned and in-flight work before new dispatch. Do not start services or rerun tests merely because a new session began.

Before closing while still owner:

- Reconcile board rows with actual attempts, commits, dirty state, logs and acceptance evidence.
- Record baseline, config revision, absolute date, next steps, unresolved decisions and known background processes.
- Keep commits/pushes/retention consistent with project policy; unpushed work is allowed when documented.
- Preserve dirty/unmerged/running/unknown/evidence-bearing worktrees; cleanup requires its own checks and permission.
- Checkpoint, pause or hand off through the runtime as appropriate. Do not edit shared files after handoff becomes prepared.
