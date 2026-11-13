#!/usr/bin/env python3
"""Read-only foundation checks and owner-guarded, create-only repairs.

Invoke with Python 3.9+ and -I. Exit 0: complete; 1: missing files or retained
conflicts; 2: invalid input, unsafe paths, ownership or runtime failure. A complete
foundation does not mean its draft is dispatch-ready. No init or takeover occurs.
"""
import argparse
import datetime
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import unicodedata
import uuid


SCRIPT = Path(__file__).resolve()
RUNTIME = SCRIPT.with_name("playbook.py")
RESOURCE_PATH = ".orchestrator/foundation-templates"
MANIFEST_PATH = ".orchestrator/runtime-manifest.json"
TEMPLATES = ("PROJECT-README.md", "status.md", "tasks.md", "ADR.md", "review.md")
MAX_RESOURCE_BYTES = 16 * 1024 * 1024
HELPER = "playbook-foundation"


class Failure(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Failure(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    require(isinstance(value, str) and value.strip() and "\0" not in value,
            "Foundation paths must be nonempty relative project paths")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.parts and ".." not in path.parts and "\\" not in value,
            "Foundation paths must stay inside the project: " + value)
    return path.as_posix()


def runtime_json(*arguments):
    require(RUNTIME.is_file() and not RUNTIME.is_symlink(), "Matching sibling playbook.py is required")
    result = subprocess.run([sys.executable, "-I", str(RUNTIME), *arguments],
                            capture_output=True, text=True, check=False)
    require(result.returncode == 0, "Runtime command failed: " + (result.stderr.strip() or result.stdout.strip()))
    try:
        value = json.loads(result.stdout)
    except ValueError as exc:
        raise Failure("Runtime did not return a JSON object") from exc
    require(isinstance(value, dict), "Runtime did not return a JSON object")
    return value


def source_bytes(path):
    """Read bounded, physical package resources; fail if a source changes mid-read."""
    require(not path.is_symlink(), "Refusing symlink package resource: " + path.name)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(str(path), flags), "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_RESOURCE_BYTES,
                "Package resource is not a bounded regular file: " + path.name)
        data = stream.read(MAX_RESOURCE_BYTES + 1)
        after = os.fstat(stream.fileno())
    require(len(data) <= MAX_RESOURCE_BYTES and
            (before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            "Package resource changed while reading: " + path.name)
    return data, stat.S_IMODE(after.st_mode) & 0o777


def resources():
    # Installed skills use ../templates. Project copies carry the exact resources
    # under a distinct metadata directory, avoiding a project's own templates/.
    copied = SCRIPT.parent.parent / RESOURCE_PATH
    folder = copied if copied.exists() or copied.is_symlink() else SCRIPT.parent.parent / "templates"
    require(folder.is_dir() and not folder.is_symlink(), "Foundation template resources are missing or symlinked")
    return {name: source_bytes(folder / name)[0] for name in TEMPLATES}


def render(data, values):
    # One pass: a user goal containing '{{...}}' is data, never another template.
    text = data.decode("utf-8")
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: str(values.get(match[1], match[0])), text).encode("utf-8")


def target(path, kind, data, mode=0o644):
    return {"path": relative(path), "kind": kind, "data": data, "mode": mode}


