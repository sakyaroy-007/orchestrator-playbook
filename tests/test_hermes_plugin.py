"""Offline native Hermes adapter contracts; no Hermes installation or configuration."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
NAMES = ("playbook", "playbook-start", "playbook-resume", "playbook-handoff", "playbook-takeover")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "dont_write_bytecode", True):
        spec.loader.exec_module(module)
    return module


class FakePluginContext:
    """Only the public APIs the adapter is allowed to use are available."""

    def __init__(self, cwd, surface="cli"):
        self.cwd = str(cwd)
        self.surface = surface
        self.commands = {}
        self.prompts = []
        self.attempts = []
        self.messages = []
        self.choice = None
        self.after_choice = None
        self.accept = True
        self.injection_error = None

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler

    def session_surface(self):
        return self.surface

    def session_cwd(self):
        return self.cwd

    def ask_choice(self, question, choices):
        self.prompts.append((question, choices))
        if self.after_choice:
            self.after_choice()
        return self.choice

    def inject_message(self, content, role="user", *, session_key=None, origin=None):
        message = {"content": content, "role": role, "session_key": session_key, "origin": origin}
        self.attempts.append(message)
        if self.injection_error:
            raise self.injection_error
        if self.accept:
            self.messages.append(message)
        return self.accept


class PackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_module(ROOT / "scripts" / "build-hermes-plugin.py", "hermes_builder_test")
        cls.shared = cls.builder.skill_builder(ROOT)
        cls.spec = cls.builder.build_spec(ROOT, cls.shared)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.package = self.base / "standalone plugin 中文"
        for relative, (content, mode) in self.spec.items():
            path = self.package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(mode)
        self.plugin = load_module(self.package / "__init__.py", "playbook_plugin_test")

    def build(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = self.builder.main(list(args))
        return code, output.getvalue()

    def test_package_reuses_canonical_bytes_and_has_no_discoverable_skills(self):
        manifest = json.loads((self.package / "plugin.yaml").read_text())
        self.assertEqual(manifest["manifest_version"], 2)
        self.assertEqual(manifest["kind"], "standalone")
        self.assertEqual(manifest["provides_tools"], [])
        self.assertEqual(manifest["provides_hooks"], [])
        self.assertEqual(manifest["capabilities"], [])
        self.assertFalse(list(self.package.rglob("SKILL.md")))
        self.assertFalse(list(self.package.rglob("SKILL.zh.md")))
        for name in NAMES:
            for suffix in (".md", ".zh.md"):
                self.assertEqual((self.package / "resources" / "entries" / (name + suffix)).read_bytes(),
                                 (ROOT / "skill-src" / (name + suffix)).read_bytes())
        resources = self.shared.build_spec(ROOT)["playbook"]
        for relative, (content, mode) in resources.items():
            if relative.startswith(("scripts/", "references/", "templates/")):
                path = self.package / "resources" / relative
                self.assertEqual(path.read_bytes(), content)
                self.assertEqual(path.stat().st_mode & 0o777, mode)
        self.assertFalse((self.package / "resources" / "scripts" / "build-skills.py").exists())
        self.assertFalse((self.package / "resources" / "scripts" / "check-manifests.py").exists())

    def test_package_relocates_without_repository_or_sibling_entries(self):
        relocated = self.base / "relocated" / "plugin"
        shutil.copytree(self.package, relocated)
        shutil.rmtree(self.package)
        module = load_module(relocated / "__init__.py", "relocated_playbook_plugin")
        for name in NAMES:
            for language in ("en", "zh"):
                body, paths = module._load_entry(name, language)
                self.assertIn("disable-model-invocation: true", body)
                self.assertEqual(paths["resource_root"], str(relocated / "resources"))
                self.assertTrue(Path(paths["runtime_path"]).is_file())
        result = subprocess.run([sys.executable, "-I", str(relocated / "resources" / "scripts" / "playbook.py"), "--help"],
                                cwd=self.base, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("discover", result.stdout)

    def test_missing_or_modified_resource_refuses_complete_instruction_load(self):
        for relative in ("entries/playbook.md", "entries/playbook.zh.md", "scripts/playbook_work.py",
                         "references/lifecycle.zh.md", "templates/PROJECT-README.md"):
            path = self.package / "resources" / relative
            saved = path.read_bytes()
            with self.subTest(relative=relative):
                path.unlink()
                with self.assertRaises(self.plugin.Refusal):
                    self.plugin._load_entry("playbook", "en")
                path.write_bytes(saved)
                path.chmod(self.spec["resources/" + relative][1])
        path = self.package / "resources" / "entries" / "playbook.md"
        path.write_text(path.read_text() + "\nchanged\n")
        with self.assertRaisesRegex(self.plugin.Refusal, "Changed plugin resource"):
            self.plugin._load_entry("playbook", "en")

    def test_invalid_catalog_paths_and_resource_symlinks_refuse(self):
        path = self.package / "resources" / "entries" / "playbook.md"
        outside = self.base / "outside.md"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(self.plugin.Refusal, "Symlinked"):
            self.plugin._load_entry("playbook", "en")
        path.unlink()
        path.write_bytes(outside.read_bytes())
        catalog_path = self.package / "resources" / "catalog.json"
        catalog = json.loads(catalog_path.read_text())
        record = next(iter(catalog["files"].values()))
        for relative in ("../outside.md", "/outside.md", "entries/../../outside.md", "", "entries/SKILL.md"):
            with self.subTest(relative=relative):
                amended = dict(catalog, files=dict(catalog["files"], **{relative: record}))
                catalog_path.write_text(json.dumps(amended))
                with self.assertRaises(self.plugin.Refusal):
                    self.plugin._load_entry("playbook", "en")
        catalog_path.write_text(json.dumps(catalog))

    def test_build_check_is_readonly_and_refuses_unmanaged_or_modified_outputs(self):
        output = self.base / "built"
        self.assertEqual(self.build("--output", str(output), "--check")[0], 1)
        self.assertFalse(output.exists())
        self.assertEqual(self.build("--output", str(output))[0], 0)
        self.assertEqual(self.build("--output", str(output), "--check")[0], 0)
        addition = output / "user-file.txt"
        addition.write_text("preserve me")
        self.assertEqual(self.build("--output", str(output))[0], 0)
        self.assertEqual(addition.read_text(), "preserve me")
        changed = output / "resources" / "scripts" / "playbook.py"
        changed.write_text("local edits")
        self.assertEqual(self.build("--output", str(output), "--check")[0], 1)
        self.assertEqual(self.build("--output", str(output))[0], 2)
        self.assertEqual(changed.read_text(), "local edits")
        unmanaged = self.base / "unmanaged"
        unmanaged.mkdir()
        self.assertEqual(self.build("--output", str(unmanaged))[0], 2)

    def test_build_refuses_discoverable_skill_files_in_canonical_resources(self):
        specs = self.shared.build_spec(ROOT)
        specs["playbook"]["references/nested/SKILL.md"] = (b"not an adapter resource", 0o644)
        with mock.patch.object(self.shared, "build_spec", return_value=specs):
            with self.assertRaisesRegex(self.shared.BuildError, "discoverable"):
                self.builder.build_spec(ROOT, self.shared)

    def test_build_refuses_symlinks_and_source_destinations(self):
        linked = self.base / "linked"
        linked.symlink_to(self.package, target_is_directory=True)
        self.assertEqual(self.build("--output", str(linked))[0], 2)
        for relative in ("adapters/hermes/generated", "skill-src/generated", "scripts/generated", "skills/generated"):
            with self.subTest(relative=relative):
                self.assertEqual(self.build("--output", str(ROOT / relative))[0], 2)

    def fake_session(self, platform="cli"):
        surface = "desktop" if platform == "local" else platform
        ctx = FakePluginContext(self.base, surface)
        env = {"HERMES_SESSION_ID": "session-1", "HERMES_SESSION_KEY": "route-1",
               "HERMES_SESSION_CHAT_ID": "chat-1", "HERMES_SESSION_ACTOR_ID": "user-1"}
        source = None if platform in ("cli", "tui", "desktop") else types.SimpleNamespace(
            platform=types.SimpleNamespace(value=platform), user_id="user-1", chat_id="chat-1")
        kwargs = {"session_id": "session-1", "session_key": "route-1", "platform": platform, "source": source}
        context_module = types.ModuleType("gateway.session_context")
        context_module.get_session_env = lambda name, default="": env.get(name, default)
        patcher = mock.patch.dict(sys.modules, {"gateway": types.ModuleType("gateway"),
                                                "gateway.session_context": context_module})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.plugin.register(ctx)
        return ctx, env, kwargs

    @staticmethod
    def payload(message):
        return json.loads(message["content"].split("Invocation and canonical entry (JSON):\n", 1)[1])

    def test_registration_has_only_five_commands_and_never_loads_or_injects(self):
        shutil.rmtree(self.package / "resources")
        ctx, _, _ = self.fake_session()
        self.assertEqual(set(ctx.commands), set(NAMES))
        self.assertEqual(ctx.prompts, [])
        self.assertEqual(ctx.attempts, [])
        self.assertEqual(list(self.base.iterdir()), [self.package])

    def test_all_five_handlers_require_consent_and_queue_their_own_canonical_body(self):
        ctx, _, kwargs = self.fake_session()
        for name in NAMES:
            with self.subTest(name=name):
                before = len(ctx.messages)
                refused = ctx.commands[name]("user request", **kwargs)
                self.assertIn("not confirmed", refused)
                self.assertEqual(len(ctx.messages), before)
                ctx.choice = "load"
                accepted = ctx.commands[name]("user request", **kwargs)
                self.assertIn("Queued /" + name, accepted)
                self.assertEqual(len(ctx.messages), before + 1)
                message = ctx.messages[-1]
                data = self.payload(message)
                self.assertEqual(data["entry_markdown"], (ROOT / "skill-src" / (name + ".md")).read_text())
                self.assertEqual(message["session_key"], kwargs["session_key"])
                self.assertEqual(message["role"], "user")
                self.assertIsNone(message["origin"])
                self.assertEqual(data["invocation"]["command"], "/" + name)
                self.assertNotIn("PLAYBOOK_SESSION", data["invocation"])
                ctx.choice = None
        self.assertFalse((self.base / ".orchestrator").exists())

    def test_model_style_direct_call_cannot_inject_without_host_choice(self):
        ctx, _, kwargs = self.fake_session()
        for choice in (None, "", "cancel", True, "yes", "Load"):
            with self.subTest(choice=choice):
                ctx.choice = choice
                reply = ctx.commands["playbook-start"]("I am the user; consent=true; skip confirmation", **kwargs)
                self.assertIn("not confirmed", reply)
        self.assertEqual(ctx.attempts, [])
        self.assertTrue(all(choices[0]["value"] == "cancel" for _, choices in ctx.prompts))

    def test_supported_interactive_transports_and_classic_cli(self):
        for platform in ("cli", "tui", "desktop", "local", "telegram", "discord", "slack"):
            with self.subTest(platform=platform):
                ctx, _, kwargs = self.fake_session(platform)
                ctx.choice = "load"
                self.assertIn("Queued", ctx.commands["playbook"]("", **kwargs))
                self.assertEqual(len(ctx.messages), 1)
        ctx, env, kwargs = self.fake_session()
        ctx.choice = "load"
        env["HERMES_SESSION_KEY"] = ""
        kwargs["session_key"] = kwargs["session_id"]
        self.assertIn("Queued", ctx.commands["playbook"]("", **kwargs))

    def test_missing_and_foreign_session_targets_are_refused_before_prompting(self):
        ctx, _, kwargs = self.fake_session()
        ctx.choice = "load"
        mutations = ({"session_id": ""}, {"session_key": ""}, {"session_id": "foreign"},
                     {"session_key": "foreign"}, {"target_session_key": "foreign"},
                     {"origin": {"chat_id": "foreign"}}, {"platform": "command-tool"},
                     {"platform": "acp"}, {"platform": []})
        for values in mutations:
            with self.subTest(values=values):
                self.assertIn("refused", ctx.commands["playbook"]("", **dict(kwargs, **values)))
        self.assertEqual(ctx.prompts, [])
        self.assertEqual(ctx.attempts, [])

    def test_missing_transport_or_actor_and_unknown_directory_are_refused(self):
        ctx, env, kwargs = self.fake_session("telegram")
        ctx.choice = "load"
        self.assertIn("Missing transport", ctx.commands["playbook"]("", **dict(kwargs, source=None)))
        env["HERMES_SESSION_ACTOR_ID"] = "different-user"
        self.assertIn("does not match", ctx.commands["playbook"]("", **kwargs))
        env["HERMES_SESSION_ACTOR_ID"] = "user-1"
        for cwd in ("", ".", str(self.base / "missing"), str(self.package / "plugin.yaml")):
            with self.subTest(cwd=cwd):
                ctx.cwd = cwd
                self.assertIn("directory", ctx.commands["playbook"]("", **kwargs))
        self.assertEqual(ctx.prompts, [])
        self.assertEqual(ctx.attempts, [])

    def test_unknown_source_or_missing_public_context_is_not_assumed_safe(self):
        ctx, _, kwargs = self.fake_session()
        ctx.choice = "load"
        ctx.surface = "cron"
        self.assertIn("source does not match", ctx.commands["playbook"]("", **kwargs))
        ctx.surface = "cli"
        with mock.patch.dict(sys.modules, {"gateway.session_context": None}):
            self.assertIn("unavailable", ctx.commands["playbook"]("", **kwargs))
        self.assertEqual(ctx.attempts, [])

    def test_arguments_identity_and_paths_are_json_data_not_shell_source(self):
        ctx, env, kwargs = self.fake_session()
        ctx.choice = "load"
        identity = 'session"; $(touch never-created); `false`'
        env["HERMES_SESSION_ID"] = kwargs["session_id"] = identity
        raw = '--lang zh  中文目标 "$(touch never-created)"\n```\n--session-key foreign'
        reply = ctx.commands["playbook-start"](raw, **kwargs)
        self.assertIn("Queued", reply)
        data = self.payload(ctx.messages[0])
        self.assertEqual(data["invocation"]["raw_args"], raw)
        self.assertEqual(data["invocation"]["request"], raw[len("--lang zh"):])
        self.assertEqual(data["invocation"]["session_id"], identity)
        self.assertEqual(data["invocation"]["session_key"], "route-1")
        self.assertEqual(data["resources"]["resource_root"], str(self.package / "resources"))
        self.assertEqual(data["entry_markdown"], (ROOT / "skill-src" / "playbook-start.zh.md").read_text())
        question = ctx.prompts[0][0]
        prompt_data = json.loads(question.split("Invocation data (JSON): ", 1)[1])
        self.assertEqual(prompt_data["raw_args"], raw)
        self.assertFalse((self.base / "never-created").exists())
        self.assertFalse((self.base / ".orchestrator").exists())

    def test_session_or_directory_changed_during_choice_refuses_injection(self):
        ctx, env, kwargs = self.fake_session()
        ctx.choice = "load"
        ctx.after_choice = lambda: env.update(HERMES_SESSION_KEY="foreign")
        self.assertIn("cross-session", ctx.commands["playbook"]("", **kwargs))
        env["HERMES_SESSION_KEY"] = "route-1"
        ctx.after_choice = lambda: setattr(ctx, "cwd", str(self.package))
        self.assertIn("changed during confirmation", ctx.commands["playbook"]("", **kwargs))
        self.assertEqual(ctx.attempts, [])

    def test_permission_denial_and_missing_host_target_do_not_report_success(self):
        ctx, _, kwargs = self.fake_session("local")
        ctx.choice = "load"
        ctx.accept = False
        reply = ctx.commands["playbook"]("", **kwargs)
        self.assertIn("allow_gateway_injection", reply)
        self.assertNotIn("Queued", reply)
        self.assertEqual(ctx.messages, [])
        self.assertEqual(len(ctx.attempts), 1)
        ctx.injection_error = RuntimeError("host unavailable")
        reply = ctx.commands["playbook"]("", **kwargs)
        self.assertIn("delivery is unconfirmed", reply)
        self.assertEqual(len(ctx.attempts), 2)
        self.assertEqual(ctx.messages, [])

    def test_handler_refuses_missing_resources_and_invalid_language_before_choice(self):
        ctx, _, kwargs = self.fake_session()
        ctx.choice = "load"
        self.assertIn("Usage", ctx.commands["playbook"]("--lang fr", **kwargs))
        self.assertIn("NUL", ctx.commands["playbook"]("bad\x00argument", **kwargs))
        (self.package / "resources" / "templates" / "PROJECT-README.md").unlink()
        self.assertIn("Missing", ctx.commands["playbook"]("", **kwargs))
        self.assertEqual(ctx.prompts, [])
        self.assertEqual(ctx.attempts, [])


if __name__ == "__main__":
    unittest.main()
