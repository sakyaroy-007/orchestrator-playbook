# {{PROJECT}}

{{GOAL}}

## Current stage

This project has a collaboration foundation. The first task card is a **draft**;
scaffolding does not dispatch work or establish acceptance.

- Project type: {{PROJECT_TYPE}}.
- Policy: `.orchestrator/config.json` (configuration revision {{REVISION}} when scaffolded).
- Plan: `{{PLAN}}`.
- Worker instructions: `{{WORKER}}`.
- Task cards: `{{CARDS}}` (first draft: `{{FIRST_CARD}}`).
- Handoff: `{{HANDOFF}}`.

Paths above are relative to the project root. Current ownership, permissions and
task state come from the runtime and policy, not this README.

## Build and test

- Build command: **pending** — confirm the actual project command and working directory.
- Test command: **pending** — confirm the relevant checks and their prerequisites.
- Acceptance criteria and evidence: **pending** — complete the first concrete task
  with its content scope, dependencies, resources and expected external behavior.

No build or test result is implied by these placeholders. Existing source,
project instructions and local work must be preserved.

## Collaboration

Use `python3 -I scripts/playbook.py status --project .` for current state and
`python3 -I scripts/playbook.py doctor --project .` for read-only diagnosis.
Project runtime copies are recorded in `.orchestrator/runtime-manifest.json`;
differing copies require review and are never upgraded automatically.

Read the configured worker instructions and the assigned card before making
changes. Use the current owner's approved lifecycle workflow for dispatch,
verification and handoff; an existing project is not appointed a new owner by
checking or repairing its foundation.
