# Structured work and acceptance (runtime API 2)

Use [configuration](configuration.md) for explicit API activation and [dispatch](dispatch.md) for approved commands. This protocol checks cooperating declarations, content and evidence; it does not authorize model calls, Git actions or resource access. All paths below are already resolved from the loaded skill and user's project.

## Register a task and inspect readiness

Write a complete spec to `PLAYBOOK_SPEC`. The paths identify relevant task content relative to its worktree root, even if a command runs in a child directory. Requirements and acceptance are nonempty string arrays; paths are nonempty. Use a narrow meaningful scope rather than collecting unrelated files.

```json
{
  "requirements": ["Return a stable identifier for each record"],
  "acceptance": ["Offline tests cover duplicate identifiers"],
  "paths": ["src", "tests"],
  "dependencies": [],
  "resources": ["fixture-database"],
  "review": {"independent": false}
}
```

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" task --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --id "$PLAYBOOK_TASK" --spec "$PLAYBOOK_SPEC" --worktree "$PLAYBOOK_WORKTREE"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" readiness --project "$PLAYBOOK_PROJECT" --task "$PLAYBOOK_TASK"
```

A new spec defaults to reserved; register/reserve work deliberately, because explicit resources held by reserved tasks can block other cards. Readiness reports `ready`, `blockers`, dependency bindings, spec hash/revision, advisory content conflicts and dispatch-state readiness. It is not a launcher. Run rechecks under the reservation lock. Changing requirements retains spec history and removes the old current acceptance/integration pointer. Do not modify an in-flight task to pretend its old worker received new requirements.

A dependency is `{"task":"upstream-id","kind":"contract"}` or `{"task":"upstream-id","kind":"integrated"}`. Contract mode pins the upstream specification revision/hash; it does not claim implementation exists or independently accepted code was delivered. Integrated mode additionally requires an intact accepted historical integration result at the consumer's actual starting point. The upstream target may advance normally; current publication applicability still requires exact target HEAD/branch/content. Accepted integration records retain their original dependency IDs rather than following later task pointers. Committed results require the accepted commit in the consumer's ancestry, allowing later downstream edits; uncommitted results also require matching accepted content in its worktree. This conservative content check can block edits overlapping an uncommitted upstream scope: commit the upstream result through the approved process or resolve the dependency contract explicitly. Losing the consumed baseline invalidates a receipt even when the task's own scoped files are unchanged. Unknown fields and cycles are rejected. All exclusive resource names share a project namespace across worktrees; unknown claims are not expired by age.

## Verify after implementation, then record evidence

Implementation dispatch finishes before managed heavy verification. Inspect that phase with `readiness --task ID --action verify` (also `--worker ID` for a model reviewer); the default readiness action is dispatch. Use the same task ID for sequential attempts. A reviewer declaration is frozen before the command; when this is a model reviewer, also select an approved worker through the documented dispatch/verify route so it consumes agent capacity. A reviewer label alone is not a model invocation or verified identity.

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" run --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --action verify --task "$PLAYBOOK_TASK" --reviewer "$PLAYBOOK_REVIEWER" --role reviewer -- "$PLAYBOOK_COMMAND"
```

