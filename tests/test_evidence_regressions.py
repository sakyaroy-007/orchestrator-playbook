"""Review regressions for durable provenance and actual scoped content."""
import unittest

import test_playbook as base_fixtures
import test_work_protocol as work_fixtures


class EvidenceRegressionTests(unittest.TestCase):
    setUp = base_fixtures.PlaybookTests.setUp
    tearDown = base_fixtures.PlaybookTests.tearDown
    cli = base_fixtures.PlaybookTests.cli
    owner = base_fixtures.PlaybookTests.owner
    config = base_fixtures.PlaybookTests.config
    init = base_fixtures.PlaybookTests.init
    git = base_fixtures.PlaybookTests.git
    git_project = base_fixtures.PlaybookTests.git_project
    spec = work_fixtures.WorkProtocolTests.spec
    verify = work_fixtures.WorkProtocolTests.verify
    receipt = work_fixtures.WorkProtocolTests.receipt
    accepted = work_fixtures.WorkProtocolTests.accepted
    initialize = work_fixtures.WorkProtocolTests.initialize
    begin = work_fixtures.WorkProtocolTests.begin
    finish = work_fixtures.WorkProtocolTests.finish

    def test_handoff_cannot_turn_the_same_author_attempt_into_independent_review(self):
        self.initialize(review={"independent": True})
        self.spec()
        attempt = self.verify(reviewer="owner")["attempt"]
        rejected = self.receipt(attempt["id"], reviewer="owner", ok=False)
        self.assertIn("Independent review", rejected.stderr)
        handoff = self.cli("handoff", *self.owner(), "--to", "next")
        self.cli("takeover", "--session", "next", "--client", "manual", "--handoff", handoff["handoff_id"])
        updated = self.cli("task", *self.owner("next", 2), "--id", "T1", "--state", "reported")
        self.assertEqual(updated["task"]["implementers"], ["next", "owner"])
        rejected = self.cli("evidence", *self.owner("next", 2), "--task", "T1", "--attempt", attempt["id"],
                            "--reviewer", "owner", "--role", "reviewer", "--note", "Same original check", ok=False)
        self.assertIn("Independent review", rejected.stderr)
        self.assertIn("owner", attempt["implementers"])
        # A new declaration by an actually distinct reviewer remains usable.
        new = self.cli("run", *self.owner("next", 2), "--action", "verify", "--task", "T1",
                       "--reviewer", "third", "--role", "reviewer", "--", *base_fixtures.PYTHON, "-c", "pass")["attempt"]
        self.cli("evidence", *self.owner("next", 2), "--task", "T1", "--attempt", new["id"],
                 "--reviewer", "third", "--role", "reviewer", "--note", "Distinct reviewer")
        self.cli("task", *self.owner("next", 2), "--id", "T1", "--state", "verified")

    def test_directory_deletion_survives_staging_and_committing_without_content_changes(self):
        self.initialize(use_git=True)
        scope = self.project / "scope"
        nested = scope / "nested"
        nested.mkdir(parents=True)
        (nested / "removed.txt").write_text("old source")
        (scope / "retained.txt").write_text("retained source")
        self.git("add", "scope")
        self.git("commit", "-qm", "Scoped sources")
        self.spec(paths=["scope"])
        self.accepted()
        (nested / "removed.txt").unlink()
        self.assertFalse(self.cli("evidence", "--operation", "status", "--task", "T1")["evidence"][0]["applicable"])
        receipt = self.accepted()
        before = receipt["content"]["sha256"]
        self.git("add", "--", "scope/nested/removed.txt")
        staged = self.cli("evidence", "--operation", "status", "--task", "T1")["evidence"][-1]
        self.assertTrue(staged["applicable"], staged)
        self.receipt(receipt["source"]["attempt"])
        self.git("commit", "-qm", "Record already tested deletion")
        committed = self.cli("evidence", "--operation", "status", "--task", "T1")["evidence"][-1]
        self.assertTrue(committed["applicable"], committed)
        self.assertEqual(committed["receipt"]["content"]["sha256"], before)
        (nested / "removed.txt").write_text("restored source")
        self.assertFalse(self.cli("evidence", "--operation", "status", "--task", "T1")["evidence"][-1]["applicable"])

    def test_explicit_git_scopes_respect_exclusion_and_tracked_exception(self):
        self.initialize(use_git=True)
        (self.project / ".env").write_text("FAKE_VALUE=fixture")
        cache = self.project / "node_modules"
        cache.mkdir()
        (cache / "offline").write_text("fake cache")
        for index, path in enumerate((".env", "node_modules/offline", "node_modules")):
            with self.subTest(path=path):
                task = "excluded" + str(index)
                self.spec(task, paths=[path])
                result = self.cli("readiness", "--task", task)
                self.assertFalse(result["ready"], result)
                self.assertIn("excluded", " ".join(result["blockers"]))
                self.cli("task", *self.owner(), "--id", task, "--state", "blocked")
        self.git("add", "-f", ".env", "node_modules/offline")
        self.spec("tracked", paths=[".env", "node_modules"])
        receipt = self.accepted("tracked")
        self.assertIn(".env", receipt["content"]["entries"])
        self.assertIn("node_modules/offline", receipt["content"]["entries"])
        self.assertNotIn(".env", receipt["content"]["excluded"])
        self.assertNotIn("node_modules", receipt["content"]["excluded"])

    def integrated_worker(self, artifact=False):
        self.initialize(use_git=True, permissions={"dispatch": "allow", "verify": "allow", "cleanup": "allow", "push": "allow"},
                        git={"cleanup_mode": "after-merge", "push_cadence": "after-merge"})
        self.git("add", ".orchestrator/config.json")
        self.git("commit", "-qm", "Portable test policy")
        worker = self.base / "worker"
        self.git("worktree", "add", "-qb", "worker", str(worker))
        (worker / "source.txt").write_text("tested worker result\n")
        if artifact:
            (worker / "review.txt").write_text("explicit retained evidence\n")
        self.git("add", ".", project=worker)
        self.git("commit", "-qm", "Worker result", project=worker)
        self.spec(worktree=worker)
        attempt = self.verify()["attempt"]["id"]
        receipt = self.receipt(attempt, artifacts=["review.txt"] if artifact else [])["evidence"]
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified")
        self.begin(extra=["--require-push"])
        self.git("merge", "--ff-only", "worker")
        self.finish(self.verify("assembly", integration="batch")["attempt"]["id"])
        self.assertTrue(self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]["applicable"])
        self.cli("checkpoint", *self.owner())
        self.cli("guard", *self.owner(), "--action", "cleanup", "--", "git", "worktree", "remove", str(worker))
        self.assertFalse(worker.exists())
        return receipt

    def test_approved_worker_cleanup_retains_integration_and_local_push_gate(self):
        self.integrated_worker()
        current = self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]
        self.assertTrue(current["applicable"], current)
        remote = self.base / "offline.git"
        self.git("init", "--bare", str(remote))
        self.git("remote", "add", "offline", str(remote))
        self.cli("guard", *self.owner(), "--action", "push", "--", "git", "push", "offline", "main:refs/heads/main")
        self.assertEqual(self.git("rev-parse", "main", project=remote), self.git("rev-parse", "main"))

    def test_explicit_artifact_still_requires_its_retained_source_after_cleanup(self):
        self.integrated_worker(artifact=True)
        current = self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]
        self.assertFalse(current["applicable"], current)
        self.assertIn("directory", current["reason"])


if __name__ == "__main__":
    unittest.main()
