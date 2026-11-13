---
name: orchestrator-playbook
description: Explicit compatibility entry for Playbook project lifecycle operations. Start, resume, hand off, take over, configure, inspect or pause only when the user requests it.
license: MIT
compatibility: Python 3.9+ on POSIX; Git optional. Legacy shell adapters also require bash and their documented dependencies.
metadata:
  version: "3.0.0"
  repository: "https://github.com/sakyaroy-007/orchestrator-playbook"
disable-model-invocation: true
---

# Orchestrator Playbook

This is the compatibility name for the `playbook` router. The five explicit entries are `playbook`, `playbook-start`, `playbook-resume`, `playbook-handoff` and `playbook-takeover`. Each installed entry contains its required scripts, references and templates; this root entry also works on its own.

Use only on explicit invocation. A bare invocation provides orientation and read-only inspection, not appointment or dispatch permission. A worker remains responsible for its assigned card. When maintaining this skill repository, follow its AGENTS.md as a maintainer; do not create a control plane here merely because you read the skill.

## Execute the requested action

1. Read the target project's instructions and [shared lifecycle procedure](references/lifecycle.md). Resolve `PLAYBOOK_SKILL_DIR` to the directory of **this loaded SKILL.md**, and `PLAYBOOK_PROJECT` to the user's target, independently of cwd. Use the host's available file and command facilities; no client-specific tool is required.
2. Discover first:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" discover --project "$PLAYBOOK_PROJECT"
   ```

   For initialized projects, also inspect authoritative state:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

3. Show a compact workspace summary in the user's language: actual project/path, state and this session's role, blockers, one recommended next action and up to three alternatives. Compare requested/canonical paths before mutation. Use the host choice UI only for a real unresolved choice; numbered text is the portable fallback. Execute the already selected procedure without another confirmation. For first setup, offer a concrete recommendation and reuse settled decisions. All procedures are bundled locally; no sibling skill invocation is necessary. An ambiguous “continue” does not replace another active holder.

| User request | Execute |
|---|---|
| Start or adopt | Lifecycle “Start”: discover, [configure](references/configuration.md) with at most four question groups, initialize for real, create only missing files, plan the first task |
| Resume | Lifecycle “Resume”: use this session's retained identity/epoch; inspect changed baseline and attempts without replay |
| Handoff | Lifecycle “Checkpoint, pause and handoff”: preserve work, prepare a complete checkpoint, return handoff ID and stop managed mutations |
| Takeover | Lifecycle “Takeover”: prepared handoff plus explicit invocation is sufficient appointment; unprepared recovery has separate prerequisites |
| Configure | Read current policy and [configuration](references/configuration.md), write the agreed temporary proposal and use configure |
| Status / diagnosis | Report status/doctor evidence and unknowns read-only; do not repair automatically |
| Pause | Persist stopped new work before checkpointing; report incomplete recovery separately, retain workers |
| Withdraw handoff | Current outgoing holder uses lifecycle `handoff --cancel` before reception; invalidate the old ID and return to paused |
| Cancel an execution | Request cancellation of the selected attempt through its supervisor; retain evidence and wait for acknowledgement |
| Check / repair foundations | Bootstrap helper `check` / guarded create-only `apply`; honor configured paths and preserve existing files |
| Runtime version | Read-only `version` and doctor diagnostics; do not overwrite differing project copies |

4. For configure/pause, retain this session's own `PLAYBOOK_SESSION`/`PLAYBOOK_EPOCH`. For a partial change, `PLAYBOOK_CONFIG` is the temporary JSON patch containing only approved changes; full replacement instead uses mutually exclusive `--config`. Run only the chosen command:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" configure --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --patch "$PLAYBOOK_CONFIG"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" pause --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH"
   ```

5. Check exit status and parse success JSON before claiming a change. Runtime ownership/epoch wins over TEAM.md. Do not copy another holder's ID. Reconcile orphaned, running and unknown attempts before new dispatch. An executable, recommendation or exit 0 is not proof of login, applied model settings or acceptance.
6. Follow the lifecycle working loop within project policy; report what changed, actual verification, preserved work, what was not done and remaining gaps.

## Shared references

- [Lifecycle](references/lifecycle.md): identity, start/resume/handoff/takeover, pause, checkpoints, working loop and limits.
- [Configuration](references/configuration.md): compact onboarding, worker inheritance, permissions and Git policy.
- [Bootstrap](references/bootstrap.md) and [handoff files](references/handoff-files.md): create-only planning and durable evidence.
- [Cards](references/cards.md), [dispatch](references/dispatch.md), [review](references/review.md) and [structured work](references/work-protocol.md): bounded work, staged execution, content-bound evidence and integration.
- [Working with the human](references/stakeholder.md), [lessons](references/lessons.md), and `templates/`: decisions and reusable project files.

Unconfigured v2 shell tools remain available outside v3 ownership/checkpoint/limit guarantees; adoption is explicit. This version coordinates cooperating sessions on one POSIX machine, not arbitrary tools or multiple machines. No automatic installation, publication, native conversation resume or unverified model/effort mapping is promised. Chinese edition: [SKILL.zh.md](SKILL.zh.md).
