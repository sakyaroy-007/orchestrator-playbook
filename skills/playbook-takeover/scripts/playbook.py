#!/usr/bin/env python3
"""Local, cooperating-session lifecycle runtime. Invoke with python3 -I.

The OS lock fences managed operations only. Raw editors, shell commands and other
machines are outside this protocol. Recovery never infers authority from age.
"""
import argparse
import contextlib
import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

try:
    import fcntl
except ImportError:
    fcntl = None

SCHEMA = 1
PACKAGE_VERSION = "3.1.0-dev.1"
RUNTIME_API = 2
RUNTIME_FILES = ("playbook.py", "playbook_work.py", "policy-dispatch.py", "playbook-foundation.py", "hermes-worker.py", "hermes_gateway.py", "wt.sh", "dispatch.sh")
CAPABILITIES = ["pause-first", "handoff-cancel", "config-patch", "attempt-cancel", "task-spec", "readiness", "immutable-evidence", "integration-results", "runtime-diagnostics", "hermes-gateway-admissions"]
CLIENTS = ("claude", "codex", "dsh", "hermes", "manual")
TASK_STATES = ("reserved", "running", "reported", "verified", "integrated", "blocked", "unknown")
ACTIVE = ("reserved", "running", "unknown")
PERMISSIONS = ("dispatch", "verify", "commit", "merge", "push", "cleanup", "worktree-create")
# Fixed, conservative local copy limits; exceeding one fails the entire checkpoint.
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
MAX_SNAPSHOT_FILES = 10000
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
DEFAULTS = {
    "schema_version": SCHEMA, "goal": "", "workers": [],
    "limits": {"agents": 2, "heavy_jobs": 1, "timeout_seconds": 7200, "max_attempts": 2},
    "permissions": {action: "ask" for action in PERMISSIONS},
    "git": {"integration_branch": "main", "merge_method": "merge", "push_cadence": "manual", "cleanup_mode": "retain"},
    "review": {"level": "adaptive"},
    "paths": {"plan": "docs/plan/README.md", "worker": "docs/plan/WORKER.md", "cards": "docs/plan/tasks", "handoff": "HANDOFF.md"},
}


class Failure(Exception):
    pass


class ExecutionUnknown(Failure):
    pass


def require(condition, message):
    if not condition:
        raise Failure(message)


def identifier(value, name="identity"):
    require(isinstance(value, str) and ID_RE.fullmatch(value), "Invalid %s: use 1-128 letters, digits, '.', '_', ':' or '-'" % name)
    return value


def timestamp():
    return time.time()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field: " + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("non-JSON numeric constant: " + value)

    try:
        require(not path.is_symlink(), "Refusing symlink metadata: %s" % path)
        with path.open("rb") as stream:
            return json.load(stream, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (OSError, ValueError) as exc:
        raise Failure("Cannot read JSON %s: %s" % (path, exc)) from exc


def sync_directory(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path, data):
    require(not path.is_symlink(), "Refusing symlink metadata: %s" % path)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, value):
    atomic_write(path, encoded(value))


def object_keys(value, allowed, name):
    require(isinstance(value, dict), "%s must be an object" % name)
    require(not (set(value) - set(allowed)), "Unknown %s fields: %s" % (name, ", ".join(sorted(set(value) - set(allowed)))))


def text(value, name):
    require(isinstance(value, str) and value.strip() and "\0" not in value, "%s must be a nonempty string without NUL" % name)
    return value


def relative_path(value, name):
    text(value, name)
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts and path.parts, "%s must be a relative project path without '..'" % name)
    return value


def validate_config(raw, goal=None):
    object_keys(raw, (*DEFAULTS, "runtime_api"), "config")
    config = copy.deepcopy(DEFAULTS)
    for key, value in raw.items():
        if isinstance(DEFAULTS.get(key), dict):
            allowed = (*DEFAULTS[key], "allow_manual", "independent") if key == "review" else DEFAULTS[key]
            object_keys(value, allowed, key)
            config[key].update(value)
        else:
            config[key] = copy.deepcopy(value)
    if "runtime_api" in raw:
        require(type(raw["runtime_api"]) is int and raw["runtime_api"] == RUNTIME_API, "Unsupported runtime_api; expected 2")
    for key in ("allow_manual", "independent"):
        if key in config["review"]:
            require(config.get("runtime_api") == RUNTIME_API and type(config["review"][key]) is bool,
                    "review.%s requires runtime_api:2 and a boolean" % key)
    if "goal" in raw:
        text(raw["goal"], "goal")
    if goal is not None:
        config["goal"] = goal
    require(type(config["schema_version"]) is int and config["schema_version"] == SCHEMA, "Unsupported config schema_version; expected 1")
    text(config["goal"], "goal")
    for key, value in config["limits"].items():
        require(type(value) is int and value > 0, "limits.%s must be a positive integer" % key)
    for key, value in config["permissions"].items():
        require(value in ("allow", "ask", "deny"), "permissions.%s must be allow, ask or deny" % key)
    git = config["git"]
    text(git["integration_branch"], "git.integration_branch")
    require(not git["integration_branch"].startswith("-") and not any(c.isspace() for c in git["integration_branch"]), "Invalid git.integration_branch")
    require(git["merge_method"] in ("merge", "squash", "rebase", "ff-only"), "Unsupported git.merge_method")
    require(git["push_cadence"] in ("manual", "after-merge", "stage", "never"), "Unsupported git.push_cadence")
    require(git["cleanup_mode"] in ("retain", "after-merge", "manual"), "Unsupported git.cleanup_mode")
    require(config["review"]["level"] in ("adaptive", "low", "medium", "high", "xhigh", "max"), "Unsupported review.level")
    for key, value in config["paths"].items():
        relative_path(value, "paths." + key)
    require(isinstance(config["workers"], list), "workers must be an array")
    seen = set()
    for worker in config["workers"]:
        object_keys(worker, ("id", "client", "model", "effort", "profile", "args", "hermes"), "worker")
        if "hermes" in worker:
            require(worker.get("client") == "hermes", "worker.hermes is only valid for the Hermes client")
            object_keys(worker["hermes"], ("approval",), "worker.hermes")
            require(worker["hermes"].get("approval") in ("inherit", "approve", "deny"),
                    "worker.hermes.approval must be inherit, approve or deny (responses to native approval requests)")
        identifier(worker.get("id"), "worker id")
        require(worker["id"] not in seen, "Duplicate worker id: " + worker["id"])
        seen.add(worker["id"])
        require(worker.get("client") in CLIENTS, "Worker client must be one of " + ", ".join(CLIENTS))
        for key in ("model", "effort"):
            worker.setdefault(key, {"mode": "inherit"})
            setting = worker[key]
            object_keys(setting, ("mode", "value"), "worker." + key)
            require(setting.get("mode") in ("inherit", "fixed", "recommend"), "worker.%s.mode must be inherit, fixed or recommend" % key)
            if setting["mode"] != "inherit":
                text(setting.get("value"), "worker." + key + ".value")
            else:
                require("value" not in setting, "An inherited %s must not contain a value" % key)
        if "profile" in worker:
            text(worker["profile"], "worker.profile")
        worker.setdefault("args", [])
        require(isinstance(worker["args"], list) and all(isinstance(arg, str) and "\0" not in arg for arg in worker["args"]), "worker.args must be an array of strings without NUL")
    return config


def machine_id():
    # Local identity, not a claim of cryptographic or multi-machine fencing.
    return digest((sys.platform + "\0" + platform.node() + "\0" + str(os.getuid())).encode())


def git_output(root, *args, optional=False):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    try:
        result = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    except OSError as exc:
        if optional:
            return None
        raise Failure("Cannot run Git: %s" % exc) from exc
    if result.returncode:
        if optional:
            return None
        raise Failure("Git %s failed in %s: %s" % (args[0], root, result.stderr.decode(errors="replace").strip()))
    return result.stdout


def git_worktrees(root):
    raw = git_output(root, "worktree", "list", "--porcelain", "-z")
    trees = []
    record = {}
    for field in raw.split(b"\0"):
        if not field:
            if record:
                trees.append(record)
                record = {}
            continue
        key, _, value = field.partition(b" ")
        record[key.decode("ascii")] = os.fsdecode(value)
    if record:
        trees.append(record)
    return trees


