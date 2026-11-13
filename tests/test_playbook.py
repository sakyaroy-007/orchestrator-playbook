#!/usr/bin/env python3
"""External-contract tests: temporary projects and fake workers only."""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


RUNTIME = Path(__file__).resolve().parents[1] / "scripts" / "playbook.py"
PYTHON = [sys.executable, "-I"]


class PlaybookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="playbook-test-")
        self.base = Path(self.tmp.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.children = []
        self.worker_groups = []

    def tearDown(self):
        for process in self.children:
            if process.poll() is None:
                process.kill()
            process.wait()
        for group in self.worker_groups:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.tmp.cleanup()

    def cli(self, action, *args, project=None, ok=True, env=None, cwd=None):
        result = subprocess.run(
            PYTHON + [str(RUNTIME), action, "--project", str(project or self.project)] + list(args),
            capture_output=True, text=True, timeout=20, env=env, cwd=cwd,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stderr.strip(), "Failures need an actionable message")
        return result

    def injected_cli(self, injection, action, *args, env=None):
        program = ("import importlib.util,sys; spec=importlib.util.spec_from_file_location('fixture_runtime',sys.argv[1]); "
                   "runtime=importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime); "
                   "exec(sys.argv[2],{'runtime':runtime}); sys.exit(runtime.main(sys.argv[3:]))")
        return subprocess.run(PYTHON + ["-c", program, str(RUNTIME), injection, action, "--project", str(self.project)] + list(args),
                              capture_output=True, text=True, timeout=20, env=env)

    def executable(self, path, program):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!" + sys.executable + " -I\n" + program + "\n")
        path.chmod(0o755)

    def owner(self, session="owner", epoch=1):
        return ["--session", session, "--epoch", str(epoch)]

    def config(self, **changes):
        value = {
            "workers": [{"id": "fake", "client": "manual"}],
            "permissions": {"dispatch": "allow", "verify": "allow", "commit": "allow",
                            "worktree-create": "allow"},
            "limits": {"agents": 2, "heavy_jobs": 1, "timeout_seconds": 5, "max_attempts": 2},
        }
        value.update(changes)
        target = self.base / "answers.json"
        target.write_text(json.dumps(value))
        return target

    def init(self, config=None, adopt=False, project=None):
        args = ["--session", "owner", "--client", "codex", "--goal", "A tested outcome"]
        if config:
            args += ["--config", str(config)]
        if adopt:
            args.append("--adopt")
        return self.cli("init", *args, project=project)

    def git(self, *args, project=None):
        result = subprocess.run(["git", "-C", str(project or self.project), *args],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def git_project(self):
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.project / "source.txt").write_text("original\n")
        self.git("add", "source.txt")
        self.git("commit", "-qm", "Initial fixture")

    def spawn(self, action, *args, project=None):
        process = subprocess.Popen(
            PYTHON + [str(RUNTIME), action, "--project", str(project or self.project)] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.children.append(process)
        return process

    def wait_file(self, path):
        end = time.monotonic() + 8
        while time.monotonic() < end:
            if path.exists():
                return
            time.sleep(0.03)
        self.fail("Child did not reach synchronization point: " + str(path))

    def wait_process(self, process, ok=True):
        out, err = process.communicate(timeout=15)
        if ok:
            self.assertEqual(process.returncode, 0, err + out)
        else:
            self.assertNotEqual(process.returncode, 0)
        return json.loads(out) if out.strip() else {"error": err}

    def fake_wait(self, ready, release):
        return PYTHON + ["-c", "import pathlib,sys,time; "
                         "pathlib.Path(sys.argv[1]).write_text('ready'); "
                         "\nwhile not pathlib.Path(sys.argv[2]).exists(): time.sleep(.02)",
                         str(ready), str(release)]

    def run_args(self, task, command, action="dispatch", worker="fake"):
        args = self.owner() + ["--action", action, "--task", task]
        if worker:
            args += ["--worker", worker]
        return args + ["--"] + command

    def test_discovery_and_doctor_do_not_create_state(self):
        before = list(self.project.rglob("*"))
        discovered = self.cli("discover")
        self.assertFalse(discovered["initialized"])
        self.assertIn("codex", discovered["clients"])
        self.cli("doctor")
        self.assertEqual(list(self.project.rglob("*")), before)
        first = self.cli("session-id")["session"]
        self.assertNotEqual(first, self.cli("session-id")["session"])

    def test_init_defaults_idempotence_and_session_conflict(self):
        state = self.init()
        self.assertEqual(state["epoch"], 1)
        config = json.loads(Path(state["config_path"]).read_text())
        self.assertEqual(config["schema_version"], 1)
        self.assertEqual(config["permissions"]["dispatch"], "ask")
        again = self.init()
        self.assertEqual(state["project_id"], again["project_id"])
        self.cli("init", "--session", "other", "--client", "codex", "--goal", "A tested outcome", ok=False)
        self.cli("resume", *self.owner("other"), ok=False)
        self.cli("resume", *self.owner(epoch=2), ok=False)

    def test_legacy_adoption_preserves_existing_bytes(self):
        legacy = self.project / ".orchestrator" / "TEAM.md"
        legacy.parent.mkdir()
        legacy.write_bytes(b"existing legacy content\x00\n")
        self.cli("init", "--session", "owner", "--client", "codex", "--goal", "x", ok=False)
        self.init(adopt=True)
        self.assertEqual(legacy.read_bytes(), b"existing legacy content\x00\n")

    def test_schema_errors_do_not_initialize_project(self):
        bad_values = [[], {"schema_version": 2}, {"limits": {"agents": True}},
                      {"limits": {"agents": 0}}, {"permissions": {"push": "yes"}},
                      {"permissions": {"pussh": "allow"}}, {"paths": {"plan": "../outside"}},
                      {"workers": [{"id": "a", "client": "manual", "effort": {"mode": "fixed"}}]},
                      {"workers": [{"id": "a", "client": "manual"}] * 2},
                      {"secret_key": "not-a-config-field"}]
        for value in bad_values:
            with self.subTest(value=value):
                config = self.base / "invalid.json"
                config.write_text(json.dumps(value))
                self.cli("init", "--session", "owner", "--client", "codex", "--goal", "x",
                         "--config", str(config), ok=False)
                self.assertFalse((self.project / ".orchestrator" / "config.json").exists())

    def test_configure_preserves_ownership_tasks_and_increments_revision(self):
        initial = self.init()
        self.cli("task", *self.owner(), "--id", "T1", "--state", "reserved")
        changed = self.cli("configure", *self.owner(), "--config", str(self.config()))
        self.assertEqual(changed["project_id"], initial["project_id"])
        self.assertEqual(changed["epoch"], 1)
        self.assertEqual(changed["config_revision"], 2)
        self.assertEqual(changed["tasks"]["T1"]["state"], "reserved")

    def test_handoff_target_repeat_takeover_and_stale_owner(self):
        self.init()
        handoff = self.cli("handoff", *self.owner(), "--to", "next")
        repeat = self.cli("handoff", *self.owner(), "--to", "next")
        self.assertEqual(handoff["handoff_id"], repeat["handoff_id"])
        self.cli("task", *self.owner(), "--id", "new", "--state", "reserved", ok=False)
        self.cli("takeover", "--session", "wrong", "--client", "codex", "--handoff", handoff["handoff_id"], ok=False)
        args = ["--session", "next", "--client", "codex", "--handoff", handoff["handoff_id"]]
        taken = self.cli("takeover", *args)
        self.assertEqual(taken["epoch"], 2)
        self.assertEqual(self.cli("takeover", *args)["epoch"], 2)
        self.cli("resume", *self.owner(), ok=False)

    def test_changed_baseline_prevents_prepared_takeover(self):
        self.init()
        handoff = self.cli("handoff", *self.owner())
        (self.project / "late.txt").write_text("late work")
        failed = self.cli("takeover", "--session", "next", "--client", "codex",
                          "--handoff", handoff["handoff_id"], ok=False)
        self.assertIn("baseline", failed.stderr.lower())
        self.assertEqual(self.cli("status")["epoch"], 1)
        recovered = self.cli("takeover", "--session", "next", "--client", "codex", "--recover", "--previous-stopped")
        self.assertEqual(recovered["epoch"], 2)

    def test_recovery_requires_attestation_and_preserves_unknown_tasks(self):
        self.init()
        self.cli("task", *self.owner(), "--id", "external", "--state", "running")
        self.cli("takeover", "--session", "next", "--client", "codex", "--recover", ok=False)
        recovered = self.cli("takeover", "--session", "next", "--client", "codex", "--recover", "--previous-stopped")
        self.assertEqual(recovered["tasks"]["external"]["state"], "unknown")
        self.assertEqual(self.cli("takeover", "--session", "next", "--client", "codex", "--recover", "--previous-stopped")["epoch"], 2)

    def test_pause_resume_reports_changes_without_dispatch(self):
        self.init(self.config())
        self.cli("pause", *self.owner())
        marker = self.base / "should-not-exist"
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", f"open({str(marker)!r},'w').close()"]), ok=False)
        (self.project / "change").write_text("changed after pause")
        result = self.cli("resume", *self.owner())
        self.assertTrue(result["baseline_changed"])
        self.assertEqual(result["mode"], "active")
        self.assertFalse(marker.exists())

    def test_git_snapshot_copies_dirty_staged_binary_untracked_and_symlink(self):
        self.git_project()
        (self.project / "source.txt").write_text("staged\n")
        self.git("add", "source.txt")
        (self.project / "source.txt").write_text("working\n")
        (self.project / "new.bin").write_bytes(bytes(range(256)))
        (self.project / "link").symlink_to("source.txt")
        initial = self.init(adopt=True)
        saved = self.cli("checkpoint", *self.owner())["checkpoint"]
        directory = Path(saved["path"])
        self.assertIn(Path(initial["runtime_path"]), directory.parents)
        manifest = json.loads((directory / "manifest.json").read_text())
        tree = manifest["capture"]["worktrees"][0]
        entries = tree["files"]
        self.assertEqual((directory / "blobs" / entries["source.txt"]["sha256"]).read_bytes(), b"working\n")
        self.assertEqual((directory / "blobs" / entries["new.bin"]["sha256"]).read_bytes(), bytes(range(256)))
        self.assertEqual(entries["link"]["kind"], "symlink")
        self.assertEqual((directory / "blobs" / entries["link"]["sha256"]).read_bytes(), b"source.txt")
        staged = (directory / "blobs" / tree["staged_patch"]["sha256"]).read_bytes()
        unstaged = (directory / "blobs" / tree["unstaged_patch"]["sha256"]).read_bytes()
        self.assertIn(b"+staged", staged)
        self.assertIn(b"+working", unstaged)
        status = self.git("status", "--porcelain", "--untracked-files=all")
        self.assertNotIn("manifest.json", status)
        self.assertNotIn("state.json", status)

    def test_non_git_snapshot_is_ignored_if_git_is_later_initialized(self):
        self.init()
        self.cli("checkpoint", *self.owner())
        self.git("init", "-q")
        status = self.git("status", "--porcelain", "--untracked-files=all")
        self.assertNotIn("state.json", status)
        self.assertNotIn("manifest.json", status)
        self.assertIn("config.json", status)

    def test_oversize_checkpoint_fails_without_preparing_handoff(self):
        self.init()
        with (self.project / "huge.bin").open("wb") as handle:
            handle.truncate(65 * 1024 * 1024)
        failed = self.cli("handoff", *self.owner(), ok=False)
        self.assertIn("64 MiB", failed.stderr)
        state = self.cli("status")
        self.assertEqual(state["mode"], "active")
        self.assertIsNotNone(state["checkpoint_failure"])
        self.assertFalse(json.loads((Path(state["checkpoint_failure"]["path"]) / "failure.json").read_text())["complete"])

    def test_tampered_recovery_copy_blocks_takeover(self):
        (self.project / "source").write_text("valuable work")
        self.init()
        handoff = self.cli("handoff", *self.owner())
        objects = Path(handoff["checkpoint"]["path"]) / "blobs"
        next(objects.iterdir()).write_text("corrupt")
        self.cli("takeover", "--session", "next", "--client", "codex", "--handoff", handoff["handoff_id"], ok=False)
        self.assertEqual(self.cli("status")["epoch"], 1)

    def test_linked_worktrees_share_owner_config_and_lock(self):
        self.git_project()
        state = self.init()
        linked = self.base / "linked"
        self.git("worktree", "add", "-qb", "linked", str(linked))
        other = self.cli("status", project=linked)
        self.assertEqual(other["runtime_path"], state["runtime_path"])
        self.assertEqual(other["config_path"], state["config_path"])
        self.cli("init", "--session", "other", "--client", "codex", "--goal", "x", project=linked, ok=False)
        (linked / "worker.txt").write_text("worktree data")
        snap = self.cli("checkpoint", *self.owner())["checkpoint"]
        manifest = json.loads((Path(snap["path"]) / "manifest.json").read_text())
        self.assertEqual(len(manifest["capture"]["worktrees"]), 2)
        self.assertTrue(any("worker.txt" in tree["files"] for tree in manifest["capture"]["worktrees"]))

    def test_missing_permissions_and_denied_push_never_execute(self):
        self.git_project()
        self.init()
        marker = self.base / "not-executed"
        command = PYTHON + ["-c", f"open({str(marker)!r},'w').close()"]
        self.cli("guard", *self.owner(), "--action", "push", "--", *command, ok=False)
        self.cli("run", *self.run_args("T1", command), ok=False)
        self.assertFalse(marker.exists())

    def test_guard_serializes_with_handoff(self):
        self.git_project()
        linked = self.base / "linked"
        self.git("worktree", "add", "-qb", "linked", str(linked))
        self.init(self.config())
        ready, release = self.base / "ready", self.base / "release"
        guard = self.spawn("guard", *self.owner(), "--action", "commit", "--", *self.fake_wait(ready, release))
        self.wait_file(ready)
        handoff = self.spawn("handoff", *self.owner(), project=linked)
        time.sleep(0.2)
        self.assertIsNone(handoff.poll())
        release.touch()
        self.wait_process(guard)
        self.wait_process(handoff)
        self.assertEqual(self.cli("status")["mode"], "prepared")

    def test_success_is_only_reported_and_command_arguments_are_literal(self):
        self.init(self.config())
        marker = self.base / "shell-must-not-run"
        literal = "$(touch " + str(marker) + "); ' quoted"
        command = PYTHON + ["-c", "import sys; print(sys.argv[1])", literal]
        result = self.cli("run", *self.run_args("T1", command))
        self.assertEqual(result["attempt"]["returncode"], 0)
        state = self.cli("status")
        self.assertEqual(state["tasks"]["T1"]["state"], "reported")
        self.assertIn(literal, Path(result["attempt"]["log"]).read_text())
        self.assertFalse(marker.exists())
        self.cli("run", *self.run_args("T1", command), ok=False)

    def test_duplicate_live_attempt_and_resource_limit_block_launch(self):
        self.init(self.config(limits={"agents": 1, "heavy_jobs": 1, "timeout_seconds": 10, "max_attempts": 2}))
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("run", *self.run_args("T1", self.fake_wait(ready, release)))
        self.wait_file(ready)
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", "pass"]), ok=False)
        self.cli("run", *self.run_args("T2", PYTHON + ["-c", "pass"]), ok=False)
        release.touch()
        self.wait_process(running)

    def test_verify_with_reviewer_counts_both_resource_limits(self):
        self.git_project()
        self.init(self.config(limits={"agents": 1, "heavy_jobs": 1, "timeout_seconds": 10, "max_attempts": 2}))
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("run", *self.run_args("review", self.fake_wait(ready, release), action="verify"))
        self.wait_file(ready)
        denied = self.cli("run", *self.run_args("dispatch", PYTHON + ["-c", "pass"]), ok=False)
        self.assertIn("Agent limit", denied.stderr)
        denied = self.cli("run", *self.run_args("verify", PYTHON + ["-c", "pass"], action="verify", worker=None), ok=False)
        self.assertIn("Heavy-job limit", denied.stderr)
        release.touch()
        self.wait_process(running)

    def test_late_result_does_not_restore_previous_owner_or_accept_task(self):
        self.init(self.config())
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("run", *self.run_args("T1", self.fake_wait(ready, release)))
        self.wait_file(ready)
        handoff = self.cli("handoff", *self.owner())
        self.cli("takeover", "--session", "next", "--client", "codex", "--handoff", handoff["handoff_id"])
        release.touch()
        result = self.wait_process(running)
        self.assertTrue(result["attempt"]["late_result"])
        state = self.cli("status")
        self.assertEqual(state["owner"]["session"], "next")
        self.assertEqual(state["tasks"]["T1"]["state"], "unknown")
        self.assertEqual(state["attempts"][-1]["returncode"], 0)

    def test_timeout_kills_only_its_process_group(self):
        self.init(self.config(limits={"timeout_seconds": 1}))
        unrelated = subprocess.Popen(PYTHON + ["-c", "import time; time.sleep(30)"], start_new_session=True)
        self.children.append(unrelated)
        result = self.cli("run", *self.run_args("slow", PYTHON + ["-c", "import time; time.sleep(30)"]), ok=False)
        data = json.loads(result.stdout)
        self.assertTrue(data["attempt"]["timed_out"])
        self.assertIsNone(unrelated.poll())
        self.assertEqual(self.cli("status")["tasks"]["slow"]["state"], "blocked")

    def test_interrupted_runner_retains_unknown_and_never_relaunches(self):
        self.init(self.config())
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("run", *self.run_args("T1", self.fake_wait(ready, release)))
        self.wait_file(ready)
        recorded = self.cli("status")["attempts"][-1]
        self.worker_groups.append(recorded["process"]["pid"])
        running.send_signal(signal.SIGTERM)
        self.wait_process(running, ok=False)
        state = self.cli("status")
        self.assertEqual(state["tasks"]["T1"]["state"], "unknown")
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", "pass"]), ok=False)
        diagnosis = self.cli("doctor")
        self.assertTrue(diagnosis["issues"])
        release.touch()

    def test_attempt_limit_requires_reconciliation_and_is_not_reset(self):
        self.init(self.config(limits={"max_attempts": 1}))
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", "raise SystemExit(7)"]), ok=False)
        self.cli("task", *self.owner(), "--id", "T1", "--state", "reserved", "--note", "Failure inspected")
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", "pass"]), ok=False)

    def test_unresolved_worker_settings_block_before_attempt(self):
        self.init(self.config(workers=[{"id": "fake", "client": "manual", "model": {"mode": "recommend", "value": "proposal"}}]))
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", "pass"]), ok=False)
        self.assertNotIn("T1", self.cli("status")["tasks"])

    def test_status_inside_guard_is_read_only_and_does_not_deadlock(self):
        self.git_project()
        initial = self.init(self.config())
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("guard", *self.owner(), "--action", "commit", "--", *self.fake_wait(ready, release))
        self.wait_file(ready)
        state_path = Path(initial["runtime_path"]) / "state.json"
        before = state_path.read_bytes()
        status = self.cli("status")
        self.assertEqual(status["project_root"], str(self.project))
        self.assertEqual(before, state_path.read_bytes())
        self.assertIsNone(running.poll())
        release.touch()
        self.wait_process(running)

    def test_configuration_revision_fences_stale_adapter_command(self):
        self.init(self.config())
        self.cli("configure", *self.owner(), "--config", str(self.config()))
        marker = self.base / "must-not-launch"
        arguments = self.owner() + ["--action", "dispatch", "--task", "T1", "--worker", "fake", "--config-revision", "1",
                                    "--"] + PYTHON + ["-c", f"open({str(marker)!r}, 'w').close()"]
        failed = self.cli("run", *arguments, ok=False)
        self.assertIn("revision", failed.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(self.cli("status")["attempts"], [])

    def test_child_observes_durable_attempt_and_canonical_project_environment(self):
        initial = self.init(self.config())
        state_path = Path(initial["runtime_path"]) / "state.json"
        program = "import json,os,pathlib,sys; s=json.loads(pathlib.Path(sys.argv[1]).read_text()); assert s['attempts'][-1]['task']=='T1'; print(os.environ['PLAYBOOK_PROJECT'])"
        result = self.cli("run", *self.run_args("T1", PYTHON + ["-c", program, str(state_path)]))
        self.assertEqual(Path(result["attempt"]["log"]).read_text().strip(), str(self.project))
        self.assertFalse(result["accepted"])
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified", ok=False)
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified", "--note", "Observed expected external result")

    def test_manual_push_cadence_and_retention_override_allowed_permission(self):
        self.git_project()
        self.init(self.config(permissions={"push": "allow", "cleanup": "allow"}))
        marker = self.base / "must-not-run"
        command = PYTHON + ["-c", f"open({str(marker)!r}, 'w').close()"]
        failed = self.cli("guard", *self.owner(), "--action", "push", "--", *command, ok=False)
        self.assertIn("push_cadence=manual", failed.stderr)
        failed = self.cli("guard", *self.owner(), "--action", "cleanup", "--", *command, ok=False)
        self.assertIn("cleanup_mode=retain", failed.stderr)
        self.assertFalse(marker.exists())

    def test_non_git_guard_cannot_acquire_git_actions(self):
        self.init(self.config())
        self.cli("guard", *self.owner(), "--action", "commit", "--", *PYTHON, "-c", "pass", ok=False)
        self.assertFalse((self.project / ".git").exists())

    def test_worktree_resources_allow_parallel_isolated_jobs(self):
        self.git_project()
        self.init(self.config(limits={"agents": 2, "timeout_seconds": 15}))
        linked = self.base / "linked space"
        self.git("worktree", "add", "-qb", "linked", str(linked))
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("run", *self.run_args("T1", self.fake_wait(ready, release)))
        self.wait_file(ready)
        args = self.owner() + ["--action", "dispatch", "--task", "T2", "--worker", "fake", "--cwd", str(linked), "--"] + PYTHON + ["-c", "print('second worktree')"]
        completed = self.cli("run", *args, project=linked)
        self.assertEqual(completed["attempt"]["returncode"], 0)
        self.assertIsNone(running.poll())
        release.touch()
        self.wait_process(running)

    def test_non_git_remains_serial_even_with_multiple_resource_slots(self):
        self.init(self.config(limits={"agents": 5, "heavy_jobs": 5, "timeout_seconds": 10}))
        subdir = self.project / "subdir"
        subdir.mkdir()
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("run", *self.run_args("T1", self.fake_wait(ready, release)))
        self.wait_file(ready)
        args = self.owner() + ["--action", "verify", "--task", "T2", "--cwd", str(subdir), "--"] + PYTHON + ["-c", "pass"]
        denied = self.cli("run", *args, ok=False)
        self.assertIn("serially", denied.stderr)
        release.touch()
        self.wait_process(running)

    def test_live_attempt_cannot_be_marked_absent_or_verified(self):
        self.init(self.config())
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("run", *self.run_args("T1", self.fake_wait(ready, release)))
        self.wait_file(ready)
        failed = self.cli("task", *self.owner(), "--id", "T1", "--state", "blocked", "--note", "assumed stopped", ok=False)
        self.assertIn("live process", failed.stderr)
        self.cli("task", *self.owner(), "--id", "T1", "--state", "verified", "--note", "no evidence", ok=False)
        release.touch()
        self.wait_process(running)

    def test_sigkill_retains_unknown_execution_and_needs_explicit_reconciliation(self):
        self.init(self.config())
        ready, release = self.base / "ready", self.base / "release"
        running = self.spawn("run", *self.run_args("T1", self.fake_wait(ready, release)))
        self.wait_file(ready)
        worker_pid = self.cli("status")["attempts"][-1]["process"]["pid"]
        self.worker_groups.append(worker_pid)
        running.kill()
        self.wait_process(running, ok=False)
        self.assertEqual(self.cli("status")["attempts"][-1]["execution"], "unknown")
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", "pass"]), ok=False)
        os.killpg(worker_pid, signal.SIGKILL)
        # ps identifies a killed/reaped worker or its zombie as stopped; no elapsed-time takeover.
        end = time.monotonic() + 5
        while time.monotonic() < end:
            attempt = subprocess.run(["ps", "-p", str(worker_pid), "-o", "stat="], capture_output=True, text=True)
            if attempt.returncode or attempt.stdout.strip().startswith("Z"):
                break
            time.sleep(0.02)
        self.cli("task", *self.owner(), "--id", "T1", "--state", "blocked", ok=False)
        self.cli("task", *self.owner(), "--id", "T1", "--state", "blocked", "--note", "Stopped recorded process group and inspected its log")
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", "pass"]))

    def test_shorter_timeout_kills_descendants_and_rejects_larger_override(self):
        self.init(self.config(limits={"timeout_seconds": 5}))
        args = self.owner() + ["--action", "dispatch", "--task", "bad", "--worker", "fake", "--timeout", "6", "--"] + PYTHON + ["-c", "pass"]
        self.cli("run", *args, ok=False)
        self.assertEqual(self.cli("status")["attempts"], [])
        child_pid = self.base / "descendant"
        program = "import pathlib,subprocess,sys,time; p=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(30)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)"
        args = self.owner() + ["--action", "dispatch", "--task", "slow", "--worker", "fake", "--timeout", "1", "--"] + PYTHON + ["-c", program, str(child_pid)]
        result = json.loads(self.cli("run", *args, ok=False).stdout)
        self.assertTrue(result["attempt"]["timed_out"])
        descendant = int(child_pid.read_text())
        self.worker_groups.append(result["attempt"]["pid"])
        observed = subprocess.run(["ps", "-p", str(descendant), "-o", "stat="], capture_output=True, text=True)
        self.assertTrue(observed.returncode or observed.stdout.strip().startswith("Z"), observed.stdout)

    def test_unreadable_and_special_files_fail_without_handoff(self):
        self.init()
        unreadable = self.project / "private-source"
        unreadable.write_text("must not be dropped")
        unreadable.chmod(0)
        try:
            self.cli("handoff", *self.owner(), ok=False)
            self.assertEqual(self.cli("status")["mode"], "active")
        finally:
            unreadable.chmod(0o600)
        fifo = self.project / "named-pipe"
        os.mkfifo(fifo)
        failure = self.cli("checkpoint", *self.owner(), ok=False)
        self.assertIn("special file", failure.stderr)

    def test_changing_content_never_prepares_a_complete_handoff(self):
        self.git_project()
        self.init()
        source = self.project / "source.txt"
        source.write_text("first dirty version")
        fakebin = self.base / "fakebin"
        fakebin.mkdir()
        real_git = shutil.which("git")
        wrapper = fakebin / "git"
        # Mutate the fixture on each status observation, deterministically between
        # capture passes; execute real Git for all external repository semantics.
        wrapper.write_text("#!" + sys.executable + " -I\nimport pathlib,subprocess,sys\nr=subprocess.run([" + repr(real_git) + ",*sys.argv[1:]])\nif 'status' in sys.argv:\n p=pathlib.Path(" + repr(str(source)) + ")\n p.write_text(p.read_text()+'changed\\n')\nsys.exit(r.returncode)\n")
        wrapper.chmod(0o755)
        failure = self.cli("handoff", *self.owner(), ok=False, env=dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ["PATH"]))
        self.assertIn("changed", failure.stderr)
        state = self.cli("status")
        self.assertEqual(state["mode"], "active")
        self.assertIsNotNone(state["checkpoint_failure"])

    def test_resume_detects_edits_with_unchanged_git_status_codes(self):
        self.git_project()
        source = self.project / "source.txt"
        source.write_text("first dirty version")
        self.init()
        status = self.git("status", "--porcelain")
        source.write_text("another dirty version")
        self.assertEqual(status, self.git("status", "--porcelain"))
        self.assertTrue(self.cli("resume", *self.owner())["baseline_changed"])

    def test_duplicate_json_fields_and_bad_runtime_are_diagnosed(self):
        config = self.base / "duplicate.json"
        config.write_text('{"permissions":{"dispatch":"deny","dispatch":"allow"}}')
        self.cli("init", "--session", "owner", "--client", "codex", "--goal", "x", "--config", str(config), ok=False)
        initial = self.init()
        state_path = Path(initial["runtime_path"]) / "state.json"
        state = json.loads(state_path.read_text())
        state["epoch"] = "bad"
        state_path.write_text(json.dumps(state))
        before = state_path.read_bytes()
        diagnosis = self.cli("doctor")
        self.assertFalse(diagnosis["ok"])
        self.assertIn("epoch", " ".join(diagnosis["issues"]))
        self.assertEqual(before, state_path.read_bytes())
        self.cli("resume", *self.owner(), ok=False)

    def test_machine_mismatch_blocks_prepared_and_unprepared_takeover(self):
        initial = self.init()
        handoff = self.cli("handoff", *self.owner())
        state_path = Path(initial["runtime_path"]) / "state.json"
        state = json.loads(state_path.read_text())
        state["machine"] = "other-machine"
        state_path.write_text(json.dumps(state))
        self.cli("takeover", "--session", "next", "--client", "codex", "--handoff", handoff["handoff_id"], ok=False)
        self.cli("takeover", "--session", "next", "--client", "codex", "--recover", "--previous-stopped", ok=False)
        self.assertEqual(self.cli("status")["epoch"], 1)

    def test_non_git_conversion_cannot_create_a_second_owner(self):
        self.init()
        self.git("init", "-q")
        failure = self.cli("init", "--session", "other", "--client", "codex", "--goal", "new", "--adopt", ok=False)
        self.assertIn("non-Git runtime", failure.stderr)
        self.assertFalse((self.project / ".git" / "orchestrator-playbook").exists())

    def test_fixed_worker_settings_are_not_silently_dropped_by_raw_run(self):
        self.init(self.config(workers=[{"id": "fake", "client": "manual", "effort": {"mode": "fixed", "value": "high"}}]))
        self.cli("run", *self.run_args("T1", PYTHON + ["-c", "pass"]), ok=False)
        self.assertEqual(self.cli("status")["attempts"], [])

    def test_two_takeovers_cannot_both_claim_the_same_handoff(self):
        self.init()
        handoff = self.cli("handoff", *self.owner())["handoff_id"]
        claimants = [self.spawn("takeover", "--session", name, "--client", "codex", "--handoff", handoff) for name in ("first", "second")]
        outcomes = []
        for claimant in claimants:
            out, err = claimant.communicate(timeout=15)
            outcomes.append(claimant.returncode)
            self.assertTrue(out.strip() or err.strip())
        self.assertEqual(sorted(outcomes), [0, 2])
        self.assertEqual(self.cli("status")["epoch"], 2)

    def test_guard_child_retains_lock_if_supervisor_is_killed(self):
        self.git_project()
        self.init(self.config())
        ready, release = self.base / "ready", self.base / "release"
        guard = self.spawn("guard", *self.owner(), "--action", "commit", "--", *self.fake_wait(ready, release))
        try:
            self.wait_file(ready)
            guard.kill()
            handoff = self.spawn("handoff", *self.owner())
            time.sleep(0.2)
            self.assertIsNone(handoff.poll(), "The guarded child must retain the OS lock until it finishes")
        finally:
            release.touch()
        self.wait_process(guard, ok=False)
        self.wait_process(handoff)

    def test_unknown_manual_work_consumes_resources_until_reconciled(self):
        self.git_project()
        self.init(self.config(limits={"agents": 1}))
        self.cli("task", *self.owner(), "--id", "external", "--state", "unknown")
        denied = self.cli("run", *self.run_args("new", PYTHON + ["-c", "pass"]), ok=False)
        self.assertIn("Agent limit", denied.stderr)
        self.cli("task", *self.owner(), "--id", "external", "--state", "blocked", "--note", "External process was stopped and its work inspected")
        self.cli("run", *self.run_args("new", PYTHON + ["-c", "pass"]))

    def test_cleanup_rejects_ignored_work_even_when_git_status_is_clean(self):
        self.git_project()
        self.init(self.config(permissions={"cleanup": "allow"}, git={"cleanup_mode": "manual"}))
        (self.project / ".gitignore").write_text("ignored-source\n")
        self.git("add", ".orchestrator/config.json", ".gitignore")
        self.git("commit", "-qm", "Portable policy fixture")
        (self.project / "ignored-source").write_text("not disposable")
        self.assertFalse(self.git("status", "--porcelain"))
        self.cli("checkpoint", *self.owner())
        marker = self.base / "must-not-clean"
        failure = self.cli("guard", *self.owner(), "--action", "cleanup", "--", *PYTHON, "-c", f"open({str(marker)!r},'w').close()", ok=False)
        self.assertIn("ignored", failure.stderr)
        self.assertFalse(marker.exists())

    def test_non_git_checkpoint_preserves_empty_directories_and_executable_mode(self):
        self.init()
        (self.project / "empty").mkdir(mode=0o750)
        script = self.project / "executable"
        script.write_bytes(b"local source\n")
        script.chmod(0o755)
        result = self.cli("checkpoint", *self.owner())["checkpoint"]
        folder = Path(result["path"])
        manifest = json.loads((folder / "manifest.json").read_text())
        tree = manifest["capture"]["worktrees"][0]
        self.assertEqual(tree["directories"]["empty"], 0o750)
        self.assertEqual(tree["files"]["executable"]["mode"], 0o755)
        self.assertEqual((folder / "blobs" / tree["files"]["executable"]["sha256"]).read_bytes(), b"local source\n")

    def test_git_project_path_with_trailing_space_is_preserved(self):
        self.project = self.base / "project with trailing space "
        self.project.mkdir()
        self.git_project()
        initial = self.init()
        self.assertEqual(initial["project_root"], str(self.project))
        self.cli("checkpoint", *self.owner())

    def test_run_resolves_relative_command_in_execution_cwd_and_preserves_argv(self):
        initial = self.init(self.config())
        workdir = self.project / "worker space"
        script = workdir / "scripts" / "verify.sh"
        state_path = Path(initial["runtime_path"]) / "state.json"
        self.executable(script, "import json,pathlib,sys; state=json.loads(pathlib.Path(sys.argv[1]).read_text()); "
                        "assert state['attempts'][-1]['state'] in ('reserved','running'); "
                        "print(json.dumps({'cwd':str(pathlib.Path.cwd()),'args':sys.argv[1:]}))")
        literal = "$(touch unwanted); 'quoted argument'"
        command = ["./scripts/verify.sh", str(state_path), literal]
        args = self.owner() + ["--action", "verify", "--task", "explicit", "--cwd", str(workdir), "--"] + command
        result = self.cli("run", *args, cwd=self.base)
        self.assertEqual(result["attempt"]["command"], command)
        observed = json.loads(Path(result["attempt"]["log"]).read_text())
        self.assertEqual(observed, {"cwd": str(workdir), "args": command[1:]})
        self.assertFalse((workdir / "unwanted").exists())
        self.cli("task", *self.owner(), "--id", "recorded", "--state", "reserved", "--worktree", str(workdir))
        result = self.cli("run", *self.run_args("recorded", command), cwd=self.base)
        self.assertEqual(result["attempt"]["cwd"], str(workdir))

    def test_run_resolves_relative_and_empty_path_entries_in_execution_cwd(self):
        self.init(self.config())
        workdir = self.project / "worker"
        for index, entry in enumerate(("relative-bin", ".", "")):
            with self.subTest(entry=entry):
                name = "verify-path-%s" % index
                self.executable(workdir / entry / name, "import pathlib; print(pathlib.Path.cwd())")
                env = dict(os.environ, PATH=entry + os.pathsep + os.defpath)
                args = self.owner() + ["--action", "verify", "--task", "path-%s" % index, "--cwd", str(workdir), "--", name]
                result = self.cli("run", *args, env=env, cwd=self.base)
                self.assertEqual(Path(result["attempt"]["log"]).read_text().strip(), str(workdir))
                self.assertEqual(result["attempt"]["command"], [name])

    def test_caller_only_command_and_denied_relative_command_do_not_reserve(self):
        self.init(self.config())
        marker = self.base / "must-not-execute"
        program = "import pathlib; pathlib.Path(%r).touch()" % str(marker)
        self.executable(self.base / "caller-only", program)
        self.cli("run", *self.run_args("missing", ["./caller-only"]), cwd=self.base, ok=False)
        self.assertEqual(self.cli("status")["attempts"], [])
        self.executable(self.project / "actual-command", program)
        self.cli("configure", *self.owner(), "--config", str(self.config(permissions={"verify": "deny"})))
        args = self.owner() + ["--action", "verify", "--task", "denied", "--", "./actual-command"]
        self.cli("run", *args, cwd=self.base, ok=False)
        self.assertEqual(self.cli("status")["attempts"], [])
        self.assertFalse(marker.exists())

    def test_guard_resolves_relative_command_and_path_in_project_cwd(self):
        self.git_project()
        self.init(self.config())
        marker = self.project / "guard-result.json"
        self.executable(self.project / "tools" / "guard-fixture", "import json,os,pathlib,sys; "
                        "pathlib.Path('guard-result.json').write_text(json.dumps({'cwd':str(pathlib.Path.cwd()),'args':sys.argv[1:],'guard':os.environ['PLAYBOOK_GUARDED']}))")
        for command in (["./tools/guard-fixture", "literal $(no-shell)"], ["guard-fixture", "path argument"]):
            with self.subTest(command=command):
                env = dict(os.environ, PATH="tools" + os.pathsep + os.defpath)
                self.cli("guard", *self.owner(), "--action", "commit", "--", *command, cwd=self.base, env=env)
                self.assertEqual(json.loads(marker.read_text()), {"cwd": str(self.project), "args": command[1:], "guard": "1"})

    def test_scaffold_guard_requires_active_owner_without_granting_other_actions(self):
        self.init()
        marker = self.project / "metadata"
        command = PYTHON + ["-c", "import os,pathlib,sys; assert os.environ['PLAYBOOK_GUARDED']=='1'; pathlib.Path(sys.argv[1]).touch()", str(marker)]
        self.cli("guard", *self.owner("other"), "--action", "scaffold", "--", *command, ok=False)
        self.cli("guard", *self.owner(epoch=2), "--action", "scaffold", "--", *command, ok=False)
        self.assertFalse(marker.exists())
        self.cli("guard", *self.owner(), "--action", "scaffold", "--", *command)
        self.assertTrue(marker.exists())
        self.assertEqual(set(self.cli("status")["policy"]["permissions"].values()), {"ask"})
        self.cli("guard", *self.owner(), "--action", "commit", "--", *command, ok=False)
        self.cli("run", *self.run_args("unapproved", command), ok=False)
        self.cli("handoff", *self.owner())
        marker.unlink()
        self.cli("guard", *self.owner(), "--action", "scaffold", "--", *command, ok=False)
        self.assertFalse(marker.exists())

    def test_interrupted_configure_can_be_recovered_with_explicit_reviewed_config(self):
        initial = self.init(self.config())
        self.cli("task", *self.owner(), "--id", "retained", "--state", "reserved")
        state_path = Path(initial["runtime_path"]) / "state.json"
        config_path = Path(initial["config_path"])
        original_state = state_path.read_bytes()
        revised = self.config(goal="Explicit reviewed recovery", permissions={"dispatch": "deny"})
        failure = self.injected_cli("def fail_save(self,state):\n raise OSError('injected state write failure')\nruntime.Project.save=fail_save", "configure", *self.owner(), "--config", str(revised))
        self.assertNotEqual(failure.returncode, 0)
        self.assertIn("injected", failure.stderr)
        conflicting_config = config_path.read_bytes()
        self.assertEqual(state_path.read_bytes(), original_state)
        self.cli("status", ok=False)
        self.cli("takeover", "--session", "next", "--client", "codex", "--recover", "--previous-stopped", ok=False)
        self.cli("configure", *self.owner("next"), "--config", str(revised), ok=False)
        self.cli("takeover", "--session", "next", "--client", "codex", "--recover", "--config", str(revised), ok=False)
        args = ["--session", "next", "--client", "codex", "--recover", "--previous-stopped", "--config", str(revised)]
        recovered = self.cli("takeover", *args)
        self.assertEqual((recovered["epoch"], recovered["config_revision"]), (2, 2))
        self.assertEqual(recovered["policy"]["permissions"]["dispatch"], "deny")
        self.assertEqual(recovered["tasks"]["retained"]["state"], "reserved")
        evidence = Path(recovered["configuration_recovery"]["path"])
        self.assertEqual((evidence / "state-before.json").read_bytes(), original_state)
        self.assertEqual((evidence / "config-before.json").read_bytes(), conflicting_config)
        self.assertEqual(json.loads((evidence / "reviewed-config.json").read_text()), recovered["policy"])
        again = self.cli("takeover", *args)
        self.assertEqual((again["epoch"], again["config_revision"]), (2, 2))

    def test_reviewed_config_does_not_bypass_prepared_handoff_validation(self):
        initial = self.init()
        handoff = self.cli("handoff", *self.owner())
        reviewed = self.config(goal="Reviewed safe policy")
        Path(initial["config_path"]).write_bytes(b"invalid interrupted config")
        self.cli("takeover", "--session", "next", "--client", "codex", "--handoff", handoff["handoff_id"], "--config", str(reviewed), ok=False)
        self.cli("takeover", "--session", "next", "--client", "codex", "--handoff", handoff["handoff_id"], ok=False)
        recovered = self.cli("takeover", "--session", "next", "--client", "codex", "--recover", "--previous-stopped", "--config", str(reviewed))
        evidence = Path(recovered["configuration_recovery"]["path"])
        self.assertEqual((evidence / "config-before.json").read_bytes(), b"invalid interrupted config")
        self.assertEqual(recovered["epoch"], 2)

    def test_snapshot_binary_patch_stops_at_small_budget_and_retains_partial(self):
        self.git_project()
        binary = self.project / "image.bin"
        binary.write_bytes(b"\x00initial binary")
        self.git("add", "image.bin")
        self.git("commit", "-qm", "Binary fixture")
        self.init()
        import hashlib
        binary.write_bytes(b"\x00" + b"".join(hashlib.sha256(str(i).encode()).digest() for i in range(1024)))
        self.git("add", "image.bin")
        fakebin = self.base / "fakebin"
        pidfile, finished = self.base / "diff-pid", self.base / "diff-finished"
        real_git = shutil.which("git")
        # Real Git produces the binary patch; its wrapper forwards small chunks so
        # completion would be observable if the runtime read it all before checking.
        program = ("import os,pathlib,subprocess,sys,time\n"
                   "if 'diff' not in sys.argv:\n os.execv(%r,[%r,*sys.argv[1:]])\n" % (real_git, real_git) +
                   "pathlib.Path(%r).write_text(str(os.getpid()))\n" % str(pidfile) +
                   "p=subprocess.Popen([%r,*sys.argv[1:]],stdout=subprocess.PIPE)\n" % real_git +
                   "while True:\n chunk=p.stdout.read(128)\n if not chunk: break\n os.write(1,chunk)\n time.sleep(.01)\n" +
                   "pathlib.Path(%r).touch()\nsys.exit(p.wait())" % str(finished))
        self.executable(fakebin / "git", program)
        env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ["PATH"])
        result = self.injected_cli("runtime.MAX_FILE_BYTES=512", "handoff", *self.owner(), env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Git patch exceeds per-artifact", result.stderr)
        self.assertFalse(finished.exists(), "Git producer must be stopped before generating the full patch")
        state = self.cli("status")
        self.assertEqual(state["mode"], "active")
        failed = Path(state["checkpoint_failure"]["path"])
        partials = list((failed / "blobs").glob(".partial-git-*"))
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].stat().st_size, 512)
        self.assertFalse((failed / "manifest.json").exists())
        observed = subprocess.run(["ps", "-p", pidfile.read_text(), "-o", "stat="], capture_output=True, text=True)
        self.assertTrue(observed.returncode or observed.stdout.strip().startswith("Z"), observed.stdout)

    def test_snapshot_patch_respects_remaining_total_budget(self):
        self.git_project()
        self.init()
        source = self.project / "source.txt"
        source.write_text("a" * 200 + "\n")
        self.git("add", "source.txt")
        source.write_text("b" * 200 + "\n")
        result = self.injected_cli("runtime.MAX_FILE_BYTES=4096\nruntime.MAX_SNAPSHOT_BYTES=600", "handoff", *self.owner())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Git patch exceeds remaining total", result.stderr)
        state = self.cli("status")
        failed = Path(state["checkpoint_failure"]["path"])
        self.assertEqual(state["mode"], "active")
        self.assertTrue(list((failed / "blobs").glob(".partial-git-*")))
        self.assertLessEqual(sum(path.stat().st_size for path in (failed / "blobs").iterdir()), 600)

    def early_exit_child(self, ready, release, heartbeat):
        child = ("import os,pathlib,sys,time; ready,release,beat=map(pathlib.Path,sys.argv[1:]); ready.write_text(str(os.getpid())); "
                 "\nwhile not release.exists(): beat.write_text(str(time.monotonic())); time.sleep(.03)")
        parent = "import subprocess,sys; subprocess.Popen([sys.executable,'-I','-c',sys.argv[1],*sys.argv[2:]])"
        return PYTHON + ["-c", parent, child, str(ready), str(release), str(heartbeat)]

    def test_early_leader_exit_keeps_resources_and_timeout_until_group_stops(self):
        self.init(self.config(limits={"agents": 1, "timeout_seconds": 1}))
        ready, release, heartbeat = self.base / "ready", self.base / "release", self.base / "heartbeat"
        running = self.spawn("run", *self.run_args("early", self.early_exit_child(ready, release, heartbeat)))
        self.wait_file(ready)
        self.wait_file(heartbeat)
        status = self.cli("status")
        self.worker_groups.append(status["attempts"][-1]["pgid"])
        self.assertEqual(status["attempts"][-1]["execution"], "running")
        self.assertEqual(status["tasks"]["early"]["state"], "running")
        self.cli("run", *self.run_args("second", PYTHON + ["-c", "pass"]), ok=False)
        result = self.wait_process(running, ok=False)
        self.assertTrue(result["attempt"]["timed_out"])
        self.assertEqual(result["attempt"]["returncode"], 124)
        last = heartbeat.read_bytes()
        time.sleep(0.12)
        self.assertEqual(heartbeat.read_bytes(), last)
        self.cli("run", *self.run_args("second", PYTHON + ["-c", "pass"]))

    def test_early_leader_exit_can_finish_when_descendant_exits_naturally(self):
        self.init(self.config(limits={"agents": 1, "timeout_seconds": 10}))
        ready, release, heartbeat = self.base / "ready", self.base / "release", self.base / "heartbeat"
        running = self.spawn("run", *self.run_args("early", self.early_exit_child(ready, release, heartbeat)))
        self.wait_file(ready)
        status = self.cli("status")
        self.worker_groups.append(status["attempts"][-1]["pgid"])
        self.assertIsNone(running.poll())
        self.cli("task", *self.owner(), "--id", "early", "--state", "reported", "--note", "leader exited", ok=False)
        release.touch()
        result = self.wait_process(running)
        self.assertFalse(result["attempt"]["timed_out"])
        self.assertEqual(result["task"]["state"], "reported")

    def test_orphan_descendant_blocks_reconciliation_after_supervisor_death(self):
        self.init(self.config())
        ready, release, heartbeat = self.base / "ready", self.base / "release", self.base / "heartbeat"
        running = self.spawn("run", *self.run_args("early", self.early_exit_child(ready, release, heartbeat)))
        self.wait_file(ready)
        status = self.cli("status")
        self.worker_groups.append(status["attempts"][-1]["pgid"])
        running.kill()
        self.wait_process(running, ok=False)
        failure = self.cli("task", *self.owner(), "--id", "early", "--state", "blocked", "--note", "leader and supervisor exited", ok=False)
        self.assertIn("live process/supervisor/group", failure.stderr)
        self.assertEqual(self.cli("status")["attempts"][-1]["execution"], "unknown")

    def test_unmerged_binary_index_is_rejected_without_losing_index_stages(self):
        self.git_project()
        binary = self.project / "image.bin"
        binary.write_bytes(b"\x00base")
        self.git("add", "image.bin")
        self.git("commit", "-qm", "Base binary")
        self.git("checkout", "-qb", "other")
        binary.write_bytes(b"\x00unique stage three")
        self.git("commit", "-qam", "Other binary")
        self.git("checkout", "-q", "main")
        binary.write_bytes(b"\x00ours")
        self.git("commit", "-qam", "Our binary")
        merge = subprocess.run(["git", "-C", str(self.project), "merge", "other"], capture_output=True, text=True)
        self.assertNotEqual(merge.returncode, 0)
        self.git("checkout", "--ours", "--", "image.bin")
        stages = self.git("ls-files", "--unmerged", "--", "image.bin")
        self.assertIn(" 3\timage.bin", stages)
        self.init()
        failure = self.cli("handoff", *self.owner(), ok=False)
        self.assertIn("unmerged index", failure.stderr)
        state = self.cli("status")
        self.assertEqual(state["mode"], "active")
        self.assertFalse((Path(state["checkpoint_failure"]["path"]) / "manifest.json").exists())
        self.assertEqual(self.git("ls-files", "--unmerged", "--", "image.bin"), stages)
        self.assertEqual(binary.read_bytes(), b"\x00ours")

    def test_first_handoff_does_not_refresh_index_for_mtime_only_changes(self):
        self.git_project()
        self.init()
        source = self.project / "source.txt"
        index = self.project / ".git" / "index"
        before = index.read_bytes(), index.stat().st_mtime_ns
        info = source.stat()
        os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns + 2000000000))
        handoff = self.cli("handoff", *self.owner())
        self.assertEqual(handoff["mode"], "prepared")
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)


if __name__ == "__main__":
    unittest.main()
