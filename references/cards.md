# Writing task cards

Templates:
- implementation card: `templates/task-card.md`
- spike card: `templates/spike-card.md`

The project also keeps a snapshot under `docs/plan/templates/`.

## How to split

- **Split along contract boundaries.** One card produces one contract (function signature, table, endpoint, file format); the next card consumes it. Until the upstream card merges, downstream cards may only write mocks or contract tests — never assume the upstream implementation exists.
- **Size**: S ≤ half a day, M ≈ one day, L ≈ two days. Anything larger must be split. An L card states a "pre-planned split point" so it can be cut when it overruns. The weaker the worker's model, the smaller the card.
- **Separate risk.** Money, auth, and isolation changes do not share a card with pages or refactors.
- **Number by epic**: E1 → T-1xx, E2 → T-2xx, and so on. Spike cards use S-NN. Insertions keep the segment, so numbers never collide.
- **Out-of-scope findings become new cards.** Number them in the same segment and state in the new card's background which card found the issue.

## Rolling expansion

- Every card gets one line in `tasks.md`; only the **current wave** is expanded into full cards. Later cards depend on contracts that do not exist yet; writing them in detail now only creates stale text.
- Before dispatching an old card, **re-check it against the current code**: line numbers, file names, and contracts may have moved. Optionally put a banner at the top: "⚠️ re-verify after the prerequisite card merges, then mark ready."

## Anatomy of a good card

| Section | Content |
|---|---|
| Dispatch prompt (top) | One fixed sentence with absolute paths: read WORKER.md and this card, work in worktree X (branch Y), report with the template. Extra restrictions known at dispatch time go here too ("offline-verifiable only") |
| Metadata table | Epic / wave, worker (and model requirement), dependencies (card, merged?, starting branch), size, flags, hot-file lock |
| Background | Why now, with **measured evidence**: commands and output, `file:line`. Not conclusions alone |
| Goal | What will be true when done, one or two sentences |
| Required reading | Specific file paths; ADR sections |
| Contract | Names other cards depend on; the worker must match them exactly |
| Scope | Numbered list, fine-grained enough to execute directly |
| Not doing | Adjacent work that is tempting to do; plus "if you cannot finish without changing X, stop and report `blocked`" |
| Acceptance | Runnable commands with expected output (specific numbers), executed in the worktree |
| Extra reporting | e.g. old→new test-name mapping, preconditions added |

## Acceptance commands that resist cheating

- **Be specific**: "expected: 52 passed", not "tests pass".
- **Tests may not shrink or weaken**: test count no lower than before; assertion count no lower, e.g. `grep -c -E '^\s*assert ' tests/*.py`.
- **Tests must be truly isolated**: each one alone and in reverse order must be green. Any card that edits tests must include this.
- **Structural invariants**: exactly one migration head; `git status --short` empty; `grep` for forbidden patterns returns 0 (e.g. `float` in money code).
- **Doc / research cards**: file exists; section count and source-link count above a floor.
- **🔴 cards**: name the three test cases — idempotency (duplicate request takes effect once), concurrency (multi-threaded result exact), authorization (another user's resource returns 401 / 403 / 404).

## What the flags mean

- 🔴 **High risk** (money / auth / isolation / data safety):
  - the three test classes above are mandatory;
  - the orchestrator reviews line by line and runs mutation tests;
  - when needed, the orchestrator writes it and an independent reviewer checks it.
- 🔒 **Shared resource** (real hardware, production or daemon services, global config):
  - globally serialized; take the lock first;
  - the card lists, **item by item**, the allowed operations and the restore checklist: back up before, restore after, then delete the backup;
  - steps needing a password or interactive confirmation are explicitly left to the orchestrator or the human.
- 🏛 **External item**: the human handles it; record it in `external.md`.

## Hot files and migrations

- **Hot files**: route registration, shared schemas, model exports, dependency manifests, main loops, migration directories. One card at a time. Record the owner in `status.md` and in the card's metadata.
- **Database migrations**: at most one new revision per card. If parallel branches collide, the orchestrator re-points the new revision's `down_revision` at the current head during merge, so the main branch always has exactly one head.
- **Local services**: use port "base + last two digits of the card number"; use a temporary database or directory; never touch a daemon service.

## Spike cards (S-NN)

For technical uncertainty whose answer would change the architecture.

- **Write it as a list of questions to answer.** Every answer needs measured evidence (command + output); citing docs is not enough. Measurements routinely overturn docs.
- **Time-boxed**: size S; when time runs out, deliver what is already established.
- **One document only**, containing:
  1. verdict summary: one line per question, marked feasible / infeasible / feasible with conditions;
  2. evidence per question: at most 15 lines each;
  3. recommendation for the ADR;
  4. restore checklist.
- **After merging**: fold verdicts into the ADR; turn discovered problems into new cards.

## Branch starting point

By default, cut from the integration branch at dispatch time.

When a card must build on an unmerged branch (e.g. it needs a function the upstream card just wrote):
1. create the worktree with `wt.sh new <card> <slug> --from <upstream branch>`;
2. note the starting point in the card and on the board;
3. before merging, update it to the upstream's final version and re-run acceptance.
