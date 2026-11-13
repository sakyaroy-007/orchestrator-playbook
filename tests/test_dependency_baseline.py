"""Actual consumer baselines for integrated dependencies; local Git only."""
import unittest

import test_playbook as base_fixtures
import test_work_protocol as work_fixtures


class DependencyBaselineTests(unittest.TestCase):
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
    begin = work_fixtures.WorkProtocolTests.begin
    finish = work_fixtures.WorkProtocolTests.finish

    def upstream(self, committed=True, kind="integrated"):
        self.git_project()
        self.original = self.git("rev-parse", "HEAD")
        self.consumer = self.base / "consumer"
        self.git("worktree", "add", "-qb", "consumer", str(self.consumer))
        self.init(self.config())
        (self.project / "source.txt").write_text("upstream feature\n")
        if committed:
            self.git("add", "source.txt")
            self.git("commit", "-qm", "upstream feature")
        self.spec("upstream")
        self.accepted("upstream")
        self.begin(tasks=["upstream"])
        attempt = self.verify("assembly", integration="batch")["attempt"]["id"]
        self.finish(attempt)
        (self.consumer / "consumer.txt").write_text("consumer work\n")
        self.spec("consumer", paths=["consumer.txt"], worktree=self.consumer,
                  dependencies=[{"task": "upstream", "kind": kind}])

    def test_missing_integration_blocks_before_launch_then_merged_baseline_runs(self):
        self.upstream()
        before = self.cli("status")["attempts"]
        ready = self.cli("readiness", "--task", "consumer")
        self.assertFalse(ready["ready"])
        self.assertIn("Consumer baseline", " ".join(ready["blockers"]))
        command = [*self.owner(), "--action", "dispatch", "--task", "consumer", "--worker", "fake", "--",
                   *base_fixtures.PYTHON, "-c", "from pathlib import Path; Path('launched').write_text('ran')"]
        self.cli("run", *command, ok=False)
        self.assertFalse((self.consumer / "launched").exists())
        self.assertEqual(self.cli("status")["attempts"], before)
        self.git("merge", "--ff-only", "main", project=self.consumer)
        self.assertTrue(self.cli("readiness", "--task", "consumer")["ready"])
        self.cli("run", *command)
        self.assertEqual((self.consumer / "launched").read_text(), "ran")
        # Ordinary downstream edits on top of the accepted commit stay possible.
        (self.consumer / "source.txt").write_text("upstream plus downstream\n")
        self.accepted("consumer")

    def test_equal_head_does_not_carry_uncommitted_upstream_content(self):
        self.upstream(committed=False)
        self.assertEqual(self.git("rev-parse", "HEAD", project=self.consumer), self.git("rev-parse", "HEAD"))
        ready = self.cli("readiness", "--task", "consumer")
        self.assertFalse(ready["ready"])
        self.assertIn("uncommitted integrated dependency", " ".join(ready["blockers"]))
        (self.consumer / "source.txt").write_text("upstream feature\n")
        self.assertTrue(self.cli("readiness", "--task", "consumer")["ready"])
        self.accepted("consumer")

    def test_receipt_becomes_inapplicable_when_consumer_loses_upstream_baseline(self):
        self.upstream()
        self.git("merge", "--ff-only", "main", project=self.consumer)
        self.accepted("consumer")
        original_content = (self.consumer / "consumer.txt").read_bytes()
        self.git("reset", "--hard", self.original, project=self.consumer)
        self.assertEqual((self.consumer / "consumer.txt").read_bytes(), original_content)
        receipt = self.cli("evidence", "--operation", "status", "--task", "consumer")["evidence"][0]
        self.assertFalse(receipt["applicable"])
        self.assertIn("Consumer baseline", receipt["reason"])
        self.cli("task", *self.owner(), "--id", "consumer", "--state", "verified", ok=False)

    def test_dependent_task_can_be_integrated_after_its_upstream(self):
        self.upstream()
        self.git("merge", "--ff-only", "main", project=self.consumer)
        self.git("add", "consumer.txt", project=self.consumer)
        self.git("commit", "-qm", "dependent result", project=self.consumer)
        self.accepted("consumer")
        self.begin(integration="downstream", tasks=["consumer"])
        self.git("merge", "--ff-only", "consumer")
        attempt = self.verify("assembly-downstream", integration="downstream")["attempt"]["id"]
        self.finish(attempt, integration="downstream")
        current = self.cli("integration", "--operation", "status", "--id", "downstream")
        self.assertTrue(current["integrations"][0]["applicable"])

    def test_later_source_edits_do_not_reclassify_a_committed_result(self):
        self.upstream()
        self.git("merge", "--ff-only", "main", project=self.consumer)
        (self.consumer / "source.txt").write_text("upstream plus downstream\n")
        (self.project / "source.txt").write_text("later upstream edit\n")
        self.assertTrue(self.cli("readiness", "--task", "consumer")["ready"])
        self.accepted("consumer")
        self.assertFalse(self.cli("integration", "--operation", "status", "--id", "batch")["integrations"][0]["applicable"])

    def test_later_commit_does_not_reclassify_an_uncommitted_result(self):
        self.upstream(committed=False)
        self.git("add", "source.txt")
        self.git("commit", "-qm", "Commit previously dirty upstream result")
        ready = self.cli("readiness", "--task", "consumer")
        self.assertFalse(ready["ready"])
        self.assertIn("uncommitted integrated dependency", " ".join(ready["blockers"]))
        (self.consumer / "source.txt").write_text("upstream feature\n")
        self.assertTrue(self.cli("readiness", "--task", "consumer")["ready"])

    def test_rebatching_upstream_and_consumer_keeps_historical_bindings_acyclic(self):
        self.upstream()
        self.git("merge", "--ff-only", "main", project=self.consumer)
        self.git("add", "consumer.txt", project=self.consumer)
        self.git("commit", "-qm", "Dependent result", project=self.consumer)
        self.accepted("consumer")
        self.begin(integration="combined", tasks=["upstream", "consumer"])
        self.git("merge", "--ff-only", "consumer")
        attempt = self.verify("assembly-combined", integration="combined")["attempt"]["id"]
        self.finish(attempt, integration="combined")
        result = self.cli("integration", "--operation", "status", "--id", "combined")["integrations"][0]
        self.assertTrue(result["applicable"], result)
        consumer = next(item for item in result["participants"] if item["task"] == "consumer")
        self.assertEqual(consumer["dependencies"][0]["integration"], "batch")
        self.spec("third", paths=["consumer.txt"], dependencies=[{"task": "consumer", "kind": "integrated"}])
        self.assertTrue(self.cli("readiness", "--task", "third")["ready"])

    def test_contract_only_dependency_does_not_require_implementation(self):
        self.upstream(kind="contract")
        self.assertEqual((self.consumer / "source.txt").read_text(), "original\n")
        self.assertTrue(self.cli("readiness", "--task", "consumer")["ready"])
        self.accepted("consumer")


if __name__ == "__main__":
    unittest.main()
