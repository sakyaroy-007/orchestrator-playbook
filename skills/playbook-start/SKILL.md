---
name: playbook-start
description: Explicitly start or adopt a project, discover it read-only, collect a compact policy, initialize the current session and plan its first task without overwriting existing files.
license: MIT
compatibility: Python 3.9+ on POSIX; Git optional.
metadata:
  version: "3.1.0-dev.1"
disable-model-invocation: true
---

<!-- Generated from skill-src/playbook-start.md by scripts/build-skills.py; edit the source, then rebuild. -->

# Start a project

The user's explicit start invocation appoints this specific session when there is no incumbent. Do not ask for that appointment again. Existing holders and files must be preserved; start is not automatic permission to dispatch, commit, push or publish.

1. Read project instructions, [lifecycle](references/lifecycle.md) and [configuration](references/configuration.md). Resolve `PLAYBOOK_SKILL_DIR` from this loaded SKILL.md, and `PLAYBOOK_PROJECT` from the target project, regardless of cwd. Use the host's file/command facilities.
2. Run read-only discovery first:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" discover --project "$PLAYBOOK_PROJECT"
   ```

   Inspect existing plans, code, dirty work and legacy files. For configured projects read `status` and `doctor`; follow lifecycle resume for this same session or takeover for a different session. Do not overwrite the incumbent. CLI presence is not login or capability proof.
3. A bare invocation is enough. If the goal is missing or vague, follow configuration's goal-clarification procedure before proposing a milestone; ask one to three consequential questions per round and reuse known answers. Existing projects start from their current plans and progress. Once the first stage has an agreed outcome, scope and acceptance, present one concrete setup summary: requested/canonical project path, stage outcome, existing files to reuse, workers/settings, limits, action permissions and foundation profile (minimal by default). Collect only missing choices in at most four compact groups: goal/boundaries, workers/local work/limits, model/effort/profile, and Git/retention; these are categories, not four mandatory questionnaires. Acceptance of that concrete recommendation resolves its choices. Inherit each worker's own supported defaults. DSH has no default profile: obtain an existing noninteractive profile or explicitly propose `headless`, with model/effort inheriting that chosen profile. Reuse settled decisions. Unverified recommendations/mappings are not applied settings.
4. Write the agreed version 1 JSON to a temporary proposal outside the project, set `PLAYBOOK_CONFIG`, `PLAYBOOK_GOAL` and the current `PLAYBOOK_CLIENT`, then create this session's ID:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" session-id --project "$PLAYBOOK_PROJECT"
   ```

   Parse the returned ID into `PLAYBOOK_SESSION`; never use another owner's ID. Initialize for real:

   ```bash
   python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" init --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --client "$PLAYBOOK_CLIENT" --goal "$PLAYBOOK_GOAL" --config "$PLAYBOOK_CONFIG"
   ```

   The target directory must exist before this init command: if discovery found the requested new target absent, create that directory first after settling the target/settings. Init does not run `git init`. Append `--adopt` only for a user-requested existing-project import. Non-Git-to-Git conversion is not automatic migration; preserve the prior runtime and never create a second owner. Failure is a blocker, not permission to reset or overwrite state.
5. Read `status`, retain owner/epoch/revision, then follow [bootstrap](references/bootstrap.md): run `playbook-foundation.py check`, review create/retain/conflict results, and `apply` the agreed profile under the scaffold guard. Honor configured paths in both Git and non-Git projects, create a truthful root README when missing, and preserve all existing files. Record missing runtime dependencies or differing existing copies rather than replacing them. Complete the first card's concrete requirements, content scope, dependencies, exclusive resources and staged checks; register its structured spec and inspect readiness before dispatch. Generated drafts and unknown test commands are not ready work. A v3 worktree setup hook is reported as pending: after guard returns, follow the approved setup procedure without nesting managed runs, verify setup, then dispatch the first bounded task through [dispatch](references/dispatch.md).
6. Report the initialized project/session, actual saved policy, first task, preserved files, verification performed and unresolved gaps. Distinguish initialized, planned and launched work. The full start procedure and working loop are in lifecycle; no sibling entry is needed.

Chinese edition: [SKILL.zh.md](SKILL.zh.md).
