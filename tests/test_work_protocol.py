"""Structured task/evidence/integration external contracts, entirely offline."""
import json
import os
from pathlib import Path
import subprocess
import unittest

import test_playbook as fixtures


class WorkProtocolTests(unittest.TestCase):
    setUp = fixtures.PlaybookTests.setUp
    tearDown = fixtures.PlaybookTests.tearDown
    cli = fixtures.PlaybookTests.cli
    owner = fixtures.PlaybookTests.owner
    config = fixtures.PlaybookTests.config
    init = fixtures.PlaybookTests.init
    git = fixtures.PlaybookTests.git
    git_project = fixtures.PlaybookTests.git_project
    spawn = fixtures.PlaybookTests.spawn
    wait_file = fixtures.PlaybookTests.wait_file
    wait_process = fixtures.PlaybookTests.wait_process
    fake_wait = fixtures.PlaybookTests.fake_wait
    run_args = fixtures.PlaybookTests.run_args

    def spec(self, task="T1", paths=None, resources=None, dependencies=None, independent=False, state=None, worktree=None, requirement="Stable source behavior"):
        data = {"requirements": [requirement], "acceptance": ["Offline check passes"], "paths": paths or ["source.txt"],
                "resources": resources or [], "dependencies": dependencies or [], "review": {"independent": independent}}
        path = self.base / (task + "-spec.json")
        path.write_text(json.dumps(data))
        args = [*self.owner(), "--id", task, "--spec", str(path)]
        if state:
            args += ["--state", state]
        if worktree:
            args += ["--worktree", str(worktree)]
        return self.cli("task", *args)

    def verify(self, task="T1", command=None, integration=None, project=None, reviewer="reviewer", role="reviewer"):
        args = [*self.owner(), "--action", "verify", "--task", task, "--reviewer", reviewer, "--role", role]
        if integration:
            args += ["--integration", integration]
        return self.cli("run", *args, "--", *(command or fixtures.PYTHON + ["-c", "pass"]), project=project)

    def receipt(self, attempt, task="T1", ok=True, reviewer="reviewer", role="reviewer", artifacts=None):
        args = [*self.owner(), "--task", task, "--attempt", attempt, "--reviewer", reviewer, "--role", role, "--note", "Offline acceptance checked"]
        for path in artifacts or []:
            args += ["--artifact", path]
        return self.cli("evidence", *args, ok=ok)

    def accepted(self, task="T1", **kwargs):
        attempt = self.verify(task, **kwargs)["attempt"]["id"]
        receipt = self.receipt(attempt, task)["evidence"]
        self.cli("task", *self.owner(), "--id", task, "--state", "verified")
        return receipt

    def initialize(self, use_git=False, **config):
        if use_git:
            self.git_project()
        else:
            (self.project / "source.txt").write_text("original\n")
        return self.init(self.config(**config))

    def begin(self, integration="batch", tasks=None, extra=None):
        return self.cli("integration", *self.owner(), "--operation", "begin", "--id", integration, "--tasks", *(tasks or ["T1"]), *(extra or []))

    def finish(self, attempt, integration="batch", ok=True):
        return self.cli("integration", *self.owner(), "--operation", "finish", "--id", integration, "--attempt", attempt, "--note", "Declared participant membership and checked assembly", ok=ok)

    def test_typed_acceptance_needs_evidence_and_mtime_does_not_invalidate(self):
        self.initialize()
        self.spec(independent=True)
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified", "--note", "looks good", ok=False)
        receipt = self.accepted()
        os.utime(self.project / "source.txt", None)
        (self.project / "unrelated").write_text("not in acceptance scope")
        status = self.cli("evidence", "--operation", "status", "--task", "T1")
        self.assertTrue(status["evidence"][0]["applicable"])
        (self.project / "source.txt").write_text("changed dirty bytes\n")
        self.assertFalse(self.cli("evidence", "--operation", "status", "--task", "T1")["evidence"][0]["applicable"])
        self.receipt(receipt["source"]["attempt"], ok=False)
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified", ok=False)
        self.assertTrue(any("inapplicable" in issue for issue in self.cli("doctor")["issues"]))

    def test_changed_requirements_keep_prior_receipts_but_reject_old_verification(self):
        initial = self.initialize()
        self.spec()
        receipt = self.accepted()
        path = Path(initial["runtime_path"]) / "evidence" / (receipt["id"] + ".json")
        original = path.read_bytes()
        changed = self.spec(requirement="New acceptance contract")
        self.assertEqual(changed["task"]["spec_revision"], 2)
        self.assertEqual(len(changed["task"]["spec_history"]), 1)
        self.assertEqual(path.read_bytes(), original)
        self.assertIn(receipt["id"], changed["task"]["evidence"])
        self.receipt(receipt["source"]["attempt"], ok=False)
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified", ok=False)

    def test_verifier_mutation_cannot_rebind_pass_to_resulting_content(self):
        self.initialize()
        self.spec()
        run = self.verify(command=fixtures.PYTHON + ["-c", "from pathlib import Path; Path('source.txt').write_text('mutated by verification')"])
        self.assertEqual(run["attempt"]["returncode"], 0)
        self.assertNotEqual(run["attempt"]["content_before"], run["attempt"]["content_after"])
        failure = self.receipt(run["attempt"]["id"], ok=False)
        self.assertIn("content", failure.stderr)

    def test_directory_symlink_ancestors_are_rejected_without_reading_outside(self):
        self.initialize(use_git=True)
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret").write_text("external")
        (self.project / "escape").symlink_to(outside, target_is_directory=True)
        self.spec(paths=["escape/secret"])
        ready = self.cli("readiness", "--task", "T1")
        self.assertFalse(ready["ready"])
        self.assertIn("symlink", " ".join(ready["blockers"]))
        self.cli("run", *self.run_args("T1", fixtures.PYTHON + ["-c", "pass"], action="verify", worker=None), ok=False)
        self.assertFalse(self.cli("status")["attempts"])

    def test_gitlink_scope_cannot_claim_submodule_content_was_verified(self):
        self.initialize(use_git=True)
        head = self.git("rev-parse", "HEAD")
        (self.project / "module").mkdir()
        (self.project / "module" / "unseen-source").write_text("submodule data")
        self.git("update-index", "--add", "--cacheinfo", "160000," + head + ",module")
        self.spec(paths=["module"])
        result = self.cli("readiness", "--task", "T1")
        self.assertFalse(result["ready"])
        self.assertIn("Submodule", " ".join(result["blockers"]))
        self.assertFalse(self.cli("status")["attempts"])

    def test_symlink_identity_is_hashed_without_target_contents(self):
        self.initialize()
        outside = self.base / "outside"
        outside.write_text("private")
        (self.project / "link").symlink_to(outside)
        self.spec(paths=["link"])
        receipt = self.accepted()
        self.assertEqual(receipt["content"]["entries"]["link"]["kind"], "symlink")
        outside.write_text("outside mutation")
        self.assertTrue(self.cli("evidence", "--operation", "status", "--task", "T1")["evidence"][0]["applicable"])
        (self.project / "link").unlink()
        (self.project / "link").symlink_to("different-target")
        self.assertFalse(self.cli("evidence", "--operation", "status", "--task", "T1")["evidence"][0]["applicable"])

    def test_git_ignored_secrets_and_untracked_caches_are_excluded(self):
        self.initialize(use_git=True)
        (self.project / ".gitignore").write_text("secret/\n")
        secret = self.project / "secret"
        secret.mkdir()
        with (secret / "large").open("wb") as stream:
            stream.truncate(70 * 1024 * 1024)
        cache = self.project / "node_modules"
        cache.mkdir()
        (cache / "package").write_text("generated")
        self.spec(paths=["."])
        receipt = self.accepted()
        self.assertNotIn("secret/large", receipt["content"]["entries"])
        self.assertNotIn("node_modules/package", receipt["content"]["entries"])
        (secret / "new-secret").write_text("not read")
        (cache / "package").write_text("changed cache")
        (cache / "new-package").write_text("new excluded cache")
        self.assertTrue(self.cli("evidence", "--operation", "status", "--task", "T1")["evidence"][0]["applicable"])

    def test_bounded_content_rejects_oversize_and_non_git_excludes_known_cache(self):
        self.initialize()
        cache = self.project / "node_modules"
        cache.mkdir()
        with (cache / "huge").open("wb") as stream:
            stream.truncate(70 * 1024 * 1024)
        (self.project / ".env").write_text("excluded")
        self.spec(paths=["."])
        self.assertTrue(self.cli("readiness", "--task", "T1")["ready"])
        with (self.project / "huge-source").open("wb") as stream:
            stream.truncate(70 * 1024 * 1024)
        self.assertFalse(self.cli("readiness", "--task", "T1")["ready"])
        self.cli("run", *self.run_args("T1", fixtures.PYTHON + ["-c", "pass"], action="verify", worker=None), ok=False)
        self.assertFalse(self.cli("status")["attempts"])

    def test_dependency_snapshot_detects_contract_changes_and_missing_upstream(self):
        self.initialize()
        self.spec("T2", dependencies=[{"task": "contract", "kind": "contract"}])
        self.assertFalse(self.cli("readiness", "--task", "T2")["ready"])
        self.spec("contract", state="blocked")
        self.assertTrue(self.cli("readiness", "--task", "T2")["ready"])
        run = self.verify("T2")
        self.spec("contract", state="blocked", requirement="Changed upstream promise")
        self.receipt(run["attempt"]["id"], "T2", ok=False)
        self.assertEqual(self.cli("status")["tasks"]["contract"]["spec_revision"], 2)
        cycle = self.base / "cycle.json"
        cycle.write_text(json.dumps({"requirements": ["cycle"], "acceptance": ["check"], "paths": ["source.txt"], "dependencies": [{"task": "T2", "kind": "contract"}]}))
        self.cli("task", *self.owner(), "--id", "contract", "--spec", str(cycle), ok=False)

    def test_exclusive_resources_are_atomic_across_isolated_worktrees(self):
        self.initialize(use_git=True)
        other = self.base / "other"
        self.git("worktree", "add", "-qb", "other", str(other))
        self.spec("T1", resources=["database"], state="blocked", worktree=self.project)
        self.spec("T2", resources=["database"], state="blocked", worktree=other)
        ready1, ready2 = self.base / "ready1", self.base / "ready2"
        release = self.base / "release"
        first = self.spawn("run", *self.run_args("T1", self.fake_wait(ready1, release)))
        second = self.spawn("run", *self.run_args("T2", self.fake_wait(ready2, release)), project=other)
        # Both calls race to reserve the same project-level resource. The first
        # ready marker proves one launch; the other process must fail prelaunch.
        import time
        deadline = time.monotonic() + 8
        while not (ready1.exists() or ready2.exists()) and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(ready1.exists() or ready2.exists())
        losing = second if ready1.exists() else first
        winning = first if ready1.exists() else second
        result = self.wait_process(losing, ok=False)
        self.assertIn("resources", result["error"].lower())
        self.assertEqual(len(self.cli("status")["attempts"]), 1)
        release.touch()
        self.wait_process(winning)

    def test_manual_reserved_resource_claim_is_visible_before_launch(self):
        self.initialize(use_git=True)
        other = self.base / "other"
        self.git("worktree", "add", "-qb", "other", str(other))
        self.spec("T1", resources=["database"], worktree=self.project)
        self.spec("T2", resources=["database"], worktree=other)
        self.assertFalse(self.cli("readiness", "--task", "T2")["ready"])
        self.cli("task", *self.owner(), "--id", "T1", "--state", "blocked")
        self.assertTrue(self.cli("readiness", "--task", "T2")["ready"])

    def test_receipt_and_artifact_tampering_remain_visible(self):
        initial = self.initialize()
        self.spec()
        artifact = self.project / "review.txt"
        artifact.write_text("signed-off declaration")
        run = self.verify()
        receipt = self.receipt(run["attempt"]["id"], artifacts=["review.txt"])["evidence"]
        artifact.write_text("replaced")
        status = self.cli("evidence", "--operation", "status", "--task", "T1")
        self.assertFalse(status["evidence"][0]["applicable"])
        path = Path(initial["runtime_path"]) / "evidence" / (receipt["id"] + ".json")
        raw = json.loads(path.read_text())
        raw["note"] = "rewritten"
        path.write_text(json.dumps(raw))
        status = self.cli("evidence", "--operation", "status", "--task", "T1")
        self.assertIn("tampered", status["evidence"][0]["reason"])
        second = self.receipt(run["attempt"]["id"])["evidence"]
        self.assertNotEqual(second["id"], receipt["id"])
        self.assertEqual(json.loads(path.read_text())["note"], "rewritten")

    def test_changed_verification_log_invalidates_acceptance(self):
        initial = self.initialize()
        self.spec()
        receipt = self.accepted()
        log = Path(initial["runtime_path"]) / "logs" / (receipt["source"]["attempt"] + ".log")
        log.write_text("rewritten test output")
        status = self.cli("evidence", "--operation", "status", "--task", "T1")
        self.assertFalse(status["evidence"][0]["applicable"])
        self.assertIn("log", status["evidence"][0]["reason"])

    def test_manual_evidence_requires_policy_artifact_and_independent_declaration(self):
        self.initialize(review={"level": "high", "independent": True})
        self.spec(independent=False)
        (self.project / "review.txt").write_text("manual check result")
        args = [*self.owner(), "--task", "T1", "--manual", "--reviewer", "reviewer", "--role", "reviewer", "--artifact", "review.txt", "--note", "Manual acceptance"]
        self.cli("evidence", *args, ok=False)
        patch = self.base / "allow-manual.json"
        patch.write_text('{"review":{"allow_manual":true}}')
        self.cli("configure", *self.owner(), "--patch", str(patch))
        result = self.cli("evidence", *args)
        self.assertEqual(result["evidence"]["source"]["kind"], "manual")
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified")
        patch.write_text('{"review":{"allow_manual":false}}')
        self.cli("configure", *self.owner(), "--patch", str(patch))
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified", ok=False)

    def test_independence_cannot_be_added_after_running_author_verification(self):
        self.initialize()
        self.spec(independent=True)
        run = self.verify(reviewer="owner", role="author")
        self.receipt(run["attempt"]["id"], reviewer="reviewer", role="reviewer", ok=False)
        self.receipt(run["attempt"]["id"], reviewer="owner", role="author", ok=False)

    def test_legacy_history_stays_readable_but_cannot_participate_in_new_acceptance(self):
        self.initialize()
        self.cli("task", *self.owner(), "--id", "legacy", "--state", "verified", "--note", "Historical note")
        self.assertEqual(self.cli("status")["evidence_protocol"]["legacy"], "legacy-note-only")
        status = self.cli("evidence", "--operation", "status", "--task", "legacy")
        self.assertEqual(status["protocol"], "legacy-note-only")
        self.cli("integration", *self.owner(), "--operation", "begin", "--id", "bad", "--tasks", "legacy", ok=False)
        self.spec("legacy")
        self.cli("task", *self.owner(), "--id", "legacy", "--state", "verified", "--note", "Historical note", ok=False)

    def test_integration_actual_content_is_rechecked_and_note_cannot_integrate(self):
        self.initialize()
        self.spec()
        self.accepted()
        self.cli("task", *self.owner(), "--id", "T1", "--state", "integrated", "--note", "claimed", ok=False)
        self.begin()
        run = self.verify("assembly", integration="batch")
        source = self.project / "source.txt"
        source.write_text("late integrated mutation")
        self.finish(run["attempt"]["id"], ok=False)
        self.assertEqual(self.cli("status")["tasks"]["T1"]["state"], "verified")
        source.write_text("original\n")
        ready, release = self.base / "extra-ready", self.base / "extra-release"
        extra = self.spawn("run", *self.run_args("extra-check", self.fake_wait(ready, release), action="verify", worker=None))
        self.wait_file(ready)
        self.finish(run["attempt"]["id"], ok=False)
        release.touch()
        self.wait_process(extra)
        finished = self.finish(run["attempt"]["id"])
        self.assertEqual(finished["integration"]["state"], "passed")
        self.assertFalse(finished["integration"]["merge_facts"][0]["semantic_inclusion_proven"])
        self.assertTrue(self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]["applicable"])
        source.write_text("changed after integration")
        self.assertFalse(self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]["applicable"])

    def test_integration_head_change_invalidates_current_result_not_historical_dependency(self):
        self.initialize(use_git=True)
        self.spec()
        self.accepted()
        self.begin()
        run = self.verify("assembly", integration="batch")
        self.git("commit", "--allow-empty", "-qm", "Changed target HEAD")
        failure = self.finish(run["attempt"]["id"], ok=False)
        self.assertIn("target", failure.stderr)
        newer = self.verify("assembly", integration="batch")
        self.finish(newer["attempt"]["id"])
        self.spec("dependent", dependencies=[{"task": "T1", "kind": "integrated"}])
        self.assertTrue(self.cli("readiness", "--task", "dependent")["ready"])
        self.git("commit", "--allow-empty", "-qm", "Changed accepted target")
        self.assertFalse(self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]["applicable"])
        # A consumer can still use the accepted historical commit in its ancestry.
        self.assertTrue(self.cli("readiness", "--task", "dependent")["ready"])

    def test_batch_integration_preserves_source_and_assembly_provenance(self):
        self.initialize(use_git=True)
        first, second = self.base / "first", self.base / "second"
        self.git("worktree", "add", "-qb", "first", str(first))
        self.git("worktree", "add", "-qb", "second", str(second))
        (first / "one.txt").write_text("one")
        self.git("add", "one.txt", project=first)
        self.git("commit", "-qm", "First participant", project=first)
        (second / "two.txt").write_text("two")
        self.git("add", "two.txt", project=second)
        self.git("commit", "-qm", "Second participant", project=second)
        self.spec("T1", paths=["one.txt"], worktree=first)
        self.accepted("T1")
        self.spec("T2", paths=["two.txt"], worktree=second)
        self.accepted("T2")
        self.begin(tasks=["T1", "T2"])
        self.git("merge", "--no-edit", "first", "second")
        failed = self.cli("run", *self.owner(), "--action", "verify", "--task", "assembly", "--integration", "batch", "--", *fixtures.PYTHON, "-c", "raise SystemExit(1)", ok=False)
        self.assertEqual(json.loads(failed.stdout)["attempt"]["returncode"], 1)
        observed = self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]
        self.assertFalse(observed["applicable"])
        self.assertEqual(observed["state"], "begun")
        self.assertEqual(observed["observations"][-1]["returncode"], 1)
        self.assertTrue(all(fact["source_is_ancestor"] for fact in observed["observations"][-1]["merge_facts"]))
        checked = self.verify("assembly", integration="batch", command=fixtures.PYTHON + ["-c", "from pathlib import Path; assert Path('one.txt').read_text()=='one'; assert Path('two.txt').read_text()=='two'"])
        result = self.finish(checked["attempt"]["id"])["integration"]
        self.assertEqual(result["paths"], ["one.txt", "two.txt"])
        self.assertTrue(all(fact["source_is_ancestor"] for fact in result["merge_facts"]))
        self.assertTrue(all(not fact["semantic_inclusion_proven"] for fact in result["merge_facts"]))
        handoff = self.cli("handoff", *self.owner(), "--to", "next")
        checkpoint = Path(handoff["checkpoint"]["path"])
        manifest = json.loads((checkpoint / "manifest.json").read_text())
        recovery = manifest["work_protocol"]
        self.assertEqual(len(recovery["evidence"]), 2)
        self.assertIn("batch", recovery["integrations"])
        for path, content in recovery["files"].items():
            self.assertTrue((checkpoint / "blobs" / content["sha256"]).is_file(), path)
        taken = self.cli("takeover", "--session", "next", "--client", "manual", "--handoff", handoff["handoff_id"])
        self.assertEqual(taken["epoch"], 2)
        self.assertEqual(taken["tasks"]["T1"]["state"], "integrated")
        self.assertTrue(self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]["applicable"])

    def test_required_result_gates_integration_push_but_not_backup_branch(self):
        self.initialize(use_git=True, permissions={"dispatch": "allow", "verify": "allow", "push": "allow"}, git={"push_cadence": "after-merge"})
        self.git("add", ".orchestrator/config.json")
        self.git("commit", "-qm", "Portable policy")
        remote = self.base / "offline-remote.git"
        self.git("init", "--bare", str(remote))
        self.git("remote", "add", "offline", str(remote))
        self.spec()
        self.accepted()
        self.begin(extra=["--require-push"])
        push = [*self.owner(), "--action", "push", "--", "git", "push", "offline"]
        self.cli("guard", *push, "main:refs/heads/main", ok=False)
        self.cli("guard", *push, "main:refs/heads/backup")
        run = self.verify("assembly", integration="batch")
        self.finish(run["attempt"]["id"])
        self.cli("guard", *push, "main:refs/heads/main")
        self.git("commit", "--allow-empty", "-qm", "Unverified target commit")
        self.cli("guard", *push, "main:refs/heads/main", ok=False)
        self.cli("guard", *push, "main:refs/heads/backup")


if __name__ == "__main__":
    unittest.main()
