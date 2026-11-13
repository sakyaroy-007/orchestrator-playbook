# v3 extended protocol validation — 2026-11-14

Status: implementation, local validation, generated bundles and reviewed local shared update completed. Version 3.0.0 remains **unreleased**. This report covers the extended protocol, not the earlier v3 baseline totals. All regression execution used temporary projects and fake workers with zero paid model calls.

## Final checks actually run

The full suite used instrumented `unittest` discovery over `tests/`, equivalent to the selection in `python3 -I -m unittest discover -s tests`. It ran **219 tests in 244.361 seconds: 0 failures, 0 errors, 0 skips**, on Darwin 27.0.0 arm64 with Python 3.9.6.

| Module | Passed tests |
|---|---:|
| `test_playbook` | 61 |
| `test_runtime_next` | 15 |
| `test_work_protocol` | 20 |
| `test_dependency_baseline` | 8 |
| `test_evidence_regressions` | 5 |
| `test_foundation` | 23 |
| `test_policy_dispatch` | 23 |
| `test_shell_integration` | 32 |
| `test_packaging` | 20 |
| `test_manifests` | 11 |
| `test_offline_pilot` | 1 |
| **Total** | **219** |

Additional completed checks:

- `bash scripts/selftest.sh`: **74 passed, 0 failed**.
- `bash -n` over the four source shell scripts and fifteen generated shell copies: **19 files passed**.
- `python3 -I scripts/build-skills.py`: rebuilt all five bundles from canonical sources; **140 managed file changes**.
- `python3 -I scripts/build-skills.py --check`: all five match their sources.
- `python3 -I scripts/check-manifests.py`: passed local manifest/resource and explicit-invocation checks.
- `claude plugin validate .`, using installed CLI **2.1.323**: passed. It also reported two filesystem warnings for ignored, untracked `.DS_Store` files. `git ls-files` confirmed neither is tracked; neither is in any generated bundle.
- `python3 -I scripts/playbook.py version`: package 3.0.0, runtime API 2, config/state schema 1, development-unreleased, six runtime dependency hashes, no missing files.
- `git diff --check`: passed for tracked changes. A separate scan of 326 public source/generated text files found no private host paths or personal forms of address.

The full suite includes isolated-bundle and copied-project runtime checks. A single skill retains all required scripts/resources after the source tree and sibling bundles are unavailable. Each final bundle has **48 files**: 47 managed payload files plus its generation manifest; the payload includes seven scripts, twenty reference files and seventeen templates.

## Completed scope and defect regressions

The five deferred cleanups are implemented: recovery-blob hash reuse within one verification only; one ordinary checkpoint state save; per-dispatch CLI-help reuse; removal of duplicate canonical adapter validation and dead worker filtering; and a shared outstanding-attempt predicate. The hash-cache regression also modifies the blob between calls and confirms the next call detects it.

The extended lifecycle covers pause-before-capture, failed-checkpoint retention, prepared-handoff withdrawal, configuration patches, targeted cancellation, state-aware routing, version/copy diagnostics and create-only foundations. Structured work covers requirement revisions, contract/integrated dependencies, exclusive resources, staged verification, immutable content-bound evidence, review declarations, assembly verification and branch-specific push gating.

Independent review reproduced and then checked counterexamples for the following defects. Focused regressions were added, and the final full suite includes their fixes:

- Foundation write failures left partial final files; relative project paths changed meaning after guard changed cwd. Complete temporary files now publish without replacing existing targets, and both guarded calls use the same absolute project path.
- Managed reviewer logs did not bind the complete output; equivalent native setting arguments could bypass dedicated settings. Complete stdout/stderr now reaches the authoritative runtime log, including quiet mode; failed log copying remains a failed verification, and conflicting aliases are rejected.
- Quoted/escaped duplicate YAML keys could override invocation metadata. The checker rejects unsupported ambiguous key syntax and duplicate fields.
- Blocking cancellation polling delayed the actual process-group timeout while another owner operation held the lock. Nonblocking polling now preserves the supervisor deadline; the regression observes the worker stopping while the guard still holds the lock, before its late-write marker can be created.
- Initialization with inferred API 2 and either new review flag could not retry identically. Retry now validates against the already-enabled policy under the owner lock, with old-policy and invalid-owner/API controls.
- Handoff plus a task-status update could erase the original implementation identity. Owner history is retained and verification freezes implementation sources; the same self-review remains rejected after handoff.
- Merely staging a deletion changed a directory-scoped fingerprint. The fingerprint now represents actual scoped content independently of deletion staging; real deletion/restoration still invalidates older content evidence.
- Explicit Git scopes could reintroduce conventionally excluded untracked files. They now obey the same exclusion policy while retaining the tracked-file exception.
- Approved cleanup of a completed worker checkout invalidated artifact-free machine integration evidence. Accepted records now use retained shared logs and the assembled target; explicit artifact locations remain required.

