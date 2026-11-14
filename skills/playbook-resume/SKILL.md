---
name: playbook-resume
description: Explicitly resume the current owning session, inspect baseline changes and recorded work, and continue without taking another session's role or replaying jobs.
license: MIT
compatibility: Python 3.9+ on POSIX; Git optional.
metadata:
  version: "3.1.0-dev.1"
disable-model-invocation: true
---

<!-- Generated from skill-src/playbook-resume.md by scripts/build-skills.py; edit the source, then rebuild. -->

# Resume this session

1. Read project instructions and [lifecycle](references/lifecycle.md), especially identity and resume. Resolve `PLAYBOOK_SKILL_DIR` from this loaded SKILL.md and `PLAYBOOK_PROJECT` from the user's target, independent of cwd. Use the host's file/command facilities.
2. Inspect authoritative state without mutation:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

   Read current config, configured handoff/plan/worker paths, board and settled decisions. If uninitialized, explain the start procedure in lifecycle; do not initialize as a side effect of resume.
3. Use **this session's previously retained** `PLAYBOOK_SESSION` and `PLAYBOOK_EPOCH`. The same client/model is not the same session. Do not obtain authority by copying the holder's identity from status or TEAM.md. If this is a new session or another owner exists, remain read-only and follow the user-requested takeover procedure in the bundled lifecycle reference.
4. Resume only the matching owner:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" resume --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
   ```

   Parse success JSON; a stale epoch or ownership conflict stops managed mutations. Resume may reactivate this owner's paused state; it does not replay dispatches or tests.
5. Compare baseline/worktrees/dirty files, logs and task records. Reconcile orphaned, reserved, running and unknown attempts and pending cancellation acknowledgements before a new launch. Inspect runtime API/project-copy differences and incomplete checkpoints without automatically overwriting or upgrading. Keep existing results and settled choices. Read [dispatch](references/dispatch.md), [review](references/review.md) and [structured work](references/work-protocol.md): recheck receipt applicability and readiness, finish implementation before heavy verification, and require applicable acceptance/integration evidence for structured tasks.
6. Report the current owner/epoch, changes since the checkpoint, tasks still in flight, unknowns, what was not rerun and the next permitted step. A resume success is not a claim that past tests remain current.

Chinese edition: [SKILL.zh.md](SKILL.zh.md).
