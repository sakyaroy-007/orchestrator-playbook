# Hermes adapter development validation

Date: 2026-11-14. Package: **3.1.0-dev.1**, runtime API 2, config/state schema 1, `release_status:development-unreleased`. Tested working tree is based on published commit `4a78f1a8b55b9a7f4f72b0e8a5201029282a9421`, on development branch `feat/hermes-adapter`. This report is not a release, installation or live-client claim.

## Completed checks

| Check | Observed result |
| --- | --- |
| `python3 -I -m unittest discover -s tests` | **255 tests, 279.756 seconds, OK** on Darwin, Python 3.9.6; no failures/errors/skips reported |
| `bash scripts/selftest.sh` | **74 passed, 0 failed**, temporary repositories and fake clients |
| `python3 -I scripts/build-skills.py` then `--check` | Five generated skills match canonical sources |
| `python3 -I scripts/check-manifests.py` | All four public manifests valid and version-aligned |
| Standalone Hermes plugin build and `--check` | Plugin matches canonical entries and bundled runtime/resources |
| Native Claude plugin validation | Repository validation passed; see fixture notes below |
| Native directory validation with `--profile directory --strict` | Clean standalone validation copy passed, nothing to report |
| Hermes 0.23.1 native manifest parser | Built plugin parsed as standalone, version 3.1.0-dev.1; supported Hermes range accepted; no tools/hooks/capability grants |
| Hermes native `ask_choice` helper | Four isolated cases: no bound UI, Load, Cancel and empty response matched expected behavior |
| Shared installer `inspect` | Five staged skills inspected; explicit-only metadata preserved, executable-review hints examined; this did not install them |
| `git diff --check` and portable-path scan | Passed; no private host paths or personal forms of address in changed/new public files |
| Source-repository boundary | No `.orchestrator` control plane created |

The full suite includes 18 plugin-context tests, 16 fake-gateway/runtime tests and the existing independent-bundle/offline integration pilot. The fake gateway uses loopback sockets and real subprocesses, without invoking Hermes, credentials or model APIs. It covers exact settings/cwd, durable identity, saved results, approval `once`/`deny`/inherit, lost submission ACK recovery without replay, unknown outcomes, admission cancellation, delegation join uncertainty, masked/fragmented WebSocket transport, owner cancellation, checkpoint recovery blobs and rejection of a bare viewer command as managed evidence.

An independent read-only review found a queued-to-running reconnect race: the old admission could have `execution_generation:null` while resumed approval prompts already named the active generation. The bridge now refreshes the exact admission receipt before handling resumed approvals. A regression reproduces that sequence and verifies only one task submission.

## Native-probe isolation

The manifest/choice probe used the already installed Python 3.14.9 environment and fixed Hermes source commit `3b421578588243f920886e6fe79a6faa87ea026e`, bypassing the launcher. It used a temporary HOME/HERMES_HOME, no inherited model credentials, restricted filesystem access and audit-hook rejection of network/subprocesses/out-of-scope writes. **Blocked attempts: none.** It parsed the manifest and called the real pure choice helper; it did not discover/register/load the plugin in a real client, start a gateway or call a model. Host frontend behavior remains unverified.

Initial repository-native validation reported two ignored, untracked `.DS_Store` files; `git ls-files` confirmed neither was tracked, and the existing ignore rule already covered them. They were not deleted. The first clean validation fixture omitted README.md and therefore received a directory-submission finding despite ordinary manifest validation exiting zero. The fixture was completed with the repository README editions and LICENSE, then strict directory validation passed with nothing to report. No validation rule was weakened.

During development, one plugin-only rerun compared a cached package against canonical sources being edited concurrently; 16 tests passed and that comparison failed. Final testing ran after inputs were stable and includes all plugin tests. Earlier 13/33-test focused successes were intermediate checks, not substitutes for the final 255-test result.

## Artifacts and retained scope

Five standalone skill directories were generated outside discovery roots and inspected through the shared installation helper. Each contains 52 files, including its generated marker: **260 files total**. The independent native Hermes plugin contains **63 files**, with no discoverable `SKILL.md`; canonical English/Chinese entries and all runtime resources are bundled. Local validation artifacts retain logs, inspection digests, native-parser results and the isolated packages; these private evidence paths are not embedded in public documentation.

At the end of the local validation recorded here, no user skill installation had been replaced. No Hermes plugin had been installed or enabled, no injection permission granted, and no global profiles/MCP/client settings changed. Existing business projects and custom team scripts had not been modified. No real gateway/model task, native frontend interaction, remote CI run, commit, push, release or deployment was part of this local validation. Subsequent GitHub commits, pull requests and Actions runs provide their own publication and CI records.

Approval policy controls responses to emitted native requests; it does not override profile grants or child policies. Completion evidence is limited to an exact admission and available live registered resources. It does not prove that arbitrary external descendants stopped. Unconfirmed outcomes and delegation interruption without join evidence remain unknown and retain reservations. See [the implementation contract](hermes-adapter.md) and [the user-facing reference](../references/hermes.md).
