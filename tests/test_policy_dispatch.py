"""Offline adapter contracts with counted, real subprocess help probes.

Run: python3 -I -m unittest discover -s tests -p test_policy_dispatch.py.
The paired fixture runtime records launches without executing any model client.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts/policy-dispatch.py"
REAL_RUN = subprocess.run


class PolicyDispatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="playbook-policy-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.adapter = self.root / "policy-dispatch.py"
        shutil.copyfile(ADAPTER, self.adapter)
        (self.root / "playbook.py").write_text('''import json, os, pathlib, sys
if sys.argv[1] == "status":
    print(pathlib.Path(os.environ["FIXTURE_STATUS"]).read_text())
    raise SystemExit(0)
assert sys.argv[1] == "run", sys.argv
patches = [pathlib.Path(sys.argv[i + 1]).read_text()
           for i, arg in enumerate(sys.argv) if arg == "--patch"]
record = {"argv": sys.argv[1:], "patches": patches,
          "profile": os.environ.get("DISPATCH_DSH_PROFILE"),
          "binary": os.environ["DISPATCH_BIN_" + os.environ["FIXTURE_CLIENT"].upper()]}
with open(os.environ["FIXTURE_LAUNCHES"], "a") as stream:
    stream.write(json.dumps(record) + "\\n")
raise SystemExit(int(os.environ.get("FIXTURE_RUN_EXIT", "0")))
''', encoding="utf-8")
        self.binary = self.root / "fake client"
        self.binary.write_text("#!" + sys.executable + " -I\n" + '''import json, os, sys, time
assert "--help" in sys.argv[1:], "fixture only accepts help probes"
with open(os.environ["FIXTURE_PROBES"], "a") as stream:
    stream.write(json.dumps({"binary": sys.argv[0], "argv": sys.argv[1:]}) + "\\n")
if os.environ.get("FIXTURE_SLOW_HELP"):
    time.sleep(5)
print(os.environ.get("FIXTURE_HELP", "--profile --config --effort --patch"))
raise SystemExit(int(os.environ.get("FIXTURE_HELP_EXIT", "0")))
''', encoding="utf-8")
        self.binary.chmod(0o755)
        self.status_file = self.root / "status.json"
        self.probes = self.root / "probes.jsonl"
        self.launches = self.root / "launches.jsonl"
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("PLAYBOOK_", "DISPATCH_", "FIXTURE_"))}
        self.env.update({
            "PLAYBOOK_PROJECT": str(self.project), "PLAYBOOK_SESSION": "owner",
            "PLAYBOOK_EPOCH": "1", "PLAYBOOK_TASK": "T-1", "PLAYBOOK_WORKER": "worker-1",
            "FIXTURE_STATUS": str(self.status_file), "FIXTURE_PROBES": str(self.probes),
            "FIXTURE_LAUNCHES": str(self.launches), "FIXTURE_CLIENT": "codex",
        })
        for client in ("claude", "codex", "dsh", "hermes"):
            self.env["DISPATCH_BIN_" + client.upper()] = str(self.binary)
        self.worker = {
            "id": "worker-1", "client": "codex", "profile": "review-profile", "args": [],
            "model": {"mode": "inherit"}, "effort": {"mode": "fixed", "value": "high"},
        }
        self.status = {"config_revision": 7, "policy": {
            "workers": [self.worker], "limits": {"timeout_seconds": 30},
        }}
        spec = importlib.util.spec_from_file_location("policy_dispatch_fixture", self.adapter)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def records(self, path):
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def arguments(self, *options):
        return [self.worker["client"], str(self.project), "fixture task"] + list(options)

    def save_status(self):
        self.status_file.write_text(json.dumps(self.status), encoding="utf-8")
        self.env["FIXTURE_CLIENT"] = self.worker["client"]

    def dispatch(self, *options, expected=0):
        self.save_status()
        result = REAL_RUN([sys.executable, "-I", str(self.adapter)] + self.arguments(*options),
                          env=self.env, cwd=self.root, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_profile_and_effort_share_one_probe_for_codex_and_dsh(self):
        for client, argv in (("codex", ["exec", "--help"]), ("dsh", ["--help"])):
            with self.subTest(client=client):
                self.worker["client"] = client
                self.dispatch()
                probe = self.records(self.probes)[-1]
                self.assertEqual(probe["argv"], argv)
                receipt = self.records(self.launches)[-1]
                self.assertEqual(receipt["binary"], str(self.binary))
                self.assertIn("--config-revision", receipt["argv"])
                self.assertIn("7", receipt["argv"])
                if client == "codex":
                    self.assertIn("review-profile", receipt["argv"])
                    self.assertIn('model_reasoning_effort="high"', receipt["argv"])
                else:
                    self.assertEqual(receipt["profile"], "review-profile")
                    self.assertEqual(json.loads(receipt["patches"][0]), [
                        {"id": "agent-default-model", "config": {"reasoningEffort": "high"}},
                    ])
                    patch = receipt["argv"][receipt["argv"].index("--patch") + 1]
                    self.assertFalse(Path(patch).exists())
        self.assertEqual(len(self.records(self.probes)), 2)
        self.assertEqual(len(self.records(self.launches)), 2)

    def test_configured_reviewer_preserves_settings_and_verification_identity(self):
        self.env["PLAYBOOK_ACTION"] = "verify"
        self.env["PLAYBOOK_INTEGRATION"] = "assembly-1"
        self.worker["model"] = {"mode": "fixed", "value": "approved-model"}
        self.dispatch()
        argv = self.records(self.launches)[0]["argv"]
        self.assertEqual(argv[argv.index("--action") + 1], "verify")
        self.assertEqual(argv[argv.index("--reviewer") + 1], "worker-1")
        self.assertEqual(argv[argv.index("--role") + 1], "reviewer")
        self.assertEqual(argv[argv.index("--integration") + 1], "assembly-1")
        self.assertEqual(argv[argv.index("--worker") + 1], "worker-1")
        self.assertEqual(argv[argv.index("-m") + 1], "approved-model")
        self.assertIn("review-profile", argv)
        self.assertIn('model_reasoning_effort="high"', argv)
        self.assertEqual(len(self.records(self.probes)), 1)

    def test_invalid_execution_stage_does_not_probe_or_launch(self):
        for action, integration in (("merge", None), ("", None), ("dispatch", "batch"), ("verify", "")):
            with self.subTest(action=action, integration=integration):
                self.env["PLAYBOOK_ACTION"] = action
                if integration is None:
                    self.env.pop("PLAYBOOK_INTEGRATION", None)
                else:
                    self.env["PLAYBOOK_INTEGRATION"] = integration
                self.dispatch(expected=2)
        self.assertFalse(self.probes.exists())
        self.assertFalse(self.launches.exists())

    def test_precheck_cannot_be_recorded_as_acceptance_verification(self):
        self.env["PLAYBOOK_ACTION"] = "verify"
        self.save_status()
        args = self.arguments()
        args[2] = "--precheck"
        result = REAL_RUN([sys.executable, "-I", str(self.adapter)] + args,
                          env=self.env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn("precheck is dispatch", result.stderr)
        self.assertFalse(self.probes.exists())
        self.assertFalse(self.launches.exists())

    def test_two_main_calls_in_one_process_probe_independently(self):
        self.save_status()
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(self.module.main(self.arguments()), 0)
            self.assertEqual(self.module.main(self.arguments()), 0)
        self.assertEqual(len(self.records(self.probes)), 2)
        self.assertEqual(len(self.records(self.launches)), 2)

    def test_changed_help_on_next_call_cannot_reuse_previous_success(self):
        self.save_status()
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(self.module.main(self.arguments()), 0)
            os.environ["FIXTURE_HELP"] = "--profile"
            with self.assertRaisesRegex(self.module.DispatchError, "does not advertise --config"):
                self.module.main(self.arguments())
        self.assertEqual(len(self.records(self.probes)), 2)
        self.assertEqual(len(self.records(self.launches)), 1)

    def test_cache_distinguishes_binary_client_and_entire_help_argv(self):
        second = self.root / "other client"
        shutil.copyfile(self.binary, second)
        second.chmod(0o755)
        probe = self.module.HelpProbe()
        with mock.patch.dict(os.environ, self.env, clear=True):
            probe.read(str(self.binary), "claude", ["--help"])
            probe.read(str(self.binary), "claude", ["--help"])
            probe.read(str(second), "claude", ["--help"])
            probe.read(str(self.binary), "dsh", ["--help"])
            probe.read(str(self.binary), "claude", ["subcommand", "--help"])
        self.assertEqual(len(self.records(self.probes)), 4)

    def test_nonzero_help_with_supported_flags_is_not_cached_as_success(self):
        self.env["FIXTURE_HELP_EXIT"] = "9"
        self.dispatch(expected=2)
        self.assertFalse(self.launches.exists())
        probe = self.module.HelpProbe()
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(self.module.DispatchError, "help probe failed"):
                probe.require_flag(str(self.binary), "codex", "--profile")
            os.environ["FIXTURE_HELP_EXIT"] = "0"
            probe.require_flag(str(self.binary), "codex", "--config")
        self.assertEqual(len(self.records(self.probes)), 3)

    def test_timeout_is_not_cached_as_success(self):
        probe = self.module.HelpProbe()

        def bounded_run(*args, **kwargs):
            kwargs["timeout"] = 1
            return REAL_RUN(*args, **kwargs)

        with mock.patch.dict(os.environ, self.env, clear=True):
            os.environ["FIXTURE_SLOW_HELP"] = "1"
            with mock.patch.object(self.module.subprocess, "run", side_effect=bounded_run):
                with self.assertRaisesRegex(self.module.DispatchError, "cannot verify"):
                    probe.require_flag(str(self.binary), "codex", "--profile")
            del os.environ["FIXTURE_SLOW_HELP"]
            probe.require_flag(str(self.binary), "codex", "--config")
        self.assertEqual(len(self.records(self.probes)), 2)

    def test_missing_executable_is_not_cached_as_success(self):
        probe = self.module.HelpProbe()
        missing = self.root / "initially missing"
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(self.module.DispatchError, "cannot verify"):
                probe.require_flag(str(missing), "claude", "--effort")
            shutil.copyfile(self.binary, missing)
            missing.chmod(0o755)
            probe.require_flag(str(missing), "claude", "--effort")
        self.assertEqual(len(self.records(self.probes)), 1)

    def test_cached_help_still_checks_each_exact_flag(self):
        self.env["FIXTURE_HELP"] = "--profile --config-file --effortless --patches"
        result = self.dispatch(expected=2)
        self.assertIn("does not advertise --config", result.stderr)
        self.assertEqual(len(self.records(self.probes)), 1)
        self.assertFalse(self.launches.exists())

    def test_relative_executable_stays_bound_after_worker_cwd_changes(self):
        self.env["DISPATCH_BIN_CODEX"] = "./fake client"
        self.dispatch()
        self.assertEqual(self.records(self.launches)[0]["binary"], str(self.binary))
        self.assertEqual(self.records(self.probes)[0]["binary"], str(self.binary))

    def test_executable_symlink_is_preserved_for_the_worker(self):
        alias = self.root / "client alias"
        alias.symlink_to(self.binary)
        self.env["DISPATCH_BIN_CODEX"] = str(alias)
        self.dispatch()
        self.assertEqual(self.records(self.launches)[0]["binary"], str(alias))
        self.assertEqual(self.records(self.probes)[0]["binary"], str(alias))

    def test_inherited_settings_need_no_probe(self):
        self.worker.pop("profile")
        self.worker["effort"] = {"mode": "inherit"}
        self.dispatch()
        self.assertFalse(self.probes.exists())
        self.assertEqual(len(self.records(self.launches)), 1)

    def test_unapproved_arguments_model_and_timeout_remain_blocked(self):
        for options in (("--", "--dangerously-skip-permissions"),
                        ("-m", "unapproved-model"), ("-t", "31"), ("-t", "0")):
            with self.subTest(options=options):
                self.dispatch(*options, expected=2)
        self.assertFalse(self.probes.exists())
        self.assertFalse(self.launches.exists())

    def test_reserved_worker_args_remain_blocked(self):
        for argument in ("--model=other", "-m", "--effort=low", "--profile=other",
                         "-p", "model=other", 'model_reasoning_effort="low"',
                         "agent-default-model=other"):
            with self.subTest(argument=argument):
                self.worker["args"] = [argument]
                result = self.dispatch(expected=2)
                self.assertIn("dedicated fields", result.stderr)
        self.assertFalse(self.probes.exists())
        self.assertFalse(self.launches.exists())

    def test_codex_equivalent_dedicated_setting_overrides_are_blocked(self):
        cases = [
            ["-mattached-model"], ["-m=attached-model"], ["-preview-profile"],
            ["--config", 'model = "other-model"'],
            ['--config=model="other-model"'],
            ["-c", ' model\t= "other-model"'],
            ['-cmodel="other-model"'], ['-c=model="other-model"'],
            ["--config", '\t"model" = "other-model"'],
            ["-c", "'model' = 'other-model'"],
            ['--config= model_reasoning_effort = "low"'],
            ['-cmodel_reasoning_effort="low"'],
            ["--config", 'profile = "other-profile"'],
            ['--config="profile" = "other-profile"'],
            ['-cprofile="other-profile"'],
        ]
        for args in cases:
            with self.subTest(args=args):
                self.worker["args"] = args
                result = self.dispatch(expected=2)
                self.assertIn("dedicated fields", result.stderr)
        self.assertFalse(self.probes.exists())
        self.assertFalse(self.launches.exists())

    def test_hermes_attached_model_override_is_blocked(self):
        self.worker.update(client="hermes", effort={"mode": "inherit"})
        self.worker.pop("profile")
        self.worker["args"] = ["-mother-model"]
        self.assertIn("dedicated fields", self.dispatch(expected=2).stderr)
        self.assertFalse(self.probes.exists())
        self.assertFalse(self.launches.exists())

    def test_unrelated_approved_codex_arguments_keep_their_exact_values(self):
        args = ["--json", "--config", 'sandbox_mode = "workspace-write"',
                '--config=notice.hide_model_migration_prompt=true',
                "-c", 'model_provider = "local"', '-cmodel_context_window=32768',
                '-c=model_supports_reasoning_summaries=true',
                "--output-last-message", "model-review.txt"]
        self.worker["args"] = args
        self.dispatch("--", *args)
        argv = self.records(self.launches)[0]["argv"]
        native_start = argv.index("--", argv.index("--") + 1) + 1
        self.assertEqual(argv[native_start:native_start + len(args)], args)

    def test_approved_args_and_model_pass_through(self):
        self.worker["args"] = ["--json"]
        self.worker["model"] = {"mode": "fixed", "value": "approved-model"}
        self.dispatch("-m", "approved-model", "--", "--json")
        argv = self.records(self.launches)[0]["argv"]
        self.assertEqual(argv[argv.index("-m") + 1], "approved-model")
        self.assertIn("--json", argv)

    def test_recommendations_and_unknown_modes_remain_blocked(self):
        original = copy.deepcopy(self.worker)
        for name in ("model", "effort"):
            for mode, message in (("recommend", "resolve the"), ("automatic", "unknown")):
                with self.subTest(setting=name, mode=mode):
                    self.worker.clear()
                    self.worker.update(copy.deepcopy(original))
                    self.worker[name] = {"mode": mode, "value": "high"}
                    self.assertIn(message, self.dispatch(expected=2).stderr)
        self.assertFalse(self.probes.exists())
        self.assertFalse(self.launches.exists())

    def test_malformed_status_is_a_boundary_error_not_a_traceback(self):
        original = copy.deepcopy(self.status)
        mutations = [
            lambda data: data.update(policy=[]),
            lambda data: data.update(config_revision=True),
            lambda data: data["policy"].update(workers={}),
            lambda data: data["policy"].update(workers=[None]),
            lambda data: data["policy"].update(limits=[]),
            lambda data: data["policy"]["limits"].update(timeout_seconds=True),
            lambda data: data["policy"]["workers"][0].update(model=[]),
            lambda data: data["policy"]["workers"][0].pop("effort"),
            lambda data: data["policy"]["workers"][0].update(args="--json"),
            lambda data: data["policy"]["workers"][0].update(args=[None]),
            lambda data: data["policy"]["workers"][0].update(args=["bad\0arg"]),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                self.status = copy.deepcopy(original)
                mutate(self.status)
                result = self.dispatch(expected=2)
                self.assertIn("policy-dispatch:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.probes.exists())
        self.assertFalse(self.launches.exists())

    def test_runtime_owns_schema_rejection_before_adapter_consumption(self):
        # These schema errors no longer need a second validator in the adapter.
        # Exercise the actual source of canonical status, in an isolated project.
        config = self.root / "unapproved.json"
        for bad_worker in ({"enabled": False}, {"model": {"mode": "inherit", "value": "hidden"}},
                           {"args": [42]}):
            with self.subTest(worker=bad_worker):
                worker = dict(self.worker, **bad_worker)
                config.write_text(json.dumps({"workers": [worker]}), encoding="utf-8")
                result = REAL_RUN([
                    sys.executable, "-I", str(ROOT / "scripts/playbook.py"), "init",
                    "--project", str(self.project), "--session", "owner", "--client", "codex",
                    "--goal", "fixture policy validation", "--config", str(config),
                ], env=self.env, text=True, capture_output=True, timeout=15)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.launches.exists())


if __name__ == "__main__":
    unittest.main()
