---
name: playbook-takeover
description: Explicitly claim a prepared handoff as a new session, or reconcile a user-directed unprepared recovery, preserving existing tasks and results.
license: MIT
compatibility: Python 3.9+ on POSIX; Git optional.
metadata:
  version: "3.1.0-dev.1"
disable-model-invocation: true
---

<!-- Generated from skill-src/playbook-takeover.md by scripts/build-skills.py; edit the source, then rebuild. -->

# Take over a project

A prepared handoff plus the user's explicit takeover invocation appoints the designated incoming session; do not ask the same appointment again. This entry does not infer replacement authority from inactivity or a stale lock.

1. Read project instructions, [lifecycle](references/lifecycle.md), [configuration](references/configuration.md) and the configured handoff/plan/worker files. Resolve `PLAYBOOK_SKILL_DIR` from this loaded SKILL.md and `PLAYBOOK_PROJECT` from the target, independent of cwd. Use the host's file/command facilities.
2. Inspect without changing ownership:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

   Check the actual requested/canonical path, baseline, dirty work, config revision, runtime API/project-copy diagnostics, target, task records, logs and known processes. Reconcile orphaned/in-flight work and cancellation acknowledgements before new dispatch. Review content-bound acceptance and integration applicability using [structured work](references/work-protocol.md). Do not automatically upgrade copies, restart services or rerun tests. Existing files and decisions remain intact.
3. Generate a fresh ID for this new session (reuse only if this same session already created one):

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" session-id --project "$PLAYBOOK_PROJECT"
   ```

   Parse it into `PLAYBOOK_SESSION` and set `PLAYBOOK_CLIENT` to this session's client. Never copy the incumbent's identity. For a prepared handoff, set `PLAYBOOK_HANDOFF` from authoritative state/outgoing output and run:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --handoff "$PLAYBOOK_HANDOFF"
   ```

4. For an **unprepared interruption**, follow lifecycle recovery instead: require user-directed stopping/replacement, establish that the previous session is stopped, and preserve/reconcile tasks and recovery content before claiming. Only then run:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --recover --previous-stopped
   ```

   This flag is an attestation, not a fence on arbitrary shell/editor writes. If its prerequisites are missing, remain read-only and report the specific blocker. Do not delete locks or state. Failed prepared validation is not permission to silently switch to recovery.

   Only to repair an interrupted/corrupt two-file configure update, and after the user reviews the complete replacement config, set `PLAYBOOK_CONFIG` to that JSON proposal outside the project and use the explicit recovery variant:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" takeover --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --recover --previous-stopped --config "$PLAYBOOK_CONFIG"
   ```

   It privately preserves the original config/old state before repair, records the configuration revision, then checkpoints and takes over. Preserve and report this evidence; checkpoint failure still blocks takeover. Without `--config`, strict validation remains. Ordinary prepared takeover cannot override config, and a failed prepared check does not authorize silently changing policy. Follow lifecycle for the full recovery prerequisites.
5. Check success JSON and retain the new epoch. Runtime validates under a shared OS lock; machine, target, revision, baseline or recovery conflicts must remain visible. After success, update readable summaries from live state, preserve late worker results and unresolved attempts, then review before dispatching under the saved policy. Same-session repeated success is idempotent.
6. Report actual owner/epoch, baseline differences, preserved work, running/unknown tasks, verified capability differences and next steps. Do not claim native conversation resumption, cross-machine arbitration or untested model/effort settings.

Chinese edition: [SKILL.zh.md](SKILL.zh.md).
