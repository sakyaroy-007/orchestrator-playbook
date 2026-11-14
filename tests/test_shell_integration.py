"""Exercise v3 policy through the actual legacy shell entry points.

Only temporary repositories and local stub executables are used. These checks
cover integration boundaries rather than calling adapter helper functions.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class ShellIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="playbook-shell-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.project = self.directory / "project with spaces"
        self.project.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("PLAYBOOK_", "DISPATCH_", "WT_", "GIT_"))}
        self.env.update({"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                         "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
                         "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                         "DISPATCH_LOG_DIR": str(self.directory / "logs")})
        self.command(["git", "init", "-q", "-b", "main", str(self.project)])
        (self.project / "source.txt").write_text("baseline\n")
        self.command(["git", "-C", str(self.project), "add", "source.txt"])
        self.command(["git", "-C", str(self.project), "commit", "-qm", "baseline"])
        self.stub_record = self.directory / "worker-argv.json"
        self.stub = self.directory / "stub-worker"
        self.stub.write_text("#!" + sys.executable + " -I\n" + '''import json, os, pathlib, sys
if "--help" in sys.argv:
    if os.environ.get("STUB_COLLISION_LOG"):
        pathlib.Path(os.environ["STUB_COLLISION_LOG"]).write_text("late evidence")
    print("--model --config --effort --profile --patch")
    raise SystemExit(0)
patches = []
for index, arg in enumerate(sys.argv[1:], 1):
    if arg == "--patch":
        value = pathlib.Path(sys.argv[index + 1]).read_text()
        patches.append(value)
pathlib.Path(os.environ["STUB_RECORD"]).write_text(json.dumps({"args":sys.argv[1:],"patches":patches,"cwd":os.getcwd()}))
print("stub completed; no model called")
for index in range(int(os.environ.get("STUB_REVIEW_LINES", "0"))):
    print("review stdout {:03d}".format(index), flush=True)
    print("review stderr {:03d}".format(index), file=sys.stderr, flush=True)
raise SystemExit(int(os.environ.get("STUB_EXIT", "0")))
''')
        self.stub.chmod(0o755)
        self.env.update({"STUB_RECORD": str(self.stub_record),
                         "DISPATCH_BIN_CLAUDE": str(self.stub), "DISPATCH_BIN_CODEX": str(self.stub),
                         "DISPATCH_BIN_DSH": str(self.stub), "DISPATCH_BIN_HERMES": str(self.stub),
                         "PLAYBOOK_SESSION": "owner", "PLAYBOOK_EPOCH": "1", "PLAYBOOK_TASK": "T-101",
                         "PLAYBOOK_WORKER": "worker-1", "PLAYBOOK_PROJECT": str(self.project)})
        self.config = {
            "schema_version": 1, "goal": "Test managed entry points",
            "workers": [{"id": "worker-1", "client": "claude", "model": {"mode": "inherit"},
                         "effort": {"mode": "inherit"}, "args": []}],
            "limits": {"agents": 2, "heavy_jobs": 1, "timeout_seconds": 30, "max_attempts": 2},
            "permissions": {"dispatch": "allow", "worktree-create": "allow", "verify": "allow",
                            "commit": "allow", "merge": "allow", "push": "deny", "cleanup": "allow"},
            "git": {"integration_branch": "main", "merge_method": "merge", "push_cadence": "manual", "cleanup_mode": "after-merge"},
        }

    def command(self, argv, success=True, env=None, cwd=None):
        result = subprocess.run(argv, cwd=str(cwd or self.project), env=env or self.env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def initialize(self):
        config_file = self.directory / "approved.json"
        config_file.write_text(json.dumps(self.config))
        self.runtime("init", "--session", "owner", "--client", "claude", "--goal", "Test managed entry points",
                     "--config", str(config_file))

    def runtime(self, action, *args, success=True):
        return self.command([sys.executable, "-I", str(SCRIPTS / "playbook.py"), action,
                             "--project", str(self.project)] + list(args), success=success)

    def worker_tree(self):
        wt = self.directory / "employee space"
        self.command(["git", "-C", str(self.project), "worktree", "add", "-qb", "t/101-test", str(wt)])
        return wt

    def dispatch(self, client="claude", *options, success=True, env=None, cwd=None, quiet=True):
        worktree = cwd or self.worker_tree()
        return self.command(["bash", str(SCRIPTS / "dispatch.sh"), client, str(worktree), "Do the scoped task"]
                            + (["-q"] if quiet else []) + list(options), success=success, env=env)

    def review_task(self, worktree):
        spec = self.directory / "review-spec.json"
        spec.write_text(json.dumps({"requirements": ["Source remains stable"],
                                    "acceptance": ["Independent review completes"],
                                    "paths": ["source.txt"], "review": {"independent": True}}))
        self.runtime("task", "--session", "owner", "--epoch", "1", "--id", "T-101",
                     "--spec", str(spec), "--worktree", str(worktree))

    def review_evidence(self, attempt, success=True):
        return self.runtime("evidence", "--session", "owner", "--epoch", "1", "--task", "T-101",
                            "--attempt", attempt["id"], "--reviewer", "worker-1", "--role", "reviewer",
                            "--note", "Fake independent review; no model called", success=success)

    def test_inherits_settings_and_records_receipt_without_claiming_acceptance(self):
        self.initialize()
        self.dispatch()
        observed = json.loads(self.stub_record.read_text())
        self.assertNotIn("--model", observed["args"])
        self.assertNotIn("--effort", observed["args"])
        state = json.loads(self.runtime("status").stdout)
        self.assertEqual(state["tasks"]["T-101"]["state"], "reported")
        self.assertNotEqual(state["tasks"]["T-101"]["state"], "verified")
        self.assertNotIn("stub completed", Path(state["attempts"][0]["log"]).read_text())
        self.assertIn("stub completed", next((self.directory / "logs").glob("*.log")).read_text())

    def test_review_freezes_full_stdout_and_stderr_with_and_without_quiet(self):
        self.initialize()
        wt = self.worker_tree()
        self.review_task(wt)
        env = dict(self.env, PLAYBOOK_ACTION="verify", STUB_REVIEW_LINES="90")
        for quiet in (True, False):
            with self.subTest(quiet=quiet):
                external = self.directory / ("quiet.log" if quiet else "verbose.log")
                result = self.dispatch("claude", "-l", str(external), env=env, cwd=wt, quiet=quiet)
                attempt = json.loads(result.stdout)["attempt"]
                frozen = Path(attempt["log"]).read_bytes()
                runtime_lines = frozen.decode().splitlines()
                external_lines = external.read_text().splitlines()
                for stream in ("stdout", "stderr"):
                    for index in range(90):
                        line = "review {} {:03d}".format(stream, index)
                        self.assertIn(line, runtime_lines)
                        self.assertIn(line, external_lines)
                self.assertEqual(attempt["log_snapshot"]["sha256"], hashlib.sha256(frozen).hexdigest())
                self.assertEqual(attempt["log_snapshot"]["size"], len(frozen))
                self.assertEqual(attempt["returncode"], 0)
                self.assertEqual(attempt["state"], "reported")
                self.assertIn("#dispatch| 结束 rc=0", external.read_text())
                # The complete runtime copy is authoritative. An optional user
                # copy can change or disappear without losing that evidence.
                if quiet:
                    external.write_text("changed optional copy\n")
                else:
                    external.unlink()
                receipt = json.loads(self.review_evidence(attempt).stdout)["evidence"]
                self.assertEqual(receipt["source"]["log_sha256"], attempt["log_snapshot"])
                self.runtime("task", "--session", "owner", "--epoch", "1", "--id", "T-101", "--state", "verified")

    def test_review_log_changes_block_receipt_creation_and_acceptance(self):
        self.initialize()
        wt = self.worker_tree()
        self.review_task(wt)
        result = self.dispatch(env=dict(self.env, PLAYBOOK_ACTION="verify", STUB_REVIEW_LINES="90"), cwd=wt)
        attempt = json.loads(result.stdout)["attempt"]
        log = Path(attempt["log"])
        original, mode = log.read_bytes(), log.stat().st_mode
        for has_receipt in (False, True):
            if has_receipt:
                self.review_evidence(attempt)
            for mutation in ("replace", "delete"):
                with self.subTest(has_receipt=has_receipt, mutation=mutation):
                    if mutation == "replace":
                        log.write_bytes(original.replace(b"review stdout 000", b"rewritten finding"))
                    else:
                        log.unlink()
                    if has_receipt:
                        status = json.loads(self.runtime("evidence", "--operation", "status", "--task", "T-101").stdout)
                        self.assertFalse(status["evidence"][0]["applicable"])
                        denied = self.runtime("task", "--session", "owner", "--epoch", "1", "--id", "T-101",
                                              "--state", "verified", success=False)
                    else:
                        denied = self.review_evidence(attempt, success=False)
                    self.assertNotEqual(denied.returncode, 0, denied.stdout + denied.stderr)
                    self.assertIn("log", denied.stderr.lower())
                    log.write_bytes(original)
                    log.chmod(mode)
        self.runtime("task", "--session", "owner", "--epoch", "1", "--id", "T-101", "--state", "verified")

    def test_review_worker_failure_is_not_hidden_by_successful_tee(self):
        self.initialize()
        wt = self.worker_tree()
        self.review_task(wt)
        result = self.dispatch(env=dict(self.env, PLAYBOOK_ACTION="verify", STUB_EXIT="23",
                                       STUB_REVIEW_LINES="90"), cwd=wt, success=False)
        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
        attempt = json.loads(result.stdout)["attempt"]
        self.assertEqual(attempt["returncode"], 23)
        self.assertEqual(attempt["state"], "blocked")
        self.assertIn("review stderr 089", Path(attempt["log"]).read_text())
        self.assertIn("结束 rc=23", next((self.directory / "logs").glob("*.log")).read_text())
        self.assertNotEqual(self.review_evidence(attempt, success=False).returncode, 0)

    def test_review_tee_failure_blocks_success_and_preserves_worker_failure(self):
        self.initialize()
        wt = self.worker_tree()
        self.review_task(wt)
        fake_bin = self.directory / "fake-bin"
        fake_bin.mkdir()
        tee = fake_bin / "tee"
        tee.write_text("#!" + sys.executable + " -I\n" + '''import pathlib, sys
sys.stdout.buffer.write(sys.stdin.buffer.read())
sys.stdout.buffer.flush()
# Simulate the user log becoming unwritable after its exclusive creation.
# Subsequent summary/tail operations must not replace the saved exit status.
log = pathlib.Path(sys.argv[-1])
log.unlink()
log.mkdir()
print("fixture: user log write failed", file=sys.stderr)
raise SystemExit(74)
''')
        tee.chmod(0o755)
        for worker_rc, expected in ((0, 74), (23, 23)):
            with self.subTest(worker_rc=worker_rc):
                env = dict(self.env, PLAYBOOK_ACTION="verify", STUB_EXIT=str(worker_rc),
                           PATH=str(fake_bin) + os.pathsep + self.env["PATH"])
                result = self.dispatch(env=env, cwd=wt, success=False, quiet=(worker_rc == 0))
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                attempt = json.loads(result.stdout)["attempt"]
                self.assertEqual(attempt["returncode"], expected)
                self.assertEqual(attempt["state"], "blocked")
                self.assertIn("fixture: user log write failed", Path(attempt["log"]).read_text())
                self.assertNotEqual(self.review_evidence(attempt, success=False).returncode, 0)

    def test_legacy_quiet_and_tail_output_keep_the_user_log_and_exit_status(self):
        env = {key: value for key, value in self.env.items() if not key.startswith("PLAYBOOK_")}
        env.update(PLAYBOOK_ACTION="verify", STUB_REVIEW_LINES="90", STUB_EXIT="23")
        for quiet in (True, False):
            with self.subTest(quiet=quiet):
                log = self.directory / ("legacy-quiet.log" if quiet else "legacy-verbose.log")
                result = self.dispatch("claude", "-l", str(log), env=env, cwd=self.project,
                                       quiet=quiet, success=False)
                self.assertEqual(result.returncode, 23)
                self.assertEqual(result.stdout.splitlines()[-1], str(log))
                self.assertIn("review stdout 000", log.read_text())
                self.assertIn("review stderr 089", log.read_text())
                self.assertIn("结束 rc=23", log.read_text())
                self.assertNotIn("review stdout 000", result.stdout)
                self.assertEqual("review stderr 089" in result.stdout, not quiet)

    def test_fixed_reviewer_uses_verify_permission_and_structured_evidence(self):
        self.config["workers"][0].update(model={"mode": "fixed", "value": "chosen-model"},
                                         effort={"mode": "fixed", "value": "high"})
        self.config["permissions"]["verify"] = "deny"
        self.initialize()
        wt = self.worker_tree()
        spec = self.directory / "review-spec.json"
        spec.write_text(json.dumps({"requirements": ["Source remains stable"],
                                    "acceptance": ["Independent review completes"],
                                    "paths": ["source.txt"], "review": {"independent": True}}))
        self.runtime("task", "--session", "owner", "--epoch", "1", "--id", "T-101",
                     "--spec", str(spec), "--worktree", str(wt))
        env = dict(self.env, PLAYBOOK_ACTION="verify")
        denied = self.dispatch(env=env, cwd=wt, success=False)
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("verify is deny", denied.stderr)
        self.assertFalse(self.stub_record.exists())
        self.assertEqual(json.loads(self.runtime("status").stdout)["attempts"], [])
        patch = self.directory / "allow-review.json"
        patch.write_text(json.dumps({"permissions": {"verify": "allow"}}))
        self.runtime("configure", "--session", "owner", "--epoch", "1", "--patch", str(patch))
        self.dispatch(env=env, cwd=wt)
        attempt = json.loads(self.runtime("status").stdout)["attempts"][0]
        self.assertEqual(attempt["action"], "verify")
        self.assertEqual(attempt["worker"], "worker-1")
        observed = json.loads(self.stub_record.read_text())
        self.assertIn("chosen-model", observed["args"])
        self.assertIn("high", observed["args"])
        self.runtime("evidence", "--session", "owner", "--epoch", "1", "--task", "T-101",
                     "--attempt", attempt["id"], "--reviewer", "worker-1", "--role", "reviewer",
                     "--note", "Fake independent review; no model called")
        self.runtime("task", "--session", "owner", "--epoch", "1", "--id", "T-101", "--state", "verified")
        self.assertEqual(json.loads(self.runtime("status").stdout)["tasks"]["T-101"]["state"], "verified")

    def test_fixed_claude_settings_reach_child(self):
        self.config["workers"][0].update(model={"mode": "fixed", "value": "chosen-model"},
                                         effort={"mode": "fixed", "value": "high"})
        self.initialize()
        self.dispatch()
        args = json.loads(self.stub_record.read_text())["args"]
        self.assertEqual(args[args.index("--model") + 1], "chosen-model")
        self.assertEqual(args[args.index("--effort") + 1], "high")

    def test_codex_profile_and_effort_are_per_run_arguments(self):
        self.config["workers"][0].update(client="codex", profile="review-profile",
                                         effort={"mode": "fixed", "value": "high"})
        self.initialize()
        self.dispatch("codex")
        args = json.loads(self.stub_record.read_text())["args"]
        self.assertEqual(args[args.index("--profile") + 1], "review-profile")
        self.assertIn('model_reasoning_effort="high"', args)

    def test_dsh_without_profile_is_blocked_before_launch(self):
        self.config["workers"][0]["client"] = "dsh"
        self.initialize()
        result = self.dispatch("dsh", success=False,
                               env=dict(self.env, DISPATCH_DSH_PROFILE="unrelated-profile"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit approved worker.profile", result.stderr)
        self.assertFalse(self.stub_record.exists())
        state = json.loads(self.runtime("status").stdout)
        self.assertEqual(state["attempts"], [])

    def test_dsh_model_and_effort_patches_do_not_inject_fields(self):
        self.config["workers"][0].update(client="dsh", profile="headless",
                                         model={"mode": "fixed", "value": 'provider/model"quoted'},
                                         effort={"mode": "fixed", "value": "high"})
        self.initialize()
        self.dispatch("dsh")
        observed = json.loads(self.stub_record.read_text())
        self.assertEqual(len(observed["patches"]), 2)
        patches = [json.loads(p)[0] for p in observed["patches"]]
        self.assertEqual(patches[0]["config"]["model"], 'model"quoted')
        self.assertEqual(patches[1]["config"], {"reasoningEffort": "high"})
        for index, arg in enumerate(observed["args"]):
            if arg == "--patch":
                self.assertFalse(Path(observed["args"][index + 1]).exists())

    def test_legacy_hermes_policy_requires_explicit_approval_selection(self):
        self.config["workers"][0].update(client="hermes", effort={"mode": "fixed", "value": "high"})
        self.initialize()
        result = self.dispatch("hermes", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("worker.hermes.approval", result.stderr)
        self.assertFalse(self.stub_record.exists())

    def test_unapproved_cli_override_is_not_applied(self):
        self.initialize()
        result = self.dispatch("claude", "-m", "another-model", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("configuration", result.stderr)
        self.assertFalse(self.stub_record.exists())

    def test_unapproved_permission_arguments_are_not_applied(self):
        self.initialize()
        result = self.dispatch("claude", "--", "--dangerously-skip-permissions", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("approved", result.stderr)
        self.assertFalse(self.stub_record.exists())

    def test_stale_session_cannot_dispatch(self):
        self.initialize()
        env = dict(self.env, PLAYBOOK_SESSION="another-window")
        result = self.dispatch(success=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.stub_record.exists())

    def test_ambiguous_worker_requires_id(self):
        self.config["workers"].append({"id": "worker-2", "client": "claude"})
        self.initialize()
        env = dict(self.env)
        env.pop("PLAYBOOK_WORKER")
        result = self.dispatch(success=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one", result.stderr)
        self.assertFalse(self.stub_record.exists())

    def test_dispatch_permission_is_enforced(self):
        self.config["permissions"]["dispatch"] = "deny"
        self.initialize()
        result = self.dispatch(success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.stub_record.exists())

    def test_review_timeout_stops_descendant_holding_the_output_pipe(self):
        self.initialize()
        wt = self.worker_tree()
        self.review_task(wt)
        pid_file = self.directory / "review-child.pid"
        child = '''import os, pathlib, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
pathlib.Path(os.environ["STUB_CHILD_PID"]).write_text(str(os.getpid()))
print("review descendant stdout", flush=True)
print("review descendant stderr", file=sys.stderr, flush=True)
time.sleep(30)
'''
        self.stub.write_text("#!" + sys.executable + " -I\nimport subprocess, sys\n"
                             + "subprocess.Popen([sys.executable, '-I', '-c', " + repr(child) + "])\n")
        env = dict(self.env, PLAYBOOK_ACTION="verify", STUB_CHILD_PID=str(pid_file))
        result = self.dispatch("claude", "-t", "2", env=env, cwd=wt, success=False)
        self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
        attempt = json.loads(result.stdout)["attempt"]
        self.assertTrue(attempt["timed_out"])
        self.assertEqual(attempt["state"], "blocked")
        child_pid = int(pid_file.read_text())
        state = self.command(["ps", "-o", "stat=", "-p", str(child_pid)], success=False)
        running = state.returncode == 0 and bool(state.stdout.strip()) and not state.stdout.lstrip().startswith("Z")
        if running and os.getpgid(child_pid) == attempt["pgid"]:
            os.kill(child_pid, 9)  # Clean up only this fixture's surviving child if the assertion fails.
        self.assertFalse(running, "review descendant survived managed timeout: " + state.stdout)
        for output in ("review descendant stdout", "review descendant stderr"):
            self.assertIn(output, Path(attempt["log"]).read_text())
            self.assertIn(output, next((self.directory / "logs").glob("*.log")).read_text())
        self.assertNotEqual(self.review_evidence(attempt, success=False).returncode, 0)

    def test_short_timeout_uses_managed_receipt(self):
        self.initialize()
        self.stub.write_text("#!" + sys.executable + " -I\nimport time\ntime.sleep(10)\n")
        result = self.dispatch("claude", "-t", "1", success=False)
        self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt["attempt"]["timed_out"])
        self.assertEqual(receipt["attempt"]["timeout_seconds"], 1)
        state = json.loads(self.runtime("status").stdout)
        self.assertEqual(state["tasks"]["T-101"]["state"], "blocked")

    def test_existing_log_is_preserved(self):
        self.initialize()
        log = self.directory / "existing.log"
        log.write_text("previous evidence")
        result = self.dispatch("claude", "-l", str(log), success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(log.read_text(), "previous evidence")
        self.assertFalse(self.stub_record.exists())

    def test_relative_log_uses_original_caller_directory(self):
        self.initialize()
        wt = self.worker_tree()
        evidence = wt / "evidence.log"
        evidence.write_text("original worker evidence")
        self.dispatch("claude", "-l", "evidence.log", cwd=wt)
        self.assertEqual(evidence.read_text(), "original worker evidence")
        self.assertIn("stub completed", (self.project / "evidence.log").read_text())

    def test_log_created_after_precheck_is_not_overwritten(self):
        self.config["workers"][0]["effort"] = {"mode": "fixed", "value": "high"}
        self.initialize()
        log = self.project / "late.log"
        result = self.dispatch("claude", "-l", str(log), success=False,
                               env=dict(self.env, STUB_COLLISION_LOG=str(log)))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(log.read_text(), "late evidence")
        self.assertFalse(self.stub_record.exists())

    def test_dsh_launcher_patch_precedes_application_arguments(self):
        self.config["workers"][0].update(client="dsh", profile="headless", args=["--json"],
                                         effort={"mode": "fixed", "value": "high"})
        self.initialize()
        self.dispatch("dsh")
        args = json.loads(self.stub_record.read_text())["args"]
        self.assertLess(args.index("--patch"), args.index("--json"))

    def test_linked_canonical_project_never_falls_back_to_legacy(self):
        main = self.project
        self.project = self.worker_tree()
        self.config["permissions"].update(dispatch="deny", **{"worktree-create": "deny"})
        self.initialize()
        canonical = self.project
        self.project = main
        env = {k: v for k, v in self.env.items() if not k.startswith("PLAYBOOK_")}
        result = self.dispatch(success=False, env=env, cwd=main)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.stub_record.exists())
        result = self.command(["bash", str(SCRIPTS / "wt.sh"), "new", "T-501", "blocked"],
                              env=env, success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(Path(str(main) + "-wt/T-501").exists())
        self.assertFalse(Path(str(canonical) + "-wt/T-501").exists())
        status = json.loads(self.runtime("status").stdout)
        self.assertEqual(status["project_root"], str(canonical))
        self.assertEqual(status["attempts"], [])

    def test_worktree_uses_normalized_sparse_adopted_config(self):
        control = self.project / ".orchestrator"
        control.mkdir()
        (control / "config.json").write_text(json.dumps({"goal": "test", "permissions": {"worktree-create": "allow"}}))
        self.runtime("init", "--session", "owner", "--client", "claude", "--goal", "test", "--adopt")
        self.command(["bash", str(SCRIPTS / "wt.sh"), "new", "T-502", "sparse"])
        self.assertTrue(Path(str(self.project) + "-wt/T-502").is_dir())

    def test_worktree_prompt_uses_custom_planning_paths(self):
        self.config["paths"] = {"worker": "coord/worker.md", "cards": "coord/cards"}
        self.initialize()
        result = self.command(["bash", str(SCRIPTS / "wt.sh"), "new", "T-503", "custom"])
        output = result.stdout + result.stderr  # guard reserves stdout for its JSON receipt.
        self.assertIn(str(self.project / "coord/worker.md"), output)
        self.assertIn(str(self.project / "coord/cards/T-503.md"), output)
        self.assertNotIn(str(self.project / "docs/plan/tasks/T-503.md"), output)

    def test_managed_setup_is_run_after_creation_guard_returns(self):
        scripts = self.project / "scripts"
        scripts.mkdir()
        hook = scripts / "wt-setup.sh"
        command = [sys.executable, "-I", str(SCRIPTS / "playbook.py"), "run", "--project", str(self.project),
                   "--session", "owner", "--epoch", "1", "--action", "verify", "--task", "setup-check"]
        child = [sys.executable, "-I", "-c", "from pathlib import Path; Path('setup-done').write_text('done')"]
        hook.write_text("#!/bin/bash\nexec " + shlex.join(command) + ' --cwd "$1" -- ' + shlex.join(child) + "\n")
        hook.chmod(0o755)
        self.command(["git", "add", "scripts/wt-setup.sh"])
        self.command(["git", "commit", "-qm", "add setup procedure"])
        self.initialize()
        result = self.command(["bash", str(SCRIPTS / "wt.sh"), "new", "T-504", "setup"])
        wt = Path(str(self.project) + "-wt/T-504")
        self.assertIn("setup pending", result.stdout + result.stderr)
        self.assertFalse((wt / "setup-done").exists())
        self.command(["bash", str(wt / "scripts/wt-setup.sh"), str(wt)])
        self.assertEqual((wt / "setup-done").read_text(), "done")

    def test_configured_scaffold_checks_owner_and_prepared_state(self):
        self.initialize()
        script = ["bash", str(SCRIPTS / "init-plan.sh"), str(self.project)]
        wrong = dict(self.env, PLAYBOOK_SESSION="other", PLAYBOOK_EPOCH="999")
        self.assertNotEqual(self.command(script, env=wrong, success=False).returncode, 0)
        self.command(script + ["--dry-run"], env=wrong)
        self.assertFalse((self.project / "docs").exists())
        self.runtime("handoff", "--session", "owner", "--epoch", "1", "--to", "next")
        self.assertNotEqual(self.command(script, success=False).returncode, 0)
        self.assertFalse((self.project / "docs").exists())

    def test_current_owner_can_scaffold_without_new_permission_choice(self):
        self.initialize()
        self.command(["bash", str(SCRIPTS / "init-plan.sh"), str(self.project)])
        self.assertTrue((self.project / "docs/plan/WORKER.md").is_file())
        state = json.loads(self.runtime("status").stdout)
        self.assertEqual(state["owner"]["session"], "owner")
        self.assertEqual(state["mode"], "active")

    def test_scaffold_commit_hint_includes_worktree_runtime(self):
        result = self.command(["bash", str(SCRIPTS / "init-plan.sh"), str(self.project)])
        hint = next(line.strip()[3:] for line in result.stdout.splitlines() if line.strip().startswith("4. git add "))
        self.command(shlex.split(hint.split(" && ", 1)[0]))
        self.command(["git", "commit", "-qm", "follow scaffold staging hint"])
        config_file = self.directory / "approved.json"
        config_file.write_text(json.dumps(self.config))
        self.runtime("init", "--session", "owner", "--client", "claude", "--goal", "test",
                     "--adopt", "--config", str(config_file))
        self.command(["bash", str(self.project / "scripts/wt.sh"), "new", "T-505", "copied"])
        wt = Path(str(self.project) + "-wt/T-505")
        self.assertTrue((wt / "scripts/playbook.py").is_file())
        self.assertTrue((wt / "scripts/playbook_work.py").is_file())
        self.command(["bash", str(wt / "scripts/wt.sh"), "ls"], cwd=wt)
        # The linked worktree must execute the copied runtime without the skill source.
        copied = [sys.executable, "-I", str(wt / "scripts/playbook.py")]
        spec = self.directory / "copied-spec.json"
        spec.write_text(json.dumps({"requirements": ["Copied runtime remains usable"],
                                    "acceptance": ["Readiness checks the registered spec"],
                                    "paths": ["scripts/wt.sh"]}))
        self.command(copied + ["task", "--project", str(wt), "--session", "owner", "--epoch", "1",
                              "--id", "copied-runtime", "--spec", str(spec), "--worktree", str(wt)], cwd=wt)
        ready = self.command(copied + ["readiness", "--project", str(wt), "--task", "copied-runtime"], cwd=wt)
        self.assertTrue(json.loads(ready.stdout)["ready"])

    def test_wt_entry_refuses_other_session_and_force_cleanup(self):
        self.initialize()
        env = dict(self.env, WT_ROOT=str(self.project), PLAYBOOK_SESSION="other")
        result = self.command(["bash", str(SCRIPTS / "wt.sh"), "new", "T-201", "sample"], success=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(Path(str(self.project) + "-wt/T-201").exists())
        env["PLAYBOOK_SESSION"] = "owner"
        self.command(["bash", str(SCRIPTS / "wt.sh"), "new", "T-201", "sample"], env=env)
        result = self.command(["bash", str(SCRIPTS / "wt.sh"), "rm", "T-201", "--force"], success=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("never force-deletes", result.stderr)

    def test_ignored_evidence_blocks_cleanup(self):
        self.initialize()
        # The portable config is deliberately untracked after init; preserve it
        # in this test repository so cleanup reaches the ignored-evidence check.
        self.command(["git", "-C", str(self.project), "add", ".orchestrator"])
        self.command(["git", "-C", str(self.project), "commit", "-qm", "record project policy"])
        env = dict(self.env, WT_ROOT=str(self.project))
        self.command(["bash", str(SCRIPTS / "wt.sh"), "new", "T-201", "sample"], env=env)
        wt = Path(str(self.project) + "-wt/T-201")
        (wt / ".gitignore").write_text("evidence.log\n")
        self.command(["git", "-C", str(wt), "add", ".gitignore"])
        self.command(["git", "-C", str(wt), "commit", "-qm", "ignore log"])
        self.command(["git", "-C", str(self.project), "merge", "--no-ff", "t/201-sample", "-m", "integrate"])
        (wt / "evidence.log").write_text("only copy of evidence")
        self.runtime("checkpoint", "--session", "owner", "--epoch", "1")
        result = self.command(["bash", str(SCRIPTS / "wt.sh"), "rm", "T-201"], success=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((wt / "evidence.log").exists())
        self.assertIn("ignored", result.stderr)


if __name__ == "__main__":
    unittest.main()
