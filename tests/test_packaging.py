"""Packaging contracts. Run: python3 -I -m unittest discover -s tests -p test_packaging.py.

Fixtures exercise failure paths without clients, network or generated repo output.
Repository integration builds only under a temporary output root.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent
BUILDER = REPO / "scripts/build-skills.py"
NAMES = ("playbook", "playbook-start", "playbook-resume", "playbook-handoff", "playbook-takeover")
SCRIPTS = (
    "playbook.py", "playbook_work.py", "playbook-foundation.py", "policy-dispatch.py",
    "init-plan.sh", "wt.sh", "dispatch.sh",
)
SHELL_SCRIPTS = ("init-plan.sh", "wt.sh", "dispatch.sh")
REFERENCES = (
    "bootstrap", "cards", "configuration", "dispatch", "handoff-files", "lessons",
    "lifecycle", "review", "stakeholder", "work-protocol",
)
TEMPLATES = (
    "ADR-001.md", "ADR.md", "AGENTS-snippet.md", "HANDOFF.md", "PLAYBOOK.md", "PROJECT-README.md", "TEAM.md", "WORKER.md",
    "changes-README.md", "external.md", "plan-README.md", "questions.md", "review.md", "spike-card.md",
    "status.md", "task-card.md", "tasks.md",
)
MARKER = ".playbook-generated.json"


def run(*args, cwd=None, env=None):
    return subprocess.run(args, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)


def snapshot(root):
    """Detect content, modes, symlinks and directory mutations (not access time)."""
    result = {}
    if root.exists():
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                result[rel] = ("link", os.readlink(path))
            elif path.is_file():
                result[rel] = ("file", path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            else:
                result[rel] = ("dir",)
    return result


class PackagingFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="playbook-packaging-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.output = self.root / "output"
        for name in ("scripts", "skill-src", "references", "templates"):
            (self.source / name).mkdir(parents=True)
        shutil.copyfile(BUILDER, self.source / "scripts/build-skills.py")
        for name in NAMES:
            for suffix, language in ((".md", "English"), (".zh.md", "中文")):
                (self.source / "skill-src" / (name + suffix)).write_text(
                    "---\nname: " + name + "\ndescription: Explicit project action\ndisable-model-invocation: true\n---\n"
                    "# " + name + "\n" + language + "\nRead references/lifecycle.md and templates/WORKER.md.\n",
                    encoding="utf-8",
                )
        for name in REFERENCES:
            for suffix in (".md", ".zh.md"):
                (self.source / "references" / (name + suffix)).write_text("# " + name + suffix + "\n", encoding="utf-8")
        for name in TEMPLATES:
            (self.source / "templates" / name).write_text("# " + name + "\n", encoding="utf-8")
        (self.source / "scripts/playbook_work.py").write_text('VALUE = "standalone"\n', encoding="utf-8")
        (self.source / "scripts/playbook.py").write_text(
            'import importlib.util, json\nfrom pathlib import Path\n'
            'root = Path(__file__).resolve().parent.parent\n'
            'spec = importlib.util.spec_from_file_location("work", root / "scripts/playbook_work.py")\n'
            'module = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n'
            'assert (root / "references/lifecycle.md").is_file()\n'
            'assert (root / "references/work-protocol.md").is_file()\n'
            'assert (root / "references/work-protocol.zh.md").is_file()\n'
            'assert (root / "templates/WORKER.md").is_file()\n'
            'assert (root / "templates/PROJECT-README.md").is_file()\n'
            'print(json.dumps({"fixture": module.VALUE}))\n', encoding="utf-8",
        )
        for name in ("policy-dispatch.py", "playbook-foundation.py"):
            (self.source / "scripts" / name).write_text(
                'from pathlib import Path\nimport subprocess, sys\n'
                'raise SystemExit(subprocess.call([sys.executable, "-I", str(Path(__file__).with_name("playbook.py"))]))\n',
                encoding="utf-8",
            )
        for name in SHELL_SCRIPTS:
            (self.source / "scripts" / name).write_text('#!/bin/sh\nprintf "fixture shell ready\\n"\n', encoding="utf-8")
        # Development inputs must never leak into each independently copied skill.
        (self.source / ".git").mkdir()
        (self.source / ".git/private-data").write_text("not a runtime resource", encoding="utf-8")
        (self.source / "scripts/selftest.sh").write_text("not a runtime resource", encoding="utf-8")
        (self.source / "scripts/check-manifests.py").write_text("not a runtime resource", encoding="utf-8")
        (self.source / ".github/workflows").mkdir(parents=True)
        (self.source / ".github/workflows/ci.yml").write_text("not a runtime resource", encoding="utf-8")
        (self.source / "tests").mkdir()
        (self.source / "tests/test_packaging.py").write_text("not a runtime resource", encoding="utf-8")

    def build(self, *args, expected=0):
        result = run(sys.executable, "-I", str(self.source / "scripts/build-skills.py"), "--output", str(self.output), *args, cwd=self.root)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_five_explicit_standalone_entries_and_resource_allowlist(self):
        self.build()
        self.assertEqual({p.name for p in self.output.iterdir()}, set(NAMES))
        for name in NAMES:
            bundle = self.output / name
            for filename in ("SKILL.md", "SKILL.zh.md"):
                content = (bundle / filename).read_text(encoding="utf-8")
                self.assertIn("name: " + name + "\n", content)
                self.assertIn("disable-model-invocation: true\n", content)
                self.assertIn("Generated from skill-src/", content)
            self.assertIn("allow_implicit_invocation: false", (bundle / "agents/openai.yaml").read_text())
            self.assertEqual({p.name for p in (bundle / "scripts").iterdir()}, set(SCRIPTS))
            for category in ("references", "templates"):
                self.assertEqual(snapshot(self.source / category), snapshot(bundle / category))
            for script in SCRIPTS:
                self.assertEqual((bundle / "scripts" / script).read_bytes(), (self.source / "scripts" / script).read_bytes())
                self.assertTrue(os.access(bundle / "scripts" / script, os.X_OK))
            marker = json.loads((bundle / MARKER).read_text())
            files = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file() and p.name != MARKER}
            self.assertEqual(set(marker["files"]), files)
            self.assertNotIn(str(self.root), (bundle / MARKER).read_text())
            for rel, saved in marker["files"].items():
                self.assertEqual(hashlib.sha256((bundle / rel).read_bytes()).hexdigest(), saved["sha256"])

    def test_check_is_read_only_and_rebuild_updates_changed_sources(self):
        self.build()
        before = snapshot(self.output)
        self.build("--check")
        self.assertEqual(snapshot(self.output), before)
        (self.source / "references/lifecycle.md").write_text("# Changed contract\n", encoding="utf-8")
        self.build("--check", expected=1)
        self.assertEqual(snapshot(self.output), before)
        self.build()
        self.build("--check")
        self.assertEqual((self.output / "playbook/references/lifecycle.md").read_text(), "# Changed contract\n")
        before = snapshot(self.output)
        self.build()
        self.assertEqual(snapshot(self.output), before)

    def test_check_missing_output_does_not_create_it(self):
        self.build("--check", expected=1)
        self.assertFalse(self.output.exists())

    def test_missing_required_sources_fail_before_writing(self):
        paths = ["scripts/" + name for name in SCRIPTS] + [
            "skill-src/playbook-takeover.zh.md", "references/lifecycle.md", "templates/WORKER.md",
            "references/work-protocol.md", "references/work-protocol.zh.md", "templates/PROJECT-README.md",
        ]
        for rel in paths:
            with self.subTest(source=rel):
                path = self.source / rel
                content = path.read_bytes()
                path.unlink()
                result = self.build(expected=2)
                self.assertIn("missing required", result.stderr)
                self.assertFalse(self.output.exists())
                path.write_bytes(content)

    def test_implicit_or_wrong_name_sources_are_rejected(self):
        path = self.source / "skill-src/playbook-start.md"
        original = path.read_text()
        for replacement in (
            original.replace("disable-model-invocation: true", "disable-model-invocation: false"),
            original.replace("name: playbook-start", "name: some-other-skill"),
            original.replace("---\n", "", 1),
        ):
            path.write_text(replacement, encoding="utf-8")
            self.build(expected=2)
            self.assertFalse(self.output.exists())

    def test_unmarked_skill_and_late_conflict_leave_entire_output_unchanged(self):
        # The last skill conflicts; the first four must not be created either.
        directory = self.output / "playbook-takeover"
        directory.mkdir(parents=True)
        (directory / "personal.txt").write_text("keep me", encoding="utf-8")
        before = snapshot(self.output)
        self.assertIn("unmarked", self.build(expected=2).stderr)
        self.assertEqual(snapshot(self.output), before)

    def test_unknown_siblings_and_user_files_are_preserved(self):
        self.output.mkdir()
        (self.output / "other-skill").mkdir()
        (self.output / "other-skill/SKILL.md").write_text("user skill", encoding="utf-8")
        self.build()
        note = self.output / "playbook/references/my-notes.md"
        note.write_text("personal addition", encoding="utf-8")
        (self.source / "references/lifecycle.md").write_text("# New version", encoding="utf-8")
        self.build()
        self.build("--check")
        self.assertEqual(note.read_text(), "personal addition")
        self.assertEqual((self.output / "other-skill/SKILL.md").read_text(), "user skill")

    def test_local_edits_are_reported_and_never_overwritten(self):
        self.build()
        path = self.output / "playbook-takeover/scripts/playbook.py"
        path.write_text("local work\n", encoding="utf-8")
        before = snapshot(self.output)
        self.build("--check", expected=1)
        self.assertEqual(snapshot(self.output), before)
        self.assertIn("locally modified", self.build(expected=2).stderr)
        self.assertEqual(snapshot(self.output), before)

    def test_new_source_cannot_overwrite_untracked_destination(self):
        self.build()
        (self.output / "playbook/references/addition.md").write_text("user content", encoding="utf-8")
        (self.source / "references/addition.md").write_text("new source", encoding="utf-8")
        before = snapshot(self.output)
        self.assertIn("untracked output", self.build(expected=2).stderr)
        self.assertEqual(snapshot(self.output), before)

    def test_only_unmodified_obsolete_generated_files_are_removed(self):
        source = self.source / "references/optional.md"
        source.write_text("old optional reference", encoding="utf-8")
        self.build()
        extra = self.output / "playbook/references/personal.md"
        extra.write_text("keep", encoding="utf-8")
        source.unlink()
        self.build("--check", expected=1)
        self.build()
        self.build("--check")
        for name in NAMES:
            self.assertFalse((self.output / name / "references/optional.md").exists())
        self.assertEqual(extra.read_text(), "keep")

    def test_modified_obsolete_generated_files_are_preserved(self):
        source = self.source / "references/optional.md"
        source.write_text("original", encoding="utf-8")
        self.build()
        target = self.output / "playbook/references/optional.md"
        target.write_text("local addition", encoding="utf-8")
        source.unlink()
        before = snapshot(self.output)
        self.build(expected=2)
        self.assertEqual(snapshot(self.output), before)

    def test_destination_symlinks_and_symlink_ancestors_are_rejected(self):
        victim = self.root / "victim"
        victim.mkdir()
        (victim / "sentinel").write_text("do not touch", encoding="utf-8")
        before = snapshot(victim)
        self.output.symlink_to(victim, target_is_directory=True)
        self.assertIn("symlink", self.build(expected=2).stderr)
        self.assertEqual(snapshot(victim), before)
        self.output.unlink()
        ancestor = self.root / "alias"
        ancestor.symlink_to(victim, target_is_directory=True)
        self.output = ancestor / "new-output"
        self.assertIn("symlink", self.build(expected=2).stderr)
        self.assertEqual(snapshot(victim), before)

    def test_generated_file_symlink_never_changes_external_target(self):
        self.build()
        path = self.output / "playbook/scripts/playbook.py"
        outside = self.root / "external.py"
        outside.write_text("user code", encoding="utf-8")
        path.unlink()
        path.symlink_to(outside)
        before = snapshot(self.output)
        for args in ((), ("--check",)):
            self.assertIn("symlink", self.build(*args, expected=2).stderr)
            self.assertEqual(outside.read_text(), "user code")
            self.assertEqual(snapshot(self.output), before)

    def test_source_symlink_is_not_packaged(self):
        path = self.source / "scripts/playbook.py"
        outside = self.root / "private.py"
        outside.write_text("private", encoding="utf-8")
        path.unlink()
        path.symlink_to(outside)
        self.assertIn("symlink", self.build(expected=2).stderr)
        self.assertFalse(self.output.exists())

    def test_dangling_symlinks_and_file_directory_collisions_fail(self):
        self.build()
        path = self.output / "playbook-takeover/templates/WORKER.md"
        path.unlink()
        path.symlink_to(self.root / "missing")
        before = snapshot(self.output)
        self.build(expected=2)
        self.assertEqual(snapshot(self.output), before)
        path.unlink()
        path.mkdir()
        before = snapshot(self.output)
        self.build(expected=2)
        self.assertEqual(snapshot(self.output), before)

    def test_corrupt_or_path_traversing_markers_fail_without_changes(self):
        self.build()
        path = self.output / "playbook" / MARKER
        original = json.loads(path.read_text())
        bad = json.loads(json.dumps(original))
        bad["files"]["../../outside"] = {"sha256": "0" * 64, "mode": 420}
        for content in ("not json", json.dumps(bad), json.dumps({"generator": "someone else"})):
            path.write_text(content, encoding="utf-8")
            before = snapshot(self.output)
            self.build(expected=2)
            self.assertEqual(snapshot(self.output), before)

    def test_output_inside_inputs_is_rejected(self):
        self.output = self.source / "references/bundles"
        self.assertIn("source inputs", self.build(expected=2).stderr)
        self.assertFalse(self.output.exists())

    def test_isolated_copy_runs_without_original_or_siblings(self):
        self.build()
        isolated = self.root / "only-this-skill"
        shutil.copytree(self.output / "playbook-takeover", isolated)
        shutil.rmtree(self.source)
        shutil.rmtree(self.output)
        # A hostile cwd module must not be imported by Python's isolated mode.
        (self.root / "json.py").write_text('raise RuntimeError("cwd imported")\n', encoding="utf-8")
        result = run(sys.executable, "-I", str(isolated / "scripts/playbook.py"), cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"fixture": "standalone"})
        for name in ("policy-dispatch.py", "playbook-foundation.py"):
            result = run(sys.executable, "-I", str(isolated / "scripts" / name), cwd=self.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"fixture": "standalone"})
        for name in SHELL_SCRIPTS:
            result = run("sh", str(isolated / "scripts" / name), cwd=self.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("fixture shell ready", result.stdout)


class RepositoryPackagingTests(unittest.TestCase):
    def test_canonical_package_in_temporary_output(self):
        """Each real bundle and its project copy work after their sources disappear."""
        required = [REPO / "scripts" / name for name in SCRIPTS] + [
            REPO / "skill-src" / (name + suffix) for name in NAMES for suffix in (".md", ".zh.md")
        ]
        missing = [p.relative_to(REPO).as_posix() for p in required if not p.is_file()]
        self.assertFalse(missing, "missing canonical inputs: " + ", ".join(missing))
        with tempfile.TemporaryDirectory(prefix="playbook-real-bundle-") as temporary:
            root = Path(temporary).resolve()
            source, output = root / "source", root / "built"
            (source / "scripts").mkdir(parents=True)
            for name in (*SCRIPTS, "build-skills.py"):
                shutil.copy2(REPO / "scripts" / name, source / "scripts" / name)
            for directory in ("skill-src", "references", "templates"):
                shutil.copytree(REPO / directory, source / directory)
            for arguments in ((), ("--check",)):
                result = run(sys.executable, "-I", str(source / "scripts/build-skills.py"),
                             "--output", str(output), *arguments, cwd=root)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            bundles = {name: snapshot(output / name) for name in NAMES}
            shutil.rmtree(source)
            shutil.rmtree(output)
            for name in NAMES:
                with self.subTest(skill=name), tempfile.TemporaryDirectory(dir=root, prefix=name + "-") as case:
                    case_root = Path(case)
                    isolated = case_root / "only-skill"
                    for relative, entry in bundles[name].items():
                        path = isolated / relative
                        if entry[0] == "dir":
                            path.mkdir(parents=True, exist_ok=True)
                        else:
                            self.assertEqual(entry[0], "file", relative)
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_bytes(entry[1])
                            path.chmod(entry[2])
                    self.exercise_standalone_bundle(isolated, case_root)

    def exercise_standalone_bundle(self, isolated, root):
        self.assertEqual({path.name for path in (isolated / "scripts").iterdir()}, set(SCRIPTS))
        for path in isolated.rglob("*"):
            if path.is_file():
                self.assertNotIn(str(REPO).encode(), path.read_bytes(), path.as_posix())
        project, unrelated = root / "project", root / "unrelated-cwd"
        project.mkdir()
        unrelated.mkdir()
        for name in ("json.py", "playbook_work.py"):
            (unrelated / name).write_text('raise RuntimeError("cwd escaped isolation")\n', encoding="utf-8")
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("PLAYBOOK_", "DISPATCH_"))}
        environment["PYTHONPATH"] = str(unrelated)
        runtime = isolated / "scripts/playbook.py"

        def cli(action, *arguments):
            result = run(sys.executable, "-I", str(runtime), action, "--project", str(project),
                         *map(str, arguments), cwd=unrelated, env=environment)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

        result = run(sys.executable, "-I", str(runtime), "version", cwd=unrelated, env=environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        version = json.loads(result.stdout)
        self.assertEqual(version["missing_files"], [])
        self.assertEqual(set(version["files"]), set(SCRIPTS) - {"init-plan.sh"})
        self.assertEqual(version["runtime_path"], str(runtime))
        for name, digest in version["files"].items():
            self.assertEqual(hashlib.sha256((isolated / "scripts" / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(cli("discover")["requested_project"], str(project))
        self.assertFalse((project / ".orchestrator").exists(), "discover must stay read-only")
        for command in ((sys.executable, "-I", str(runtime), "--help"),
                        ("bash", str(isolated / "scripts/init-plan.sh"), "--help"),
                        ("git", "init", "--quiet", str(project))):
            result = run(*command, cwd=unrelated, env=environment)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = run("bash", str(isolated / "scripts/wt.sh"), "ls", cwd=project, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(project), result.stdout)
        fake = root / "fake-worker"
        fake.write_text('#!/bin/sh\nprintf "bundle fake worker ran\\n"\n', encoding="utf-8")
        fake.chmod(0o755)
        environment["DISPATCH_BIN_CLAUDE"] = str(fake)
        legacy_log = root / "legacy.log"
        result = run("bash", str(isolated / "scripts/dispatch.sh"), "claude", str(project), "fixture only",
                     "-t", "5", "-q", "-l", str(legacy_log), cwd=unrelated, env=environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("bundle fake worker ran", legacy_log.read_text())
        config = root / "answers.json"
        config.write_text(json.dumps({"workers": [{"id": "fake", "client": "claude"}],
                                      "permissions": {"dispatch": "allow", "verify": "allow"}}), encoding="utf-8")
        initialized = cli("init", "--session", "owner", "--client", "manual", "--goal", "Offline standalone acceptance",
                          "--config", config)
        owner = ("--session", "owner", "--epoch", str(initialized["epoch"]))
        helper = isolated / "scripts/playbook-foundation.py"
        before = snapshot(project)
        result = run(sys.executable, "-I", str(helper), "check", "--project", str(project), cwd=unrelated, env=environment)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("README.md", {item["path"] for item in json.loads(result.stdout)["create"]})
        self.assertEqual(snapshot(project), before)
        result = run(sys.executable, "-I", str(helper), "apply", "--project", str(project), *owner,
                     cwd=unrelated, env=environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["readiness"]["foundation_complete"])
        readme = (project / "README.md").read_text(encoding="utf-8")
        self.assertIn("Offline standalone acceptance", readme)
        self.assertIn("Build command: **pending**", readme)
        self.assertIn("Test command: **pending**", readme)
        self.assertEqual(cli("doctor")["runtime_diagnostics"]["manifest"]["status"], "recorded")

        # The project runtime, adapter and foundation resources must survive the
        # removal of the only installed skill, including its templates directory.
        shutil.rmtree(isolated)
        runtime = project / "scripts/playbook.py"
        self.assertEqual(cli("version")["missing_files"], [])
        helper = project / "scripts/playbook-foundation.py"
        result = run(sys.executable, "-I", str(helper), "apply", "--project", str(project),
                     "--profile", "standard", *owner, cwd=unrelated, env=environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["readiness"]["foundation_complete"])
        self.assertTrue((project / "docs/plan/templates/review.md").is_file())
        self.assertEqual((project / "README.md").read_text(encoding="utf-8"), readme)
        content = project / "source.txt"
        content.write_text("standalone acceptance\n", encoding="utf-8")
        spec = root / "task-spec.json"
        spec.write_text(json.dumps({"requirements": ["Preserve source content"],
                                    "acceptance": ["Offline verifier checks the content"],
                                    "paths": ["source.txt"]}), encoding="utf-8")
        cli("task", *owner, "--id", "T1", "--spec", spec)
        self.assertTrue(cli("readiness", "--task", "T1")["ready"])
        managed_environment = dict(environment, PLAYBOOK_PROJECT=str(project), PLAYBOOK_SESSION="owner",
                                   PLAYBOOK_EPOCH=str(initialized["epoch"]), PLAYBOOK_TASK="T1", PLAYBOOK_WORKER="fake")
        managed_log = root / "managed.log"
        result = run("bash", str(project / "scripts/dispatch.sh"), "claude", str(project), "fixture only",
                     "-t", "5", "-q", "-l", str(managed_log), cwd=unrelated, env=managed_environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("bundle fake worker ran", managed_log.read_text())
        self.assertEqual(cli("status")["tasks"]["T1"]["state"], "reported")
        verification = cli("run", *owner, "--action", "verify", "--task", "T1", "--reviewer", "reviewer", "--role", "reviewer",
                           "--", sys.executable, "-I", "-c",
                           "from pathlib import Path; assert Path('source.txt').read_text() == 'standalone acceptance\\n'")
        cli("evidence", *owner, "--task", "T1", "--attempt", verification["attempt"]["id"],
            "--reviewer", "reviewer", "--role", "reviewer", "--note", "Offline content verified")
        cli("task", *owner, "--id", "T1", "--state", "verified")
        self.assertTrue(cli("evidence", "--operation", "status", "--task", "T1")["evidence"][0]["applicable"])
        diagnosis = cli("doctor")["runtime_diagnostics"]
        self.assertEqual(diagnosis["manifest"]["status"], "recorded")
        self.assertTrue(all(item["status"] == "matching" and item["provenance"] == "recorded"
                            for item in diagnosis["project_copies"]))

    def test_public_manifests_and_compatibility_root(self):
        for rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            manifest = json.loads((REPO / rel).read_text())
            self.assertEqual(manifest["version"], "3.0.0")
            self.assertIn(manifest["skills"], ("./skills/", "./skills", ["./skills/" + name for name in NAMES]))
        marketplace = json.loads((REPO / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(marketplace["metadata"]["version"], "3.0.0")
        self.assertEqual(marketplace["plugins"][0]["skills"], ["./skills/" + name for name in NAMES])
        for filename in ("SKILL.md", "SKILL.zh.md"):
            content = (REPO / filename).read_text(encoding="utf-8")
            self.assertIn("name: orchestrator-playbook\n", content)
            self.assertIn("disable-model-invocation: true", content)
        self.assertIn("allow_implicit_invocation: false", (REPO / "agents/openai.yaml").read_text())


if __name__ == "__main__":
    unittest.main()
