# Lessons from real runs

Format: pitfall → countermeasure. Skim before dispatching and before merging. Append new ones at the end.

1. **You think you dispatched a strong model; the default cheap one ran.** → Check the log after dispatching to see the model actually used. Do not gamble a high-risk card on a difficulty-based auto-router.
2. **A one-shot worker hits an interaction (sudo password, authorization dialog) and exits.** → State "offline-verifiable only" in the card; leave interactive and privileged steps to the orchestrator or the human. Decide who runs that step before dispatching.
3. **Merges stopped being pushed; twelve commits piled up.** → After every merge run `git status -sb`; it must never show "ahead".
4. **A change note claims "updated" but nothing changed.** → Verify every claim during review; a false claim is itself a must-fix.
5. **A branch started from another unmerged branch, and the upstream was reworked later.** → Record the starting point on the board; update to the upstream's final version and re-run acceptance before merging.
6. **An app's branch picker checked out in the main repo, or created its own worktree.** → Only use dispatch methods that take an explicit working directory; preflight pwd and branch before every dispatch.
7. **Tests had order dependencies: 19 of 52 failed alone.** → During inspection run each test alone and in reverse order; fix it before starting parallel work.
8. **Worktrees isolate files, not runtime: two service instances under one user, and a bare `pkill -f <name>` killed the wrong one.** → Always match processes by full path; lock shared resources globally; allocate ports per card.
9. **zsh aborts on an unmatched glob and kills the whole `&&` chain**, so a background service never started. → Quote `*`, `[`, `?` in arguments; keep globs out of start commands; delete temp files by exact name or `find … -delete`.
10. **Workers have no sandbox** (full access, or approvals auto-approved). → Boundaries rest on WORKER.md prohibitions and shared-resource locks. Name credential dirs, daemons, and system settings one by one; rotate any secret a worker could have seen before release.
11. **A worker's report pointed out something review missed.** → Keep a "findings" section in the report template and read it. Turn out-of-scope findings into new cards; several critical fixes came from here, including a P0 security hole.
12. **The human changed a rule mid-day; two versions coexisted.** → Open a new ledger entry that supersedes the old one; change the board rules, master plan, and worker rules in the same commit.
13. **Editing a running dispatch script broke it** (sh re-reads the script from disk). → Only replace scripts atomically: write a temp file, then `mv`; back up first.
14. **Starting an agent without written rules got blocked by a safety classifier.** → Write WORKER.md boundaries first. Do not switch launchers to get around a block.
15. **The documented start command was stale and failed when followed.** → When docs disagree with reality, fix the docs first. At phase close, run a consistency scan: dead links, stale status, directory tree vs disk.
16. **The two most common high-risk bugs are trust boundaries and transaction boundaries.** Examples: client IP taken from a forgeable header; shared infrastructure committing the caller's uncommitted changes. → Always ask two questions on a 🔴 card: "who controls this input?" and "whose changes does this commit carry?"
17. **A conclusion inferred from docs was overturned by measurement.** → For any decision that changes architecture, run a spike and let commands and output speak.
18. **Large cards given to weak models have a high rework rate.** → Split smaller; have the orchestrator write the contract tests first; write core pieces yourself and hand them to an independent reviewer.
19. **macOS's bundled bash 3.2 swallows non-ASCII characters that follow `$var` into the variable name.** With `set -u` this raises `unbound variable`; without it the value silently becomes empty. → Always write `${var}` when non-ASCII text follows. Find leftovers with: `LC_ALL=C grep -nE '\$[A-Za-z_][A-Za-z0-9_]*[^ -~]' *.sh`.
