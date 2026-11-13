# v3 validation record — 2026-11-13

This records the unreleased local implementation on `feat/lifecycle-skills`, based on commit `39c0ace085481fa8af1da025f45a08173a0db670`. It is not a release announcement. No repository commit, push, marketplace publication or deployment was performed as part of this work.

## Completed checks

The final assembled source was tested on macOS Darwin 27 with Python 3.9.6. Automated tests use temporary projects, local Git history and fake worker commands; they make no paid model calls.

| Check | Result |
|---|---|
| `python3 -I -m unittest discover -s tests` | 106 passed, 69.297 seconds; no failures or skips |
| Runtime integration cases within that suite | 61 passed |
| Real shell-entry integration cases within that suite | 25 passed |
| Packaging cases within that suite | 20 passed |
| `bash scripts/selftest.sh` | 74 checks passed, 0 failed |
| `bash -n` on the changed shell entry points | Passed |
| `python3 -I scripts/build-skills.py --check` | All five generated bundles match canonical sources |
| `claude plugin validate .` | Passed; local ignored/untracked `.DS_Store` produced a directory warning, and is absent from generated bundles |
| `git diff --check` | Passed |

Packaging tests include isolated copies with no dependency on the checkout or sibling skills, retained unknown files, refusal of modified generated files and symlinks, and failure before writes on conflicting inputs. Each installed bundle contains 43 files, including its generation marker.

The final bundles were separately staged and installed through the reviewed shared-skill helper for Codex, DSH and Claude. The helper bound each install to its inspected content digest. Post-install checks compared all 215 installed file hashes and modes, and verified DSH/Claude links resolve to the shared source. Hermes skill installation was excluded to preserve explicit-invocation semantics. Local installation receipts are host-specific and are not part of this repository.

## Native discovery evidence

- Codex CLI 0.166.0: `app-server` initialization followed only by `skills/list` discovered all five standalone entries, enabled, first in a temporary Git project and then in the installed user root. No thread or model turn was started.
- DSH: the installed `FileSystemSkillProvider` read the final staged and installed entries. All five names were found with `modelInvocable=false` and `userInvocable=true`; resource bases resolve to the complete bundles. This verifies the native scanner, not every active DSH profile or conversation.
- Claude Code 2.1.323: final plugin validation passed and installed links/resources were verified. Active conversation reload and slash-menu interaction were not exercised.
- CLI help and local schemas support the documented effort/profile argument mappings. Those checks and fake-worker argv tests do not prove authentication, model availability, actual reasoning behavior or successful live work.

## Independent review and regression repairs

The review identified and the implementation repaired these behavior defects:

- Linked-checkout initialization could make shell helpers miss the canonical configuration and fall back to legacy behavior. Helpers now detect shared runtime state and use normalized policy, including custom worker/card paths and defaulted settings.
- Relative log checks used the caller directory while dispatch wrote in the worker directory. Paths are now anchored before the cwd change, and managed log creation also refuses a concurrent existing-file collision.
- DSH effort overlays could follow application arguments and escape launcher parsing. Launcher overlays now precede application arguments.
- A worker leader could exit while descendants retained the process group. Resource slots and the original deadline now remain supervised until group work ends; timeout signals stay scoped to that group.
- Relative executable validation used the wrong cwd. Validation now uses the actual execution directory, including relative and empty PATH entries.
- Configured scaffolding lacked ownership protection, and its staging hint omitted the copied runtime. Writes now use the scaffold guard; the hint includes the runtime dependency.
- A setup hook could recursively wait for the worktree creation lock. Managed creation now reports setup as pending; the approved setup flow runs after the guard returns. Legacy automatic hooks are retained.
- Interrupted configuration writes could leave config/state inconsistent with no new-owner recovery path. Explicit reviewed-configuration recovery preserves the old state/config evidence before applying a revision and checkpointing.
- Git binary patch capture buffered output before checking limits. Capture now bounds data while reading and preserves partial recovery data on failure.
- An unmerged index could contain unique staged content absent from the claimed complete snapshot. Such indexes now block a complete checkpoint while preserving all stages.
- Snapshot diff could refresh the index itself and falsely report a concurrent change. Snapshot commands disable that refresh.

The final two snapshot defects were independently rechecked with their original temporary reproductions after repair: unmerged indexes were rejected with all stages intact, and mtime-only changes permitted a complete prepared handoff without index mutation.

Five lower-priority performance/maintenance suggestions were deliberately deferred: deduplicating recovery-blob hash reads, eliminating an extra checkpoint state save, caching identical per-dispatch CLI help probes, reducing duplicate adapter schema checks/dead `enabled` filtering, and centralizing the outstanding-attempt predicate. These are not presented as completed work.

## Scope not validated or implemented

- No real LLM worker task, login exercise, GUI workflow, paid service call or live model/effort behavior verification.
- No active-conversation discovery/reload guarantee; no Codex/DSH plugin-marketplace installation test.
- No multi-machine arbitration, native conversation restoration, automatic upgrade/migration, hard monetary cap or automatic publishing.
- No claim of interception of arbitrary client shell/edit tools. Ownership and limits apply to cooperating managed paths.
- No Hermes skill installation or fixed Hermes effort/profile mapping; no Claude profile override mapping.
- No Linux or Windows execution test. The runtime requires POSIX file locking.
- Checkpoints exclude Git-ignored untracked files and reject unmerged indexes, dirty submodules, special files, unstable/unreadable content, or the documented size/count limits. Needed excluded evidence must be preserved explicitly; a rejected snapshot is not a completed handoff.