class Project:
    def __init__(self, path):
        self.requested = Path(path).expanduser().resolve()
        require(self.requested.is_dir(), "Project directory does not exist; create it first: %s" % self.requested)
        top = git_output(self.requested, "rev-parse", "--show-toplevel", optional=True)
        self.is_git = top is not None
        if self.is_git:
            self.root = Path(os.fsdecode(top).removesuffix("\n")).resolve()
            common = git_output(self.root, "rev-parse", "--git-common-dir")
            self.common = (self.root / os.fsdecode(common).removesuffix("\n")).resolve()
            self.runtime = self.common / "orchestrator-playbook"
            require(not (self.root / ".orchestrator" / "local" / "state.json").exists(), "A non-Git runtime already exists; automatic conversion to Git is unsupported. Preserve it and reconcile migration before creating another owner")
        else:
            require(git_output(self.requested, "rev-parse", "--is-bare-repository", optional=True) != b"true\n", "Bare Git projects are unsupported; use a checked-out working directory")
            self.root = self.requested
            self.common = None
            self.runtime = self.root / ".orchestrator" / "local"
        self.state_path = self.runtime / "state.json"
        self.lock_path = self.runtime / "lock"

    @contextlib.contextmanager
    def lock(self, create=False, shared=False, blocking=True):
        require(fcntl is not None and os.name == "posix", "OS file locking requires a supported POSIX machine")
        if create:
            if not self.is_git:
                require(not (self.root / ".orchestrator").is_symlink(), "Refusing symlink .orchestrator directory")
            require(not self.runtime.is_symlink(), "Refusing symlink runtime directory")
            self.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        require(self.runtime.is_dir() and not self.runtime.is_symlink(), "Project is not initialized; use init, or inspect discover")
        require(not self.lock_path.is_symlink(), "Refusing symlink OS lock")
        flags = os.O_RDONLY if shared else os.O_RDWR
        if create:
            flags |= os.O_CREAT
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(str(self.lock_path), flags, 0o600)
        except OSError as exc:
            raise Failure("Cannot open project OS lock: %s; run doctor to inspect the state" % exc) from exc
        try:
            operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            if not blocking:
                operation |= fcntl.LOCK_NB
            try:
                fcntl.flock(fd, operation)
            except OSError as exc:
                if not blocking and exc.errno in (errno.EACCES, errno.EAGAIN):
                    yield None  # A polling caller must defer its read while the lock is busy.
                    return
                raise Failure("OS locking failed: %s" % exc) from exc
            yield fd
        finally:
            os.close(fd)

    def load(self):
        require(not self.runtime.is_symlink(), "Refusing symlink runtime directory")
        state = read_json(self.state_path)
        require(isinstance(state, dict) and type(state.get("schema_version")) is int and state["schema_version"] == SCHEMA, "Unsupported runtime schema; do not overwrite it")
        for key in ("project_id", "machine", "config_path", "config_hash", "root", "owner", "epoch", "revision", "mode", "tasks", "attempts", "baseline"):
            require(key in state, "Runtime state missing %s; inspect doctor and recovery copies" % key)
        for key in ("project_id", "machine", "config_path", "config_hash", "root"):
            text(state[key], "runtime." + key)
        require(not (Path(state["root"]) / ".orchestrator").is_symlink(), "Refusing symlink canonical .orchestrator directory")
        require(type(state["epoch"]) is int and state["epoch"] > 0 and type(state["revision"]) is int and state["revision"] > 0, "Invalid runtime epoch/revision")
        require(state["mode"] in ("active", "paused", "prepared"), "Invalid runtime mode")
        require(isinstance(state["owner"], dict) and state["owner"].get("client") in CLIENTS, "Invalid runtime owner")
        identifier(state["owner"].get("session"), "owner session")
        require(isinstance(state["tasks"], dict) and isinstance(state["attempts"], list), "Invalid task/attempt ledger")
        require(Path(state["root"]).is_dir(), "Canonical project root is unavailable: " + state["root"])
        require(Path(state["config_path"]) == Path(state["root"]) / ".orchestrator" / "config.json", "Invalid canonical configuration path")
        if self.is_git:
            common = git_output(Path(state["root"]), "rev-parse", "--git-common-dir")
            require((Path(state["root"]) / os.fsdecode(common).removesuffix("\n")).resolve() == self.common, "Canonical root belongs to another Git common directory")
        else:
            require(Path(state["root"]).resolve() == self.root, "Non-Git project root changed")
        for task_id, task in state["tasks"].items():
            identifier(task_id, "task id")
            require(isinstance(task, dict) and task.get("state") in TASK_STATES, "Invalid task record: " + task_id)
            if "worktree" in task:
                text(task["worktree"], "task.worktree")
        ids = set()
        for attempt in state["attempts"]:
            require(isinstance(attempt, dict) and attempt.get("state") in TASK_STATES and attempt.get("action") in ("dispatch", "verify"), "Invalid attempt record")
            identifier(attempt.get("id"), "attempt id")
            require(attempt["id"] not in ids and attempt.get("task") in state["tasks"], "Duplicate or orphan attempt record")
            ids.add(attempt["id"])
            text(attempt.get("cwd"), "attempt.cwd")
            require(type(attempt.get("epoch")) is int and attempt["epoch"] > 0, "Invalid attempt epoch")
            for key in ("process", "supervisor"):
                identity = attempt.get(key)
                if identity is not None:
                    require(isinstance(identity, dict) and type(identity.get("pid")) is int and identity["pid"] > 0 and isinstance(identity.get("start"), str), "Invalid attempt process identity")
        return state

    def settings(self, state):
        config = validate_config(read_json(Path(state["config_path"])))
        require(digest(encoded(config)) == state["config_hash"], "Configuration changed outside configure, or a write was interrupted; owner may use configure --config FILE, or a new session may explicitly recover with takeover --recover --previous-stopped --config REVIEWED_FILE")
        require(not state.get("runtime_api_required") or config.get("runtime_api") == RUNTIME_API,
                "Project requires runtime_api:2; configuration cannot downgrade it")
        return config

    def save(self, state):
        state["updated_at"] = timestamp()
        write_json(self.state_path, state)

    def owned(self, state, session, epoch, modes=("active",)):
        require(state["machine"] == machine_id(), "State belongs to another machine; multi-machine takeover is unsupported")
        require(state["owner"]["session"] == session, "Ownership conflict: another session is the current owner; use explicit handoff/takeover")
        require(state["epoch"] == epoch, "Stale epoch: expected %s, received %s" % (state["epoch"], epoch))
        require(state["mode"] in modes, "Project is %s; this managed operation is stopped" % state["mode"])


def process_identity(pid):
    try:
        result = subprocess.run(["ps", "-p", str(pid), "-o", "lstart=", "-o", "stat="], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=dict(os.environ, LC_ALL="C", TZ="UTC"), check=False)
        fields = result.stdout.decode(errors="replace").strip().rsplit(None, 1)
        if result.returncode == 0 and len(fields) == 2:
            return {"pid": pid, "start": fields[0], "zombie": fields[1].startswith("Z")}
    except OSError:
        pass
    return None


def process_status(identity):
    if not isinstance(identity, dict) or not identity.get("pid") or not identity.get("start"):
        return "unknown"
    current = process_identity(identity["pid"])
    if current:
        if current["start"] != identity["start"]:
            return "reused"
        return "exited" if current["zombie"] else "alive"
    try:
        os.kill(identity["pid"], 0)
    except ProcessLookupError:
        return "exited"
    except (PermissionError, OSError):
        return "unknown"
    return "unknown"


def process_group_status(pgid):
    if type(pgid) is not int or pgid <= 0:
        return "unknown"
    try:
        result = subprocess.run(["ps", "-A", "-o", "pgid=", "-o", "stat="], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=dict(os.environ, LC_ALL="C"), check=False)
        if result.returncode:
            return "unknown"
        for line in result.stdout.decode(errors="replace").splitlines():
            fields = line.split()
            if len(fields) != 2 or not fields[0].isdigit():
                return "unknown"
            if int(fields[0]) == pgid and not fields[1].startswith(("Z", "X")):
                return "alive"
        return "exited"
    except OSError:
        return "unknown"


def outstanding(attempt):
    return attempt["state"] in ACTIVE and not attempt.get("reconciled")


def attempt_status(attempt):
    if not outstanding(attempt):
        return attempt["state"]
    child = process_status(attempt.get("process"))
    group = process_group_status(attempt.get("pgid", attempt.get("pid")))
    supervisor = process_status(attempt.get("supervisor"))
    return "running" if (child == "alive" or group == "alive") and supervisor == "alive" else "unknown"


def summarize(project, state, config):
    attempts = []
    for item in state["attempts"]:
        attempts.append({key: item.get(key) for key in ("id", "task", "action", "worker", "epoch", "state", "returncode", "late_result", "log", "process", "pgid", "cancel_request", "cancelled", "cancel_acknowledgement", "spec_hash", "content_error", "integration", "external_receipt", "external_execution")})
        if item.get("external_receipt"):
            try:
                attempts[-1]["external_execution"] = external_receipt(item)
            except Failure as exc:
                attempts[-1]["external_execution"] = {"state": "unknown", "error": str(exc)}
        attempts[-1]["execution"] = attempt_status(item)
    return {"schema_version": SCHEMA, "project_id": state["project_id"], "project_root": state["root"], "git": project.is_git,
            "runtime_path": str(project.runtime), "config_path": state["config_path"], "owner": state["owner"], "epoch": state["epoch"],
            "config_revision": state["revision"], "revision": state["revision"], "mode": state["mode"], "machine_matches": state["machine"] == machine_id(),
            "tasks": state["tasks"], "attempts": attempts, "policy": config, "checkpoint": state.get("checkpoint"),
            "checkpoint_failure": state.get("checkpoint_failure"), "configuration_recovery": state.get("configuration_recovery"), "handoff": state.get("handoff"),
            "handoff_history": state.get("handoff_history", []), "integrations": state.get("integrations", {}),
            "evidence_protocol": {key: "structured" if task.get("spec") else "legacy-note-only" for key, task in state["tasks"].items()}}


