---
name: playbook-handoff
description: Explicitly prepare a local handoff from the current owner, preserving dirty and in-flight work in a complete checkpoint before stopping managed mutations.
license: MIT
compatibility: Python 3.9+ on POSIX; Git optional.
metadata:
  version: "3.0.0"
disable-model-invocation: true
---

# Prepare a handoff

1. Read project instructions, [lifecycle](references/lifecycle.md) and [handoff files](references/handoff-files.md). Resolve `PLAYBOOK_SKILL_DIR` from this loaded SKILL.md and `PLAYBOOK_PROJECT` from the target, independent of cwd. Use the host's file/command facilities.
2. Inspect state and diagnostics:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

   Use only this session's retained `PLAYBOOK_SESSION`/`PLAYBOOK_EPOCH`. Another owner is a conflict, not permission to hand off on its behalf.
3. Reconcile recorded attempts with logs, branches, dirty/untracked work and known processes. Preserve orphaned and unknown results; missing notifications do not prove completion. Coordinate a stable snapshot without killing unrelated processes. Record running workers, shared resources, unpushed commits, baseline, config revision, open decisions, evidence gaps and next steps in the configured handoff document. Copy only relevant project memory.
4. Finish those document edits **before** preparing the checkpoint. Git-ignored untracked files are not captured: explicitly archive needed ignored evidence within authorized scope into a covered location first; cleanup still refuses ignored work. An unmerged index or dirty submodule is rejected; special files or size/read failures can also leave partial recovery data. Preserve it and report failure instead of claiming completeness. Save the needed contents of all conflict stages and resolve conflicts before normal handoff; do not erase stage contents just to pass the check. Do not mark the incoming session as owner. Run:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" handoff --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
   ```

   If a concrete incoming session ID is already known, append `--to "$PLAYBOOK_NEXT_SESSION"`; do not substitute a model/client name. The command creates a complete checkpoint before `prepared`. Oversized, unreadable or changing recovery content is a blocker, not a successful handoff. Follow lifecycle for a failed checkpoint; never drop files to make it appear complete.
5. On success, parse and return the handoff ID, target and checkpoint facts. Stop managed mutations and dispatch, including further shared-document edits. Repeating the same handoff is idempotent. Commit/push and worktree retention follow project policy; local handoff does not require a remote push.
6. Tell the user what is preserved and still running/unknown. Give a copyable instruction with the actual project path: “Use playbook to take over this project's prepared handoff, retain the current settings and inspect the next ready task.” The incoming session reads IDs from authoritative status; its explicit takeover invocation needs no duplicate appointment confirmation. Report unperformed steps and never claim reception already happened. If the user withdraws before reception, follow lifecycle `handoff --cancel` as the outgoing owner: preserve evidence, invalidate the old ID, return to paused, then resume or prepare again only as requested.

Chinese edition: [SKILL.zh.md](SKILL.zh.md).
