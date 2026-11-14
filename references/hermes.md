# Hermes adapter

Hermes can deliver work as an employee without installing any of the five orchestrator entries. Its native command plugin is a separate integration. This adapter targets the public gateway protocol inspected in Hermes 0.23.1 (`3b421578588243f920886e6fe79a6faa87ea026e`); live model execution and frontend plugin loading are separate validation steps.

## Managed employee configuration

Select the worker through the normal project configuration flow. A concrete example is:

```json
{
  "id": "hermes-worker",
  "client": "hermes",
  "model": {"mode": "inherit"},
  "effort": {"mode": "inherit"},
  "hermes": {"approval": "inherit"},
  "args": []
}
```

The optional `profile` selects an existing Hermes profile through `hermes --profile NAME gateway attach --json`. Without it, Hermes resolves its own current/default profile. The bridge never edits profile configuration, installs dependencies, starts/restarts a gateway, or passes `--start`, `--recover`, `-z`, `yolo` or `unattended`. A selected profile must already have a ready gateway. Hermes's native launcher may perform its own bootstrap maintenance; an attach is not advertised as a side-effect-free discovery probe.

`model.mode:fixed` maps to `session.create.model`; `effort.mode:fixed` maps to the native `reasoning` value. The bridge checks the actual owner's advertised capabilities/creation parameters, requires matching client/owner code SHA, and verifies session profile, cwd and requested setting echoes before submitting a task. An accepted echo establishes configuration selection, not provider availability or the model's actual reasoning behavior. Unsupported values fail; no cross-provider translation is invented. `recommend` must be resolved first. Managed Hermes `args` must be empty: CLI escape hatches cannot silently change this protocol.

Old worker records stay readable without changing their hashes. Dispatch requires an explicit `hermes.approval` selection; it does not reinterpret the old `-z` choice as permission for a new transport. Older Playbook runtimes reject this new worker field. Update matched runtime resources deliberately, preserving existing project copies and local changes.

| Approval response policy | Behavior |
| --- | --- |
| `inherit` | Preserve profile behavior. Leave a native approval request unanswered; the receipt exposes `waiting_approval` for user resolution in Hermes. Unresolved waits remain subject to the task timeout. |
| `approve` | Answer an actual native approval request with `once`; never persist `always` or session-wide approval. |
| `deny` | Answer an actual native approval request with `deny`. |

These policies govern **requests Hermes emits**. They do not override profile `approvals.mode:off`, existing native grants, hard denials, or child-task policies. `deny` is not a sandbox or a promise that every tool action is forbidden. Configure Hermes itself if stronger native restrictions are needed; the package does not grant or weaken host permissions. Project `permissions.dispatch` remains independently required.

## Identity, completion and cancellation

The runtime reserves an attempt and writes `logs/ATTEMPT.hermes.json` before launching the bridge. The bridge persists unique create/submission IDs before sending the task and saves session/stored-session IDs, admission ID, owner instance/profile/code SHA, authority epoch and generation as received. Tickets remain only in memory. `status`/`doctor` expose `external_receipt` and its current `external_execution`; the regular attempt log contains the saved final response and errors. An explicitly supplied `-l` log is an additional exclusive-created copy.

Each attempt owns a fresh session. Normal completion requires the exact admission's terminal receipt, its saved result, and available live projections with no listed subagents and no running registered processes. A successful dispatch still becomes only `reported`; acceptance requires the existing verification/evidence workflow. The receipt labels its scope `admission-and-live-session-resources` and `entire_task_tree_proven:false`. This does not prove that arbitrary unregistered external jobs, side effects or all possible descendants have ended.

`playbook cancel --attempt ...` remains a request to the live supervisor. For Hermes, the bridge sends `prompt.cancel` for the exact admission and `process.stop` for its exclusive session, then polls the receipt and resources. The supervisor allows up to 30 seconds of cleanup after its deadline/request. The gateway itself is never killed. A cancellation ACK is not completion; observed delegation interruption without join proof, unavailable projections, unknown outcomes or failed cleanup leave the attempt `unknown`, retaining its slot/worktree/resource claims. Killing the local bridge cannot supply a missing terminal receipt.

One bounded reconnect attaches to the same owner, resumes the saved session and queries the original admission. If a submit ACK was lost, only an exact pending `input_id == submission_id` match may recover it. The task text is never resubmitted. An owner/authority change or unrecoverable identity remains unknown. No automatic `prompt.resolve_unknown` or retry releases the reservation. If the supervisor is lost, inspect the saved IDs in Hermes and reconcile explicitly under current Playbook ownership; never infer completion from elapsed time or the viewer's PID.

Unconfigured legacy `dispatch.sh hermes` retains the existing `-z` employee path, including native automatic approval. Its timeout now reports an unknown gateway task state. It has no admission ledger or managed cancellation guarantee. Existing project copies and custom team scripts are not rewritten by this package update.

## Five native orchestrator commands

Build the native plugin with `scripts/build-hermes-plugin.py --output /physical/staging/orchestrator-playbook`; see the source repository's `adapters/hermes/README.md` for the complete host contract. Do not link the ordinary five skill directories into Hermes: 0.23.1 does not enforce their invocation-policy metadata.

The plugin registers only the five familiar commands, reuses the canonical English/Chinese entries and runtime resources, and contains no discoverable `SKILL.md`. It registers no model tool or automatic hook. The current native command context lacks a verified human-origin marker, so each invocation requires the current session's choice UI to select **Load** before instruction injection. Cancellation, missing UI, mismatched session/cwd and denied injection refuse loading. This trusts the host's bound UI; it is not protection against arbitrary same-user code.

Gateway/TUI injection requires the existing operator-owned `plugins.entries.orchestrator-playbook.allow_gateway_injection: true` permission. The plugin never sets it. Building, file installation, plugin enablement, command discovery, message queueing and actual model execution are distinct facts. Offline fake-context and local fake-gateway tests prove only their stated contracts; native installation/activation and a live paid pilot require their own authorized validation.
