"""Read-only manifest checks, including missing generated resources.

Run: python3 -I -m unittest discover -s tests -p test_manifests.py.
No native client or network is used by these tests.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check-manifests.py"
SKILLS = ("playbook", "playbook-start", "playbook-resume", "playbook-handoff", "playbook-takeover")
MANIFESTS = (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
             ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="playbook-manifests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.package = self.root / "package"
        self.package.mkdir()
        for relative in MANIFESTS + ("assets/icon.png", "SKILL.md", "SKILL.zh.md"):
            target = self.package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        for name in SKILLS:
            directory = self.package / "skills" / name
            directory.mkdir(parents=True)
            for filename in ("SKILL.md", "SKILL.zh.md"):
                (directory / filename).write_text(
                    "---\nname: " + name + "\ndescription: Fixture\n"
                    "disable-model-invocation: true\n---\n# Explicit fixture\n", encoding="utf-8")

    def check(self, expected=0):
        result = subprocess.run([sys.executable, "-I", str(CHECKER), "--root", str(self.package)],
                                cwd=self.root, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        if expected:
            self.assertIn("check-manifests:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        return result

    def snapshot(self):
        return {path.relative_to(self.package).as_posix():
                (path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns)
                for path in self.package.rglob("*") if path.is_file()}

    def edit_json(self, relative, mutate):
        path = self.package / relative
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_success_is_read_only_and_does_not_claim_native_validation(self):
        before = self.snapshot()
        # Isolated mode must not import modules from the caller's directory.
        (self.root / "json.py").write_text('raise RuntimeError("hostile cwd import")\n')
        result = json.loads(self.check().stdout)
        self.assertIs(result["ok"], True)
        self.assertEqual(result["native_validation"], "not_run")
        self.assertEqual(result["skills"], list(SKILLS))
        self.assertEqual(result["manifests"], list(MANIFESTS))
        self.assertEqual(self.snapshot(), before)

    def test_missing_generated_directory_is_a_failure(self):
        shutil.rmtree(self.package / "skills/playbook-takeover")
        before = self.snapshot()
        self.assertIn("missing generated skill", self.check(expected=2).stderr)
        self.assertEqual(self.snapshot(), before)

    def test_missing_entry_or_icon_is_a_failure(self):
        for relative in ("skills/playbook-resume/SKILL.md", "skills/playbook-start/SKILL.zh.md",
                         "SKILL.md", "assets/icon.png"):
            with self.subTest(path=relative):
                path = self.package / relative
                saved = path.read_bytes()
                path.unlink()
                self.check(expected=2)
                path.write_bytes(saved)

    def test_every_version_must_match_the_package(self):
        mutations = (
            (MANIFESTS[0], lambda data: data.update(version="2.0.0")),
            (MANIFESTS[2], lambda data: data.update(version="2.0.0")),
            (MANIFESTS[1], lambda data: data["metadata"].update(version="2.0.0")),
            (MANIFESTS[1], lambda data: data["plugins"][0].update(version="2.0.0")),
            (MANIFESTS[3], lambda data: data["plugins"][0].update(version="2.0.0")),
        )
        for relative, mutate in mutations:
            with self.subTest(path=relative):
                path = self.package / relative
                original = path.read_bytes()
                self.edit_json(relative, mutate)
                self.assertIn("version", self.check(expected=2).stderr)
                path.write_bytes(original)

    def test_references_reject_escape_and_symlinks(self):
        path = self.package / MANIFESTS[0]
        original = path.read_bytes()
        for value in ("../outside", str(self.root), "./skills/playbook/../playbook"):
            with self.subTest(reference=value):
                self.edit_json(MANIFESTS[0], lambda data: data["skills"].__setitem__(0, value))
                self.check(expected=2)
                path.write_bytes(original)
        entry = self.package / "skills/playbook/SKILL.md"
        saved = entry.read_bytes()
        entry.unlink()
        outside = self.root / "outside.md"
        outside.write_bytes(saved)
        entry.symlink_to(outside)
        self.assertIn("symlink", self.check(expected=2).stderr)
        self.assertEqual(outside.read_bytes(), saved)

    def test_wrong_duplicate_or_extra_skill_is_rejected(self):
        path = self.package / MANIFESTS[0]
        original = path.read_bytes()
        for selection in (["./skills/playbook"] * 5,
                          ["./skills/" + name for name in SKILLS[:-1]],
                          ["./skills/" + name for name in SKILLS] + ["./other"]):
            with self.subTest(selection=selection):
                self.edit_json(MANIFESTS[0], lambda data: data.update(skills=selection))
                self.assertIn("exactly the five", self.check(expected=2).stderr)
                path.write_bytes(original)
        directory = self.package / "skills/unintended-entry"
        directory.mkdir()
        (directory / "SKILL.md").write_text("unintended published entry")
        self.assertIn("exactly the five", self.check(expected=2).stderr)

    def test_wrong_names_and_implicit_entry_are_rejected(self):
        path = self.package / "skills/playbook/SKILL.md"
        original = path.read_text()
        for content in (original.replace("name: playbook", "name: other"),
                        original.replace("disable-model-invocation: true", "disable-model-invocation: false"),
                        original.removeprefix("---\n")):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.check(expected=2)
        path.write_text(original, encoding="utf-8")
        self.edit_json(MANIFESTS[2], lambda data: data.update(name="other"))
        self.assertIn("package name", self.check(expected=2).stderr)

    def test_ambiguous_yaml_cannot_override_explicit_invocation(self):
        additions = ('"disable-model-invocation": false', "'disable-model-invocation': false",
                     '"\\x64isable-model-invocation": false',
                     '? disable-model-invocation\n: false',
                     '<<: {disable-model-invocation: false}',
                     'disable-model-invocation: false', '"name": other')
        for relative in ("SKILL.md", "skills/playbook/SKILL.md"):
            path = self.package / relative
            original = path.read_text()
            for addition in additions:
                with self.subTest(path=relative, syntax=addition):
                    path.write_text(original.replace("\n---\n", "\n" + addition + "\n---\n", 1))
                    self.check(expected=2)
            path.write_text(original)

    def test_simple_quoted_name_value_keeps_its_actual_identity(self):
        path = self.package / "skills/playbook/SKILL.md"
        original = path.read_text()
        for value in ('"playbook"', "'playbook'"):
            path.write_text(original.replace("name: playbook", "name: " + value))
            self.check()
        path.write_text(original.replace("name: playbook", "name: '\"playbook\"'"))
        self.check(expected=2)

    def test_invalid_json_duplicates_and_shapes_are_rejected(self):
        path = self.package / MANIFESTS[1]
        original = path.read_bytes()
        for content in ("not JSON", "[]", '{"extra": NaN}', '{"name":"first","name":"second"}',
                        '{"name":"orchestrator-playbook","metadata":null}',
                        '{"name":"orchestrator-playbook","metadata":{"version":"3.0.0"},"plugins":[]}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.check(expected=2)
        path.write_bytes(original)

    def test_catalog_source_must_point_to_the_local_package(self):
        path = self.package / MANIFESTS[3]
        original = path.read_bytes()
        for source in ({"source": "url", "url": "../outside"},
                       {"source": "url", "url": "https://example.invalid/package"}, None):
            with self.subTest(source=source):
                self.edit_json(MANIFESTS[3], lambda data: data["plugins"][0].update(source=source))
                self.check(expected=2)
                path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
