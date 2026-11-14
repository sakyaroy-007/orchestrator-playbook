# Hermes adapter implementation contract

Status: unpublished development `3.1.0-dev.1`. Extends the v3/API-2 contracts. This is package development, not authorization to alter a user's Hermes installation, profiles, plugin permissions, active gateway or business projects. Python 3.9+ standard library and POSIX remain the runtime baseline. Historical 3.0.0 release checks do not validate this change.

## Employee backend

- Keep the existing dispatch interface and project owner/epoch/revision checks. Hermes workers require the optional `hermes: {approval: inherit|approve|deny}` field; absent remains absent during configuration reads, preserving legacy hashes. Old runtimes reject the field. Native args must be empty.
- `policy-dispatch.py` selects the matched `hermes-worker.py`; `run` refuses an arbitrary Hermes viewer command as completion evidence. The worker configuration, timeout and cwd are frozen in a supervisor-created receipt before Popen. No task is submitted during a capability/help discovery.
- Use the public `hermes [--profile NAME] gateway attach --json` and canonical `hermes-gateway-v1` protocol. No internal Hermes import or extra runtime dependency; `hermes_gateway.py` implements bounded loopback-only WebSocket framing and JSON-RPC. Do not start/recover/restart an owner. Check owner/client SHA, runtime identity, durable-admission capabilities and exact session setting echoes.
- Persist attempt, create request, submission, session and admission identities and execution stamps. Store no ticket. Submit the task text once. At most one same-owner reconnect may resume/query it; a lost submit ACK may only recover through its exact pending submission identity. Refresh admission generation before handling resumed approvals. No resolve-unknown or automatic replay.
- Approval policy answers actual native requests only: `approve` sends `once`, `deny` sends `deny`, `inherit` leaves native interaction pending. Never silently imply these override profile-wide grants or child policies. No `-z`, finite/unattended, yolo, persistent approval or global configuration writes.
- Normal success requires the exact terminal completed admission, saved response and available idle live resource projections. A receipt is scoped to the admission and registered session resources, not arbitrary external descendants. Return reported work; verification/acceptance are separate.
- Cancellation sends exact admission cancel and exclusive-session process.stop; wait for terminal observations. The process supervisor permits a bounded 30-second cleanup interval, then retains unknown if the receipt cannot establish the supported scope. An interrupted observed delegation has no join proof and remains unknown. Never signal a shared gateway or guess historical PIDs.
- `status`/`doctor` expose the local external receipt. Checkpoints preserve its bytes and any existing attempt log under existing aggregate budgets, including unknown admissions. Local viewer exit or a cancel ACK cannot release unknown task/resource reservations.
- Legacy unconfigured `-z` remains available with its automatic-approval behavior documented; timeout reports the unknown gateway task state. No existing project/team copy is automatically replaced.

## Native orchestrator entries

- `adapters/hermes/` contains the plugin source and documented host contract. `build-hermes-plugin.py` builds an independent plugin using canonical entries and the shared skill builder's dependency/resource list. No extra `SKILL.md` is packaged and no skill/model tool/automatic hook is registered.
- Five synchronous command handlers check session/routing/cwd and intact resources, require current-session `ctx.ask_choice` loading consent, recheck binding, then queue canonical instructions with `inject_message`. They do not execute lifecycle operations themselves. Native metadata does not prove human invocation; the choice UI is a declared host trust dependency.
- Existing gateway-injection permission is required; never grant it in plugin code or an installation helper. Missing UI/identity/resources/permission refuses loading. Queue acceptance is not model execution. Arguments remain data, not shell source.
- Standalone build checks preserve unknown files and reject unmarked/edited outputs and symlinks. The source checkout, other installed skills and global Python packages are not runtime dependencies.

## Validation and installation boundary

Required checks are fake-gateway protocol/lifecycle regressions, fake-context plugin tests, existing Python regressions, shell selftest, regenerated skill drift checks, local manifests/native Claude manifest validation, and independent relocated bundles. Tests must never call a real LLM, install dependencies or write real client settings. Source inspection is anchored to Hermes 0.23.1 commit `3b421578588243f920886e6fe79a6faa87ea026e`; offline tests do not prove native frontend loading or actual provider execution.

Stage reviewed artifacts outside discovery roots. Ordinary five-skill installation still follows the shared skill audit/helper process; this native Hermes plugin must not be slipped into a normal skill root or installed by deleting invocation restrictions. Plugin installation/enablement and the injection grant are separate host changes. Commit, push, release and live paid pilots are not implied by this implementation.

User-facing configuration and recovery details are maintained in [English](../references/hermes.md) and [Chinese](../references/hermes.zh.md). Validation results belong in `hermes-validation.md` after checks complete.
