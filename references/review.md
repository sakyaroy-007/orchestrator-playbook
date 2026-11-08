# Review and merge

The rule is **do not trust self-reports**. A worker saying "done" does not make it done. Every conclusion in a review must rest on evidence you produced yourself.

## Review steps

1. **See the whole picture**
   ```bash
   git -C <wt> status --short                     # must be empty
   git -C <wt> log --oneline <main>..HEAD          # commits start with the card id; the last includes docs/changes/<card>.md
   git -C <wt> diff --stat <main>...HEAD           # which files changed, any scope creep
   ```
2. **Re-run every acceptance command** in the card; if a number differs, send it back. Run the full suite once more; if the card touched tests, also run each test alone and in reverse order.
3. **Read the full diff**, not just the summary. Look for four classes of problems:
   - **Scope creep**: files outside the card, shared docs, drive-by refactors, dependency changes.
   - **Fake tests**: `skip` / `xfail`, `|| true`, `try/except: pass`; deleted or weakened assertions; expected values copied from actual output; tests that never call the code under test.
   - **Secrets and residue**: tokens, passwords, debug prints, breakpoints, personal absolute paths, temp files.
   - **Irreversibility**: migrations without `downgrade`, destructive scripts, defaults that lose data.
4. **Check the change note**: every "updated"/"verified" claim gets inspected. A claim that was written but not done is itself a must-fix.
5. **Extra for high-risk (🔴) cards**:
   - **Read line by line.** For every input ask "who controls this?" — that is the trust boundary. Typical bugs: forgeable request headers; client-reported durations, times, identities.
   - **Transaction boundaries**: does shared infrastructure commit changes the caller had not committed? Do failure paths leave half-written data?
   - **Concurrency and idempotency**: run concurrency tests repeatedly; try duplicate requests, replays, out-of-order events.
   - **Mutation testing**: deliberately break one critical line (remove a lock, swap lock order, delete a validation) and confirm the tests go red; restore it and `diff` to prove it is back. A mutation the tests miss is a test gap and counts as a must-fix.
6. **The report's "findings" section**: decide for each item — new card, decision ledger, or explicitly not doing (with the reason).

## Three verdicts

- **Pass**: run the merge pipeline.
- **Fix, then merge**: write review findings, send them back to the original worker, append commits on the same branch.
- **Redo**: wrong direction. Explain why; amend the card if needed, then re-dispatch.

## Merge pipeline (do it in one go)

```bash
git -C <repo> merge --no-ff t/NNN-<slug> -m "merge T-NNN: <one line + key acceptance numbers>"
<run the full suite on main>                    # red? fix or roll back immediately; main is always green
git -C <repo> push                             # then run git status -sb and confirm it does not show "ahead"
```

Then sync docs in a separate commit titled `docs(plan): merge T-NNN`:
- `status.md`: mark merged, record the merge commit and one line of review notes with key numbers, so later readers know what was verified;
- `tasks.md`: mark the card done;
- handoff doc: current state, completed items, test count;
- root README tree, ADRs, decision ledger: apply every item from the change note's "documentation impact".

Finally run `scripts/wt.sh rm <card>`. It refuses if the branch is unmerged or the worktree is dirty.

- **Conflicts and multiple migration heads**: the orchestrator resolves them (re-point `down_revision`); never push that back to the worker.
- **Branch started from another unmerged branch**: update it to the upstream's final version, re-run acceptance, then merge.

## Rework

1. Write `docs/plan/reviews/<card>-rN.md` from `templates/review.md`, containing:
   - **Verdict**: one line on what was right and where the problems concentrate;
   - **Must fix**: location, reproduction (input, actual vs expected), and the fix;
   - **Should fix**: table form; anything deferred names the card that takes it;
   - **Not doing / reporting requirements**: commit message for the follow-up, outputs to attach, no weakening of existing assertions.
2. Send it back to the **original worker** on the same branch (rework prompt in `references/dispatch.md`); mark "rework" on the board.
3. Two failures on the same problem: different worker, different model, or the orchestrator takes over.

## Independent review

**When**: cards the orchestrator wrote, unusually risky merges, and cards you reviewed but still cannot judge confidently.

**How**:
1. Start another agent — a subagent or another worker. Give it **only the spec (card + relevant ADRs) and the code or branch**. Do not give it your conclusions or your guesses.
2. Require it to reproduce every must-fix finding, propose should-fix items, and give a verdict.
3. Decide item by item whether to accept or reject, and record the reason in the change note or review.

In the source project, independent review caught real problems twice: an idempotency comparison that ignored business fields, and a CSRF path that returned 500 on non-ASCII input, and a form parser that consumed the request body.
