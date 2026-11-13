# v3 pilot protocol

This is a reproducible trial plan, not a claim that live model work has run. Offline regressions and client discovery do not demonstrate live authentication, reasoning settings or successful cross-client work. Keep trial receipts outside the repository and record each actual result.

## Offline assembled-flow trial

Use a fresh temporary Git project, local fixture commits and fake worker commands. Give it an explicit test-only policy: two agent slots, one heavy verification slot, short deadlines, and no push. The project is a fixture, never this skill repository or another ongoing project.

Exercise this sequence using the final standalone bundle:

1. Discover, initialize, inspect the actual stored policy/version, check minimal foundations and apply them with the current holder. Check again to show create-only idempotence. Retain a pre-existing README unchanged in a separate adoption case. Exercise a non-Git project and custom paths separately.
2. Register two bounded independent task specs with explicit requirements, content scopes and resource declarations. Launch two fake implementation workers in distinct Git worktrees. Preserve a completion receipt for each. Require a deliberately conflicting exclusive declaration to be rejected before a child runs.
3. After implementation ends, run managed verification against each task. Keep `heavy_jobs=1`; a second simultaneous heavy job must not overlap. Queue/retry only after the recorded first job finishes, keeping the stable task ID and actual attempt history.
4. Record applicable structured acceptance evidence. Change relevant content and demonstrate that the old evidence cannot accept it; preserve the old receipt and rerun the affected verification. A pure mtime change must not invalidate identical content. Attempt a note-only acceptance of a structured card and require rejection.
5. Begin an integration record, integrate only the fixture branches through the authorized path, verify the assembled target and finish its acceptance. Demonstrate a changed target or failed assembled check cannot reuse an earlier passing result. Report actual merge facts separately from overall acceptance.
6. Prepare a handoff, verify that outgoing managed writes are blocked, and claim it with a different simulated session identity. Continue using the retained policy and evidence without launching implementation again. Also cover withdrawal before reception, failed checkpoint with persisted pause, and cancellation of only one selected process group.
7. End paused, retain test receipts and report the exact number of executed checks, commands, failures, skips and exclusions. Do not turn a successful fixture into a claim about live client conversations.

Run the assembled offline regression from a reviewed checkout:

```bash
python3 -I -m unittest discover -s tests -p test_offline_pilot.py -v
```

It generates an isolated bundle and executes that bundle's real CLI with fake workers. To retain command receipts outside the repository, set `PLAYBOOK_OFFLINE_PILOT_ARTIFACTS` to an explicitly chosen physical directory before running it; otherwise the test cleans up its temporary data. The combined flow and focused failure cases are complementary: `test_runtime_next.py`, `test_work_protocol.py`, `test_dependency_baseline.py` and `test_foundation.py` exercise lifecycle races, stale evidence, actual consumer baselines and create-only edge cases. Do not count those as executed by the assembled test unless they were actually run separately. The portable [pilot result](v3-offline-pilot-result.json) records the tested hashes and exclusions.

## Opt-in live-client trial

Before starting, settle a small invocation scope and any service budget with the user. The following is a concrete proposed workload; it has not itself been approved for model billing. Command discovery/help is separate from paid execution. If the client cannot enforce a monetary budget, report that limit rather than translating wall time or call count into a hard cost cap.

- Use a fresh disposable project implementing a tiny Python standard-library CSV reporting tool. Do not send existing private project content.
- Card A implements parsing and validation, with fixtures for quoted fields, missing required columns and malformed rows.
- Card B implements deterministic rendering against a written row-data contract, with empty-input and ordering cases. A and B own separate files; the contract is fixed before parallel implementation.
- The holder schedules local verification after implementation. An independent review call examines both diffs and actual evidence. Integration and assembled tests use the authorized local workflow.
- Prepare a handoff, then an explicitly appointed incoming client conversation reads the bundle, claims it, reports retained tasks/settings/evidence and continues the next permitted local check. This is an additional model invocation when automated through a CLI.

Proposed maximum: two implementation invocations, one independent review invocation and one incoming-holder invocation, at most two simultaneously and a five-minute process deadline per invocation. No automatic retries, push, publication or deployment. Select the actual clients, models/profiles and permissions before execution; do not silently choose a DSH profile or broaden a client's permissions. User authorization may choose a smaller trial or leave this live phase unrun.

Record the exact approved scope separately from the proposed one. A capped invocation count/deadline still does not guarantee a spending amount. If a real client cannot perform its assigned work within the allowed noninteractive capabilities, report the blocker and preserve the partial results rather than changing its global configuration.

## Measurements and acceptance

| Measurement | Record |
|---|---|
| Environment and versions | OS, Python/Git/client versions, active runtime API and hashes, foundation profile |
| User decisions | Goal, client/settings choices, action permissions, actual approval scope, repeated questions |
| Execution | Actual worker/task/attempt IDs, command/cwd, start/end times, return status and log path |
| Concurrency | Implementation overlap, heavy-job overlap, exclusive-resource rejection before launch |
| Quality | First acceptance result, required rework, stale-evidence detection, assembled result |
| Recovery | Pause/handoff/takeover elapsed time, retained dirty work, repeated launches, unknown work |
| Settings | Requested model/effort/profile versus any settings actually reported by the client; unknown stays unknown |
| Cost | Provider-reported usage/cost when available; otherwise unavailable, never assumed zero |

Success requires preserved user/fixture files, no unauthorized launch or Git action, no duplicate work on takeover, no overlap beyond declared managed limits, and acceptance bound to the tested result. Also record how many user interventions were necessary. A failed trial is useful evidence; do not delete it or reduce its criteria to obtain a pass.

## Interaction walkthrough

These are behavioral review scenarios, not assertions that all clients expose the same UI:

- Bare `playbook` in an unspecified directory: show orientation and ask only for the unresolved project/action; create nothing.
- Known project, same active holder: present the next ready task and blockers, reuse settings, do not replay completed work.
- Same paused holder: offer resume, including any incomplete checkpoint; do not describe paused as a complete recovery point.
- Prepared handoff, incoming session: one explicit reception request is enough; resolve handoff IDs from authoritative state and retain policy.
- Another active holder without a prepared handoff: remain read-only; ambiguous “continue” is not replacement authority.
- Requested independent subproject resolves to a parent repository: expose the actual root and resolve intent before initialization.
- Change one setting: show the patch and resulting changed fields; unrelated permission denials, worker defaults and custom paths remain intact.
- Foundation repair: show missing/retained/conflicting files, only create explicitly requested missing items, and keep generated drafts visibly pending.
