"""API 2 lifecycle regression tests: temporary projects, no model clients."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import unittest

import test_playbook as fixtures


class RuntimeNextTests(unittest.TestCase):
    setUp = fixtures.PlaybookTests.setUp
    tearDown = fixtures.PlaybookTests.tearDown
    cli = fixtures.PlaybookTests.cli
    injected_cli = fixtures.PlaybookTests.injected_cli
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

    def test_pause_failure_is_durably_stopped_and_retains_failure(self):
        self.init(self.config())
        os.mkfifo(self.project / "unfinished")
        failure = self.cli("pause", *self.owner(), ok=False)
        self.assertIn("incomplete", failure.stderr.lower())
        status = self.cli("status")
        self.assertEqual(status["mode"], "paused")
        self.assertTrue(status["checkpoint_failure"])
        self.cli("run", *self.run_args("must-not-start", fixtures.PYTHON + ["-c", "pass"]), ok=False)
        self.assertFalse(self.cli("status")["attempts"])

    def test_handoff_withdrawal_is_idempotent_invalidates_token_and_keeps_evidence(self):
        self.init()
        handoff = self.cli("handoff", *self.owner(), "--to", "next")
        old_snapshot = Path(handoff["checkpoint"]["path"])
        result = self.cli("handoff", *self.owner(), "--cancel")
        self.assertEqual(result["mode"], "paused")
        self.assertIsNone(result["handoff"])
        self.assertEqual(result["handoff_history"][-1]["id"], handoff["handoff_id"])
        self.assertTrue(old_snapshot.is_dir())
        self.assertTrue(self.cli("handoff", *self.owner(), "--cancel")["already_cancelled"])
        self.cli("takeover", "--session", "next", "--client", "manual", "--handoff", handoff["handoff_id"], ok=False)
        new = self.cli("handoff", *self.owner(), "--to", "next")
        self.assertNotEqual(new["handoff_id"], handoff["handoff_id"])

    def test_withdrawal_and_takeover_have_exactly_one_winner(self):
        self.init()
        handoff = self.cli("handoff", *self.owner(), "--to", "next")
        cancel = self.spawn("handoff", *self.owner(), "--cancel")
        takeover = self.spawn("takeover", "--session", "next", "--client", "manual", "--handoff", handoff["handoff_id"])
        results = [p.communicate(timeout=20) for p in (cancel, takeover)]
        self.assertEqual(sum(p.returncode == 0 for p in (cancel, takeover)), 1, results)
        state = self.cli("status")
        if cancel.returncode == 0:
            self.assertEqual((state["mode"], state["epoch"]), ("paused", 1))
        else:
            self.assertEqual((state["owner"]["session"], state["epoch"]), ("next", 2))

    def test_patch_preserves_unrelated_authorizations_and_rejects_null(self):
        initial = self.init(self.config(paths={"plan": "plan/custom.md"}, review={"level": "high"}))
        patch = self.base / "patch.json"
        patch.write_text(json.dumps({"limits": {"agents": 4}}))
        result = self.cli("configure", *self.owner(), "--patch", str(patch))
        self.assertEqual(result["changed_paths"], ["limits.agents"])
        self.assertEqual(result["policy"]["permissions"], initial["policy"]["permissions"])
        self.assertEqual(result["policy"]["workers"], initial["policy"]["workers"])
        self.assertEqual(result["policy"]["paths"], initial["policy"]["paths"])
        for value in ({"permissions": None}, {"limits": {"agents": None}}, {"unknown": 1}, {"runtime_api": 1}):
            patch.write_text(json.dumps(value))
            self.cli("configure", *self.owner(), "--patch", str(patch), ok=False)
        self.assertEqual(self.cli("status")["config_revision"], 2)
        replaced = self.cli("configure", *self.owner(), "--config", str(self.config()))
        self.assertEqual(replaced["policy"]["runtime_api"], 2)

    def test_init_review_fields_retry_with_inherited_or_explicit_api(self):
        for field in ("allow_manual", "independent"):
            for value in (True, False):
                for explicit_api in (False, True):
                    with self.subTest(field=field, value=value, explicit_api=explicit_api):
                        project = self.base / ("init-%s-%s-%s" % (field, value, explicit_api))
                        project.mkdir()
                        settings = {"review": {field: value}}
                        if explicit_api:
                            settings["runtime_api"] = 2
                        config = self.config(**settings)
                        first = self.init(config, project=project)
                        paths = (Path(first["config_path"]), Path(first["runtime_path"]) / "state.json")
                        before = [path.read_bytes() for path in paths]
                        again = self.init(config, project=project)
                        self.assertEqual(again["project_id"], first["project_id"])
                        self.assertEqual(again["policy"], first["policy"])
                        self.assertEqual(again["policy"]["runtime_api"], 2)
                        self.assertIs(again["policy"]["review"][field], value)
                        self.assertEqual([path.read_bytes() for path in paths], before)

    def test_init_api_inheritance_checks_owner_client_and_existing_policy(self):
        config = self.config(review={"allow_manual": True})
        first = self.init(config)
        paths = (Path(first["config_path"]), Path(first["runtime_path"]) / "state.json")
        before = [path.read_bytes() for path in paths]
        for session, client, expected in (("other", "codex", "Ownership conflict"),
                                          ("owner", "manual", "different client")):
            with self.subTest(session=session, client=client):
                failure = self.cli("init", "--session", session, "--client", client,
                                   "--goal", "A tested outcome", "--config", str(config), ok=False)
                self.assertIn(expected, failure.stderr)
                self.assertEqual([path.read_bytes() for path in paths], before)
        changed = json.loads(paths[0].read_text())
        changed["review"]["allow_manual"] = False
        paths[0].write_text(json.dumps(changed))
        failure = self.cli("init", "--session", "owner", "--client", "codex",
                           "--goal", "A tested outcome", "--config", str(config), ok=False)
        self.assertIn("Configuration changed outside configure", failure.stderr)
        self.assertEqual(paths[1].read_bytes(), before[1])

    def test_init_rejects_explicit_invalid_api_before_creation_and_on_retry(self):
        first = self.init(self.config(review={"independent": True}))
        paths = (Path(first["config_path"]), Path(first["runtime_path"]) / "state.json")
        before = [path.read_bytes() for path in paths]
        fresh = self.base / "fresh"
        fresh.mkdir()
        for api in (None, True, False, 0, 1, 3, "2", 2.0):
            for project in (fresh, self.project):
                with self.subTest(api=api, initialized=project == self.project):
                    config = self.config(runtime_api=api, review={"independent": True})
                    failure = self.cli("init", "--session", "owner", "--client", "codex",
                                       "--goal", "A tested outcome", "--config", str(config),
                                       project=project, ok=False)
                    self.assertIn("Unsupported runtime_api", failure.stderr)
                    self.assertFalse((fresh / ".orchestrator").exists())
                    self.assertEqual([path.read_bytes() for path in paths], before)

    def test_init_adopts_legacy_portable_policy_without_api_upgrade(self):
        config = self.config(goal="A tested outcome", review={"level": "high"})
        portable = self.project / ".orchestrator" / "config.json"
        portable.parent.mkdir()
        portable.write_bytes(config.read_bytes())
        original = portable.read_bytes()
        first = self.init(config, adopt=True)
        self.assertNotIn("runtime_api", first["policy"])
        again = self.init(config)
        self.assertEqual(again["project_id"], first["project_id"])
        self.assertNotIn("runtime_api", again["policy"])
        self.assertEqual(portable.read_bytes(), original)

    def test_legacy_config_hash_stays_identical_until_explicit_activation(self):
        state = self.init(self.config())
        config_path = Path(state["config_path"])
        config = json.loads(config_path.read_text())
        config.pop("runtime_api")
        config_path.write_text(json.dumps(config))
        state_path = Path(state["runtime_path"]) / "state.json"
        raw = json.loads(state_path.read_text())
        raw.pop("runtime_api_required", None)
        canonical = (json.dumps(config, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()
        raw["config_hash"] = hashlib.sha256(canonical).hexdigest()
        state_path.write_text(json.dumps(raw))
        before = state_path.read_bytes()
        policy_before = config_path.read_bytes()
        self.assertNotIn("runtime_api", self.cli("status")["policy"])
        self.assertNotIn("runtime_api", self.init(self.config())["policy"])
        for field in ("allow_manual", "independent"):
            for value in (True, False):
                with self.subTest(field=field, value=value):
                    supplied = self.config(review={field: value})
                    failure = self.cli("init", "--session", "owner", "--client", "codex",
                                       "--goal", "A tested outcome", "--config", str(supplied), ok=False)
                    self.assertIn("requires runtime_api:2", failure.stderr)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertEqual(config_path.read_bytes(), policy_before)
        patch = self.base / "activate.json"
        patch.write_text('{"runtime_api": 2}')
        active = self.cli("configure", *self.owner(), "--patch", str(patch))
        self.assertEqual(active["policy"]["runtime_api"], 2)
        config_path.write_text("broken transaction")
        reviewed = self.base / "reviewed.json"
        reviewed.write_text(json.dumps(config))
        recovered = self.cli("takeover", "--session", "next", "--client", "manual", "--recover", "--previous-stopped", "--config", str(reviewed))
        self.assertEqual(recovered["policy"]["runtime_api"], 2)

    def test_timeout_stops_worker_while_independent_owner_guard_holds_lock(self):
        self.init(self.config(limits={"timeout_seconds": 2}))
        ready, stopped = self.base / "worker-ready", self.base / "worker-stopped"
        locked, unlocked = self.base / "guard-locked", self.base / "guard-unlocked"
        late_write = self.base / "after-deadline"
        worker = ("import json,os,pathlib,signal,sys,time\n"
                  "ready,stopped,late=map(pathlib.Path,sys.argv[1:])\n"
                  "def stop(signum,frame):\n"
                  " stopped.write_text(str(time.monotonic()))\n"
                  " raise SystemExit(0)\n"
                  "signal.signal(signal.SIGTERM,stop)\n"
                  "ready.write_text(json.dumps({'pid':os.getpid(),'started':time.monotonic()}))\n"
                  "time.sleep(3)\n"
                  "late.write_text('worker continued past the attempt deadline')\n"
                  "time.sleep(10)\n")
        running = self.spawn("run", *self.run_args("deadline", fixtures.PYTHON +
                             ["-c", worker, str(ready), str(stopped), str(late_write)]))
        self.wait_file(ready)
        launched = json.loads(ready.read_text())
        self.worker_groups.append(launched["pid"])
        holder = ("import pathlib,sys,time; "
                  "pathlib.Path(sys.argv[1]).write_text(str(time.monotonic())); "
                  "time.sleep(4); pathlib.Path(sys.argv[2]).write_text(str(time.monotonic()))")
        guard = self.spawn("guard", *self.owner(), "--action", "scaffold", "--",
                           *fixtures.PYTHON, "-c", holder, str(locked), str(unlocked))
        self.wait_file(locked)
        self.assertLess(float(locked.read_text()) - launched["started"], 1,
                        "Guard must acquire the lock before the attempt deadline")
        self.wait_file(stopped)
        self.assertFalse(late_write.exists(), "Worker wrote after its deadline while the owner held the lock")
        self.assertIsNone(guard.poll(), "Timeout must stop only the managed worker group")
        self.assertFalse(unlocked.exists(), "Worker must stop before the independent guard releases its lock")
        self.wait_process(guard)
        result = self.wait_process(running, ok=False)
        self.assertEqual(running.returncode, 124)
        self.assertTrue(result["attempt"]["timed_out"])
        self.assertFalse(result["attempt"]["cancelled"])
        self.assertEqual(result["task"]["state"], "blocked")
        self.assertFalse(late_write.exists())

    def test_cancel_stops_only_supervised_attempt_and_retains_reason(self):
        self.git_project()
        other = self.base / "other-tree"
        self.git("worktree", "add", "-qb", "other", str(other))
        self.init(self.config())
        first_ready, second_ready = self.base / "first-ready", self.base / "second-ready"
        first = self.spawn("run", *self.run_args("first", self.fake_wait(first_ready, self.base / "never")))
        self.wait_file(first_ready)
        second = self.spawn("run", *self.run_args("second", self.fake_wait(second_ready, self.base / "release")), project=other)
        self.wait_file(second_ready)
        self.cli("pause", *self.owner())
        self.assertIsNone(first.poll())
        self.assertIsNone(second.poll())
        attempt = next(a for a in self.cli("status")["attempts"] if a["task"] == "first")
        requested = self.cli("cancel", *self.owner(), "--attempt", attempt["id"], "--reason", "Work superseded")
        self.assertTrue(requested["requested"])
        result = self.wait_process(first, ok=False)
        self.assertTrue(result["attempt"]["cancelled"])
        self.assertEqual(result["attempt"]["cancel_acknowledgement"]["outcome"], "cancelled")
        self.assertEqual(result["attempt"]["cancel_request"]["reason"], "Work superseded")
        self.assertIsNone(second.poll())
        repeated = self.cli("cancel", *self.owner(), "--attempt", attempt["id"], "--reason", "different")
        self.assertEqual(repeated["status"], "terminal")
        self.assertEqual(repeated["attempt"]["cancel_request"]["reason"], "Work superseded")
        (self.base / "release").touch()
        self.wait_process(second)

    def test_cancel_orphan_keeps_unknown_and_does_not_signal_requester_guesses(self):
        self.init(self.config())
        ready = self.base / "orphan-ready"
        runner = self.spawn("run", *self.run_args("orphan", self.fake_wait(ready, self.base / "release")))
        self.wait_file(ready)
        attempt = self.cli("status")["attempts"][-1]
        self.worker_groups.append(attempt["pgid"])
        runner.kill()
        runner.communicate(timeout=10)
        result = self.cli("cancel", *self.owner(), "--attempt", attempt["id"], "--reason", "Supervisor unavailable")
        self.assertEqual(result["status"], "unknown")
        os.kill(attempt["pgid"], 0)
        self.cli("run", *self.run_args("other", fixtures.PYTHON + ["-c", "pass"]), ok=False)
        self.assertIsNone(result["attempt"].get("cancel_acknowledgement"))

    def test_natural_exit_wins_terminal_cancel(self):
        self.init(self.config())
        finished = self.cli("run", *self.run_args("natural", fixtures.PYTHON + ["-c", "pass"]))
        result = self.cli("cancel", *self.owner(), "--attempt", finished["attempt"]["id"], "--reason", "Late request")
        self.assertEqual(result["status"], "terminal")
        self.assertFalse(result["requested"])
        self.assertEqual(result["attempt"]["returncode"], 0)

    def test_checkpoint_one_save_and_per_call_blob_verification_cache(self):
        initial = self.init()
        (self.project / "first.txt").write_bytes(b"duplicate-blob-content")
        (self.project / "second.txt").write_bytes(b"duplicate-blob-content")
        counter = self.base / "saves"
        injection = ("old=runtime.Project.save\n"
                     "def save(self,state):\n"
                     f" p=runtime.Path({str(counter)!r}); p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\n"
                     " old(self,state)\n"
                     "runtime.Project.save=save")
        result = self.injected_cli(injection, "checkpoint", *self.owner())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(counter.read_text(), "1")
        hashes = self.base / "hashes"
        injection = ("old=runtime.digest\n"
                     "def hashed(data):\n"
                     " if data == b'duplicate-blob-content':\n"
                     f"  p=runtime.Path({str(hashes)!r}); p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\n"
                     " return old(data)\n"
                     "runtime.digest=hashed")
        result = self.injected_cli(injection, "doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(hashes.read_text(), "1")
        checkpoint = self.cli("status")["checkpoint"]
        blob = Path(checkpoint["path"]) / "blobs" / hashlib.sha256(b"duplicate-blob-content").hexdigest()
        blob.write_bytes(b"modified-blob-content!")
        result = self.cli("doctor")
        self.assertFalse(result["ok"])
        self.assertTrue(any("blob" in issue for issue in result["issues"]))
        self.assertTrue(Path(initial["runtime_path"]).is_dir())

    def test_discover_requested_path_and_version_copy_diagnostics(self):
        self.git_project()
        subdir = self.project / "src"
        subdir.mkdir()
        discovered = self.cli("discover", project=subdir)
        self.assertEqual(discovered["requested_project"], str(subdir))
        self.assertEqual(discovered["project"], str(self.project))
        version = subprocess.run(fixtures.PYTHON + [str(fixtures.RUNTIME), "version"], capture_output=True, text=True, check=True)
        version = json.loads(version.stdout)
        self.assertEqual(version["runtime_api"], 2)
        self.assertIn("playbook_work.py", version["files"])
        self.init()
        scripts = self.project / "scripts"
        scripts.mkdir()
        manifest = {"source": version, "files": {}}
        for name, sha in version["files"].items():
            source = fixtures.RUNTIME.with_name(name)
            target = scripts / name
            shutil.copy2(source, target)
            manifest["files"]["scripts/" + name] = {"sha256": sha, "mode": target.stat().st_mode & 0o777}
        manifest_path = self.project / ".orchestrator" / "runtime-manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        result = self.cli("doctor")["runtime_diagnostics"]
        self.assertTrue(all(item["status"] == "matching" for item in result["project_copies"]))
        (scripts / "playbook.py").write_text("changed runtime copy")
        (scripts / "playbook_work.py").unlink()
        result = self.cli("doctor")["runtime_diagnostics"]
        indexed = {item["path"]: item for item in result["project_copies"]}
        self.assertEqual(indexed["scripts/playbook.py"]["status"], "differing")
        self.assertEqual(indexed["scripts/playbook_work.py"]["status"], "missing")
        manifest_path.unlink()
        self.assertEqual(self.cli("doctor")["runtime_diagnostics"]["manifest"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