def documents(status, profile, templates):
    policy = status["policy"]
    paths = {key: relative(policy["paths"][key]) for key in ("plan", "worker", "cards", "handoff")}
    first = paths["cards"] + "/T-001.md"
    root = Path(status["project_root"])
    project_type = "Git project" if status["git"] else "non-Git project; work proceeds serially"
    values = {"PROJECT": root.name, "GOAL": policy["goal"], "PROJECT_TYPE": project_type,
              "REVISION": status["config_revision"], "FIRST_CARD": first,
              **{key.upper(): value for key, value in paths.items()}}
    reference = "Policy: `.orchestrator/config.json`; configuration revision %s when scaffolded.\n" % status["config_revision"]
    plan = ("# %s — project plan\n\n%s\n## Stage goal\n\n%s\n\n"
            "## Next task\n\n`%s` is a draft. Its concrete outcome, allowed files, content scope,\n"
            "dependencies, exclusive resources and acceptance evidence are pending.\n"
            "Complete them from actual project facts before recording a task spec or dispatching.\n\n"
            "Build command: pending. Test command: pending. No checks have been run by this scaffold.\n\n"
            "## Working agreement\n\nWorker instructions: `%s`. Cards: `%s`. Handoff: `%s`.\n"
            "All paths are project-relative. %s. Existing source and project instructions remain authoritative.\n"
            "Runtime status records the current owner, epoch and tasks; documents cannot appoint an owner.\n"
            "Implementation/light checks and owner-scheduled heavy verification are separate stages.\n"
            "Permissions, limits and review policy come from the project configuration.\n") % (
                root.name, reference, policy["goal"], first, paths["worker"], paths["cards"], paths["handoff"], project_type)
    worker = ("# %s — worker instructions\n\n%s\n"
              "1. Read existing project rules, `%s` and the assigned card in `%s`.\n"
              "2. Confirm actual baseline, existing changes, allowed files, dependencies and resource reservations.\n"
              "3. Work only on the assigned scope. Missing executable acceptance details are blockers.\n"
              "4. Preserve existing, dirty, untracked and ignored work. Do not reset, clean or discard it.\n"
              "5. Report actual commands, working directories, exit states, evidence and exclusions.\n\n"
              "A worker is not appointed orchestrator by this file or a skill. Do not borrow the owner's\n"
              "session identity, dispatch other work or change shared policy. Git, model calls and other\n"
              "actions require the applicable project authorization. %s.\n\n"
              "Build command: pending. Test command: pending. Confirm these in the concrete task.\n"
              "Run assigned light checks; leave scheduled heavy verification to the owner. Do not nest\n"
              "managed verification inside an active managed dispatch of the same task/worktree.\n"
              "Exit 0 is a reported result; verified and integrated require applicable acceptance evidence.\n"
              "Handoff context: `%s`. Report blocked/partial/unknown work truthfully.\n") % (
                  root.name, reference, paths["plan"], paths["cards"], project_type, paths["handoff"])
    handoff = ("# %s — handoff draft\n\n%s\nStage goal: %s\n\n"
               "This scaffold is not a prepared handoff or a new appointment. Read runtime status/doctor\n"
               "and the existing project instructions before acting. Plan: `%s`; worker rules: `%s`.\n\n"
               "- Current owner/session/epoch: read runtime status; do not infer from this document.\n"
               "- Actual baseline, existing work and recovery evidence: pending inspection.\n"
               "- Tasks and attempts: read runtime status; absence of a message does not prove absence of work.\n"
               "- Checks run, results and evidence: pending; scaffolding did not run project checks.\n"
               "- Next concrete card: `%s` (draft; acceptance details pending).\n"
               "- Transfer intent and receiving session: pending explicit lifecycle action.\n\n"
               "Do not redispatch or rerun checks merely because this document exists. Preserve ongoing,\n"
               "unknown and unmerged work. Prepared handoff and takeover use the lifecycle runtime.\n") % (
                   root.name, reference, policy["goal"], paths["plan"], paths["worker"], first)
    card = ("# T-001 — first task draft\n\n**Status: draft; not dispatch-ready.**\n\n%s\n"
            "Project goal: %s\n\nRead `%s` and `%s`. This card grants no ownership or additional permission.\n\n"
            "- Concrete outcome and external behavior: pending.\n"
            "- Worker, approved working directory and baseline: pending.\n"
            "- Allowed files and relevant content scopes: pending.\n"
            "- Upstream dependencies (contract-only versus integrated): pending.\n"
            "- Exclusive resources and existing work to preserve: pending.\n"
            "- Build command and working directory: pending.\n"
            "- Test command, expected behavior and failure cases: pending.\n"
            "- Acceptance/review requirements and evidence artifacts: pending.\n\n"
            "Complete a concrete task/spec using project facts before dispatch. Do not submit placeholder\n"
            "values as a runnable spec. No task is registered or launched by this scaffold.\n"
            "Keep implementation/light checks separate from owner-scheduled heavy verification.\n"
            "Report actual changes, commands/results, evidence, unverified items and retained work.\n") % (reference, policy["goal"], paths["worker"], paths["plan"])
    result = [target("README.md", "readme", render(templates["PROJECT-README.md"], values)),
              target(paths["plan"], "plan", plan.encode("utf-8")),
              target(paths["worker"], "worker", worker.encode("utf-8")),
              target(paths["handoff"], "handoff", handoff.encode("utf-8")),
              target(first, "task_draft", card.encode("utf-8"))]
    if profile == "standard":
        base = PurePosixPath(paths["plan"]).parent
        values.update(ORCHESTRATOR="current runtime owner", DECIDER="project decision maker",
                      DATE=datetime.date.today().isoformat(), MAIN=policy["git"]["integration_branch"],
                      ROOT=".", WT_BASE="<approved worktree directory; pending>")
        for source, destination, kind in (("status.md", "status.md", "board"), ("tasks.md", "tasks.md", "task_index"),
                                           ("ADR.md", "templates/ADR.md", "decision_template"),
                                           ("review.md", "templates/review.md", "review_template")):
            data = render(templates[source], values)
            result.append(target(str(base / destination), kind,
                                 b"> Planning template; pending project facts, not approved or accepted evidence.\n\n" + data))
    return result, first