def git_status(root):
    return git_output(root, "-c", "core.quotePath=false", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none")


def baseline(project):
    if not project.is_git:
        entries = {}
        for relative in local_paths(project.root, include_directories=True):
            path = project.root / relative
            info = path.lstat()
            entries[relative] = [info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
        return {"git": False, "root": str(project.root), "entries_hash": digest(encoded(entries))}
    trees = git_worktrees(project.root)
    result = []
    for tree in trees:
        require("worktree" in tree and "bare" not in tree, "Bare worktrees are unsupported")
        root = Path(tree["worktree"])
        require(root.is_dir() and "prunable" not in tree, "Missing/prunable worktree needs explicit reconciliation: %s" % root)
        status = git_status(root)
        metadata = {}
        for relative in dirty_paths(status):
            path = root / relative
            try:
                info = path.lstat()
                metadata[relative] = [info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
            except FileNotFoundError:
                metadata[relative] = None
        index_path = root / os.fsdecode(git_output(root, "rev-parse", "--git-path", "index")).removesuffix("\n")
        index_stat = index_path.stat() if index_path.exists() else None
        result.append({"path": str(root.resolve()), "head": tree.get("HEAD"), "branch": tree.get("branch"), "status_hash": digest(status),
                       "dirty_metadata_hash": digest(encoded(metadata)), "index": [index_stat.st_size, index_stat.st_mtime_ns] if index_stat else None})
    return {"git": True, "worktrees": result}


def discover(project):
    clients = {name: shutil.which(name) for name in CLIENTS if name != "manual"}
    return {"project": str(project.root), "requested_project": str(project.requested), "git": project.is_git, "git_common_dir": str(project.common) if project.common else None,
            "runtime": str(project.runtime), "initialized": project.state_path.exists(), "legacy": (project.root / ".orchestrator").exists(),
            "clients": clients, "client_note": "Executable presence only; login, permissions and capabilities are not probed",
            "baseline": baseline(project)}


def dirty_paths(raw):
    fields = raw.split(b"\0")
    paths = set()
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        require(len(field) >= 4, "Malformed Git status output")
        code = field[:2]
        paths.add(os.fsdecode(field[3:]))
        if b"R" in code or b"C" in code:
            require(index < len(fields) and fields[index], "Malformed Git rename status")
            paths.add(os.fsdecode(fields[index]))
            index += 1
    return sorted(paths)


def local_paths(root, include_directories=False):
    found = []
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
        base = Path(directory)
        kept = []
        for name in sorted(dirs):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if relative in (".git", ".orchestrator/local"):
                continue
            if path.is_symlink():
                found.append(relative)
            else:
                kept.append(name)
                if include_directories:
                    found.append(relative)
        dirs[:] = kept
        found.extend((base / name).relative_to(root).as_posix() for name in sorted(files))
    return sorted(found)


class Snapshot:
    def __init__(self, destination=None):
        self.destination = destination
        self.total = 0
        self.count = 0

    def data(self, data):
        self.total += len(data)
        require(self.total <= MAX_SNAPSHOT_BYTES, "Checkpoint exceeds 256 MiB total; preserve large work separately before retrying")
        result = {"sha256": digest(data), "size": len(data)}
        if self.destination:
            blob = self.destination / "blobs" / result["sha256"]
            if not blob.exists():
                atomic_write(blob, data)
        return result

    def git_patch(self, root, cached=False):
        remaining = MAX_SNAPSHOT_BYTES - self.total
        limit = min(MAX_FILE_BYTES, remaining)
        budget = "per-artifact" if MAX_FILE_BYTES <= remaining else "remaining total"
        require(limit >= 0, "Checkpoint has exhausted its total byte budget")
        command = ["git", "-C", str(root), "-c", "diff.autoRefreshIndex=false", "diff"] + (["--cached"] if cached else [])
        command += ["--binary", "--no-ext-diff", "--no-textconv"]
        hasher = hashlib.sha256()
        copied = 0
        pending = None
        with contextlib.ExitStack() as stack:
            errors = stack.enter_context(tempfile.TemporaryFile())
            saved = None
            if self.destination:
                saved = stack.enter_context(tempfile.NamedTemporaryFile(prefix=".partial-git-", dir=self.destination / "blobs", delete=False))
                pending = Path(saved.name)
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, bufsize=0,
                                       env=dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C"), start_new_session=True)
            reaped = False
            try:
                while True:
                    # At most one byte beyond the remaining budget is consumed;
                    # pipe backpressure prevents Git from buffering a whole patch.
                    chunk = process.stdout.read(min(65536, limit - copied + 1))
                    if not chunk:
                        break
                    accepted = chunk[:limit - copied]
                    if accepted:
                        hasher.update(accepted)
                        if saved:
                            saved.write(accepted)
                        copied += len(accepted)
                        self.total += len(accepted)
                    require(len(accepted) == len(chunk), "Git patch exceeds %s snapshot budget (%s bytes); preserve large work separately before retrying" % (budget, limit))
                if saved:
                    saved.flush()
                    os.fsync(saved.fileno())
                returncode = process.wait()
                reaped = True
                if returncode:
                    errors.seek(0)
                    raise Failure("Git diff failed in %s: %s" % (root, errors.read(8192).decode(errors="replace").strip()))
            except BaseException:
                if not reaped:
                    stop_own_group(process)
                raise
            finally:
                process.stdout.close()
                if saved:
                    saved.flush()
                    os.fsync(saved.fileno())
        result = {"sha256": hasher.hexdigest(), "size": copied}
        if pending:
            blob = self.destination / "blobs" / result["sha256"]
            if blob.exists():
                pending.unlink()
            else:
                os.replace(pending, blob)
            sync_directory(blob.parent)
        return result

    def file(self, root, relative):
        relative_path(relative, "checkpoint path")
        path = root / relative
        # Never follow a symlink ancestor out of a worktree.
        parent = path.parent
        while parent != root:
            require(not parent.is_symlink(), "Checkpoint path has a symlink ancestor: %s" % path)
            parent = parent.parent
        self.count += 1
        require(self.count <= MAX_SNAPSHOT_FILES, "Checkpoint exceeds 10000 files; preserve large work separately before retrying")
        try:
            before = path.lstat()
        except FileNotFoundError:
            return {"kind": "deleted"}
        mode = stat.S_IMODE(before.st_mode)
        if stat.S_ISLNK(before.st_mode):
            target = os.fsencode(os.readlink(path))
            return {"kind": "symlink", "mode": mode, **self.data(target)}
        require(stat.S_ISREG(before.st_mode), "Cannot checkpoint directory/submodule/special file: %s; preserve and reconcile it explicitly" % path)
        require(before.st_size <= MAX_FILE_BYTES, "Checkpoint file exceeds 64 MiB: %s" % path)
        require(mode & 0o444, "Unreadable checkpoint file: %s" % path)
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            require(stat.S_ISREG(opened.st_mode) and (opened.st_ino, opened.st_dev) == (before.st_ino, before.st_dev), "Checkpoint file changed while opening: %s" % path)
            data = stream.read(MAX_FILE_BYTES + 1)
            after = os.fstat(stream.fileno())
        require(len(data) <= MAX_FILE_BYTES and (before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "Checkpoint file changed during read: %s" % path)
        return {"kind": "file", "mode": mode, **self.data(data)}

    def capture(self, project):
        initial = baseline(project)
        entries = []
        roots = [Path(item["path"]) for item in initial["worktrees"]] if project.is_git else [project.root]
        for root in roots:
            if project.is_git:
                require(not git_output(root, "ls-files", "--unmerged", "-z"),
                        "Cannot checkpoint an unmerged index in %s; resolve conflicts or preserve every index stage explicitly before retrying" % root)
                status = git_status(root)
                paths = dirty_paths(status)
                entry = {"path": str(root), "status": self.data(status), "staged_patch": self.git_patch(root, cached=True),
                         "unstaged_patch": self.git_patch(root)}
            else:
                paths = local_paths(root)
                directories = {}
                for relative in local_paths(root, include_directories=True):
                    info = (root / relative).lstat()
                    if stat.S_ISDIR(info.st_mode):
                        directories[relative] = stat.S_IMODE(info.st_mode)
                entry = {"path": str(root), "directories": directories}
            entry["files"] = {path: self.file(root, path) for path in paths}
            entries.append(entry)
        require(initial == baseline(project), "Project baseline changed during checkpoint; stop writers and retry")
        return {"baseline": initial, "worktrees": entries, "bytes": self.total, "files": self.count}


def checkpoint(project, state, config):
    checkpoint_id = uuid.uuid4().hex
    container = project.runtime / "checkpoints"
    require(not container.is_symlink(), "Refusing symlink checkpoint directory")
    container.mkdir(exist_ok=True, mode=0o700)
    pending = container / (".pending-" + checkpoint_id)
    final = container / checkpoint_id
    pending.mkdir(mode=0o700)
    (pending / "blobs").mkdir(mode=0o700)
    try:
        first = Snapshot(pending).capture(project)
        second = Snapshot().capture(project)
        require(first == second, "Project content changed during checkpoint; stop writers and retry")
        require(project.settings(state) == config, "Configuration changed during checkpoint")
        protocol = {}
        if state.get("evidence") or state.get("integrations") or any(a.get("external_receipt") for a in state["attempts"]):
            extra = Snapshot(pending)
            extra.total, extra.count = first["bytes"], first["files"]
            protocol = work_protocol().checkpoint_records(project, state, extra)
        manifest = {"schema_version": SCHEMA, "id": checkpoint_id, "complete": True, "created_at": timestamp(), "project_id": state["project_id"],
                    "machine": state["machine"], "epoch": state["epoch"], "revision": state["revision"], "config": config,
                    "owner": state["owner"], "mode": state["mode"], "project_root": state["root"],
                    "tasks": copy.deepcopy(state["tasks"]), "attempts": copy.deepcopy(state["attempts"]), "capture": first,
                    "work_protocol": protocol, "runtime_api_required": state.get("runtime_api_required")}
        write_json(pending / "manifest.json", manifest)
        os.replace(pending, final)
        sync_directory(container)
    except (Failure, OSError) as exc:
        # Retain partial recovery copies, explicitly marked incomplete, never prepare a handoff.
        with contextlib.suppress(OSError, Failure):
            write_json(pending / "failure.json", {"complete": False, "error": str(exc), "created_at": timestamp()})
        state["checkpoint_failure"] = {"path": str(pending), "error": str(exc)}
        project.save(state)
        raise Failure("Checkpoint incomplete: %s. Partial copies retained at %s" % (exc, pending)) from exc
    result = {"id": checkpoint_id, "path": str(final), "manifest_hash": digest(encoded(manifest)), "complete": True}
    state["checkpoint"] = result
    state.pop("checkpoint_failure", None)
    state["baseline"] = first["baseline"]
    project.save(state)
    return result


def verify_checkpoint(project, state, checkpoint_record, current=False):
    identifier(checkpoint_record.get("id"), "checkpoint id")
    location = project.runtime / "checkpoints" / checkpoint_record["id"]
    require(not location.is_symlink() and not (location / "blobs").is_symlink(), "Recovery directory is a symlink")
    manifest = read_json(location / "manifest.json")
    require(digest(encoded(manifest)) == checkpoint_record.get("manifest_hash"), "Recovery manifest changed or is corrupt; use explicit recovery")
    require(manifest.get("complete") is True and manifest.get("project_id") == state["project_id"] and manifest.get("machine") == state["machine"], "Recovery manifest identity/completeness mismatch")
    verified_blobs = {}
    for entry in manifest["capture"]["worktrees"] + [{"files": manifest.get("work_protocol", {}).get("files", {})}]:
        records = [entry[key] for key in ("status", "staged_patch", "unstaged_patch") if key in entry]
        records += list(entry["files"].values())
        for record in records:
            if "sha256" not in record:
                continue
            sha = record["sha256"]
            require(isinstance(sha, str) and re.fullmatch("[a-f0-9]{64}", sha), "Invalid recovery blob hash")
            require(type(record.get("size")) is int and 0 <= record["size"] <= MAX_SNAPSHOT_BYTES, "Invalid recovery blob size")
            if sha not in verified_blobs:
                blob = location / "blobs" / sha
                require(not blob.is_symlink() and blob.is_file(), "Missing recovery blob: %s" % blob)
                require(blob.stat().st_size == record["size"], "Recovery blob size mismatch: %s" % blob)
                with blob.open("rb") as stream:
                    data = stream.read(record["size"] + 1)
                require(len(data) == record["size"] and digest(data) == sha, "Recovery blob changed or is corrupt: %s" % blob)
                verified_blobs[sha] = len(data)
            require(verified_blobs[sha] == record["size"], "Conflicting recovery blob sizes")
    if current:
        require(manifest["revision"] == state["revision"] and manifest["config"] == project.settings(state), "Configuration revision changed since handoff; use explicit recovery")
        require(Snapshot().capture(project) == manifest["capture"], "Project baseline/content changed since handoff; inspect doctor, then use explicit recovery with --previous-stopped")
    return manifest


def init_project(project, args):
    identifier(args.session, "session")
    supplied_raw = read_json(Path(args.config).resolve()) if args.config else {}
    config_path = project.root / ".orchestrator" / "config.json"
    # Reject invalid new-project inputs before creating runtime metadata. Recheck
    # under the lock: another initializer may establish a policy in the meantime.
    if not project.state_path.exists():
        initial_raw = supplied_raw
        if isinstance(initial_raw, dict) and not config_path.exists():
            initial_raw = {"runtime_api": RUNTIME_API, **initial_raw}
        validate_config(initial_raw, goal=args.goal)
    with project.lock(create=True):
        if project.state_path.exists():
            state = project.load()
            project.owned(state, args.session, state["epoch"], modes=("active", "paused", "prepared"))
            require(state["owner"]["client"] == args.client, "Existing session has a different client")
            config = project.settings(state)
            if config.get("runtime_api") == RUNTIME_API and isinstance(supplied_raw, dict):
                supplied_raw = {"runtime_api": RUNTIME_API, **supplied_raw}
            supplied = validate_config(supplied_raw, goal=args.goal)
            require(config["goal"] == args.goal and (not args.config or supplied == config), "Existing initialization differs; use configure with the current epoch")
            return summarize(project, state, config)
        control = project.root / ".orchestrator"
        require(not control.is_symlink(), "Refusing symlink .orchestrator directory")
        existing = [p for p in control.iterdir() if p.name != "local"] if control.exists() else []
        require(not existing or args.adopt, "Existing .orchestrator files require explicit init --adopt; they will be preserved")
        control.mkdir(exist_ok=True)
        if config_path.exists():
            config = validate_config(read_json(config_path))
            supplied = validate_config(supplied_raw, goal=args.goal)
            require(config["goal"] == args.goal and (not args.config or config == supplied), "Existing portable config conflicts; preserve it and supply matching goal/config")
        else:
            if isinstance(supplied_raw, dict):
                supplied_raw = {"runtime_api": RUNTIME_API, **supplied_raw}
            config = validate_config(supplied_raw, goal=args.goal)
            write_json(config_path, config)
        if not project.is_git:
            ignore = control / ".gitignore"
            require(not ignore.is_symlink(), "Refusing symlink local ignore file")
            previous = ignore.read_bytes() if ignore.exists() else b""
            if b"/local/" not in previous.splitlines():
                atomic_write(ignore, previous + (b"\n" if previous and not previous.endswith(b"\n") else b"") + b"/local/\n")
        state = {"schema_version": SCHEMA, "project_id": uuid.uuid4().hex, "machine": machine_id(), "root": str(project.root),
                 "config_path": str(config_path), "config_hash": digest(encoded(config)), "revision": 1, "epoch": 1,
                 "owner": {"session": args.session, "client": args.client}, "mode": "active", "tasks": {}, "attempts": [],
                 "baseline": baseline(project), "created_at": timestamp(), "runtime_api_required": config.get("runtime_api")}
        project.save(state)
        return summarize(project, state, config)


def preserve_runtime_api(state, raw):
    required = state.get("runtime_api_required") == RUNTIME_API
    with contextlib.suppress(Failure):
        existing = read_json(Path(state["config_path"]))
        required = required or (isinstance(existing, dict) and existing.get("runtime_api") == RUNTIME_API)
    if required and isinstance(raw, dict):
        raw = {"runtime_api": RUNTIME_API, **raw}
        require(raw.get("runtime_api") == RUNTIME_API, "Cannot downgrade runtime_api:2")
    return raw


def merge_patch(original, patch):
    require(patch is not None, "Configuration patch cannot contain null")
    if isinstance(patch, dict):
        result = copy.deepcopy(original) if isinstance(original, dict) else {}
        for key, value in patch.items():
            result[key] = merge_patch(result.get(key), value)
        return result
    if isinstance(patch, list):
        for value in patch:
            merge_patch(None, value)
    return copy.deepcopy(patch)


def changed_paths(before, after, prefix=""):
    if isinstance(before, dict) and isinstance(after, dict):
        return [path for key in sorted(set(before) | set(after))
                for path in changed_paths(before.get(key), after.get(key), prefix + ("." if prefix else "") + key)]
    return [prefix] if before != after else []


def configure(project, args):
    raw = read_json(Path(args.patch or args.config).resolve())
    with project.lock():
        state = project.load()
        project.owned(state, args.session, args.epoch, modes=("active", "paused"))
        previous = None
        if args.patch:
            object_keys(raw, (*DEFAULTS, "runtime_api"), "patch")
            previous = project.settings(state)
            raw = merge_patch(previous, raw)
        else:
            with contextlib.suppress(Failure):
                previous = project.settings(state)
        goal = raw.get("goal") if isinstance(raw, dict) else None
        if isinstance(raw, dict) and "goal" not in raw:
            goal = project.settings(state)["goal"]
        config = validate_config(preserve_runtime_api(state, raw), goal=goal)
        # Persist the protocol floor before the two-file configuration transaction.
        if config.get("runtime_api") == RUNTIME_API and not state.get("runtime_api_required"):
            state["runtime_api_required"] = RUNTIME_API
            project.save(state)
        write_json(Path(state["config_path"]), config)
        state["config_hash"] = digest(encoded(config))
        state["revision"] += 1
        project.save(state)
        return {**summarize(project, state, config), "changed_paths": changed_paths(previous, config) if previous is not None else ["*"]}


def lifecycle(project, args):
    with project.lock():
        state = project.load()
        if args.command == "takeover":
            config = None if args.config else project.settings(state)
            return takeover(project, state, config, args)
        config = project.settings(state)
        modes = ("active", "paused", "prepared") if args.command == "handoff" else ("active", "paused")
        project.owned(state, args.session, args.epoch, modes=modes)
        if args.command == "resume":
            current = baseline(project)
            changed = current != state["baseline"]
            state["mode"] = "active"
            project.save(state)
            return {**summarize(project, state, config), "baseline_changed": changed, "current_baseline": current}
        if args.command == "handoff" and args.cancel:
            if state["mode"] == "paused" and state.get("handoff_history"):
                last = state["handoff_history"][-1]
                if last.get("cancelled_by") == args.session and last.get("epoch") == args.epoch:
                    return {**summarize(project, state, config), "cancelled_handoff": last["id"], "already_cancelled": True}
            require(state["mode"] == "prepared", "Only a prepared handoff can be withdrawn")
            previous = state.pop("handoff")
            previous.update(cancelled_by=args.session, cancelled_at=timestamp())
            state.setdefault("handoff_history", []).append(previous)
            state["mode"] = "paused"
            project.save(state)
            return {**summarize(project, state, config), "cancelled_handoff": previous["id"], "already_cancelled": False}
        if args.command == "handoff" and state["mode"] == "prepared":
            require(state["handoff"].get("to") == args.to, "Prepared handoff has a different target")
            verify_checkpoint(project, state, state["handoff"]["checkpoint"], current=True)
            return {**summarize(project, state, config), "handoff_id": state["handoff"]["id"]}
        if args.command == "handoff" and args.to:
            identifier(args.to, "target session")
            require(args.to != args.session, "Handoff target must be a different session")
        if args.command == "pause":
            state["mode"] = "paused"
            state["checkpoint_failure"] = {"path": None, "error": "Pause is durable; recovery checkpoint has not completed"}
            project.save(state)
        result = checkpoint(project, state, config)
        if args.command == "handoff":
            state["mode"] = "prepared"
            state["handoff"] = {"id": uuid.uuid4().hex, "from": args.session, "to": args.to, "epoch": state["epoch"], "revision": state["revision"], "checkpoint": result}
            project.save(state)
        output = summarize(project, state, config)
        if args.command == "handoff":
            output["handoff_id"] = state["handoff"]["id"]
        return output


def recover_configuration(project, state, reviewed, args):
    try:
        if project.settings(state) == reviewed:
            return reviewed
    except Failure:
        pass
    config_path = Path(state["config_path"])
    require(not config_path.is_symlink(), "Refusing symlink configuration; preserve and reconcile it explicitly")
    container = project.runtime / "configuration-recovery"
    require(not container.is_symlink(), "Refusing symlink configuration recovery directory")
    container.mkdir(mode=0o700, exist_ok=True)
    recovery_id = uuid.uuid4().hex
    evidence = container / recovery_id
    evidence.mkdir(mode=0o700)
    original = config_path.read_bytes() if config_path.exists() else None
    atomic_write(evidence / "state-before.json", project.state_path.read_bytes())
    if original is not None:
        atomic_write(evidence / "config-before.json", original)
    write_json(evidence / "reviewed-config.json", reviewed)
    receipt = {"id": recovery_id, "path": str(evidence), "session": args.session, "epoch": state["epoch"],
               "previous_revision": state["revision"], "revision": state["revision"] + 1,
               "previous_config_hash": state["config_hash"], "config_hash": digest(encoded(reviewed)),
               "original_config_missing": original is None, "original_config_sha256": digest(original) if original is not None else None,
               "at": timestamp(), "complete": True}
    write_json(evidence / "manifest.json", receipt)
    sync_directory(container)
    # The explicit reviewed file authorizes this repair. Evidence is durable before
    # replacing either side of the interrupted configuration transaction.
    if reviewed.get("runtime_api") == RUNTIME_API:
        state["runtime_api_required"] = RUNTIME_API
        project.save(state)
    write_json(config_path, reviewed)
    state["config_hash"] = receipt["config_hash"]
    state["revision"] = receipt["revision"]
    state["configuration_recovery"] = receipt
    project.save(state)
    return reviewed


def takeover(project, state, config, args):
    identifier(args.session, "session")
    require(state["machine"] == machine_id(), "State belongs to another machine; multi-machine takeover is unsupported")
    require(not (args.recover and args.handoff), "Choose a prepared handoff or --recover, not both")
    require(not args.config or (args.recover and args.previous_stopped), "Takeover --config requires --recover --previous-stopped and an explicitly reviewed configuration")
    reviewed = validate_config(preserve_runtime_api(state, read_json(Path(args.config).resolve()))) if args.config else None
    receipt = state.get("takeover")
    if receipt and receipt["session"] == args.session and state["owner"] == {"session": args.session, "client": args.client}:
        if (args.handoff and receipt.get("handoff") == args.handoff) or (args.recover and args.previous_stopped and receipt.get("recovered")):
            if reviewed is not None:
                config = project.settings(state)
                require(reviewed == config, "Recovery already completed with different settings; current owner must use configure")
            return summarize(project, state, config)
    require(state["owner"]["session"] != args.session, "Current owner must use resume, not takeover")
    if args.recover:
        require(args.previous_stopped, "Unprepared recovery requires --previous-stopped: explicit attestation that the previous commander was stopped/replaced")
        if reviewed is not None:
            config = recover_configuration(project, state, reviewed, args)
        checkpoint(project, state, config)
    else:
        require(args.handoff and not args.previous_stopped, "Prepared takeover requires --handoff ID; unprepared recovery needs --recover --previous-stopped")
        handoff = state.get("handoff")
        require(state["mode"] == "prepared" and handoff and handoff["id"] == args.handoff, "No matching prepared handoff; use explicit recovery for an interruption")
        require(handoff.get("to") in (None, args.session), "Handoff is designated for another session")
        require(handoff["epoch"] == state["epoch"] and handoff["revision"] == state["revision"], "Handoff epoch/revision changed")
        verify_checkpoint(project, state, handoff["checkpoint"], current=True)
    previous = copy.deepcopy(state["owner"])
    for task in state["tasks"].values():
        if task["state"] in ("running", "unknown"):
            task.update(state="unknown", needs_reconciliation=True)
    for attempt in state["attempts"]:
        if outstanding(attempt):
            attempt["state"] = "unknown"
            task = state["tasks"][attempt["task"]]
            task["state"] = "unknown"
            task["needs_reconciliation"] = True
    state["epoch"] += 1
    state["owner"] = {"session": args.session, "client": args.client}
    state["mode"] = "active"
    state["takeover"] = {"session": args.session, "previous": previous, "handoff": args.handoff, "recovered": args.recover, "at": timestamp()}
    state.pop("handoff", None)
    project.save(state)
    return summarize(project, state, config)


def task_worktree(project, path):
    root = Path(path).expanduser().resolve()
    require(root.is_dir(), "Task working directory does not exist: %s" % root)
    if project.is_git:
        common = git_output(root, "rev-parse", "--git-common-dir", optional=True)
        require(common is not None and (root / os.fsdecode(common).removesuffix("\n")).resolve() == project.common, "Task working directory is not in this shared Git project")
    else:
        require(root == project.root or project.root in root.parents, "Non-Git task directory must be inside the project")
    return root


_work_module = None


def work_protocol():
    global _work_module
    if _work_module is None:
        path = Path(__file__).resolve().with_name("playbook_work.py")
        require(path.is_file() and not path.is_symlink(), "Required runtime dependency playbook_work.py is missing; copy the complete runtime bundle")
        spec = importlib.util.spec_from_file_location("playbook_work", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.bind(globals())
        _work_module = module
    return _work_module


def record_task(project, args):
    identifier(args.id, "task id")
    with project.lock():
        state = project.load()
        project.owned(state, args.session, args.epoch)
        config = project.settings(state)
        old = state["tasks"].get(args.id, {})
        args.state = args.state or ("reserved" if args.spec else None)
        require(args.state is not None, "Task requires --state or --spec")
        active = [attempt for attempt in state["attempts"] if attempt["task"] == args.id and outstanding(attempt)]
        require(not args.spec or (not active and old.get("state") not in ("running", "unknown")), "Cannot revise a specification while execution is outstanding")
        reconciling = args.state not in ("running", "unknown") and (active or old.get("state") in ("running", "unknown"))
        if reconciling:
            text(args.note, "reconciliation note (explain execution outcome/evidence)")
            for attempt in active:
                require(process_status(attempt.get("process")) != "alive" and process_status(attempt.get("supervisor")) != "alive"
                        and process_group_status(attempt.get("pgid", attempt.get("pid"))) != "alive",
                        "Task still has a live process/supervisor/group; do not release its reservation")
                attempt["reconciled"] = {"session": args.session, "epoch": args.epoch, "note": args.note, "at": timestamp()}
                attempt["state"] = "blocked"
        if args.state in ("verified", "integrated") and not (old.get("spec") or args.spec):
            text(args.note, "acceptance/integration evidence note")
        root = task_worktree(project, args.worktree) if args.worktree else None
        if active and root and old.get("worktree"):
            require(str(root) == old["worktree"], "Cannot change the working directory of active work")
        task = {**old, "state": args.state, "updated_at": timestamp(), "recorded_by": args.session, "epoch": args.epoch}
        if root:
            task["worktree"] = str(root)
        if args.note is not None:
            task["note"] = args.note
        if reconciling:
            task.pop("needs_reconciliation", None)
        if args.spec:
            work_protocol().api_required(config)
            work_protocol().install_spec(state, args.id, task, read_json(Path(args.spec).resolve()))
        if task.get("spec"):
            work_protocol().record_implementers(state, args.id, task, args.session)
        state["tasks"][args.id] = task
        if task.get("spec") and args.state in ("verified", "integrated"):
            work_protocol().api_required(config)
            if args.state == "verified":
                receipt = work_protocol().acceptance(project, state, config, args.id)
                task["accepted_evidence"] = receipt["id"]
            else:
                record = state.get("integrations", {}).get(task.get("integration"))
                require(record is not None, "Structured integration requires integration begin/finish")
                work_protocol().integration_current(project, state, record, (record["id"],))
        project.save(state)
        return {"task": task, "id": args.id, "epoch": state["epoch"], "revision": state["revision"]}


def permission(config, action):
    value = config["permissions"].get(action, "ask")
    require(value == "allow", "Action %s is %s; record the user's authorization with configure before running it" % (action, value))


def ensure_command(command, cwd):
    require(command and command[0] and all(isinstance(arg, str) and "\0" not in arg for arg in command), "Supply a nonempty command after --; arguments are executed without a shell")
    # subprocess resolves both slash-containing commands and relative/empty PATH
    # entries after changing to the child's cwd. Validate the same search without
    # changing the caller's directory or rewriting the literal execution argv.
    search = os.pathsep.join(os.path.join(str(cwd), entry) for entry in os.get_exec_path())
    executable = os.path.join(str(cwd), command[0]) if os.path.dirname(command[0]) else command[0]
    require(shutil.which(executable, path=search) is not None, "Command executable not found: %s (cwd: %s)" % (command[0], cwd))


def cleanup_checks(project, state, config):
    require(config["git"]["cleanup_mode"] != "retain", "git.cleanup_mode=retain prevents cleanup; configure the intended retention policy first")
    require(not any(outstanding(a) for a in state["attempts"]), "Cleanup blocked by reserved/running/unknown attempts")
    require(not any(t["state"] in ("running", "unknown") for t in state["tasks"].values()), "Cleanup blocked by running/unknown tasks")
    require(state.get("checkpoint"), "Cleanup needs a complete checkpoint with recovery evidence first")
    verify_checkpoint(project, state, state["checkpoint"], current=True)
    main = config["git"]["integration_branch"]
    git_output(project.root, "rev-parse", "--verify", main + "^{commit}")
    for tree in git_worktrees(project.root):
        root = Path(tree["worktree"])
        require(not git_status(root), "Cleanup blocked by dirty/untracked work: %s" % root)
        require(not git_output(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"), "Cleanup blocked by ignored files without recovery evidence: %s" % root)
        require(git_output(root, "merge-base", "--is-ancestor", tree["HEAD"], main, optional=True) is not None, "Cleanup blocked by unmerged work: %s" % root)


def guard(project, args):
    ensure_command(args.argv, project.root)
    with project.lock() as lock_fd:
        state = project.load()
        project.owned(state, args.session, args.epoch)
        config = project.settings(state)
        if args.action != "scaffold":
            permission(config, args.action)
            require(project.is_git, "Non-Git projects do not acquire Git actions")
        if args.action == "push":
            require(config["git"]["push_cadence"] not in ("manual", "never"), "git.push_cadence=%s prevents managed push; record the intended cadence/authorization with configure" % config["git"]["push_cadence"])
            work_protocol().push_gate(project, state, config, args.argv)
        if args.action == "cleanup":
            cleanup_checks(project, state, config)
        state["last_guard"] = {"action": args.action, "session": args.session, "epoch": args.epoch, "command": args.argv, "state": "running", "at": timestamp()}
        project.save(state)
        try:
            result = subprocess.run(args.argv, cwd=project.root, env=dict(os.environ, PLAYBOOK_GUARDED="1", PLAYBOOK_PROJECT=state["root"]),
                                    stdout=sys.stderr, pass_fds=(lock_fd,), check=False)
        except OSError as exc:
            state["last_guard"].update(state="blocked", error=str(exc))
            project.save(state)
            raise Failure("Guarded command could not start: %s" % exc) from exc
        state["last_guard"].update(state="reported" if result.returncode == 0 else "blocked", returncode=result.returncode)
        project.save(state)
        return {"action": args.action, "returncode": result.returncode, "epoch": state["epoch"]}, result.returncode


def select_worker(config, args):
    if not args.worker:
        require(args.action != "dispatch", "Dispatch requires --worker ID from the configured roster")
        return None
    workers = [worker for worker in config["workers"] if worker["id"] == args.worker]
    require(workers, "Worker is not configured: " + args.worker)
    worker = workers[0]
    for key in ("model", "effort"):
        require(worker[key]["mode"] != "recommend", "Resolve the worker's recommended %s with configure before launching" % key)
    # The sibling adapter validates actual CLI mappings. Raw commands cannot silently
    # discard requested settings. This marker is cooperation, not a security boundary.
    customized = worker["model"]["mode"] != "inherit" or worker["effort"]["mode"] != "inherit" or worker.get("profile") or worker["args"]
    require(not customized or os.environ.get("PLAYBOOK_DISPATCHED") == "1", "Worker has explicit model/effort/profile/args; use the validating dispatch adapter (raw run does not translate client settings)")
    return worker


def resources_available(project, state, config, args, cwd):
    attempts = [item for item in state["attempts"] if outstanding(item)]
    covered = {item["task"] for item in attempts}
    external = [task for key, task in state["tasks"].items() if key not in covered and key != args.task
                and (task["state"] in ("running", "unknown") or (task.get("spec") and task["state"] == "reserved"))]
    require(project.is_git or not (attempts or external), "Non-Git projects run serially; reconcile existing work first")
    agents = sum(item["action"] == "dispatch" or bool(item.get("worker")) for item in attempts) + len(external)
    heavy = sum(item["action"] == "verify" for item in attempts) + len(external)
    if args.action == "dispatch" or args.worker:
        require(agents < config["limits"]["agents"], "Agent limit reached (reserved/running/unknown work counts)")
    if args.action == "verify":
        require(heavy < config["limits"]["heavy_jobs"], "Heavy-job limit reached (reserved/running/unknown work counts)")
    def workspace(path):
        path = Path(path)
        if project.is_git:
            top = git_output(path, "rev-parse", "--show-toplevel", optional=True)
            require(top is not None, "Active work directory disappeared; reconcile it before dispatch")
            return Path(os.fsdecode(top).removesuffix("\n")).resolve()
        return project.root

    occupied = [item["cwd"] for item in attempts] + [task.get("worktree", str(project.root)) for task in external]
    target = workspace(cwd)
    require(not any(workspace(path) == target for path in occupied), "Worktree already has reserved/running/unknown work")


def mark_interrupted(project, attempt_id, message):
    with project.lock():
        state = project.load()
        attempt = next(item for item in state["attempts"] if item["id"] == attempt_id)
        attempt.update(state="unknown", interruption=message, interrupted_at=timestamp())
        task = state["tasks"][attempt["task"]]
        task.update(state="unknown", needs_reconciliation=True)
        project.save(state)


class CancellationRequested(Exception):
    pass


def cancel_attempt(project, args):
    identifier(args.attempt, "attempt ID")
    text(args.reason, "cancellation reason")
    with project.lock():
        state = project.load()
        project.owned(state, args.session, args.epoch, modes=("active", "paused"))
        project.settings(state)
        attempt = next((item for item in state["attempts"] if item["id"] == args.attempt), None)
        require(attempt is not None, "Unknown attempt ID")
        if not outstanding(attempt):
            return {"attempt": attempt, "status": "terminal", "requested": bool(attempt.get("cancel_request"))}
        if not attempt.get("cancel_request"):
            attempt["cancel_request"] = {"reason": args.reason, "session": args.session, "epoch": args.epoch, "at": timestamp()}
            project.save(state)
        return {"attempt": attempt, "status": "requested" if attempt_status(attempt) == "running" else "unknown", "requested": True}


def cancellation_requested(project, attempt_id):
    # Reading never signals a PID. Only this invocation's live supervisor, still
    # retaining its unreaped Popen leader, may act on the durable request. A busy
    # project lock must not delay that supervisor's process-group deadline.
    with project.lock(shared=True, blocking=False) as lock_fd:
        if lock_fd is None:
            return False
        state = project.load()
        attempt = next(item for item in state["attempts"] if item["id"] == attempt_id)
        return bool(attempt.get("cancel_request"))


def wait_for_process_group(process, deadline, cancelled=None):
    # Keep the leader unreaped while any group member can still work. Its zombie
    # retains the PID, so the PGID cannot be reused before a deadline-triggered kill.
    while True:
        status = process_group_status(process.pid)
        if status == "exited":
            try:
                return process.wait(timeout=1)
            except subprocess.TimeoutExpired as exc:
                raise ExecutionUnknown("Process group disappearance could not be confirmed") from exc
        if status == "unknown":
            raise ExecutionUnknown("Cannot inspect the managed process group; its reservation remains unknown")
        if cancelled and cancelled():
            raise CancellationRequested()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, 0)
        time.sleep(min(0.1, remaining))


def external_receipt(attempt):
    path = Path(attempt["external_receipt"])
    require(path.is_file() and path.stat().st_size <= 1024 * 1024, "Missing or oversized Hermes execution receipt")
    receipt = read_json(path)
    require(isinstance(receipt, dict) and receipt.get("protocol") == "hermes-gateway-v1"
            and receipt.get("attempt_id") == attempt["id"], "Hermes receipt identity mismatch")
    return receipt


def confirm_external(attempt, returncode):
    try:
        receipt = external_receipt(attempt)
        if receipt.get("state") == "not_submitted" and returncode != 0:
            return receipt
        require(receipt.get("state") == "terminal" and receipt.get("tracked_resources_idle") is True
                and receipt.get("turn_outcome") in ("completed", "failed", "cancelled", "interrupted"),
                "Hermes admission/resource termination is unconfirmed")
        require(returncode != 0 or (receipt.get("returncode") == 0 and receipt.get("turn_outcome") == "completed"),
                "Hermes success lacks a completed admission receipt")
        return receipt
    except Failure as exc:
        raise ExecutionUnknown(str(exc) + "; preserve the receipt and reconcile before redispatch") from exc


def stop_own_group(process, grace=1):
    # start_new_session gives precisely this invocation its own process group.
    # The caller has not reaped its leader, including when that leader exited early.
    if process_group_status(process.pid) == "exited":
        wait_for_process_group(process, time.monotonic() + 1)
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError as exc:
        # Darwin may return EPERM for a group containing only an exited leader.
        if process_group_status(process.pid) != "exited":
            raise ExecutionUnknown("Cannot signal the managed process group") from exc
    try:
        wait_for_process_group(process, time.monotonic() + grace)
        return
    except (subprocess.TimeoutExpired, ExecutionUnknown):
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError as exc:
        if process_group_status(process.pid) != "exited":
            raise ExecutionUnknown("Cannot stop the managed process group") from exc
    try:
        wait_for_process_group(process, time.monotonic() + 1)
    except subprocess.TimeoutExpired as exc:
        raise ExecutionUnknown("Managed process group did not stop; retain its reservation and reconcile explicitly") from exc


def run_job(project, args):
    identifier(args.task, "task id")
    process = None
    attempt_id = None
    old_handlers = {}

    def interrupted(signum, frame):
        raise KeyboardInterrupt("signal %s" % signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, interrupted)
    try:
        with project.lock():
            state = project.load()
            project.owned(state, args.session, args.epoch)
            config = project.settings(state)
            if args.config_revision is not None:
                require(args.config_revision == state["revision"], "Configuration revision changed; re-read status and rebuild the command before retrying")
            permission(config, args.action)
            timeout = args.timeout if args.timeout is not None else config["limits"]["timeout_seconds"]
            require(0 < timeout <= config["limits"]["timeout_seconds"], "--timeout must be positive and no greater than limits.timeout_seconds")
            worker = select_worker(config, args)
            hermes = bool(worker and worker["client"] == "hermes")
            if hermes:
                require("hermes" in worker, "Configure worker.hermes.approval explicitly before managed Hermes dispatch")
                bridge = str(Path(__file__).resolve().with_name("hermes-worker.py"))
                require(len(args.argv) >= 3 and args.argv[:3] == [sys.executable, "-I", bridge],
                        "Managed Hermes requires its matched gateway bridge; use policy-dispatch.py")
            task = state["tasks"].get(args.task)
            if task:
                require(task["state"] not in ("running", "unknown", "integrated") and not task.get("needs_reconciliation"), "Task has running/unknown/integrated work; explicitly reconcile it before another attempt")
                if args.action == "dispatch":
                    require(task["state"] in ("reserved", "blocked"), "Task already has a report/acceptance; explicitly record a new reservation before dispatch")
            require(not any(a["task"] == args.task and outstanding(a) for a in state["attempts"]), "Task has an outstanding attempt; do not relaunch it")
            count = sum(a["task"] == args.task and a["action"] == args.action for a in state["attempts"])
            require(count < config["limits"]["max_attempts"], "Task action reached limits.max_attempts; inspect its evidence and configure explicitly before retrying")
            cwd = task_worktree(project, args.cwd or (task or {}).get("worktree") or project.root)
            ensure_command(args.argv, cwd)
            resources_available(project, state, config, args, cwd)
            protocol = work_protocol().before_attempt(project, state, config, args.task, task, args, cwd)
            reviewer = args.reviewer or args.worker or args.session
            identifier(reviewer, "reviewer")
            attempt_id = uuid.uuid4().hex
            log_dir = project.runtime / "logs"
            require(not log_dir.is_symlink(), "Refusing symlink log directory")
            log_dir.mkdir(exist_ok=True, mode=0o700)
            log_path = log_dir / (attempt_id + ".log")
            attempt = {"id": attempt_id, "task": args.task, "action": args.action, "worker": args.worker, "worker_config": worker, "session": args.session,
                       "epoch": args.epoch, "revision": state["revision"], "state": "reserved", "command": args.argv, "cwd": str(cwd),
                       "log": str(log_path), "timeout_seconds": timeout, "supervisor": process_identity(os.getpid()), "created_at": timestamp(),
                       "reviewer": reviewer, "role": args.role, **protocol}
            child_env = dict(os.environ, PLAYBOOK_PROJECT=state["root"])
            if hermes:
                receipt_path = log_dir / (attempt_id + ".hermes.json")
                attempt["external_receipt"] = str(receipt_path)
                write_json(receipt_path, {"protocol": "hermes-gateway-v1", "attempt_id": attempt_id,
                           "state": "not_submitted", "worker": worker, "cwd": str(cwd),
                           "timeout_seconds": timeout})
                child_env.update(PLAYBOOK_HERMES_RECEIPT=str(receipt_path), PLAYBOOK_ATTEMPT=attempt_id)
            state["attempts"].append(attempt)
            state["tasks"][args.task] = {**(task or {}), "state": "reserved", "worktree": str(cwd), "attempt": attempt_id, "epoch": args.epoch}
            project.save(state)  # Must be durable before Popen can execute any child code.
            try:
                with log_path.open("xb") as log:
                    deadline = time.monotonic() + timeout
                    process = subprocess.Popen(args.argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                               env=child_env, start_new_session=True)
                attempt.update(state="running", process=process_identity(process.pid), pid=process.pid, pgid=process.pid, started_at=timestamp())
                state["tasks"][args.task]["state"] = "running"
                project.save(state)
            except OSError as exc:
                if process is None:
                    attempt.update(state="blocked", error=str(exc))
                    state["tasks"][args.task]["state"] = "blocked"
                    project.save(state)
                    raise Failure("Attempt reserved but executable failed to start: %s" % exc) from exc
                raise
        timed_out = False
        cancelled = False
        try:
            returncode = wait_for_process_group(process, deadline, lambda: cancellation_requested(project, attempt_id))
        except CancellationRequested:
            cancelled = True
            stop_own_group(process, grace=30 if hermes else 1)
            returncode = 125
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_own_group(process, grace=30 if hermes else 1)
            returncode = 124
        external = confirm_external(attempt, returncode) if hermes else None
        with project.lock():
            state = project.load()
            attempt = next(item for item in state["attempts"] if item["id"] == attempt_id)
            late = state["epoch"] != args.epoch or state["owner"]["session"] != args.session
            if external is not None:
                attempt["external_execution"] = external
            attempt.update(state="reported" if returncode == 0 else "blocked", returncode=returncode, timed_out=timed_out, late_result=late, finished_at=timestamp(), cancelled=cancelled)
            if attempt.get("cancel_request"):
                attempt["cancel_acknowledgement"] = {"at": timestamp(), "outcome": "cancelled" if cancelled else "completed-before-cancel" if not timed_out else "timed-out"}
            work_protocol().after_attempt(project, state, attempt)
            task = state["tasks"][args.task]
            if not late and task.get("attempt") == attempt_id and not attempt.get("reconciled"):
                task["state"] = attempt["state"]
            else:
                task["needs_reconciliation"] = True
            project.save(state)
            return {"attempt": attempt, "task": task, "epoch": state["epoch"], "accepted": False}, returncode
    except (KeyboardInterrupt, OSError, ExecutionUnknown) as exc:
        if attempt_id:
            mark_interrupted(project, attempt_id, str(exc) or "supervisor interrupted")
        raise Failure("Run interrupted; reservation remains unknown and will not be relaunched automatically. Inspect status/doctor and the recorded process/group/log; worker processes may still be running: %s" % (str(exc) or "supervisor interrupted")) from exc
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


def runtime_version():
    directory = Path(__file__).resolve().parent
    files = {}
    missing = []
    snapshot = Snapshot()
    for name in RUNTIME_FILES:
        path = directory / name
        if not path.is_file() or path.is_symlink():
            missing.append(name)
            continue
        files[name] = snapshot.file(directory, name)["sha256"]
    return {"package_version": PACKAGE_VERSION, "runtime_api": RUNTIME_API, "schema_version": SCHEMA,
            "config_schema_version": SCHEMA, "state_schema_version": SCHEMA, "release_status": "development-unreleased",
            "capabilities": CAPABILITIES, "runtime_path": str(Path(__file__).resolve()), "files": files, "missing_files": missing}


def runtime_diagnostics(project, canonical=None):
    running = runtime_version()
    root = Path(canonical or project.root)
    manifest_path = root / ".orchestrator" / "runtime-manifest.json"
    manifest_info = {"path": str(manifest_path), "status": "unknown", "source": None}
    records = {}
    if manifest_path.exists() or manifest_path.is_symlink():
        try:
            require(not manifest_path.parent.is_symlink(), "Runtime manifest has a symlink parent")
            manifest = read_json(manifest_path)
            require(isinstance(manifest, dict) and isinstance(manifest.get("files"), dict), "Invalid runtime manifest")
            source = manifest.get("source", manifest.get("source_version", manifest.get("version")))
            if source is None and manifest.get("package_version"):
                source = {key: manifest.get(key) for key in ("package_version", "runtime_api", "source_runtime")}
            known = isinstance(source, dict) and isinstance(source.get("package_version"), str) and type(source.get("runtime_api")) is int
            manifest_info.update(status="recorded" if known else "unknown", source=source)
            require(len(manifest["files"]) <= MAX_SNAPSHOT_FILES, "Runtime manifest exceeds entry budget")
            for relative, record in manifest["files"].items():
                relative_path(relative, "runtime manifest path")
                require(isinstance(record, dict) and isinstance(record.get("sha256"), str)
                        and re.fullmatch("[a-f0-9]{64}", record["sha256"]) and type(record.get("mode")) is int,
                        "Invalid runtime manifest file record")
                records[relative] = record
        except (Failure, OSError) as exc:
            manifest_info.update(status="differing", error=str(exc))
    for name in RUNTIME_FILES:
        records.setdefault("scripts/" + name, None)
    copies = []
    snapshot = Snapshot()
    for relative, recorded in sorted(records.items()):
        path = root / relative
        item = {"path": relative, "provenance": "recorded" if recorded and manifest_info["status"] == "recorded" else "unknown"}
        try:
            parent = path.parent
            while parent != root:
                require(not parent.is_symlink(), "Runtime copy has a symlink ancestor")
                parent = parent.parent
            require(not path.is_symlink(), "Runtime copy is a symlink")
            if not path.exists():
                item.update(status="missing", comparison="missing")
            else:
                require(path.is_file() and path.stat().st_size <= MAX_FILE_BYTES, "Runtime copy is not a bounded regular file")
                content = snapshot.file(root, relative)
                require(content["kind"] == "file", "Runtime copy must be a regular file")
                actual = content["sha256"]
                mode = content["mode"]
                comparison = "matching" if running["files"].get(path.name) == actual else "differing" if path.name in running["files"] else "unknown"
                item.update(sha256=actual, mode=mode, comparison=comparison,
                            status=("matching" if actual == recorded["sha256"] and mode == recorded["mode"] else "differing") if recorded else "unknown")
        except (Failure, OSError) as exc:
            item.update(status="differing", comparison="unknown", error=str(exc))
        copies.append(item)
    return {"running": running, "manifest": manifest_info, "project_copies": copies, "read_only": True}


def doctor(project):
    issues = []
    output = {"project": str(project.root), "runtime": str(project.runtime), "read_only": True,
              "runtime_diagnostics": runtime_diagnostics(project)}
    if not project.state_path.exists():
        return {**output, "ok": False, "issues": ["No runtime state; use discover and explicit init/adoption" ]}
    try:
        with project.lock(shared=True):
            state = project.load()
            config = project.settings(state)
            output.update(summarize(project, state, config))
            output["runtime_diagnostics"] = runtime_diagnostics(project, state["root"])
            output["task_evidence"] = {key: work_protocol().evidence_status(project, state, config, key) for key in state["tasks"]}
            for key, task in state["tasks"].items():
                if task.get("spec") and task["state"] in ("verified", "integrated"):
                    try:
                        if task["state"] == "integrated":
                            record = state.get("integrations", {}).get(task.get("integration"))
                            require(record is not None, "Missing integration result")
                            work_protocol().integration_current(project, state, record, (record["id"],))
                        else:
                            work_protocol().acceptance(project, state, config, key)
                    except (Failure, OSError) as exc:
                        issues.append("Task %s acceptance is inapplicable: %s" % (key, exc))
            if state["machine"] != machine_id():
                issues.append("State machine identity differs; multi-machine takeover is unsupported")
            current = baseline(project)
            if current != state["baseline"]:
                issues.append("Git baseline/status changed since the recorded baseline")
            for attempt in state["attempts"]:
                if attempt_status(attempt) == "unknown":
                    issues.append("Attempt %s has unknown execution; reconcile explicitly, do not relaunch" % attempt["id"])
            for task_id, task in state["tasks"].items():
                if task.get("worktree") and not Path(task["worktree"]).is_dir():
                    issues.append("Task %s working directory is missing" % task_id)
                if task["state"] == "unknown" or task.get("needs_reconciliation"):
                    issues.append("Task %s requires explicit reconciliation" % task_id)
            output["paths"] = {}
            canonical = Path(state["root"])
            for key, relative in config["paths"].items():
                path = (canonical / relative).resolve()
                inside = path == canonical or canonical in path.parents
                output["paths"][key] = {"path": str(path), "exists": path.exists(), "inside_project": inside}
                if not inside:
                    issues.append("Configured path %s resolves outside the project" % key)
            if state.get("last_guard", {}).get("state") == "running":
                issues.append("Guarded mutation has no recorded completion; inspect its effects and baseline before retrying")
            if state.get("checkpoint_failure"):
                issues.append("Last checkpoint was incomplete: " + state["checkpoint_failure"]["error"])
            if state.get("checkpoint"):
                verify_checkpoint(project, state, state["checkpoint"], current=state["mode"] == "prepared")
    except (Failure, OSError) as exc:
        issues.append(str(exc))
    diagnosis = output["runtime_diagnostics"]
    if diagnosis["running"]["missing_files"]:
        issues.append("Executing runtime bundle is incomplete: " + ", ".join(diagnosis["running"]["missing_files"]))
    if diagnosis["manifest"]["status"] == "differing":
        issues.append("Project runtime manifest could not be validated")
    for item in diagnosis["project_copies"]:
        if item["status"] == "differing" or (item["provenance"] == "recorded" and item["status"] == "missing"):
            issues.append("Project runtime copy %s is %s" % (item["path"], item["status"]))
        elif item["comparison"] == "differing":
            issues.append("Project runtime copy %s differs from the executing runtime" % item["path"])
    return {**output, "ok": not issues, "issues": issues}


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    actions = root.add_subparsers(dest="command", required=True)
    help_text = {
        "discover": "Read-only project, Git and executable inventory (no login/capability probing)",
        "session-id": "Create an opaque session identity without project mutation",
        "version": "Read-only runtime/package API, capabilities and required file hashes",
        "cancel": "Request cancellation by attempt ID; only its live supervisor may stop its group",
        "readiness": "Read-only task dependencies, scope and exclusive resource readiness",
        "evidence": "Append immutable scoped acceptance evidence, or inspect applicability",
        "integration": "Begin, finish or inspect an assembled result bound to actual verification",
        "init": "Initialize/adopt portable policy and shared local ownership",
        "status": "Read-only authoritative state, tasks, attempts and policy",
        "resume": "Resume only the current owner; report baseline changes without dispatch",
        "configure": "Validate and atomically replace project policy; preserve ownership/tasks",
        "checkpoint": "Copy dirty/untracked recovery content locally (64 MiB/file, 256 MiB/10000 files total)",
        "handoff": "Checkpoint and prepare a transfer; stop old-owner managed mutations",
        "takeover": "Claim a prepared handoff, or explicitly recover after stopping the old commander",
        "pause": "Persist paused before checkpointing; existing workers continue",
        "doctor": "Read-only schema, ownership, paths, recovery and execution diagnosis",
        "task": "Record/reconcile legacy work or structured specs; typed acceptance requires evidence",
        "guard": "Hold shared OS lock across owner/policy checks and a short command",
        "run": "Reserve attempt/resources, launch argv, record evidence without automatic acceptance",
    }
    for name, description in help_text.items():
        sub = actions.add_parser(name, description=description, help=description)
        sub.add_argument("--project", required=name not in ("session-id", "version"), help="Project directory (linked worktrees share Git common-directory state)")
        if name in ("init", "resume", "configure", "checkpoint", "handoff", "takeover", "pause", "task", "guard", "run", "cancel", "evidence", "integration"):
            sub.add_argument("--session", required=name not in ("evidence", "integration"), help="Opaque current session ID; required for mutation")
        if name in ("resume", "configure", "checkpoint", "handoff", "pause", "task", "guard", "run", "cancel", "evidence", "integration"):
            sub.add_argument("--epoch", type=int, required=name not in ("evidence", "integration"), help="Current ownership epoch; required for mutation")
        if name in ("init", "takeover"):
            sub.add_argument("--client", required=True, choices=CLIENTS)
        if name == "init":
            sub.add_argument("--goal", required=True)
            sub.add_argument("--config", help="JSON settings; defaults filled and all fields validated")
            sub.add_argument("--adopt", action="store_true", help="Explicitly preserve/import existing .orchestrator files")
        if name == "configure":
            settings = sub.add_mutually_exclusive_group(required=True)
            settings.add_argument("--config", help="Full replacement JSON")
            settings.add_argument("--patch", help="Recursive object patch JSON; arrays replace, null is rejected")
        if name == "handoff":
            handoff = sub.add_mutually_exclusive_group()
            handoff.add_argument("--to", help="Optional designated receiving session ID")
            handoff.add_argument("--cancel", action="store_true", help="Withdraw a prepared handoff and remain paused")
        if name == "takeover":
            sub.add_argument("--handoff", help="ID returned by a prepared handoff")
            sub.add_argument("--recover", action="store_true", help="Explicit unprepared recovery; checkpoint existing work first")
            sub.add_argument("--config", help="Explicitly reviewed JSON settings to repair an interrupted configuration transaction; requires --recover --previous-stopped")
            sub.add_argument("--previous-stopped", action="store_true", help="Attest user-directed stopping/replacement of the old commander; does not fence raw writers")
        if name == "task":
            sub.add_argument("--id", required=True)
            sub.add_argument("--state", choices=TASK_STATES)
            sub.add_argument("--spec", help="Structured requirements, acceptance, content paths, dependencies and resources JSON")
            sub.add_argument("--worktree")
            sub.add_argument("--note", help="Reconciliation, acceptance or integration evidence")
        if name == "cancel":
            sub.add_argument("--attempt", required=True)
            sub.add_argument("--reason", required=True)
        if name == "readiness":
            sub.add_argument("--task", required=True)
            sub.add_argument("--action", choices=("dispatch", "verify"), default="dispatch")
            sub.add_argument("--worker", help="Optional reviewer worker; counts verification against agent capacity too")
        if name == "evidence":
            sub.add_argument("--operation", choices=("append", "status"), default="append")
            sub.add_argument("--task", required=True)
            source = sub.add_mutually_exclusive_group()
            source.add_argument("--attempt")
            source.add_argument("--manual", action="store_true")
            sub.add_argument("--reviewer")
            sub.add_argument("--role", choices=("author", "reviewer"), default="author")
            sub.add_argument("--result", choices=("passed", "failed"), default="passed")
            sub.add_argument("--note")
            sub.add_argument("--artifact", action="append", default=[], help="Explicit task-root-relative regular artifact; hashed and retained by reference")
        if name == "integration":
            sub.add_argument("--operation", required=True, choices=("begin", "finish", "status"))
            sub.add_argument("--id")
            sub.add_argument("--tasks", nargs="+", default=[])
            sub.add_argument("--target", help="Target worktree (defaults to project)")
            sub.add_argument("--paths", nargs="+", default=[], help="Additional assembly scopes, unioned with participant scopes")
            sub.add_argument("--require-push", action="store_true", help="Gate pushes of the integration branch on this result")
            sub.add_argument("--attempt", help="Successful integration verification attempt for finish")
            sub.add_argument("--note", help="Explicit membership and result declaration for finish")
        if name == "guard":
            sub.add_argument("--action", required=True, choices=("commit", "merge", "push", "cleanup", "worktree-create", "scaffold"))
            sub.epilog = "Append -- COMMAND ARG... (argv is not interpreted by a shell)."
        if name == "run":
            sub.add_argument("--action", required=True, choices=("dispatch", "verify"))
            sub.add_argument("--task", required=True)
            sub.add_argument("--config-revision", type=int, help="Expected policy revision; reject commands built from stale settings")
            sub.add_argument("--timeout", type=int, help="Shorter per-invocation timeout, bounded by limits.timeout_seconds")
            sub.add_argument("--worker", help="Configured worker ID; required for dispatch, counts verify/reviewer jobs as agents too")
            sub.add_argument("--cwd", help="Working directory in this project (default: task worktree/project)")
            sub.add_argument("--integration", help="Integration ID for verification of the assembled target")
            sub.add_argument("--reviewer", help="Declared verification identity (default worker or session)")
            sub.add_argument("--role", choices=("author", "reviewer"), default="author")
            sub.epilog = "Append -- COMMAND ARG...; logs stay in local runtime. Limits count unknown work."
    return root


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        split = argv.index("--")
        command, argv = argv[split + 1:], argv[:split]
    args = parser().parse_args(argv)
    args.argv = command
    try:
        if command:
            require(args.command in ("guard", "run"), "Only guard/run accept a command after --")
        if args.command == "session-id":
            result = {"session": uuid.uuid4().hex}
        elif args.command == "version":
            result = runtime_version()
        else:
            project = Project(args.project)
            if args.command == "discover":
                result = discover(project)
            elif args.command == "init":
                result = init_project(project, args)
            elif args.command == "configure":
                result = configure(project, args)
            elif args.command == "status":
                # Atomic files permit adapters inside a guarded child to inspect state
                # without deadlocking on their parent's exclusive lock.
                state = project.load()
                result = summarize(project, state, project.settings(state))
            elif args.command == "doctor":
                result = doctor(project)
            elif args.command in ("resume", "checkpoint", "handoff", "takeover", "pause"):
                result = lifecycle(project, args)
            elif args.command == "task":
                result = record_task(project, args)
            elif args.command == "cancel":
                result = cancel_attempt(project, args)
            elif args.command == "readiness":
                with project.lock(shared=True):
                    state = project.load()
                    result = work_protocol().readiness(project, state, project.settings(state), args.task, args.action, args.worker)
            elif args.command == "evidence":
                result = work_protocol().evidence(project, args)
            elif args.command == "integration":
                result = work_protocol().integration(project, args)
            elif args.command == "guard":
                result, code = guard(project, args)
                print(json.dumps(result, ensure_ascii=True))
                if code:
                    print(json.dumps({"error": "Guarded command failed", "returncode": code}), file=sys.stderr)
                return min(code if code >= 0 else 128 - code, 255)
            elif args.command == "run":
                result, code = run_job(project, args)
                print(json.dumps(result, ensure_ascii=True))
                if code:
                    print(json.dumps({"error": "Attempt failed; inspect the recorded log", "returncode": code}), file=sys.stderr)
                return min(code if code >= 0 else 128 - code, 255)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (Failure, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted; inspect status/doctor before retrying"}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