Additional dependency regressions reject a consumer that lacks the accepted upstream baseline, permit ordinary downstream integration after the main branch advances, freeze whether upstream content was committed at acceptance, and retain original dependency IDs when a later batch contains both upstream and consumer. Current publication status and push gates still reject a changed target. Historical acceptance is not proof of arbitrary semantic merge inclusion.

## Complete offline pilot

The final retained run used one freshly generated `playbook-start` bundle after deleting its generation tree and siblings. It completed **67 commands**, **9 combined-flow checks**, and **8 fake-worker checks**, with **6 expected nonzero commands**, **0 unexpected exits**, and **0 paid model/service calls**.

It demonstrated two implementation workers running concurrently in distinct worktrees, prelaunch exclusive-resource denial, serialized heavy verification, two content-bound task receipts, authorized fixture integration and assembly verification, prepared handoff without repeated attempts, and a paused final owner at epoch 2. The ledger contains five attempts: two dispatches, two task verifications and one assembly verification.

The pilot passed inside the 219-test suite. After correcting one cited regression-method name in the pilot's report metadata, the pilot alone was rerun and passed in **13.888 seconds**; runtime and bundle inputs were unchanged. The [portable result](v3-offline-pilot-result.json) binds the final runtime, generator and test hashes to actual receipts, and preserves six retained pilot runs, including the earlier two fixture failures. Those failures were corrected without removing their acceptance assertions. A later evidence-test fixture initially retained unrelated task reservations; releasing those deliberate reservations corrected the fixture before the final suite.

The pilot is one composed scenario. The full suite separately covers non-Git/custom-path setup, dirty and changed evidence, failed assembly, cancellation, handoff races and failed pause checkpoints; they are not falsely counted as steps inside that single pilot.

## Reviewed local installation

The five final bundles were generated into a physical staging directory outside normal skill-discovery roots, inspected with the user's shared installer, and bound to exact content digests. Existing installed digests matched the prior reviewed installation. Every changed existing file was backed up before replacement; there were 28 changed/added paths per package and no old files were removed. The installer helper's `reconcile` completed for **Codex, DSH and Claude**, preserving the existing correct links.

Post-update checks confirmed all five complete package digests, file modes, explicit invocation policies, link realpaths and the installed runtimes' dependency hashes. Native observations were:

| Client | Actual verification | Limit |
|---|---|---|
| Codex CLI 0.166.0 | `app-server` `skills/list` found all five enabled staged paths, then all five installed shared paths | No conversation turn or model request |
| DSH | Installed `FileSystemSkillProvider` found all five staged and installed entries; `modelInvocable:false`, `userInvocable:true` | Provider discovery, not a model execution |
| Claude CLI 2.1.323 | Native plugin validation; entry/frontmatter/resource review; all five shared links and content verified | This active session's reload/new-content loading was not observed |

Codex discovers the shared root directly. DSH and Claude retain their targeted links. Hermes remains excluded because the required explicit-invocation restrictions are not equivalently enforced by the reviewed version. No client-global settings, profiles, MCP registrations or permissions were changed. Installation receipts, affected-file backups and native discovery outputs remain in local installation/validation records; private host paths are omitted here.

## CI and unperformed work

`.github/workflows/ci.yml` configures Linux/macOS with Python 3.9/3.13 for shell syntax, shell selftest, full offline regressions, generated-bundle drift and manifest checks. A separate pinned Claude CLI job validates the plugin without a model call. **No remote CI run was triggered**; local macOS/Python 3.9 results do not establish Linux or Python 3.13 execution.

The [real-client pilot](v3-pilot.md) is a concrete plan, not a completed paid test. Real worker authentication, effective live model/effort/profile behavior, billing and cross-client conversation transfer were not tested. Current-session skill loading is distinct from installation and native discovery; refresh the skill list when needed.

No source-repository commit, push, release or deployment was performed. Local fixture commits and local bare-remotes used by regression tests remain confined to their temporary projects. Unrelated projects were not modified, and this skill repository was not initialized as a managed project.
