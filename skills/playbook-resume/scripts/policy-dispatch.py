#!/usr/bin/env python3
"""Bridge the legacy dispatcher to a configured project's managed run protocol.

This adapter never changes client/global settings. It resolves approved per-run
settings, then lets playbook.py reserve the task and enforce the current policy.
Raw tools and forged recursion markers are outside this cooperative protocol.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


class DispatchError(Exception):
    pass


def text(value, label):
    if not isinstance(value, str) or not value or "\0" in value:
        raise DispatchError("{} must be a nonempty string without NUL".format(label))
    return value


def read_status(runtime, project):
    result = subprocess.run(
        [sys.executable, "-I", str(runtime), "status", "--project", str(project)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if result.returncode:
        raise DispatchError(result.stderr.strip() or result.stdout.strip() or "cannot read project state")
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise DispatchError("runtime status did not return JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("policy"), dict):
        raise DispatchError("runtime status lacks its canonical policy; update the matched runtime and adapter")
    # The runtime validates and normalizes policy. Check the JSON boundary, not
    # the full schema or defaults again; dispatch-specific checks follow below.
    policy = data["policy"]
    roster = policy.get("workers")
    if not isinstance(roster, list) or any(not isinstance(worker, dict) for worker in roster):
        raise DispatchError("runtime policy workers must be a list of objects")
    limits = policy.get("limits")
    if not isinstance(limits, dict) or type(limits.get("timeout_seconds")) is not int:
        raise DispatchError("runtime policy lacks its canonical timeout")
    if type(data.get("config_revision")) is not int:
        raise DispatchError("runtime status lacks config_revision; use a matched runtime")
    return data


def parse_legacy(argv):
    if len(argv) < 3:
        raise DispatchError('usage: policy-dispatch.py CLIENT WORKTREE "PROMPT" [dispatcher options]')
    client, cwd, prompt = argv[:3]
    options = {"client": client, "cwd": str(Path(cwd).resolve()), "prompt": prompt,
               "timeout": None, "model": None, "quiet": False, "log": None, "extra": []}
    rest = list(argv[3:])
    while rest:
        option = rest.pop(0)
        if option == "--":
            options["extra"] = rest
            break
        if option == "-q":
            options["quiet"] = True
        elif option in ("-t", "-m", "-l"):
            if not rest:
                raise DispatchError("{} needs a value".format(option))
            key = {"-t": "timeout", "-m": "model", "-l": "log"}[option]
            options[key] = rest.pop(0)
        else:
            raise DispatchError("unknown dispatcher option: {}".format(option))
    if client not in ("claude", "codex", "hermes", "dsh"):
        raise DispatchError("no native adapter for {}".format(client))
    if not Path(options["cwd"]).is_dir():
        raise DispatchError("worker directory does not exist")
    text(prompt, "prompt")
    return options


def setting(worker, name):
    obj = worker.get(name)
    if not isinstance(obj, dict):
        raise DispatchError("runtime worker.{} must be a canonical object".format(name))
    mode = obj.get("mode")
    if mode == "recommend":
        raise DispatchError("resolve the {} recommendation to inherit or fixed before launch".format(name))
    if mode == "inherit":
        return None
    if mode == "fixed":
        return text(obj.get("value"), "worker.{}.value".format(name))
    raise DispatchError("unknown {} mode".format(name))


def choose_worker(config, client, requested):
    matches = [w for w in config["workers"] if w.get("client") == client
               and (not requested or w.get("id") == requested)]
    if len(matches) != 1:
        raise DispatchError("select exactly one approved worker with PLAYBOOK_WORKER (found {})".format(len(matches)))
    text(matches[0].get("id"), "worker id")
    return matches[0]


def reject_setting_overrides(client, arguments):
    """Recognize dedicated-setting aliases, not arbitrary native CLI syntax."""
    flags = ("--model", "-m", "--effort", "--profile", "-p", "--reasoning")
    attached = {"codex": ("-m", "-p"), "hermes": ("-m", "-p")}.get(client, ())
    keys = ("model", "model_reasoning_effort", "agent-default-model")
    for index, arg in enumerate(arguments):
        conflict = arg.partition("=")[0] in flags or any(arg.startswith(flag) for flag in attached)
        payload = arg
        config_value = client == "codex" and index > 0 and arguments[index - 1] in ("-c", "--config")
        if client == "codex":
            if arg.startswith("--config="):
                payload, config_value = arg[len("--config="):], True
            elif arg.startswith("-c") and arg != "-c":
                payload, config_value = arg[2:], True
                if payload.startswith("="):
                    payload = payload[1:]
        # Codex accepts whitespace around the assignment and quoted top-level
        # keys. Normalize only the key; unrelated values/arguments pass intact.
        key = payload.partition("=")[0].strip()
        if len(key) >= 2 and key[0] in ("'", '"') and key[-1] == key[0]:
            key = key[1:-1]
        if conflict or key in keys or (config_value and key == "profile"):
            raise DispatchError("configure model/effort/profile using their dedicated fields, not worker.args")


class HelpProbe:
    """Successful help output reused only within one dispatch invocation."""

    def __init__(self):
        self.cache = {}

    def read(self, binary, client, argv):
        # Keep client and the entire argv in the key even when two adapters use
        # the same launcher. A changed subcommand must be probed independently.
        key = (binary, client, tuple(argv))
        if key not in self.cache:
            result = subprocess.run([binary] + list(argv), stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, timeout=15)
            if result.returncode:
                raise DispatchError("{} help probe failed (exit {})".format(client, result.returncode))
            self.cache[key] = result.stdout + "\n" + result.stderr
        return self.cache[key]

    def require_flag(self, binary, client, flag):
        """Probe only CLI help, never authentication or an LLM request."""
        argv = (["exec"] if client == "codex" else []) + ["--help"]
        try:
            output = self.read(binary, client, argv)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DispatchError("cannot verify {} support: {}".format(flag, exc)) from exc
        if not re.search(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])", output):
            raise DispatchError("{} does not advertise {}; keep settings inherited or choose a supported adapter".format(client, flag))


def main(argv):
    opts = parse_legacy(argv)
    directory = Path(__file__).resolve().parent
    runtime = directory / "playbook.py"
    project = Path(text(os.environ.get("PLAYBOOK_PROJECT"), "PLAYBOOK_PROJECT")).resolve()
    session = text(os.environ.get("PLAYBOOK_SESSION"), "PLAYBOOK_SESSION")
    epoch = text(os.environ.get("PLAYBOOK_EPOCH"), "PLAYBOOK_EPOCH")
    if not epoch.isdecimal():
        raise DispatchError("PLAYBOOK_EPOCH must be the numeric epoch returned by start/resume")
    task = text(os.environ.get("PLAYBOOK_TASK"), "PLAYBOOK_TASK")
    action = os.environ.get("PLAYBOOK_ACTION", "dispatch")
    if action not in ("dispatch", "verify"):
        raise DispatchError("PLAYBOOK_ACTION must be dispatch or verify")
    integration = os.environ.get("PLAYBOOK_INTEGRATION")
    if integration is not None:
        text(integration, "PLAYBOOK_INTEGRATION")
        if action != "verify":
            raise DispatchError("PLAYBOOK_INTEGRATION requires PLAYBOOK_ACTION=verify")
    if opts["prompt"] == "--precheck":
        if action != "dispatch":
            raise DispatchError("a native precheck is dispatch, not acceptance verification")
        task += "-precheck"
    status = read_status(runtime, project)
    config = status["policy"]
    revision = status["config_revision"]
    worker = choose_worker(config, opts["client"], os.environ.get("PLAYBOOK_WORKER"))
    model, effort = setting(worker, "model"), setting(worker, "effort")
    if opts["model"] is not None and opts["model"] != model:
        raise DispatchError("-m differs from approved worker configuration; use configure first")
    approved_args = worker.get("args")
    if not isinstance(approved_args, list) or any(not isinstance(a, str) or "\0" in a for a in approved_args):
        raise DispatchError("worker.args must be a list of strings without NUL")
    if opts["extra"] and opts["extra"] != approved_args:
        raise DispatchError("native CLI arguments differ from approved worker.args; use configure first")
    # Native argument escape hatches remain explicit project choices. Reject
    # conflicting model/effort/profile overrides rather than hiding precedence.
    reject_setting_overrides(opts["client"], approved_args)
    limit = config["limits"]["timeout_seconds"]
    try:
        timeout = int(opts["timeout"]) if opts["timeout"] is not None else limit
    except ValueError as exc:
        raise DispatchError("-t requires a positive integer") from exc
    if timeout < 1 or timeout > limit:
        raise DispatchError("requested timeout exceeds the project budget")
    if opts["log"]:
        # Resolve against the caller before run switches to the worker cwd.
        log_path = Path(opts["log"]).absolute()
        if log_path.exists() or log_path.is_symlink():
            raise DispatchError("refusing to overwrite an existing dispatch log")
        opts["log"] = str(log_path)

    env = dict(os.environ)
    env["PLAYBOOK_DISPATCHED"] = "1"
    env["PLAYBOOK_PROJECT"] = str(project)
    client = opts["client"]
    binary_key = "DISPATCH_BIN_" + client.upper()
    binary = shutil.which(env.get(binary_key, client))
    if not binary:
        raise DispatchError("approved client executable is unavailable: {}".format(client))
    # Preserve executable symlinks but keep the same binary after changing cwd.
    binary = str(Path(binary).absolute())
    env[binary_key] = binary
    probe = HelpProbe()
    native = list(approved_args)
    profile = worker.get("profile")
    if client == "hermes":
        policy = worker.get("hermes")
        if not isinstance(policy, dict) or policy.get("approval") not in ("inherit", "approve", "deny"):
            raise DispatchError("configure worker.hermes.approval explicitly; legacy -z approval is not inherited")
        if native:
            raise DispatchError("managed Hermes uses the gateway protocol; worker.args must be empty")
    if client == "dsh" and not profile:
        # The verified DSH launcher requires a profile, with no native default.
        # Choosing headless here would silently replace the worker's settings.
        raise DispatchError("DSH requires an explicit approved worker.profile; choose its existing noninteractive profile (for example headless) in configure")
    if profile:
        text(profile, "worker.profile")
        if client == "dsh":
            probe.require_flag(binary, client, "--profile")
            env["DISPATCH_DSH_PROFILE"] = profile
        elif client == "codex":
            probe.require_flag(binary, client, "--profile")
            native += ["--profile", profile]
        elif client != "hermes":
            raise DispatchError("a profile mapping is not verified for {}; keep it unset".format(client))
    temporary_patch = None
    try:
        if effort is not None:
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", effort):
                raise DispatchError("effort must be a native option name, not an expression")
            if client == "claude":
                probe.require_flag(binary, client, "--effort")
                if effort not in ("low", "medium", "high", "xhigh", "max"):
                    raise DispatchError("unrecognized Claude effort; no automatic cross-provider mapping")
                native += ["--effort", effort]
            elif client == "codex":
                probe.require_flag(binary, client, "--config")
                native += ["--config", "model_reasoning_effort=" + json.dumps(effort)]
            elif client == "dsh":
                probe.require_flag(binary, client, "--patch")
                # JSON is a YAML subset. It avoids injecting model values into
                # patch syntax and never modifies the user's profile on disk.
                fd, temporary_patch = tempfile.mkstemp(prefix="playbook-effort-", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump([{"id": "agent-default-model", "config": {"reasoningEffort": effort}}], stream)
                # DSH stops parsing launcher flags at the first application
                # argument (for example --json). Keep overlays before those.
                native = ["--patch", temporary_patch] + native
            # Hermes sends this native value through session.create.reasoning;
            # the bridge requires an exact snapshot echo before task submission.
        legacy = ["bash", str(directory / "dispatch.sh"), client, opts["cwd"], opts["prompt"], "-t", str(timeout)]
        if model is not None:
            legacy += ["-m", model]
        if opts["quiet"]:
            legacy.append("-q")
        if opts["log"]:
            legacy += ["-l", opts["log"]]
        if native:
            legacy += ["--"] + native
        if client == "hermes":
            legacy = [sys.executable, "-I", str(directory / "hermes-worker.py"),
                      "--binary", binary, "--prompt=" + opts["prompt"]]
            if opts["prompt"] == "--precheck":
                legacy.append("--precheck")
            if opts["log"]:
                legacy += ["--log", opts["log"]]
        command = [sys.executable, "-I", str(runtime), "run", "--project", str(project),
                   "--session", session, "--epoch", epoch, "--action", action, "--task", task,
                   "--worker", worker["id"], "--cwd", opts["cwd"], "--config-revision", str(revision),
                   "--timeout", str(timeout)]
        if action == "verify":
            command += ["--reviewer", worker["id"], "--role", "reviewer"]
        if integration is not None:
            command += ["--integration", integration]
        command += ["--"] + legacy
        # The runtime owns process groups, timeout, receipts and resource slots.
        # The adapter waits so its temporary DSH overlay stays available.
        return subprocess.run(command, env=env).returncode
    finally:
        if temporary_patch:
            try:
                os.unlink(temporary_patch)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (DispatchError, OSError) as exc:
        print("policy-dispatch: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
