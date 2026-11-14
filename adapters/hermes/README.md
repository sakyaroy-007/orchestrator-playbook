# Playbook native Hermes adapter

This adapter registers five in-session commands: `/playbook`, `/playbook-start`,
`/playbook-resume`, `/playbook-handoff` and `/playbook-takeover`. A command validates
its calling session and packaged resources, asks that session's user to select
**Load**, then queues the canonical entry with `ctx.inject_message`. The adapter
executes no project lifecycle actions itself. A successful reply means Hermes
accepted the message for scheduling, not that a model processed it or a project
action succeeded.

## Build a standalone package

From the repository root, use a physical staging path:

```sh
python3 -I scripts/build-hermes-plugin.py --output "$(pwd -P)/dist/hermes/orchestrator-playbook"
python3 -I scripts/build-hermes-plugin.py --output "$(pwd -P)/dist/hermes/orchestrator-playbook" --check
```

The output directory itself is a native plugin package. It contains
`plugin.yaml`, `__init__.py`, this README, and `resources/`. The unbuilt
`adapters/hermes/` source directory is incomplete and refuses instruction loading.
Building does not install the package, load a live Hermes plugin, change a profile,
grant permissions or contact a model/gateway.

The builder reuses `scripts/build-skills.py`'s resource specification. Runtime
scripts and Markdown references/templates stay byte-identical to their canonical
sources; all ten English/Chinese entry files come directly from `skill-src/`.
The plugin resolves resources relative to its own installed package. It does not
need sibling skills or the source checkout, and the generated package contains no
`SKILL.md` or `SKILL.zh.md`. Do not link it into an ordinary skill scanning root.
No skill, model tool, CLI subcommand, RPC method or automatic hook is registered.

`--check` is read-only: exit 0 means current, 1 means drift, and 2 means invalid or
unsafe input. Rebuilding preserves unknown files and refuses unmarked directories,
locally modified generated files and symlinks. The generated marker and resource
hashes detect accidental changes; they are not security signatures. Preserve local
edits before rebuilding, and use one builder at a time per output directory.

## Invocation and language

```text
/playbook
/playbook-start describe the first project milestone
/playbook-resume --lang zh 继续当前会话的工作
/playbook-handoff --lang en prepare the agreed handoff
/playbook-takeover accept the designated handoff
```

English is the default. A leading `--lang en`, `--lang zh`, `--lang=en` or
`--lang=zh` selects an edition; the original arguments are preserved in full as
JSON data. The remaining request is also preserved, without shell parsing or
interpolation. The confirmation presents the command, exact request, session and
working directory. **Cancel** is listed first. A missing choice UI, cancellation,
empty response, timeout or any answer other than the host's `load` value refuses
to queue instructions. There is no consent bypass setting or argument.

Both editions retain the canonical explicit-only metadata. `PLAYBOOK_SKILL_DIR`
is supplied as the package's absolute resource directory; references/templates and
the runtime are resolved there. The entry's original `SKILL.md`/`SKILL.zh.md`
references are mapped to the packaged English/Chinese entry paths in the injected
context. 中文正文、参考资料和模板保留为 UTF-8 文件；`--lang zh` 会加载中文正文。

Hermes session IDs are routing metadata, not Playbook ownership IDs. The loaded
entry follows the existing session's retained Playbook identity and epoch, or its
canonical identity creation procedure when appropriate. It does not copy the
incumbent owner's identity from status, silently take ownership or change project
permissions. The current session workspace is only the initial project location;
an explicit project request is resolved under the canonical lifecycle rules.

## Host boundary and required permission

The manifest uses native `plugin.yaml` schema version 2, `kind: standalone` and
`register(ctx)`, with a Hermes version range of `>=0.23.1,<0.24.0`. Its JSON syntax
is valid YAML. No Python dependencies, tools, hooks or capability IDs are declared.
The adapter uses public `ctx.register_command`, `ctx.session_surface`,
`ctx.session_cwd`, `ctx.ask_choice`, `ctx.inject_message`, and the published
`gateway.session_context.get_session_env` import.

Hermes 0.23.1 does not supply a verified human invocation marker to a slash
handler. `source`, `platform`, `session_id` and `session_key` describe transport and
routing; they do not distinguish a typed slash command from another authenticated
caller of `command.dispatch`/`slash.exec`. Legacy local handlers may receive
`source=None`. Checking these values alone cannot enforce explicit human intent.
For that reason every load requires the host's session-bound interactive choice.
The adapter trusts Hermes to bind the choice UI and its answer to the current
conversation. It does not claim to sandbox arbitrary same-user shell access,
malicious in-process code or a host that forges UI responses. Such callers could
read the same local resources directly; ordinary skill-discovery flags are not a
replacement for this boundary.

Only contexts with a working choice UI are supported. CLI, TUI and Desktop
contexts must identify a current session and existing local workspace; a native
`local` source must also match the bound actor/chat. Telegram, Discord and Slack
contexts must supply matching transport, actor, chat and session IDs. Other
platforms, missing identity, unknown or nonlocal working directories, cross-session
routing targets and extra target overrides are refused. Handler context is checked
again after the choice; a detected identity or directory change stops the load.
The adapter never derives a target from user arguments, never supplies `origin`,
and never falls back to another session.

For gateway/TUI delivery, Hermes 0.23.1 checks the operator-owned setting
`plugins.entries.orchestrator-playbook.allow_gateway_injection: true`.
That version's capability registry does **not** declare a gateway-injection
capability ID; inventing one in the manifest would not grant access. The adapter
lets `ctx.inject_message` enforce the live permission and reports a refusal when
Hermes returns false. It cannot enable this setting. Installation, plugin enablement
and this separate permission require operator review outside the build. A classic
in-process CLI has its own pending-input queue; the adapter still requires a
matching session and interactive choice there.

A command's returned string is only display output. The canonical instructions
are delivered through `inject_message`, with role `user` and the verified calling
routing key. If injection raises, delivery is reported as unconfirmed; there is no
retry or fallback that could enqueue duplicates or target another chat.

## Offline checks and limits

```sh
python3 -I -m unittest discover -s tests -p test_hermes_plugin.py -v
```

Tests use a fake `PluginContext` and synthetic calling-session data. They exercise
all five handlers, registration without injection, interactive consent, permission
refusal, absent/mismatched targets, exact arguments, missing or changed resources,
and a standalone package moved away from the checkout. The only runtime subprocess
is the bundled Playbook's local `--help`; no model, actual gateway, user config or
credentials are used.

The API and routing assumptions were checked against Hermes 0.23.1 source, including
`plugins_context.py`, `plugin_command_dispatch.py`, `plugins_injection.py`,
`plugin_choices.py`, `gateway/plugin_command_choice.py` and
`gateway/run_inbound_hooks.py`. Offline tests do not establish live plugin loading,
menu registration, frontend UI availability, actual delivery or model execution.
Verify those separately on an explicitly authorized host before claiming native
end-to-end support.
