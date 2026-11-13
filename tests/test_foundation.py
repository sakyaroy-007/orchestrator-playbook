"""Offline foundation contracts: real runtime guards, temporary projects only."""
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "scripts/playbook-foundation.py"
RUNTIME = REPO / "scripts/playbook.py"
PYTHON = [sys.executable, "-I"]


def run(script, *arguments, env=None, cwd=None):
    return subprocess.run(PYTHON + [str(script), *map(str, arguments)], capture_output=True,
                          text=True, timeout=30, env=env, cwd=cwd)


def snapshot(root, include_runtime=True):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if not include_runtime and (relative == ".git" or relative.startswith(".git/") or
                                    relative == ".orchestrator/local" or relative.startswith(".orchestrator/local/")):
            continue
        if path.is_symlink():
            result[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            info = path.stat()
            result[relative] = ("file", path.read_bytes(), stat.S_IMODE(info.st_mode), info.st_mtime_ns)
        else:
            result[relative] = ("directory",)
    return result


def load_helper():
    spec = importlib.util.spec_from_file_location("foundation_fixture", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="playbook-foundation-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.children = []
        self.addCleanup(self.stop_children)

    def stop_children(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)

    def owner(self, session="owner", epoch=1):
        return ["--session", session, "--epoch", str(epoch)]

    def runtime(self, action, *args, project=None, expected=0, runtime=RUNTIME):
        result = run(runtime, action, "--project", project or self.project, *args)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {"error": result.stderr}

    def init(self, paths=None, project=None, runtime=RUNTIME):
        arguments = ["--session", "owner", "--client", "manual", "--goal", "Deliver a checkable local outcome {{PLAN}}"]
        if paths:
            config = self.base / "answers.json"
            config.write_text(json.dumps({"paths": paths}), encoding="utf-8")
            arguments += ["--config", str(config)]
        return self.runtime("init", *arguments, project=project, runtime=runtime)

    def foundation(self, action="check", *args, project=None, helper=HELPER, expected=0, env=None, cwd=None):
        result = run(helper, action, "--project", project or self.project, *args, env=env, cwd=cwd)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["helper"], "playbook-foundation")
        for key in ("create", "retain", "conflict", "readiness"):
            self.assertIn(key, payload)
        self.assertFalse(payload["readiness"]["dispatch_ready"])
        return payload

    def apply(self, *args, **kwargs):
        return self.foundation("apply", *self.owner(), *args, **kwargs)

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.project), *args], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def copy_bundle(self):
        bundle = self.base / "standalone-skill"
        (bundle / "scripts").mkdir(parents=True)
        version = run(RUNTIME, "version")
        self.assertEqual(version.returncode, 0, version.stdout + version.stderr)
        files = json.loads(version.stdout)["files"]
        for name in files:
            shutil.copy2(REPO / "scripts" / name, bundle / "scripts" / name)
        (bundle / "templates").mkdir()
        for name in load_helper().TEMPLATES:
            shutil.copy2(REPO / "templates" / name, bundle / "templates" / name)
        return bundle

    def test_uninitialized_check_does_not_appoint_or_write(self):
        (self.project / "source.txt").write_text("existing\n", encoding="utf-8")
        before = snapshot(self.project)
        report = self.foundation(expected=2)
        self.assertIn("error", report)
        self.assertEqual(before, snapshot(self.project))

    def test_invalid_project_path_still_returns_a_structured_error(self):
        loop = self.base / "loop"
        loop.symlink_to(loop)
        before = snapshot(self.project)
        for action in ("check", "apply"):
            report = self.foundation(action, *self.owner(), project=loop, expected=2)
            self.assertIn("error", report)
            self.assertEqual(snapshot(self.project), before)

    def test_non_git_check_is_read_only_and_uses_normalized_defaults(self):
        initial = self.init({"cards": "work/cards"})
        before = snapshot(self.project)
        report = self.foundation(expected=1)
        self.assertTrue(report["read_only"])
        self.assertTrue(report["readiness"]["can_apply"])
        paths = {item["path"] for item in report["create"]}
        self.assertTrue({"README.md", "docs/plan/README.md", "docs/plan/WORKER.md", "HANDOFF.md", "work/cards/T-001.md"}.issubset(paths))
        self.assertFalse(report["readiness"]["foundation_complete"])
        self.assertEqual(snapshot(self.project), before)
        self.assertEqual(report["owner"], initial["owner"])

    def test_minimal_apply_is_create_only_truthful_and_idempotent(self):
        initial = self.init()
        report = self.apply()
        self.assertTrue(report["readiness"]["foundation_complete"])
        self.assertTrue(all(item["state"] == "created" for item in report["create"]))
        readme = (self.project / "README.md").read_text(encoding="utf-8")
        self.assertIn("Deliver a checkable local outcome {{PLAN}}", readme)
        self.assertIn("Build command: **pending**", readme)
        self.assertIn("Test command: **pending**", readme)
        self.assertIn("non-Git", readme)
        self.assertIn("draft", (self.project / "docs/plan/tasks/T-001.md").read_text())
        self.assertFalse((self.project / "docs/plan/status.md").exists())
        self.assertFalse((self.project / "docs/plan/templates").exists())
        state = self.runtime("status")
        self.assertEqual(state["owner"], initial["owner"])
        self.assertEqual(state["epoch"], initial["epoch"])
        self.assertEqual(state["tasks"], {})
        self.assertEqual(state["attempts"], [])
        before = snapshot(self.project, include_runtime=False)
        again = self.apply()
        self.assertEqual(again["create"], [])
        self.assertEqual(snapshot(self.project, include_runtime=False), before)
        readonly = snapshot(self.project)
        self.foundation()
        self.assertEqual(snapshot(self.project), readonly)
        manifest = json.loads((self.project / ".orchestrator/runtime-manifest.json").read_text())
        self.assertNotIn(str(self.base), json.dumps(manifest))
        self.assertFalse(Path(manifest["source_runtime"]).is_absolute())
        self.assertEqual(manifest["package_version"], report["package_version"])
        self.assertIn("scripts/playbook-foundation.py", manifest["files"])
        self.assertIn("scripts/dispatch.sh", manifest["files"])
        for path, expected in manifest["files"].items():
            actual = self.project / path
            self.assertEqual(hashlib.sha256(actual.read_bytes()).hexdigest(), expected["sha256"])
            self.assertEqual(stat.S_IMODE(actual.stat().st_mode), expected["mode"])

    def test_relative_project_from_parent_can_check_and_apply(self):
        self.init()
        before = snapshot(self.project)
        checked = self.foundation(project=self.project.name, cwd=self.base, expected=1)
        self.assertEqual(checked["requested_project"], str(self.project))
        self.assertEqual(checked["project_root"], str(self.project))
        self.assertEqual(snapshot(self.project), before)
        applied = self.apply(project=self.project.name, cwd=self.base)
        self.assertTrue(applied["readiness"]["foundation_complete"])
        self.assertEqual(applied["requested_project"], checked["requested_project"])
        self.assertEqual(applied["project_root"], checked["project_root"])
        self.assertTrue((self.project / "README.md").is_file())
        self.foundation(project=self.project.name, cwd=self.base)

    def test_file_size_failure_leaves_no_partial_document_and_allows_retry(self):
        self.init()
        before = snapshot(self.project, include_runtime=False)
        limited = ("import resource,runpy,signal,sys; "
                   "signal.signal(signal.SIGXFSZ,signal.SIG_IGN); "
                   "resource.setrlimit(resource.RLIMIT_FSIZE,(128,128)); "
                   "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')")
        # Restrict only the guarded child; the guard must be able to save its own state.
        result = run(RUNTIME, "guard", "--project", self.project, *self.owner(), "--action", "scaffold", "--",
                     *PYTHON, "-c", limited, HELPER, "apply", "--project", self.project, *self.owner(), "--_under-guard")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        reports = [json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")]
        reports = [report for report in reports if report.get("helper") == "playbook-foundation"]
        self.assertEqual(len(reports), 1, result.stdout + result.stderr)
        failed = reports[0]
        self.assertTrue(any(item["path"] == "README.md" and item["reason"] == "creation_failed" and
                            "[Errno %d]" % errno.EFBIG in item["detail"] for item in failed["conflict"]), failed)
        self.assertFalse(failed["readiness"]["foundation_complete"])
        self.assertEqual(snapshot(self.project, include_runtime=False), before)
        checked = self.foundation(expected=1)
        self.assertIn("README.md", {item["path"] for item in checked["create"]})
        self.assertFalse(checked["readiness"]["foundation_complete"])
        repaired = self.apply()
        self.assertTrue(repaired["readiness"]["foundation_complete"])
        self.assertTrue(any(item["path"] == "README.md" and item["state"] == "created" for item in repaired["create"]))
        reference = self.base / "reference" / self.project.name
        reference.mkdir(parents=True)
        self.init(project=reference)
        self.apply(project=reference)
        self.assertEqual((self.project / "README.md").read_bytes(), (reference / "README.md").read_bytes())
        self.foundation()

    def test_custom_standard_layout_preserves_existing_git_work_and_uses_templates(self):
        self.git("init", "-q", "-b", "main")
        (self.project / "README.md").write_text("Original project readme\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text("Existing project rules\n", encoding="utf-8")
        (self.project / "source.txt").write_text("Existing source\n", encoding="utf-8")
        paths = {"plan": "planning/roadmap.md", "worker": "contributor/rules.md",
                 "handoff": "continuity/next.md", "cards": "tickets/drafts"}
        self.init(paths)
        before = snapshot(self.project, include_runtime=False)
        report = self.apply("--profile", "standard")
        after = snapshot(self.project, include_runtime=False)
        for name in ("README.md", "AGENTS.md", "source.txt", ".orchestrator/config.json"):
            self.assertEqual(after[name], before[name])
        for path in (paths["plan"], paths["worker"], paths["handoff"], "tickets/drafts/T-001.md",
                     "planning/status.md", "planning/tasks.md", "planning/templates/ADR.md", "planning/templates/review.md"):
            self.assertTrue((self.project / path).is_file(), path)
        self.assertFalse((self.project / "docs/plan").exists())
        for name in ("ADR.md", "review.md"):
            self.assertIn((REPO / "templates" / name).read_bytes(), (self.project / "planning/templates" / name).read_bytes())
        worker = (self.project / paths["worker"]).read_text()
        self.assertIn("tickets/drafts", worker)
        self.assertIn("planning/roadmap.md", worker)
        self.assertNotIn("docs/plan", worker)
        self.assertIn("AGENTS.md", {entry["path"] for entry in report["retain"]})

    def test_existing_documents_are_retained_and_only_missing_files_are_repaired(self):
        self.init()
        for name in ("README.md", "docs/plan/README.md", "docs/plan/WORKER.md", "HANDOFF.md", "docs/plan/tasks/T-001.md"):
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("User-authored " + name + "\n", encoding="utf-8")
        before = snapshot(self.project, include_runtime=False)
        report = self.apply()
        after = snapshot(self.project, include_runtime=False)
        for path, value in before.items():
            self.assertEqual(after[path], value)
        self.assertIn("README.md", {item["path"] for item in report["retain"]})
        self.assertFalse(any(item["kind"] == "task_draft" for item in report["create"]))

    def test_different_runtime_and_manifest_are_reported_without_replacement(self):
        self.init()
        scripts = self.project / "scripts"
        scripts.mkdir()
        existing = scripts / "wt.sh"
        existing.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        existing.chmod(0o755)
        before = existing.read_bytes()
        report = self.apply(expected=1)
        self.assertEqual(existing.read_bytes(), before)
        self.assertTrue(any(item["path"] == "scripts/wt.sh" and item["reason"] == "different_copy" for item in report["conflict"]))
        self.assertFalse(report["readiness"]["foundation_complete"])
        manifest_path = self.project / ".orchestrator/runtime-manifest.json"
        manifest_path.write_text('{"old": true}\n', encoding="utf-8")
        manifest = manifest_path.read_bytes()
        self.apply(expected=1)
        self.assertEqual(manifest_path.read_bytes(), manifest)
        self.assertTrue((self.project / "README.md").exists())

    def test_symlink_and_non_directory_targets_abort_the_whole_preflight(self):
        for case in ("leaf", "dangling", "parent", "directory", "parent_file"):
            with self.subTest(case=case):
                project = self.base / case
                project.mkdir()
                self.init(project=project)
                outside = self.base / (case + "-outside")
                outside.mkdir()
                if case == "leaf":
                    (outside / "keep.md").write_text("keep\n", encoding="utf-8")
                    (project / "README.md").symlink_to(outside / "keep.md")
                elif case == "dangling":
                    (project / "HANDOFF.md").symlink_to(outside / "missing.md")
                elif case == "parent":
                    (project / "docs").symlink_to(outside, target_is_directory=True)
                elif case == "directory":
                    (project / "HANDOFF.md").mkdir()
                else:
                    (project / "scripts").write_text("not a directory\n", encoding="utf-8")
                before = snapshot(project, include_runtime=False)
                external = snapshot(outside)
                report = self.apply(project=project, expected=2)
                self.assertTrue(any(item["blocking"] for item in report["conflict"]))
                self.assertFalse(any(item["state"] == "created" for item in report["create"]))
                self.assertEqual(snapshot(project, include_runtime=False), before)
                self.assertEqual(snapshot(outside), external)

    def test_colliding_and_reserved_custom_paths_fail_before_creating_anything(self):
        variants = ({"plan": "README.md"}, {"plan": "readme.md"}, {"plan": "planning", "worker": "planning/rules.md"},
                    {"worker": ".orchestrator/config.json"}, {"cards": ".git/cards"}, {"plan": "docs/./plan/WORKER.md"})
        for index, paths in enumerate(variants):
            with self.subTest(paths=paths):
                project = self.base / ("collision-%d" % index)
                project.mkdir()
                self.init(paths, project=project)
                before = snapshot(project, include_runtime=False)
                report = self.apply(project=project, expected=2)
                self.assertTrue(any(item["reason"] in ("target_collision", "reserved_path") for item in report["conflict"]))
                self.assertEqual(snapshot(project, include_runtime=False), before)

    def test_current_owner_is_required_even_with_an_inherited_guard_marker(self):
        self.init()
        environment = dict(os.environ, PLAYBOOK_GUARDED="1", PLAYBOOK_PROJECT=str(self.project))
        before = snapshot(self.project)
        rejected = self.foundation("apply", *self.owner("other"), expected=2, env=environment)
        self.assertIn("Ownership conflict", rejected["error"])
        self.assertEqual(snapshot(self.project), before)
        self.foundation("apply", *self.owner(epoch=2), expected=2)
        self.assertEqual(snapshot(self.project), before)
        self.foundation("apply", expected=2)
        self.assertEqual(snapshot(self.project), before)
        self.runtime("pause", *self.owner())
        paused = snapshot(self.project)
        self.apply(expected=2)
        self.assertEqual(snapshot(self.project), paused)
        self.assertFalse((self.project / "README.md").exists())

    def test_subdirectory_request_does_not_silently_scaffold_enclosing_git_root(self):
        self.git("init", "-q", "-b", "main")
        self.init()
        nested = self.project / "nested"
        nested.mkdir()
        before = snapshot(self.project, include_runtime=False)
        for requested, cwd in ((nested, None), (nested.relative_to(self.base), self.base)):
            with self.subTest(project=requested):
                report = self.apply(project=requested, cwd=cwd, expected=2)
                self.assertEqual(report["requested_project"], str(nested))
                self.assertTrue(any(item["reason"] == "project_root_mismatch" for item in report["conflict"]))
                self.assertEqual(snapshot(self.project, include_runtime=False), before)

    def test_isolated_skill_and_project_copies_work_with_python_isolation(self):
        bundle = self.copy_bundle()
        helper, runtime = bundle / "scripts/playbook-foundation.py", bundle / "scripts/playbook.py"
        self.init(runtime=runtime)
        poison = self.base / "unrelated-cwd"
        poison.mkdir()
        (poison / "json.py").write_text("raise RuntimeError('cwd import escaped isolation')\n", encoding="utf-8")
        self.apply(helper=helper, cwd=poison)
        shutil.rmtree(bundle)
        project_runtime = self.project / "scripts/playbook.py"
        project_helper = self.project / "scripts/playbook-foundation.py"
        status = self.runtime("status", runtime=project_runtime)
        self.assertEqual(status["owner"]["session"], "owner")
        self.foundation(helper=project_helper, cwd=poison)
        self.apply("--profile", "standard", helper=project_helper, cwd=poison)
        self.assertTrue((self.project / "docs/plan/templates/review.md").exists())

    def test_manifest_is_recognized_by_runtime_diagnostics(self):
        self.init()
        self.apply()
        before = snapshot(self.project)
        diagnosis = self.runtime("doctor")["runtime_diagnostics"]
        self.assertEqual(snapshot(self.project), before)
        self.assertEqual(diagnosis["manifest"]["status"], "recorded")
        manifest = json.loads((self.project / ".orchestrator/runtime-manifest.json").read_text())
        copies = {item["path"]: item for item in diagnosis["project_copies"]}
        for path in manifest["files"]:
            self.assertEqual(copies[path]["status"], "matching", path)
            self.assertEqual(copies[path]["provenance"], "recorded", path)

    def test_missing_required_source_fails_without_partial_foundations(self):
        bundle = self.copy_bundle()
        runtime = bundle / "scripts/playbook.py"
        self.init(runtime=runtime)
        (bundle / "scripts/wt.sh").unlink()
        before = snapshot(self.project, include_runtime=False)
        report = self.apply(helper=bundle / "scripts/playbook-foundation.py", expected=2)
        self.assertIn("error", report)
        self.assertEqual(snapshot(self.project, include_runtime=False), before)

    def test_two_applies_serialize_and_preserve_a_single_foundation(self):
        self.init()
        command = PYTHON + [str(HELPER), "apply", "--project", str(self.project), *self.owner()]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        self.children.extend(processes)
        reports = []
        for process in processes:
            out, err = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, out + err)
            reports.append(json.loads(out))
        self.assertEqual(sum(bool(report["create"]) for report in reports), 1)
        self.foundation()

    def test_preflight_happens_after_guard_lock_is_acquired(self):
        self.init()
        ready, release = self.base / "locked", self.base / "release"
        outside = self.base / "outside"
        outside.mkdir()
        command = PYTHON + ["-c", "import pathlib,sys,time; ready,release,target,outside=map(pathlib.Path,sys.argv[1:]); "
                           "ready.write_text('locked');\nwhile not release.exists(): time.sleep(.01)\n"
                           "target.symlink_to(outside,target_is_directory=True)",
                           str(ready), str(release), str(self.project / "docs"), str(outside)]
        holder = subprocess.Popen(PYTHON + [str(RUNTIME), "guard", "--project", str(self.project), *self.owner(),
                                           "--action", "scaffold", "--", *command],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.children.append(holder)
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(ready.exists(), "Real guard did not reach synchronization point")
        apply = subprocess.Popen(PYTHON + [str(HELPER), "apply", "--project", str(self.project), *self.owner()],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.children.append(apply)
        release.write_text("release", encoding="utf-8")
        out, err = holder.communicate(timeout=20)
        self.assertEqual(holder.returncode, 0, out + err)
        out, err = apply.communicate(timeout=20)
        self.assertEqual(apply.returncode, 2, out + err)
        report = json.loads(out)
        self.assertTrue(any(item["reason"] == "unsafe_parent" for item in report["conflict"]))
        self.assertFalse((self.project / "README.md").exists())
        self.assertEqual(snapshot(outside), {})


class ExclusiveCreationTests(unittest.TestCase):
    def test_short_writes_publish_only_complete_content(self):
        helper = load_helper()
        with tempfile.TemporaryDirectory(prefix="foundation-short-write-") as temporary:
            root = Path(temporary)
            root_fd = os.open(str(root), helper.directory_flags())
            self.addCleanup(os.close, root_fd)
            data = bytes(range(256)) * 3 + b"complete\n"
            item = helper.target("docs/plan.md", "plan", data, mode=0o640)
            destination = root / item["path"]
            original_write = os.write

            def short_write(fd, remaining):
                self.assertFalse(destination.exists(), "The final path exposed unfinished content")
                return original_write(fd, remaining[:37])

            with mock.patch.object(helper.os, "write", side_effect=short_write):
                helper.create_exclusive(root_fd, item)
            self.assertEqual(destination.read_bytes(), data)
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o640)
            self.assertEqual(set(root.rglob("*")), {root / "docs", destination})

    def test_file_sync_failure_does_not_publish_and_can_be_retried(self):
        helper = load_helper()
        with tempfile.TemporaryDirectory(prefix="foundation-sync-failure-") as temporary:
            root = Path(temporary)
            root_fd = os.open(str(root), helper.directory_flags())
            self.addCleanup(os.close, root_fd)
            item = helper.target("README.md", "readme", b"complete scaffold\n" * 100)
            with mock.patch.object(helper.os, "fsync", side_effect=OSError(errno.EIO, "Injected file sync failure")):
                with self.assertRaises(OSError) as failure:
                    helper.create_exclusive(root_fd, item)
            self.assertEqual(failure.exception.errno, errno.EIO)
            self.assertEqual(snapshot(root), {})
            helper.create_exclusive(root_fd, item)
            self.assertEqual((root / "README.md").read_bytes(), item["data"])
            self.assertEqual({path.name for path in root.iterdir()}, {"README.md"})

    def test_late_file_creation_is_never_overwritten(self):
        helper = load_helper()
        for kind in ("file", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="foundation-race-") as temporary:
                root = Path(temporary)
                root_fd = os.open(str(root), helper.directory_flags())
                self.addCleanup(os.close, root_fd)
                item = helper.target("README.md", "readme", b"new scaffold\n")
                destination = root / "README.md"
                author = root / "author.md"
                author.write_bytes(b"concurrent author\n")
                original_link = os.link

                def concurrent_link(source, target, *args, **kwargs):
                    if target == "README.md":
                        if kind == "file":
                            destination.write_bytes(author.read_bytes())
                        else:
                            destination.symlink_to(author)
                    return original_link(source, target, *args, **kwargs)

                with mock.patch.object(helper.os, "link", side_effect=concurrent_link):
                    with self.assertRaises(FileExistsError):
                        helper.create_exclusive(root_fd, item)
                self.assertEqual(destination.is_symlink(), kind == "symlink")
                self.assertEqual(destination.read_bytes(), b"concurrent author\n")
                self.assertEqual(author.read_bytes(), b"concurrent author\n")
                self.assertEqual({path.name for path in root.iterdir()}, {"README.md", "author.md"})

    def test_path_traversal_is_rejected_before_a_target_is_planned(self):
        helper = load_helper()
        for value in ("../outside.md", "/outside.md", "docs/../../outside.md", ".", "", "docs\\outside.md"):
            with self.subTest(value=value), self.assertRaises(helper.Failure):
                helper.target(value, "plan", b"draft")

    def test_source_hash_drift_is_not_copied_as_a_matching_runtime(self):
        helper = load_helper()
        status = {"project_root": "/project", "git": False, "config_revision": 1,
                  "policy": {"goal": "A useful outcome", "paths": {"plan": "docs/plan.md", "worker": "docs/worker.md",
                                                                       "cards": "cards", "handoff": "HANDOFF.md"}}}
        version = {"package_version": "3.0.0", "runtime_api": 2,
                   "files": {"playbook.py": "0" * 64, "wt.sh": "0" * 64}}
        with mock.patch.object(helper, "runtime_json", return_value=version):
            with self.assertRaisesRegex(helper.Failure, "source changed or differs"):
                helper.make_plan(status, "minimal")


if __name__ == "__main__":
    unittest.main()