Take the actual attempt ID from the successful receipt, then register the result:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" evidence --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --task "$PLAYBOOK_TASK" --attempt "$PLAYBOOK_ATTEMPT" --reviewer "$PLAYBOOK_REVIEWER" --role reviewer --note "$PLAYBOOK_NOTE"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" evidence --project "$PLAYBOOK_PROJECT" --operation status --task "$PLAYBOOK_TASK"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" task --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --id "$PLAYBOOK_TASK" --state verified
```

Only successful completed verify attempts can yield passing machine evidence; dispatch success remains reported. The tested requirements/dependencies and relevant content before/after verification must match the accepted object. Evidence is append-only, with a unique receipt and hash pointer; status reports stale, missing or changed artifacts. A spec-backed task cannot become verified merely because a note is nonempty. Legacy tasks retain their history and are labelled `legacy-note-only`.

Manual evidence must be explicitly permitted with `review.allow_manual:true`. Use `evidence --manual --reviewer NAME --role reviewer --artifact RELATIVE_PATH --note TEXT`; this is labelled manual, not a test command. `--result passed|failed` defaults to passed. Project `review.independent:true` or task-level independent review requires a reviewer distinct from the recorded implementation participants. A task can strengthen that requirement, not weaken it. Manual and independent policy flags default to false when absent; reading old policy does not insert them.

Fingerprints compare bytes, modes, deletion and symlink identity, not mtime, with bounded capture. Directory symlinks are not followed. Git includes tracked and nonignored untracked content. Conventional untracked caches/`.env` files and ignored content are excluded and reported; non-Git uses conservative exclusions. A fingerprint is not proof that excluded content was tested. Explicitly archived artifacts may be registered separately; artifact paths must be regular files without symlink ancestors. Record any required excluded evidence rather than pretending it was captured.

Owner/implementation provenance is retained across task updates and handoffs, and frozen on the verification attempt. A rejected self-review cannot become independent by changing the owner afterward. Staging or committing an existing deletion does not change the content fingerprint; changing the actual content does.

The shared runtime's complete verification log is authoritative, including managed adapter stdout/stderr in quiet mode. A separate user log is a convenience copy. Deleting or changing the authoritative log invalidates evidence. Explicit artifacts must remain available at their recorded paths; keep or archive them before verification and registration.

## Integrate a declared group of accepted tasks

Begin with verified participants and applicable receipts. Set the real target worktree, integration ID and participant IDs. Extra paths add assembled checks; participant scopes are always included.

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" integration --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --operation begin --id "$PLAYBOOK_INTEGRATION" --tasks "$PLAYBOOK_TASK_A" "$PLAYBOOK_TASK_B" --target "$PLAYBOOK_TARGET" --paths integration-tests
```

Begin records facts and grants no merge permission. Execute the separately authorized integration method, then run a stable assembly verification task associated with the integration:

```bash
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" run --project "$PLAYBOOK_TARGET" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --action verify --task "$PLAYBOOK_ASSEMBLY_TASK" --integration "$PLAYBOOK_INTEGRATION" --reviewer "$PLAYBOOK_REVIEWER" --role reviewer -- "$PLAYBOOK_COMMAND"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" integration --project "$PLAYBOOK_PROJECT" --session "$PLAYBOOK_SESSION" --epoch "$PLAYBOOK_EPOCH" --operation finish --id "$PLAYBOOK_INTEGRATION" --attempt "$PLAYBOOK_ATTEMPT" --note "$PLAYBOOK_NOTE"
python3 -I "$PLAYBOOK_SKILL_DIR/scripts/playbook.py" integration --project "$PLAYBOOK_PROJECT" --operation status --id "$PLAYBOOK_INTEGRATION"
```

Finish verifies the associated successful attempt, relevant content and target HEAD/branch, plus still-applicable participant requirements/dependencies. It records the assembled result and actual merge facts, then marks participants integrated. Target changes after testing invalidate current publication applicability. Finish freezes whether the scoped result was committed; later changes to the source tree cannot reclassify old results. Historical dependency validation keeps the accepted result and checks the actual consumer baseline. Once integration has passed, approved cleanup of a source worktree does not invalidate a machine receipt with no explicit artifacts; retained shared logs, dependency records and the actual integration target are still checked. Membership is explicitly declared and `semantic_inclusion_proven:false` remains visible: source ancestry and hashes do not prove that every intended behavior was included, especially for dirty changes or squash/rebase. Failed assembled tests preserve merged work and evidence; they cannot become a passing result.

If the project requires an accepted assembled result before pushing its integration branch, begin may add `--require-push`. This gate applies only to the configured integration branch. Guarded push with a recorded gate uses explicit `git push REMOTE SOURCE:DESTINATION`; ambiguous wrappers/default/wildcard/force/deletion forms are rejected. The integration source must equal the accepted result and its target worktree must be clean. Explicit backup destinations remain subject to ordinary push permissions/cadence but do not acquire release acceptance. No action here grants publication or deployment rights.