def make_plan(status, profile):
    version = runtime_json("version")
    files = version.get("files")
    require(isinstance(files, dict) and files, "Runtime version.files must list required runtime filenames and SHA-256 hashes")
    require(isinstance(version.get("package_version"), str) and version["package_version"], "Runtime package_version is missing")
    require(type(version.get("runtime_api")) is int and version["runtime_api"] > 0, "Runtime API version is missing")
    missing = version.get("missing_files", [])
    require(isinstance(missing, list) and all(isinstance(name, str) for name in missing), "Invalid runtime missing_files list")
    required_missing = [name for name in missing if name.endswith(".py") or name in ("wt.sh", "dispatch.sh")]
    require(not required_missing, "Required runtime sources are missing: " + ", ".join(required_missing))
    templates = resources()
    entries, first = documents(status, profile, templates)
    copies = []
    for name, expected in sorted(files.items()):
        require(isinstance(name, str) and relative(name) == name and "/" not in name,
                "Runtime version.files must use simple sibling filenames")
        # policy-dispatch.py delegates supported clients to dispatch.sh.
        if not (name.endswith(".py") or name in ("wt.sh", "dispatch.sh")):
            continue
        require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
                "Runtime version has no valid source hash for " + name)
        data, mode = source_bytes(SCRIPT.parent / name)
        require(sha256(data) == expected, "Runtime source changed or differs from version.files: " + name)
        copies.append(target("scripts/" + name, "runtime", data, mode))
    require({"scripts/playbook.py", "scripts/wt.sh"}.issubset(item["path"] for item in copies),
            "Runtime version.files must include playbook.py and wt.sh")
    if any(item["path"] == "scripts/playbook-foundation.py" for item in copies):
        copies.extend(target(RESOURCE_PATH + "/" + name, "runtime_resource", data) for name, data in templates.items())
    entries.extend(copies)
    manifest = {"package_version": version["package_version"], "runtime_api": version["runtime_api"],
                "source_runtime": "orchestrator-playbook/scripts/playbook.py",
                "files": {item["path"]: {"sha256": sha256(item["data"]), "mode": item["mode"]} for item in copies}}
    entries.append(target(MANIFEST_PATH, "runtime_manifest", encoded(manifest)))
    return entries, first, version


def conflict(report, path, reason, detail, blocking=True):
    report["conflict"].append({"path": path, "reason": reason, "detail": detail, "blocking": blocking})


def path_key(path):
    # Conservative portable collision detection, including case-insensitive Mac
    # volumes and Unicode normalization aliases. This may reject aliases on Linux.
    return unicodedata.normalize("NFC", path).casefold()


def validate_layout(entries, report):
    seen = {}
    for item in entries:
        path = item["path"]
        key = path_key(path)
        parts = key.split("/")
        if ".git" in parts or key == ".orchestrator/config.json" or key.startswith((".orchestrator/config.json/", ".orchestrator/local/")) or key == ".orchestrator/local":
            conflict(report, path, "reserved_path", "Foundation documents cannot occupy runtime/configuration or Git internals")
        if key in seen:
            conflict(report, path, "target_collision", "Also used by " + seen[key])
        for previous, display in seen.items():
            if key.startswith(previous + "/") or previous.startswith(key + "/"):
                conflict(report, path, "target_collision", "A target file is also a parent directory of " + display)
        seen[key] = path


