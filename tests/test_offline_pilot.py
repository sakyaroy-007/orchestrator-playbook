"""One assembled offline pilot through a freshly generated standalone bundle.

Run with: python3 -I -m unittest discover -s tests -p test_offline_pilot.py -v
Set PLAYBOOK_OFFLINE_PILOT_ARTIFACTS to an external evidence directory to retain
this run's unique temporary project, command receipts, barriers and result.json.
Without it, unittest cleans up automatically, including after a failed pilot.
No source-runtime imports, sibling skills, model clients or network are used.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
PYTHON = [sys.executable, "-I", "-B"]
REQUIRED_SCRIPTS = {
    "playbook.py", "playbook_work.py", "playbook-foundation.py",
    "policy-dispatch.py", "wt.sh", "dispatch.sh", "init-plan.sh",
}
PARSER_SOURCE = '''import csv
import io


def parse_rows(text):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ["name", "value"]:
        raise ValueError("Expected name,value header")
    return [(row["name"], int(row["value"])) for row in reader]
'''
RENDER_SOURCE = '''def render_rows(rows):
    return "".join("{}: {}\\n".format(name, value) for name, value in sorted(rows))
'''
# Every fake child has its own finite deadline, including when a supervisor
# fails. Only the parent opens release gates; no recorded PID is ever signalled.
FAKE_WORKER = r'''import json
import os
from pathlib import Path
import runpy
import sys
import time

mode, task, signal_root, token, gate, peer, sources_path = sys.argv[1:]
signals = Path(signal_root)
root = Path.cwd()
deadline = time.monotonic() + 20

def emit(event, **extra):
    record = {"token": token, "event": event, "pid": os.getpid(),
              "process_monotonic_ns": time.monotonic_ns(), "wall_time_ns": time.time_ns(),
              "cwd": str(root), **extra}
    path = signals / (token + "." + event + ".json")
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(record), encoding="utf-8")
    temporary.replace(path)
    print(json.dumps(record), flush=True)

def wait_for(name):
    while not (signals / name).exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("Fake-worker barrier expired: " + name)
        time.sleep(0.02)

def parse():
    return runpy.run_path(str(root / "parser.py"))["parse_rows"]

def render():
    return runpy.run_path(str(root / "renderer.py"))["render_rows"]

emit("started")
if mode == "forbidden":
    raise SystemExit("A prelaunch denial incorrectly started its child")
if mode == "implement":
    wait_for(peer + ".started.json")
    emit("rendezvous", peer=peer)
wait_for(gate)
if mode == "implement":
    filename = "parser.py" if task == "parse" else "renderer.py"
    sources = json.loads(Path(sources_path).read_text(encoding="utf-8"))
    (root / filename).write_text(sources[filename], encoding="utf-8")
    if task == "parse":
        assert parse()("name,value\na,1\n") == [("a", 1)]
    else:
        assert render()([("a", 1)]) == "a: 1\n"
    checks = 1
elif mode == "verify" and task == "parse":
    parser = parse()
    assert parser('name,value\n"alpha,one",2\nbeta,3\n') == [("alpha,one", 2), ("beta", 3)]
    assert parser("name,value\n") == []
    try:
        parser("wrong,header\na,1\n")
    except ValueError:
        pass
    else:
        raise AssertionError("Missing columns were accepted")
    checks = 3
elif mode == "verify" and task == "render":
    renderer = render()
    assert renderer([("z", 3), ("a", 2)]) == "a: 2\nz: 3\n"
    assert renderer([]) == ""
    checks = 2
elif mode == "assembly":
    rows = parse()((root / "input.csv").read_text(encoding="utf-8"))
    assert render()(rows) == "alpha,one: 2\nbeta: 3\n"
    checks = 1
else:
    raise AssertionError("Unknown fake-worker stage")
emit("finished", checks=checks)
'''


class OfflinePilotTests(unittest.TestCase):
    def setUp(self):
        retained = os.environ.get("PLAYBOOK_OFFLINE_PILOT_ARTIFACTS")
        if retained:
            evidence_root = Path(retained).expanduser().resolve()
            if evidence_root == REPO or REPO in evidence_root.parents:
                raise ValueError("Retained pilot evidence must be outside the source repository")
            evidence_root.mkdir(parents=True, exist_ok=True)
            self.base = Path(tempfile.mkdtemp(prefix="offline-pilot-", dir=evidence_root)).resolve()
        else:
            temporary = tempfile.TemporaryDirectory(prefix="offline-pilot-")
            self.addCleanup(temporary.cleanup)
            self.base = Path(temporary.name).resolve()
        self.commands = []
        self.pending = []
        self.gates = set()
        self.phase = "setup"
        self.report = {
            "schema_version": 1,
            "status": "running",
            "test": "OfflinePilotTests.test_standalone_offline_pilot",
            "test_source_sha256": self.sha(Path(__file__)),
            "invocation": "python3 -I -m unittest discover -s tests -p test_offline_pilot.py -v",
            "package_mode": "official-generator-only",
            "manual_bundle_fallback": False,
            "environment": {"os": platform.system(), "release": platform.release(),
                            "machine": platform.machine(), "python": platform.python_version()},
            "checks": [],
            "paid_model_calls": 0,
            "external_service_calls": 0,
            "human_interventions": 0,
            "skipped_checks": [],
            "existing_regressions_not_rerun_by_this_pilot": [
                "tests/test_work_protocol.py::WorkProtocolTests.test_typed_acceptance_needs_evidence_and_mtime_does_not_invalidate",
                "tests/test_work_protocol.py::WorkProtocolTests.test_integration_head_change_invalidates_current_result_not_historical_dependency",
                "tests/test_work_protocol.py::WorkProtocolTests.test_batch_integration_preserves_source_and_assembly_provenance",
                "tests/test_foundation.py::FoundationTests.test_custom_standard_layout_preserves_existing_git_work_and_uses_templates",
                "tests/test_foundation.py::FoundationTests.test_minimal_apply_is_create_only_truthful_and_idempotent",
                "tests/test_runtime_next.py::RuntimeNextTests.test_pause_failure_is_durably_stopped_and_retains_failure",
                "tests/test_runtime_next.py::RuntimeNextTests.test_handoff_withdrawal_is_idempotent_invalidates_token_and_keeps_evidence",
                "tests/test_runtime_next.py::RuntimeNextTests.test_cancel_stops_only_supervised_attempt_and_retains_reason",
            ],
            "exclusions": [
                "Live model/client execution, authentication, native skill discovery and billing were not exercised.",
                "Independent reviewer identities are cooperating fixture declarations, not proof of model independence.",
                "Merge ancestry and declared membership do not prove arbitrary semantic inclusion.",
                "Dirty-content/mtime, changed assembly target, handoff withdrawal, failed pause and cancellation use the cited focused regressions.",
                "Non-Git/custom-path adoption uses the cited foundation regressions.",
            ],
        }
        self.addCleanup(self.cleanup_pilot)
        (self.base / "commands").mkdir()
        self.signals = self.base / "signals"
        self.signals.mkdir()
        self.inputs = self.base / "inputs"
        self.inputs.mkdir()
        self.project = self.base / "project"
        self.project.mkdir()
        # Ignore host Git routing, signing and template configuration without
        # changing the user's home, installed skills, config files or Git config.
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("GIT_", "PLAYBOOK_"))}
        self.env.update({
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0", "GIT_AUTHOR_NAME": "Offline Pilot",
            "GIT_AUTHOR_EMAIL": "offline-pilot@example.invalid",
            "GIT_COMMITTER_NAME": "Offline Pilot",
            "GIT_COMMITTER_EMAIL": "offline-pilot@example.invalid",
            "LC_ALL": "C",
        })
        self.worker = self.inputs / "fake_worker.py"
        self.worker.write_text(FAKE_WORKER, encoding="utf-8")
        self.sources = self.inputs / "sources.json"
        self.write_json(self.sources, {"parser.py": PARSER_SOURCE, "renderer.py": RENDER_SOURCE})

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def owner(session="pilot-owner", epoch=1):
        return ["--session", session, "--epoch", str(epoch)]

    @staticmethod
    def commit_message(title):
        return title + "\n\nCo-Authored-By: Claude Code <noreply@anthropic.com>"

    def portable(self, value):
        if isinstance(value, dict):
            return {key: self.portable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.portable(item) for item in value]
        if isinstance(value, str):
            return value.replace(str(self.base), "<pilot>").replace(str(REPO), "<source>").replace(sys.executable, "<python>")
        return value

    def start(self, argv, label, expected=0):
        number = len(self.commands) + 1
        stem = "{:03d}-{}".format(number, label)
        stdout = self.base / "commands" / (stem + ".stdout")
        stderr = self.base / "commands" / (stem + ".stderr")
        record = {"number": number, "label": label, "argv": list(map(str, argv)),
                  "cwd": str(self.base), "expected_returncode": expected,
                  "started_ns": time.monotonic_ns(),
                  "stdout": stdout.relative_to(self.base).as_posix(),
                  "stderr": stderr.relative_to(self.base).as_posix()}
        self.commands.append(record)
        with stdout.open("w", encoding="utf-8") as out, stderr.open("w", encoding="utf-8") as err:
            process = subprocess.Popen(record["argv"], cwd=self.base, env=self.env,
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        item = (process, record)
        self.pending.append(item)
        self.write_json(self.base / "commands" / (stem + ".json"), record)
        return item

    def finish(self, item, timeout=40, check=True):
        process, record = item
        if "returncode" not in record:
            record["returncode"] = process.wait(timeout=timeout)
            record["finished_ns"] = time.monotonic_ns()
            record["expected_exit"] = record["returncode"] == record["expected_returncode"]
            stem = "{:03d}-{}".format(record["number"], record["label"])
            self.write_json(self.base / "commands" / (stem + ".json"), record)
        output = (self.base / record["stdout"]).read_text(encoding="utf-8")
        error = (self.base / record["stderr"]).read_text(encoding="utf-8")
        if check:
            self.assertEqual(record["returncode"], record["expected_returncode"],
                             "{}: {}\n{}".format(record["label"], error, output))
        return output, error

    def command(self, argv, label, expected=0):
        return self.finish(self.start(argv, label, expected))

    def cli_argv(self, action, args, project=None):
        return PYTHON + [str(self.runtime), action, "--project", str(project or self.project), *map(str, args)]

    def cli(self, action, *args, project=None, expected=0, label=None):
        out, err = self.command(self.cli_argv(action, args, project), label or action, expected)
        if expected:
            self.assertTrue(err.strip(), "A denied runtime action needs an explanation")
            return err
        return json.loads(out)

    def foundation(self, action, expected=0):
        args = [*PYTHON, str(self.bundle / "scripts" / "playbook-foundation.py"), action,
                "--project", str(self.project), "--profile", "minimal"]
        if action == "apply":
            args += self.owner()
        out, _ = self.command(args, "foundation-" + action, expected)
        return json.loads(out)

    def git(self, *args, project=None):
        out, _ = self.command(["git", "-C", str(project or self.project), *args], "git-" + args[0])
        return out.strip()

    def guard(self, action, *command, project=None, expected=0):
        return self.cli("guard", *self.owner(), "--action", action, "--", *command,
                        project=project, expected=expected, label="guard-" + action)

    def wait_files(self, *names):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if all((self.signals / name).is_file() for name in names):
                return
            time.sleep(0.02)
        self.fail("Fake workers did not reach bounded barrier: " + ", ".join(names))

    def event(self, token, kind):
        return json.loads((self.signals / (token + "." + kind + ".json")).read_text(encoding="utf-8"))

    def worker_command(self, mode, task, token, gate="unused", peer="unused"):
        self.gates.add(gate)
        return [*PYTHON, str(self.worker), mode, task, str(self.signals), token,
                gate, peer, str(self.sources)]

    def run_args(self, task, command, action="dispatch", integration=None):
        args = [*self.owner(), "--action", action, "--task", task]
        if action == "dispatch":
            args += ["--worker", "fake-" + ("render" if task == "T-render" else "parse")]
        else:
            args += ["--reviewer", "fixture-reviewer", "--role", "reviewer"]
        if integration:
            args += ["--integration", integration]
        return args + ["--", *command]

    def task_spec(self, task, paths, resource, worktree):
        name = "CSV parser" if task == "T-parse" else "sorted renderer" if task == "T-render" else "conflicting fixture"
        spec = {"requirements": ["Provide the bounded " + name + " contract"],
                "acceptance": ["Actual fixture inputs produce the declared output in managed verification"],
                "paths": paths, "dependencies": [], "resources": [resource],
                "review": {"independent": True}}
        path = self.inputs / (task + ".json")
        self.write_json(path, spec)
        # A blocked card is launchable after readiness checks, but holds no manual
        # reservation. This isolates exclusive-resource gating from agent limits.
        record = self.cli("task", *self.owner(), "--id", task, "--spec", path,
                          "--state", "blocked", "--worktree", worktree)["task"]
        self.assertEqual(record["spec"], spec)
        return record

    def checked(self, name, **measurements):
        self.report["checks"].append({"name": name, "status": "passed", **measurements})

    def test_standalone_offline_pilot(self):
        try:
            self.pilot()
            self.report["status"] = "passed"
        except Exception as exc:
            self.report.update(status="failed", failed_phase=self.phase,
                               failure={"type": type(exc).__name__, "message": str(exc)})
            raise

    def pilot(self):
        self.phase = "official standalone generation"
        generator = REPO / "scripts" / "build-skills.py"
        generated = self.base / "generated"
        self.report["generator_sha256"] = self.sha(generator)
        self.command([*PYTHON, str(generator), "--output", str(generated)], "build-skills")
        self.command([*PYTHON, str(generator), "--check", "--output", str(generated)], "check-generated")
        self.bundle = self.base / "isolated" / "playbook-start"
        shutil.copytree(generated / "playbook-start", self.bundle)
        shutil.rmtree(generated)
        self.assertEqual(list(self.bundle.parent.iterdir()), [self.bundle])
        available = {path.name for path in (self.bundle / "scripts").iterdir() if path.is_file()}
        self.assertFalse(REQUIRED_SCRIPTS - available,
                         "Official generator omitted required standalone dependencies: " + ", ".join(sorted(REQUIRED_SCRIPTS - available)))
        marker = json.loads((self.bundle / ".playbook-generated.json").read_text(encoding="utf-8"))
        for name in REQUIRED_SCRIPTS:
            path = self.bundle / "scripts" / name
            self.assertEqual(self.sha(path), marker["files"]["scripts/" + name]["sha256"])
        self.runtime = self.bundle / "scripts" / "playbook.py"
        out, _ = self.command([*PYTHON, str(self.runtime), "version"], "bundle-version")
        version = json.loads(out)
        self.assertEqual(version["runtime_api"], 2)
        self.assertEqual(version["missing_files"], [])
        self.assertEqual(Path(version["runtime_path"]).resolve(), self.runtime)
        self.report["runtime"] = {key: version[key] for key in ("package_version", "runtime_api", "release_status", "files")}
        self.report["bundle_manifest_sha256"] = self.sha(self.bundle / ".playbook-generated.json")
        self.checked("official-generated-single-bundle", bundle="playbook-start", siblings_removed=True)

        self.phase = "temporary Git foundations and stored policy"
        self.report["environment"]["git"] = self.command(["git", "--version"], "git-version")[0].strip()
        template = self.base / "empty-git-template"
        template.mkdir()
        self.git("init", "-q", "-b", "main", "--template=" + str(template))
        (self.project / "input.csv").write_text('name,value\nbeta,3\n"alpha,one",2\n', encoding="utf-8")
        (self.project / "preserved.txt").write_bytes(b"Original fixture bytes\n")
        (self.project / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", self.commit_message("Initial offline fixture"))
        discovery = self.cli("discover")
        self.assertFalse(discovery["initialized"])
        self.assertEqual(discovery["requested_project"], str(self.project))
        policy = {
            "runtime_api": 2,
            "workers": [{"id": "fake-parse", "client": "manual"}, {"id": "fake-render", "client": "manual"}],
            "permissions": {"dispatch": "allow", "verify": "allow", "commit": "allow",
                            "worktree-create": "allow", "merge": "ask", "push": "deny", "cleanup": "deny"},
            "limits": {"agents": 2, "heavy_jobs": 1, "timeout_seconds": 30, "max_attempts": 2},
            "review": {"level": "high", "independent": True},
            "git": {"integration_branch": "main", "push_cadence": "never"},
        }
        policy_path = self.inputs / "policy.json"
        self.write_json(policy_path, policy)
        initial = self.cli("init", "--session", "pilot-owner", "--client", "manual",
                           "--goal", "Offline CSV parsing and deterministic reporting", "--config", policy_path)
        stored = json.loads(Path(initial["config_path"]).read_text(encoding="utf-8"))
        self.assertEqual(initial["policy"], stored)
        self.assertEqual(stored["limits"], policy["limits"])
        self.assertEqual(stored["permissions"], policy["permissions"])
        self.report["policy"] = {key: stored[key] for key in ("runtime_api", "limits", "permissions")}
        self.assertTrue(self.foundation("check", expected=1)["readiness"]["can_apply"])
        applied = self.foundation("apply")
        self.assertTrue(applied["readiness"]["foundation_complete"])
        self.assertFalse(applied["readiness"]["dispatch_ready"])
        readme = (self.project / "README.md").read_bytes()
        self.assertEqual(self.foundation("apply")["create"], [])
        self.assertTrue(self.foundation("check")["readiness"]["foundation_complete"])
        self.assertEqual((self.project / "README.md").read_bytes(), readme)
        self.guard("commit", "git", "add", ".")
        self.guard("commit", "git", "commit", "-qm", self.commit_message("Offline fixture policy and foundations"))
        self.checked("stored-policy-and-create-only-foundations", foundation_profile="minimal")

        self.phase = "independent worktrees and exclusive-resource prelaunch denial"
        first, second = self.base / "parse-tree", self.base / "render-tree"
        for branch, tree in (("pilot-parse", first), ("pilot-render", second)):
            self.guard("worktree-create", "git", "worktree", "add", "-qb", branch, str(tree))
        parse_spec = self.task_spec("T-parse", ["parser.py"], "parser-fixture", first)
        render_spec = self.task_spec("T-render", ["renderer.py"], "renderer-fixture", second)
        self.task_spec("T-conflict", ["conflict.txt"], "parser-fixture", self.project)
        for task in ("T-parse", "T-render"):
            self.assertTrue(self.cli("readiness", "--task", task)["ready"])
        implementation = {}
        command = self.worker_command("implement", "parse", "implement-parse", "implementation-release", "implement-render")
        implementation["T-parse"] = self.start(self.cli_argv("run", self.run_args("T-parse", command)), "implement-parse")
        self.wait_files("implement-parse.started.json")
        before_conflict = self.cli("status")["attempts"]
        ready = self.cli("readiness", "--task", "T-conflict")
        self.assertFalse(ready["ready"])
        self.assertIn("resources", " ".join(ready["blockers"]).lower())
        denial = self.cli("run", *self.run_args("T-conflict", self.worker_command("forbidden", "parse", "conflict-child")),
                          expected=2, label="exclusive-resource-denied")
        self.assertIn("resources", denial.lower())
        self.assertFalse((self.signals / "conflict-child.started.json").exists())
        self.assertEqual(self.cli("status")["attempts"], before_conflict)
        self.checked("exclusive-resource-denied-before-child", rejected_task="T-conflict", attempts_created=0)

        self.phase = "two implementation workers at a process barrier"
        command = self.worker_command("implement", "render", "implement-render", "implementation-release", "implement-parse")
        implementation["T-render"] = self.start(self.cli_argv("run", self.run_args("T-render", command)), "implement-render")
        self.wait_files("implement-parse.rendezvous.json", "implement-render.rendezvous.json")
        # Python 3.9 on macOS has process-relative monotonic clocks. Measure the
        # common barrier interval only on this parent clock; child wall times
        # remain diagnostic, never the proof of concurrency or serialization.
        barrier_observed_ns = time.monotonic_ns()
        live = self.cli("status")["attempts"]
        self.assertEqual({item["task"] for item in live if item["execution"] == "running"}, {"T-parse", "T-render"})
        self.assertTrue(all(item[0].poll() is None for item in implementation.values()))
        overlap_ns = time.monotonic_ns() - barrier_observed_ns
        (self.signals / "implementation-release").touch()
        dispatches = {}
        for task, pending in implementation.items():
            result = json.loads(self.finish(pending)[0])
            self.assertFalse(result["accepted"])
            self.assertEqual(result["task"]["state"], "reported")
            dispatches[task] = result["attempt"]
        starts = [self.event("implement-" + name, "started") for name in ("parse", "render")]
        self.assertGreater(overlap_ns, 0)
        self.assertNotEqual(starts[0]["pid"], starts[1]["pid"])
        self.assertEqual({item["cwd"] for item in starts}, {str(first), str(second)})
        for task, event in zip(("T-parse", "T-render"), starts):
            self.assertEqual(dispatches[task]["pid"], event["pid"])
        self.checked("parallel-implementation-barrier", observed_barrier_overlap_ns=overlap_ns,
                     clock="single parent monotonic clock", attempt_ids=[item["id"] for item in dispatches.values()], distinct_worktrees=2)
        for tree, filename, title in ((first, "parser.py", "Offline parser fixture"), (second, "renderer.py", "Offline renderer fixture")):
            self.guard("commit", "git", "add", filename, project=tree)
            self.guard("commit", "git", "commit", "-qm", self.commit_message(title), project=tree)
        denial = self.cli("task", *self.owner(), "--id", "T-parse", "--state", "verified", "--note", "Implementation exited zero", expected=2,
                          label="note-only-acceptance-denied")
        self.assertIn("evidence", denial.lower())

        self.phase = "managed heavy verification serialization"
        command = self.worker_command("verify", "parse", "verify-parse", "verify-parse-release")
        pending = self.start(self.cli_argv("run", self.run_args("T-parse", command, action="verify")), "verify-parse")
        self.wait_files("verify-parse.started.json")
        attempts_before = self.cli("status")["attempts"]
        blocked_command = self.worker_command("forbidden", "render", "heavy-conflict-child")
        denial = self.cli("run", *self.run_args("T-render", blocked_command, action="verify"), expected=2, label="heavy-slot-denied")
        self.assertIn("heavy-job", denial.lower())
        self.assertFalse((self.signals / "heavy-conflict-child.started.json").exists())
        self.assertEqual(self.cli("status")["attempts"], attempts_before)
        (self.signals / "verify-parse-release").touch()
        verifications = {"T-parse": json.loads(self.finish(pending)[0])["attempt"]}
        (self.signals / "verify-render-release").touch()
        command = self.worker_command("verify", "render", "verify-render", "verify-render-release")
        second_verification = self.start(self.cli_argv("run", self.run_args("T-render", command, action="verify")), "verify-render")
        verifications["T-render"] = json.loads(self.finish(second_verification)[0])["attempt"]
        end = pending[1]["finished_ns"]
        start = second_verification[1]["started_ns"]
        self.assertLessEqual(end, start)
        self.checked("heavy-verification-serialized", heavy_jobs=1, overlap_ns=0, gap_ns=start - end,
                     rejected_launch_attempts_created=0, stable_task_ids=["T-parse", "T-render"])

        self.phase = "content-bound evidence to verified"
        evidence = {}
        receipt_bytes = {}
        for task, spec, tree, filename in (("T-parse", parse_spec, first, "parser.py"), ("T-render", render_spec, second, "renderer.py")):
            attempt = verifications[task]
            receipt = self.cli("evidence", *self.owner(), "--task", task, "--attempt", attempt["id"],
                               "--reviewer", "fixture-reviewer", "--role", "reviewer", "--note", "Actual offline acceptance inputs checked")["evidence"]
            self.assertEqual(receipt["spec_hash"], spec["spec_hash"])
            self.assertEqual(receipt["spec_hash"], attempt["spec_hash"])
            self.assertEqual(receipt["content"], attempt["content_before"])
            self.assertEqual(receipt["content"], attempt["content_after"])
            self.assertEqual(receipt["content"]["entries"][filename]["sha256"], self.sha(tree / filename))
            self.assertEqual(receipt["source"]["attempt"], attempt["id"])
            self.assertEqual(receipt["source"]["log_sha256"]["sha256"], self.sha(Path(attempt["log"])))
            self.assertTrue(all(item["applicable"] for item in self.cli("evidence", "--operation", "status", "--task", task)["evidence"]))
            accepted = self.cli("task", *self.owner(), "--id", task, "--state", "verified")["task"]
            self.assertEqual(accepted["accepted_evidence"], receipt["id"])
            evidence[task] = receipt
            receipt_path = Path(initial["runtime_path"]) / "evidence" / (receipt["id"] + ".json")
            receipt_bytes[receipt_path] = receipt_path.read_bytes()
        self.checked("two-tasks-evidence-to-verified", receipts={task: {"id": item["id"], "spec_hash": item["spec_hash"],
                     "content_sha256": item["content"]["sha256"], "source_attempt": item["source"]["attempt"]} for task, item in evidence.items()})

        self.phase = "integration begin, fixture-authorized merges, assembly verification, finish"
        baseline = self.git("rev-parse", "HEAD")
        begun = self.cli("integration", *self.owner(), "--operation", "begin", "--id", "pilot-batch", "--tasks", "T-parse", "T-render",
                         "--target", self.project, "--paths", "input.csv")["integration"]
        self.assertEqual(begun["begin_target"]["head"], baseline)
        self.assertEqual({item["evidence"] for item in begun["participants"]}, {item["id"] for item in evidence.values()})
        self.guard("merge", "git", "merge", "--no-edit", "pilot-parse", expected=2)
        self.assertEqual(self.git("rev-parse", "HEAD"), baseline)
        merge_patch = self.inputs / "fixture-merge-approval.json"
        self.write_json(merge_patch, {"permissions": {"merge": "allow"}})
        configured = self.cli("configure", *self.owner(), "--patch", merge_patch)
        self.assertEqual(configured["policy"]["permissions"]["merge"], "allow")
        expected_policy = json.loads(json.dumps(stored))
        expected_policy["permissions"]["merge"] = "allow"
        self.assertEqual(configured["policy"], expected_policy)
        self.guard("commit", "git", "add", ".orchestrator/config.json")
        self.guard("commit", "git", "commit", "-qm", self.commit_message("Record fixture-only merge approval"))
        for branch in ("pilot-parse", "pilot-render"):
            self.guard("merge", "git", "merge", "--no-ff", "-m", self.commit_message("Integrate offline fixture " + branch), branch)
        (self.signals / "assembly-release").touch()
        command = self.worker_command("assembly", "both", "assembly", "assembly-release")
        assembly = self.cli("run", *self.run_args("assembled-pilot-batch", command, action="verify", integration="pilot-batch"),
                            label="assembly-verify")["attempt"]
        self.assertEqual(assembly["integration"], "pilot-batch")
        self.assertEqual(assembly["content_before"], assembly["content_after"])
        self.assertEqual(assembly["target_before"], assembly["target_after"])
        finished = self.cli("integration", *self.owner(), "--operation", "finish", "--id", "pilot-batch", "--attempt", assembly["id"],
                            "--note", "Declared both fixture participants and checked their assembled CSV report")["integration"]
        self.assertEqual(finished["state"], "passed")
        self.assertEqual(finished["result_content"], assembly["content_after"])
        self.assertEqual(finished["result_target"]["head"], self.git("rev-parse", "HEAD"))
        self.assertTrue(all(fact["source_is_ancestor"] for fact in finished["merge_facts"]))
        self.assertTrue(all(fact["membership"] == "declared" and not fact["semantic_inclusion_proven"] for fact in finished["merge_facts"]))
        self.assertTrue(self.cli("integration", "--operation", "status", "--id", "pilot-batch")["integrations"][0]["applicable"])
        self.checked("fixture-authorized-integration-and-assembly", result_hash=finished["result_hash"],
                     assembly_attempt=assembly["id"], merge_facts=finished["merge_facts"],
                     approval="Explicit test-only policy patch; no live-user approval or external Git action is implied")

        self.phase = "prepared handoff and simulated new owner without repeated work"
        before = self.cli("status")
        attempts = [item["id"] for item in before["attempts"]]
        self.assertEqual(len(attempts), 5)
        self.assertEqual(sum(item["action"] == "dispatch" for item in before["attempts"]), 2)
        handoff_started = time.monotonic_ns()
        handoff = self.cli("handoff", *self.owner(), "--to", "pilot-next")
        self.assertEqual(handoff["mode"], "prepared")
        self.cli("task", *self.owner(), "--id", "outgoing-write", "--state", "reserved", expected=2, label="prepared-owner-write-denied")
        checkpoint = Path(handoff["checkpoint"]["path"])
        recovery = json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))["work_protocol"]
        self.assertEqual(len(recovery["evidence"]), 2)
        self.assertIn("pilot-batch", recovery["integrations"])
        for content in recovery["files"].values():
            self.assertEqual(self.sha(checkpoint / "blobs" / content["sha256"]), content["sha256"])
        taken = self.cli("takeover", "--session", "pilot-next", "--client", "manual", "--handoff", handoff["handoff_id"])
        handoff_elapsed = time.monotonic_ns() - handoff_started
        self.assertEqual(taken["owner"]["session"], "pilot-next")
        self.assertEqual(taken["epoch"], 2)
        self.assertEqual(taken["policy"], before["policy"])
        self.assertEqual(taken["tasks"], before["tasks"])
        self.assertEqual([item["id"] for item in taken["attempts"]], attempts)
        self.assertEqual(taken["integrations"], before["integrations"])
        for path, content in receipt_bytes.items():
            self.assertEqual(path.read_bytes(), content)
        resumed = self.cli("resume", *self.owner("pilot-next", 2))
        self.assertEqual([item["id"] for item in resumed["attempts"]], attempts)
        self.assertTrue(self.cli("integration", "--operation", "status", "--id", "pilot-batch")["integrations"][0]["applicable"])
        self.checked("prepared-handoff-retains-evidence-without-duplicate-work", incoming_epoch=2,
                     elapsed_ns=handoff_elapsed, attempt_ids=attempts, repeated_dispatches=0)

        self.phase = "paused exit and preserved fixtures"
        paused = self.cli("pause", *self.owner("pilot-next", 2))
        self.assertEqual(paused["mode"], "paused")
        self.assertIsNone(paused["checkpoint_failure"])
        final = self.cli("status")
        self.assertEqual(final["mode"], "paused")
        self.assertEqual([item["id"] for item in final["attempts"]], attempts)
        self.assertFalse(any(item["execution"] in ("running", "unknown", "reserved") for item in final["attempts"]))
        for task in ("T-parse", "T-render"):
            self.assertEqual(final["tasks"][task]["state"], "integrated")
        for tree in (self.project, first, second):
            self.assertEqual((tree / "preserved.txt").read_bytes(), b"Original fixture bytes\n")
        self.assertEqual((self.project / "README.md").read_bytes(), readme)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.report["final_state"] = {"mode": final["mode"], "owner": final["owner"]["session"], "epoch": final["epoch"],
                                      "attempts": len(attempts), "dispatches": 2, "verifications": 3,
                                      "participant_states": {task: final["tasks"][task]["state"] for task in ("T-parse", "T-render")}}
        self.checked("paused-exit-and-preserved-fixtures", outstanding_attempts=0)

    def cleanup_pilot(self):
        # Open our gates before waiting. Fake children self-timeout; supervisors
        # are allowed to finish first. Escalation touches only retained Popen
        # objects owned by this test, never a recorded process/group ID.
        for gate in self.gates:
            (self.signals / gate).touch(exist_ok=True)
        cleanup_errors = []
        deadline = time.monotonic() + 35
        for item in self.pending:
            process, record = item
            if "returncode" in record:
                continue
            try:
                self.finish(item, timeout=max(1, deadline - time.monotonic()), check=False)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    self.finish(item, timeout=3, check=False)
                except subprocess.TimeoutExpired:
                    process.kill()
                    self.finish(item, timeout=3, check=False)
                cleanup_errors.append("Supervisor exceeded bounded cleanup: " + record["label"])
        if cleanup_errors:
            self.report.update(status="failed", cleanup_errors=cleanup_errors)
        self.report["check_count"] = len(self.report["checks"])
        self.report["unittest_case_count"] = 1
        self.report["fixture_check_count"] = sum(json.loads(path.read_text(encoding="utf-8"))["checks"]
                                                 for path in self.signals.glob("*.finished.json"))
        self.report["command_count"] = len(self.commands)
        self.report["expected_nonzero_commands"] = sum(record["expected_returncode"] != 0 for record in self.commands)
        self.report["unexpected_exit_commands"] = sum(not record.get("expected_exit", False) for record in self.commands)
        self.report["command_receipts"] = "commands/index.jsonl"
        self.report["worker_events"] = "signals/*.json"
        with (self.base / "commands" / "index.jsonl").open("w", encoding="utf-8") as stream:
            for record in self.commands:
                stream.write(json.dumps(record, sort_keys=True) + "\n")
        self.write_json(self.base / "result.json", self.portable(self.report))
        if cleanup_errors:
            self.fail("; ".join(cleanup_errors))


if __name__ == "__main__":
    unittest.main()
