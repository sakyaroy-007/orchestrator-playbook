# v3.0.0 release preparation — 2026-11-14

This report records local checks of the final 3.0.0 package before publication. The [development report](v3-next-validation.md) and [earlier pilot receipt](v3-offline-pilot-result.json) remain historical records of their original bytes; their development hashes are not the final release hashes. Publication and remote CI results are recorded in [Releases](https://github.com/sakyaroy-007/orchestrator-playbook/releases) and [Actions](https://github.com/sakyaroy-007/orchestrator-playbook/actions).

## Release changes

- Keep the five lifecycle entries and the existing runtime API 2 / config-state schema 1 contracts.
- Clarify that a bare `playbook-start` needs no prepared prompt. Missing goals are explored in focused rounds of one to three consequential questions before a full setup recommendation. An agreed first-stage outcome, scope, exclusions and observable acceptance end the interview; feasibility uncertainty can become a bounded exploration task.
- Reuse clear goals and existing-project plans without restarting an interview or asking settled choices again. A project that has never adopted v3 uses `playbook-start` directly; existing owners and differing local runtime copies remain protected.
- Synchronize English and Chinese instructions and first-use examples, date the changelog, and change `version.release_status` to `released`.

Independent read-only review and a separate attempt to refute its findings found no new functional release blocker in onboarding or release preparation. Goal-clarification wording was a usability improvement, not evidence that previous initialization could not work. This review did not execute a model-backed user interview.

## Checks actually completed on final package inputs

Local platform: Darwin 27.0.0 arm64, Python 3.9.6.

| Check | Observed result |
|---|---|
| Instrumented `unittest` discovery over `tests/` | 219 tests in 241.148 seconds; 0 failures, 0 errors, 0 skips |
| Shell selftest | 74 passed, 0 failed |
| `bash -n` | All 19 source/generated shell files passed |
| Five generated bundles | Rebuilt from canonical sources; `build-skills.py --check` passed |
| Local manifests and invocation policies | `check-manifests.py` passed |
| Native plugin validator | Claude Code 2.1.323 passed |
| Runtime diagnosis | Package 3.0.0, runtime API 2, schema 1, `released`, six required files present |
| Staged Codex discovery | All five exact staged paths found enabled through `app-server` `skills/list`; no model turn |
| Staged DSH discovery | All five staged entries found; explicit invocation restrictions retained; no model call |

The native validator reported two local `.DS_Store` warnings. Neither file is tracked or included in the generated packages. Each skill still has 48 files. Shared installation is a separate action; staged discovery is not an observation of the active conversation loading the new content.

The final full suite includes a newly generated, isolated `playbook-start` pilot: 67 commands, 9 combined-flow checks and 8 fake-worker checks, with no unexpected exit and no paid model/service call. It retains the implementation, verification, integration and handoff assertions from the development pilot. The runtime, generator and pilot-source hashes were compared with the current source after the run.

The final `scripts/playbook.py` SHA256 is:

```text
fe88556295e27012906e4132651677af72bc0f763b37f6cf594cfba9374bafbb
```

The portable `release-validation.json` artifact records the complete runtime hashes, package-manifest hashes, full-suite totals and final pilot receipt. Its SHA256 is:

```text
06e980ea8085c358dac82d28a849513aaa484fd308a03a4e5ce92d8c867a6710
```

## Publication and remaining limits

The release process submits the complete source, generated skills, tests, documentation and CI together. Remote Linux/macOS and Python 3.9/3.13 results must be read for the actual publication commit; local success does not predict them. The release tag and default installation branch must point to the intended commit before publication is reported complete.

This repository distributes skills; it has no application server or website deployment target. Publishing its GitHub version and updating an explicitly chosen local installation are separate operations. No business project was adopted as part of these checks, and no client-global settings were changed.

Live worker authentication, effective model/effort/profile behavior, paid usage and the quality of an actual goal-clarification conversation remain outside these automated checks. The [real-client pilot procedure](v3-pilot.md) describes how to scope that work. Installation, native discovery, active-session loading and model execution remain distinct observations.