def directory_flags():
    require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and os.name == "posix",
            "Safe foundation writes require POSIX directory descriptors and O_NOFOLLOW")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def parent_fd(root_fd, path, create=False):
    fd = os.dup(root_fd)
    try:
        for part in PurePosixPath(path).parts[:-1]:
            try:
                next_fd = os.open(part, directory_flags(), dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
                next_fd = os.open(part, directory_flags(), dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def inspect_target(root_fd, item):
    """Return missing/existing without following any target or ancestor symlink."""
    path = item["path"]
    try:
        fd = parent_fd(root_fd, path)
    except FileNotFoundError:
        return "missing", None
    try:
        name = PurePosixPath(path).name
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return "missing", None
        if stat.S_ISLNK(info.st_mode):
            return "symlink", None
        if not stat.S_ISREG(info.st_mode):
            return "not_regular", None
        if item["kind"] in ("runtime", "runtime_resource", "runtime_manifest"):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            with os.fdopen(os.open(name, flags, dir_fd=fd), "rb") as stream:
                current = os.fstat(stream.fileno())
                require(stat.S_ISREG(current.st_mode), "Existing target changed type: " + path)
                data = stream.read(MAX_RESOURCE_BYTES + 1)
            matches = data == item["data"] and stat.S_IMODE(current.st_mode) == item["mode"]
            return "matching" if matches else "different", None
        return "existing", info.st_size
    finally:
        os.close(fd)


def preflight(root_fd, entries, report):
    validate_layout(entries, report)
    for item in entries:
        path, kind = item["path"], item["kind"]
        try:
            state, size = inspect_target(root_fd, item)
        except (OSError, Failure) as exc:
            conflict(report, path, "unsafe_parent", "Cannot traverse a physical target parent: " + str(exc))
            continue
        record = {"path": path, "kind": kind}
        if state == "missing":
            report["create"].append({**record, "state": "planned"})
        else:
            report["retain"].append({**record, "reason": state})
            if state in ("symlink", "not_regular"):
                conflict(report, path, "unsafe_target", "Existing symlink, directory or special file is retained")
            elif state == "different":
                conflict(report, path, "different_copy", "Existing helper/resource/manifest differs; review it explicitly", blocking=False)
            elif size == 0:
                conflict(report, path, "empty_document", "Existing document is empty; retained for explicit review", blocking=False)


def create_exclusive(root_fd, item):
    fd = parent_fd(root_fd, item["path"], create=True)
    try:
        # A failed write must leave the final name absent so a retry can repair it.
        temporary = ".playbook-foundation-" + uuid.uuid4().hex + ".tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        out = os.open(temporary, flags, 0o600, dir_fd=fd)
        try:
            try:
                remaining = memoryview(item["data"])
                while remaining:
                    written = os.write(out, remaining)
                    if written <= 0:
                        raise OSError(errno.EIO, "Foundation write made no progress")
                    remaining = remaining[written:]
                os.fchmod(out, item["mode"])
                os.fsync(out)
            finally:
                os.close(out)
            # link publishes the complete file atomically and fails if a concurrent
            # author has occupied the destination, including with a symlink.
            os.link(temporary, PurePosixPath(item["path"]).name,
                    src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        finally:
            os.unlink(temporary, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)


def empty_report(args):
    return {"helper": HELPER, "action": args.action, "profile": args.profile,
            "read_only": args.action == "check", "requested_project": os.path.abspath(os.path.expanduser(args.project)),
            "create": [], "retain": [], "conflict": [],
            "readiness": {"foundation_complete": False, "dispatch_ready": False, "can_apply": False,
                          "pending": ["Complete and review the first concrete task/spec", "Confirm actual build/test commands and acceptance evidence"]}}


def inspect_or_apply(args, report):
    status = runtime_json("status", "--project", args.project)
    require(isinstance(status.get("policy"), dict) and isinstance(status["policy"].get("paths"), dict),
            "Runtime status must provide normalized policy.paths")
    root = Path(status["project_root"]).resolve()
    report.update(project_root=str(root), config_revision=status["config_revision"],
                  owner=status["owner"], epoch=status["epoch"], mode=status["mode"])
    if root != Path(report["requested_project"]).resolve():
        conflict(report, str(root), "project_root_mismatch", "Use the canonical project root explicitly; foundation repair does not select an enclosing checkout")
    if status["mode"] != "active" or not status.get("machine_matches", True):
        conflict(report, ".orchestrator/config.json", "owner_inactive", "Apply requires the active owner on this machine", blocking=False)
    if args.session is not None and (args.session != status["owner"]["session"] or args.epoch != status["epoch"]):
        conflict(report, ".orchestrator/config.json", "ownership_conflict", "Session and epoch must match runtime status", blocking=False)
    if args._under_guard:
        require(os.environ.get("PLAYBOOK_GUARDED") == "1" and os.environ.get("PLAYBOOK_PROJECT") == str(root),
                "Internal apply requires the real runtime scaffold guard")
        require(status["mode"] == "active" and status.get("machine_matches", True) and
                args.session == status["owner"]["session"] and args.epoch == status["epoch"],
                "Internal apply does not match the active runtime owner and epoch")
    entries, first, version = make_plan(status, args.profile)
    report.update(package_version=version["package_version"], runtime_api=version["runtime_api"])
    report["readiness"]["first_card"] = {"path": first, "status": "draft"}
    root_fd = os.open(str(root), directory_flags())
    try:
        preflight(root_fd, entries, report)
        if any(item["path"] == first for item in report["retain"]):
            report["readiness"]["first_card"]["status"] = "existing_unreviewed"
        agents = root / "AGENTS.md"
        if agents.exists() or agents.is_symlink():
            report["retain"].append({"path": "AGENTS.md", "kind": "project_rules", "reason": "existing_untouched"})
        blocking = any(item["blocking"] for item in report["conflict"])
        owner_ok = status["mode"] == "active" and status.get("machine_matches", True) and not any(
            item["reason"] == "ownership_conflict" for item in report["conflict"])
        report["readiness"]["can_apply"] = not blocking and owner_ok
        if args.action == "apply":
            require(args._under_guard, "Apply must execute through the runtime guard")
            if blocking:
                report["error"] = "All targets were preflighted; unsafe paths or collisions prevent foundation writes"
                return 2
            by_path = {item["path"]: item for item in entries}
            for proposed in report["create"]:
                try:
                    create_exclusive(root_fd, by_path[proposed["path"]])
                    proposed["state"] = "created"
                except OSError as exc:
                    if isinstance(exc, FileExistsError):
                        report["retain"].append({"path": proposed["path"], "kind": proposed["kind"], "reason": "concurrent_creation"})
                    conflict(report, proposed["path"], "creation_failed", "Exclusive creation stopped; existing files were not overwritten: " + str(exc))
                    report["error"] = "Creation stopped; earlier new files are retained. Inspect this report before retrying"
                    report["readiness"]["can_apply"] = False
                    return 2
        missing = any(item["state"] == "planned" for item in report["create"])
        report["readiness"]["foundation_complete"] = not missing and not report["conflict"]
        return 2 if blocking else (1 if missing or report["conflict"] else 0)
    finally:
        os.close(root_fd)


def guarded_apply(args, report):
    require(RUNTIME.is_file() and not RUNTIME.is_symlink(), "Matching sibling playbook.py is required")
    require(args.session and args.epoch is not None, "Apply requires --session and --epoch from the current owner's status")
    # The guard changes cwd to the runtime root. Preserve the absolute request
    # captured in the caller's cwd, including its separate root-intent check.
    project = report["requested_project"]
    child = [sys.executable, "-I", str(SCRIPT), "apply", "--project", project,
             "--profile", args.profile, "--session", args.session, "--epoch", str(args.epoch), "--_under-guard"]
    command = [sys.executable, "-I", str(RUNTIME), "guard", "--project", project,
               "--session", args.session, "--epoch", str(args.epoch), "--action", "scaffold", "--", *child]
    # An inherited adapter marker never skips the outer ownership check. Only
    # the real guard sets it for the recursively launched internal apply.
    environment = dict(os.environ)
    environment.pop("PLAYBOOK_GUARDED", None)
    environment.pop("PLAYBOOK_PROJECT", None)
    result = subprocess.run(command, capture_output=True, text=True, env=environment, check=False)
    # guard routes child stdout to stderr to keep its own stdout a single JSON
    # object. Recover our tagged single-line report without parsing human text.
    inner = None
    for line in result.stderr.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("helper") == HELPER and value.get("action") == "apply":
            inner = value
    if inner is not None:
        report.clear()
        report.update(inner)
        return min(result.returncode if result.returncode >= 0 else 128 - result.returncode, 255)
    raise Failure("Runtime scaffold guard did not complete foundation apply: " + (result.stderr.strip() or result.stdout.strip()))


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("action", choices=("check", "apply"))
    root.add_argument("--project", required=True, help="Initialized canonical project root; check never initializes or appoints an owner")
    root.add_argument("--profile", choices=("minimal", "standard"), default="minimal")
    root.add_argument("--session", help="Current owner session; required for apply")
    root.add_argument("--epoch", type=int, help="Current ownership epoch; required for apply")
    root.add_argument("--_under-guard", action="store_true", help=argparse.SUPPRESS)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    report = empty_report(args)
    try:
        require((args.session is None) == (args.epoch is None), "Supply --session and --epoch together")
        require(not args._under_guard or args.action == "apply", "Internal guard flag is only for apply")
        code = guarded_apply(args, report) if args.action == "apply" and not args._under_guard else inspect_or_apply(args, report)
    except (Failure, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
        code = 2
    print(json.dumps(report, ensure_ascii=True))
    if report.get("error"):
        print(report["error"], file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
