---
name: playbook
description: Explicit project workspace and lifecycle entry. Show the current state and next action; start, continue, hand off, take over, configure, inspect, pause, cancel or repair missing foundations on request.
license: MIT
compatibility: Python 3.9+ on POSIX; Git is optional. Legacy shell adapters additionally require bash and their documented dependencies.
metadata:
  version: "3.0.0"
disable-model-invocation: true
---

# Playbook

Use only when explicitly invoked. A bare invocation provides read-only orientation; it does not appoint a holder, create project files or dispatch workers. A dispatched worker continues its assigned card and does not become the orchestrator.

1. Read project instructions and [lifecycle](references/lifecycle.md). Resolve `PLAYBOOK_SKILL_DIR` from the loaded SKILL.md and `PLAYBOOK_PROJECT` from the user's actual target. Reuse a settled project; never infer that the user's home or this skill repository is the target. If the target is missing or ambiguous, inspect the known location read-only and collect only the missing choice.
2. Run discovery, then status/doctor if initialized:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" discover --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" status --project "$PLAYBOOK_PROJECT"
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" doctor --project "$PLAYBOOK_PROJECT"
   ```

   Compare the requested path with the canonical root. Resolve a conflicting intent, such as a requested independent subproject resolving to its enclosing repository, before mutation. Routine work inside a known repository does not need another confirmation. Report version/copy mismatches without replacing files.
3. Present a compact workspace summary in the user's language: **project and path; current state/holder relationship; blockers; one recommended next action; up to three relevant alternatives**. If a real choice remains, use the host's choice UI when available, otherwise numbered text. Do not promise a clickable menu on every client. Execute an already explicit action without asking the same question again.

   | Observed state | Recommended next action |
   |---|---|
   | No configuration | Offer start/adoption with a concrete setup recommendation |
   | Active, this session is the holder | Continue the next ready task or inspect its blocker |
   | Paused, this session is the holder | Resume when requested; disclose an incomplete recovery point |
   | Prepared, outgoing holder | Wait for reception; offer explicit withdrawal if plans changed |
   | Prepared, incoming session | Offer takeover; an explicit takeover request authorizes the claim |
   | Another active holder, no prepared handoff | Read-only inspection or ask the old holder to prepare a handoff |
   | Unknown attempts / version or evidence conflicts | Diagnose and reconcile the specific blocker first |

   An ambiguous “continue” never authorizes replacing another active holder. Runtime IDs are internal bookkeeping; obtain a prepared handoff ID from authoritative state rather than requiring the user to copy it.
4. Route the requested action through the bundled procedure:

   | Request | Procedure |
   |---|---|
   | Start / adopt | [Lifecycle](references/lifecycle.md) and [configuration](references/configuration.md); initialize, create missing foundations, complete the first bounded card |
   | Continue this session | Resume with this session's retained identity/epoch; no automatic replay |
   | Prepare / withdraw handoff | Lifecycle handoff / withdrawal; preserve work and invalidate withdrawn transfer IDs |
   | Take over | Prepared takeover or explicitly authorized interrupted recovery |
   | Change selected settings | Configuration patch; preserve unrelated values and authorization |
   | Inspect / diagnose / runtime version | Read-only status, doctor or version; no automatic repair |
   | Pause new work | Persist the pause, then checkpoint; report incomplete recovery separately |
   | Cancel one execution | Lifecycle cancellation by attempt ID; do not confuse it with pause |
   | Check / fill missing project files | [Bootstrap](references/bootstrap.md) foundation check / create-only apply; preserve existing files |

5. For any mutation use only this session's established identity and current epoch. Read the selected procedure and actual command help, parse success JSON and exit codes, and preserve conflicts. Never copy another owner's identity, rewrite TEAM.md to claim authority, or use old helpers to escape newer protocol requirements. Check [cards](references/cards.md), [dispatch](references/dispatch.md) and [review](references/review.md) before new work. Heavy verification follows completed implementation dispatch instead of nesting inside the same active job.
6. Report actual changes, retained files/results, verification, unresolved choices and the next permitted step. Distinguish installed, initialized, scaffolded, dispatch-ready, reported, accepted and integrated. After a prepared handoff, provide a short copyable incoming instruction containing the actual project path: “Use playbook to take over the prepared handoff for <project path>, retain the existing settings and inspect the next ready task.” Do not edit shared files after preparation.

All procedures and resources are bundled with this entry; sibling skills are shortcuts, not dependencies. Chinese edition: [SKILL.zh.md](SKILL.zh.md).
