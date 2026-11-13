"""API 2 cooperative task, content, evidence and integration protocol.

Loaded by explicit sibling path by playbook.py, including under Python -I.
Receipts describe cooperating declarations, not cryptographic worker identity.
"""
import copy
import fnmatch
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
import uuid


def bind(api):
    for name in ("Failure", "require", "identifier", "text", "relative_path", "object_keys", "encoded", "digest",
                 "read_json", "timestamp", "Snapshot", "git_output", "task_worktree", "outstanding", "sync_directory", "resources_available",
                 "MAX_SNAPSHOT_FILES", "MAX_FILE_BYTES", "MAX_SNAPSHOT_BYTES"):
        globals()[name] = api[name]


def api_required(config):
    require(config.get("runtime_api") == 2, "Structured work requires explicit configure --patch with runtime_api:2")


def strings(value, name, nonempty=False):
    require(isinstance(value, list) and (value or not nonempty) and len(value) <= 1000, name + " must be a bounded array")
    for item in value:
        text(item, name)
        require(len(item) <= 8192, name + " entry is too long")
    require(len(set(value)) == len(value), name + " contains duplicates")
    return value


def scope_path(value):
    if value != ".":
        relative_path(value, "content path")
    require(isinstance(value, str) and len(value) <= 4096, "Invalid content path")
    normalized = Path(value).as_posix()
    require(normalized == value and not value.startswith(".git/") and value != ".git"
            and value != ".orchestrator/local" and not value.startswith(".orchestrator/local/"), "Invalid or runtime-owned content path: " + value)
    return value


def validate_spec(raw):
    object_keys(raw, ("requirements", "acceptance", "paths", "dependencies", "resources", "review"), "task spec")
    spec = copy.deepcopy(raw)
    for key in ("requirements", "acceptance", "paths"):
        strings(spec.get(key), "spec." + key, nonempty=True)
    spec["paths"] = sorted(scope_path(path) for path in spec["paths"])
    spec.setdefault("dependencies", [])
    spec.setdefault("resources", [])
    spec.setdefault("review", {"independent": False})
    strings(spec["resources"], "spec.resources")
    for resource in spec["resources"]:
        identifier(resource, "resource")
    spec["resources"].sort()
    object_keys(spec["review"], ("independent",), "spec.review")
    spec["review"].setdefault("independent", False)
    require(type(spec["review"]["independent"]) is bool, "spec.review.independent must be boolean")
    require(isinstance(spec["dependencies"], list) and len(spec["dependencies"]) <= 1000, "spec.dependencies must be a bounded array")
    seen = set()
    for dep in spec["dependencies"]:
        object_keys(dep, ("task", "kind"), "dependency")
        identifier(dep.get("task"), "dependency task")
        require(dep.get("kind") in ("contract", "integrated"), "Dependency kind must be contract or integrated")
        require(dep["task"] not in seen, "Duplicate dependency task")
        seen.add(dep["task"])
    spec["dependencies"].sort(key=lambda item: item["task"])
    return spec


def record_implementers(state, task_id, task, session):
    # Keep owner provenance across ordinary status updates and handoffs. Worker
    # dispatch provenance already lives in the retained attempt ledger.
    previous = state["tasks"].get(task_id, {})
    task["implementers"] = sorted(set(task.get("implementers", []))
                                  | set(previous.get("implementers", []))
                                  | {previous.get("recorded_by", session), session})


def implementation_sources(state, task_id, task):
    sources = set(task.get("implementers", [])) | {task.get("recorded_by", state["owner"]["session"])}
    for attempt in state["attempts"]:
        if attempt["task"] == task_id:
            sources.update(attempt.get("implementers", []))
            if attempt["action"] == "dispatch":
                sources.add(attempt.get("worker") or attempt["session"])
    return sorted(sources)


def install_spec(state, task_id, task, raw):
    record_implementers(state, task_id, task, state["owner"]["session"])
    spec = validate_spec(raw)
    fingerprint = digest(encoded(spec))
    if task.get("spec_hash") == fingerprint:
        return False
    visited = set()
    def visit(key, chain):
        require(key not in chain, "Task dependency cycle: " + " -> ".join(chain + [key]))
        require(len(chain) < 128 and len(visited) <= MAX_SNAPSHOT_FILES, "Task dependency graph exceeds traversal budget")
        if key in visited:
            return
        candidate = spec if key == task_id else state["tasks"].get(key, {}).get("spec", {})
        for dep in candidate.get("dependencies", []):
            visit(dep["task"], chain + [key])
        visited.add(key)
    visit(task_id, [])
    if task.get("spec"):
        task.setdefault("spec_history", []).append({key: copy.deepcopy(task[key]) for key in ("spec", "spec_hash", "spec_revision")})
    task.update(spec=spec, spec_hash=fingerprint, spec_revision=task.get("spec_revision", 0) + 1)
    task.pop("accepted_evidence", None)
    task.pop("integration", None)
    return True


# Excluded only when untracked (or in a non-Git project). Tracked source remains
# relevant even if its name happens to match a conventional generated directory.
CACHE_NAMES = {"node_modules", "__pycache__", ".venv", "venv", ".cache", ".pytest_cache", "dist", "build"}


def excluded_path(path):
    parts = Path(path).parts
    return (any(part in CACHE_NAMES for part in parts) or any(part == ".env" or part.startswith(".env.") for part in parts)
            or parts[:1] == (".git",) or parts[:2] == (".orchestrator", "local"))


def safe_ancestors(root, path):
    current = root
    for part in Path(path).parts[:-1]:
        current = current / part
        require(not current.is_symlink(), "Content path has a symlink ancestor: " + str(current))


def bounded_git_paths(root, paths, cached):
    command = ["git", "--literal-pathspecs", "-C", str(root), "ls-files", "-z"]
    command += ["--cached", "--stage"] if cached else ["--others", "--exclude-standard"]
    command += ["--", *paths]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    try:
        data = process.stdout.read(min(MAX_SNAPSHOT_BYTES, MAX_SNAPSHOT_FILES * 4096) + 1)
        require(len(data) <= min(MAX_SNAPSHOT_BYTES, MAX_SNAPSHOT_FILES * 4096), "Content inventory exceeds bounded path budget")
        require(process.wait() == 0, "Cannot enumerate scoped Git content")
        result = set()
        for item in data.split(b"\0"):
            if not item:
                continue
            if cached:
                metadata, separator, item = item.partition(b"\t")
                fields = metadata.split()
                require(separator and len(fields) == 3 and fields[2] == b"0", "Scoped content has an unmerged index")
                require(fields[0] != b"160000", "Submodule content requires separate explicit evidence; parent scopes cannot verify it")
            result.add(os.fsdecode(item))
        require(len(result) <= MAX_SNAPSHOT_FILES, "Content scope exceeds file budget")
        return result
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()


def non_git_paths(root, paths):
    found, exclusions = set(), set()
    patterns = []
    ignore = root / ".gitignore"
    if ignore.exists() or ignore.is_symlink():
        # Conservative simple matching: negation never re-includes excluded data.
        Snapshot().file(root, ".gitignore")
        require(not ignore.is_symlink(), "Non-Git ignore rules must be a regular file")
        require(ignore.stat().st_size <= 1024 * 1024, "Non-Git ignore rules exceed 1 MiB")
        patterns = [line.strip().rstrip("/") for line in ignore.read_text(errors="surrogateescape").splitlines()
                    if line.strip() and not line.startswith(("#", "!"))]
    def ignored(relative):
        return excluded_path(relative) or any(fnmatch.fnmatch(relative, p.lstrip("/"))
            or fnmatch.fnmatch(Path(relative).name, p) or relative.startswith(p.lstrip("/") + "/") for p in patterns)
    def walk(relative):
        require(len(found) + len(exclusions) < MAX_SNAPSHOT_FILES, "Content scope exceeds entry budget")
        safe_ancestors(root, relative)
        if ignored(relative):
            exclusions.add(relative)
            return
        found.add(relative)
        path = root / relative
        try:
            info = path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(path) as entries:
                for entry in entries:
                    walk((Path(relative) / entry.name).as_posix())
    for path in paths:
        walk(path)
    return found, exclusions


def fingerprint_once(project, root, paths):
    root = Path(root)
    for path in paths:
        scope_path(path)
        safe_ancestors(root, path)
    if project.is_git:
        tracked = bounded_git_paths(root, paths, True)
        untracked = bounded_git_paths(root, paths, False)
        exclusions = {path for path in untracked if excluded_path(path)}
        found = tracked | (untracked - exclusions)
        for path in paths:
            # Explicit scopes obey the same exclusions; tracked descendants still
            # make a directory relevant even when its name is conventional cache.
            ignored = git_output(root, "check-ignore", "--", path, optional=True)
            tracked_scope = path in tracked or any(item.startswith(path + "/") for item in tracked)
            if not tracked_scope and (ignored is not None or excluded_path(path)):
                exclusions.add(path)
            else:
                found.add(path)
        # Missing descendants represent absence, independently of whether Git's
        # index still lists them. Explicit missing scopes retain a deleted entry.
        for path in list(found):
            safe_ancestors(root, path)
            if path not in paths and not os.path.lexists(root / path):
                found.remove(path)
        notes = ["Git-ignored untracked files are excluded", "Untracked conventional caches and .env files are excluded"]
    else:
        found, exclusions = non_git_paths(root, paths)
        notes = ["Conventional caches, .env files and conservative root .gitignore matches are excluded; negation is not re-included"]
    # Include directory modes for relevant ancestors, without following symlinks.
    for path in list(found):
        parent = Path(path).parent
        while str(parent) != ".":
            found.add(parent.as_posix())
            parent = parent.parent
    require(len(found) <= MAX_SNAPSHOT_FILES, "Content scope exceeds entry budget")
    snapshot = Snapshot()
    entries = {}
    for path in sorted(found):
        safe_ancestors(root, path)
        try:
            info = (root / path).lstat()
        except FileNotFoundError:
            info = None
        if info is not None and stat.S_ISDIR(info.st_mode):
            entries[path] = {"kind": "directory", "mode": stat.S_IMODE(info.st_mode)}
        else:
            entries[path] = snapshot.file(root, path)
    require(entries, "All requested content scopes are excluded; choose actual relevant source paths")
    payload = {"paths": paths, "entries": entries, "excluded": sorted(exclusions), "exclusion_policy": notes}
    return {"sha256": digest(encoded({key: value for key, value in payload.items() if key != "excluded"})), **payload}


def content_matches(*records):
    return bool(records) and isinstance(records[0], dict) and isinstance(records[0].get("sha256"), str) and all(
        isinstance(record, dict) and record.get("sha256") == records[0]["sha256"] for record in records)


def fingerprint(project, root, paths):
    first = fingerprint_once(project, root, paths)
    require(content_matches(first, fingerprint_once(project, root, paths)), "Scoped content changed during fingerprint; stop writers and retry")
    return first


def task_root(project, task):
    cwd = task_worktree(project, task.get("worktree", str(project.root)))
    if project.is_git:
        return Path(os.fsdecode(git_output(cwd, "rev-parse", "--show-toplevel")).removesuffix("\n")).resolve()
    return project.root


def target_identity(project, root):
    if not project.is_git:
        return {"git": False}
    return {"git": True, "head": os.fsdecode(git_output(root, "rev-parse", "--verify", "HEAD")).strip(),
            "branch": os.fsdecode(git_output(root, "symbolic-ref", "--quiet", "--short", "HEAD", optional=True) or b"").strip() or None}


def dependency_snapshot(project, state, spec, seen=(), bindings=None):
    # Accepted integration records keep their original dependency IDs. Following
    # mutable task.integration pointers would rewrite history or create cycles
    # when an upstream is included in a later batch with its consumer.
    pinned = {item["task"]: item for item in bindings} if bindings is not None else None
    result = []
    for dep in spec["dependencies"]:
        upstream = state["tasks"].get(dep["task"])
        require(upstream and upstream.get("spec"), "Dependency has no structured contract: " + dep["task"])
        binding = {**dep, "spec_hash": upstream["spec_hash"], "spec_revision": upstream["spec_revision"]}
        if dep["kind"] == "integrated":
            integration_id = pinned.get(dep["task"], {}).get("integration") if pinned is not None else upstream.get("integration")
            record = state.get("integrations", {}).get(integration_id)
            require(record is not None, "Dependency has no integration result: " + dep["task"])
            require(integration_id not in seen, "Recursive integration dependency")
            integration_current(project, state, record, seen + (integration_id,), check_target=False)
            binding.update(integration=integration_id, result_hash=record["result_hash"])
        result.append(binding)
    return result


def integrated_baseline(project, state, dependencies, consumer):
    """Check the actual consumer, not just an upstream integration elsewhere.

    Committed results require commit ancestry; this permits normal downstream
    edits on top of that baseline. Uncommitted results additionally require the
    accepted scoped bytes in the consumer, since ancestry cannot carry them.
    """
    for binding in dependencies:
        if binding["kind"] != "integrated":
            continue
        record = state["integrations"][binding["integration"]]
        if project.is_git:
            upstream_head = record["result_target"]["head"]
            require(git_output(consumer, "merge-base", "--is-ancestor", upstream_head, "HEAD", optional=True) is not None,
                    "Consumer baseline does not contain integrated dependency: " + binding["task"])
        # Freeze this fact at finish. A later source-tree edit or commit must not
        # change whether an already accepted result required uncommitted bytes.
        if not (project.is_git and record.get("result_committed") is True):
            require(content_matches(record["result_content"], fingerprint(project, consumer, record["paths"])),
                    "Consumer content does not contain uncommitted integrated dependency: " + binding["task"])


def committed_scope(project, root, paths):
    if not project.is_git:
        return False
    clean = git_output(root, "-c", "core.filemode=true", "--literal-pathspecs", "diff", "--quiet", "--no-ext-diff", "HEAD", "--", *paths, optional=True)
    return clean is not None and not any(not excluded_path(path) for path in bounded_git_paths(root, paths, False))


def active_claims(state, exclude_task):
    attempts = [item for item in state["attempts"] if outstanding(item)]
    covered = {item["task"] for item in attempts}
    claims = [(item["task"], item.get("resources", state["tasks"][item["task"]].get("spec", {}).get("resources", [])))
              for item in attempts if item["task"] != exclude_task]
    claims += [(key, task.get("spec", {}).get("resources", [])) for key, task in state["tasks"].items()
               if key != exclude_task and key not in covered and (task["state"] in ("running", "unknown")
               or (task.get("spec") and task["state"] == "reserved"))]
    return claims


def readiness(project, state, config, task_id, action="dispatch", worker=None):
    task = state["tasks"].get(task_id)
    require(task is not None, "Unknown task: " + task_id)
    blockers, dependencies, overlaps = [], [], []
    if state["mode"] != "active":
        blockers.append("Managed work is stopped while project is " + state["mode"])
    if config["permissions"].get(action) != "allow":
        blockers.append("Action %s is not allowed by project policy" % action)
    if action == "dispatch" and task["state"] not in ("reserved", "blocked"):
        blockers.append("Dispatch requires an explicit reserved or blocked task")
    try:
        resources_available(project, state, config, SimpleNamespace(action=action, task=task_id, worker=worker), task_root(project, task))
    except (Failure, OSError) as exc:
        blockers.append(str(exc))
    if not task.get("spec"):
        blockers.append("Legacy task has no structured specification")
    else:
        try:
            api_required(config)
            dependencies = dependency_snapshot(project, state, task["spec"])
            consumer = task_root(project, task)
            integrated_baseline(project, state, dependencies, consumer)
            fingerprint(project, consumer, task["spec"]["paths"])
        except (Failure, OSError) as exc:
            blockers.append(str(exc))
        resources = set(task["spec"]["resources"])
        for key, held in active_claims(state, task_id):
            common = sorted(resources & set(held))
            if common:
                blockers.append("Exclusive resources held by %s: %s" % (key, ", ".join(common)))
            other = state["tasks"][key]
            if other.get("worktree", str(project.root)) == task.get("worktree", str(project.root)):
                for left in task["spec"]["paths"]:
                    for right in other.get("spec", {}).get("paths", []):
                        if left == "." or right == "." or left == right or left.startswith(right + "/") or right.startswith(left + "/"):
                            overlaps.append({"task": key, "paths": [left, right]})
    if any(item["task"] == task_id and outstanding(item) for item in state["attempts"]):
        blockers.append("Task has an outstanding attempt")
    if task["state"] in ("running", "unknown", "integrated") or task.get("needs_reconciliation"):
        blockers.append("Task state needs explicit reconciliation before another attempt")
    return {"task": task_id, "action": action, "ready": not blockers, "blockers": blockers, "dependencies": dependencies,
            "spec_hash": task.get("spec_hash"), "spec_revision": task.get("spec_revision"), "content_conflicts": overlaps,
            "dispatch_state_ready": task["state"] in ("reserved", "blocked"), "read_only": True}


def before_attempt(project, state, config, task_id, task, args, cwd):
    result = {}
    if task and task.get("spec"):
        api_required(config)
        candidate = {**task, "worktree": str(cwd)}
        temporary = {**state, "tasks": {**state["tasks"], task_id: candidate}}
        ready = readiness(project, temporary, config, task_id, args.action, args.worker)
        require(ready["ready"], "Task is not ready: " + "; ".join(ready["blockers"]))
        result.update(spec_hash=task["spec_hash"], spec_revision=task["spec_revision"], dependencies=ready["dependencies"],
                      implementers=implementation_sources(state, task_id, task),
                      resources=task["spec"]["resources"], content_paths=task["spec"]["paths"], content_root=str(task_root(project, candidate)))
    if args.integration:
        require(args.action == "verify", "Integration attempts must use --action verify")
        record = state.get("integrations", {}).get(args.integration)
        require(record and record["state"] == "begun", "Integration is not awaiting verification")
        require(str(task_root(project, {"worktree": str(cwd)})) == record["target"], "Integration verification must run in the target worktree")
        bindings_current(project, state, record)
        result.update(integration=args.integration, integration_bindings=record["participants"], content_paths=record["paths"], content_root=record["target"])
    if args.action == "verify" and result.get("content_paths"):
        result["content_before"] = fingerprint(project, Path(result["content_root"]), result["content_paths"])
        if args.integration:
            result["target_before"] = target_identity(project, Path(result["content_root"]))
    return result


def merge_facts(project, record, identity):
    facts = []
    for binding in record["participants"]:
        source_head = binding["source_target"].get("head")
        ancestry = None
        if project.is_git and source_head and identity and identity.get("head"):
            ancestry = git_output(Path(record["target"]), "merge-base", "--is-ancestor", source_head, identity["head"], optional=True) is not None
        facts.append({"task": binding["task"], "source_head": source_head, "source_is_ancestor": ancestry,
                      "membership": "declared", "semantic_inclusion_proven": False})
    return facts


def after_attempt(project, state, attempt):
    if attempt.get("content_before"):
        try:
            if attempt.get("integration"):
                attempt["target_after"] = target_identity(project, Path(attempt["content_root"]))
            attempt["content_after"] = fingerprint(project, Path(attempt["content_root"]), attempt["content_paths"])
            attempt["log_snapshot"] = Snapshot().file(project.runtime, "logs/" + attempt["id"] + ".log")
        except (Failure, OSError) as exc:
            attempt["content_error"] = str(exc)
    if attempt.get("integration"):
        record = state["integrations"][attempt["integration"]]
        observation = {"attempt": attempt["id"], "returncode": attempt["returncode"], "cancelled": attempt["cancelled"],
                       "target_before": attempt.get("target_before"), "target_after": attempt.get("target_after"),
                       "content_error": attempt.get("content_error"), "at": timestamp(),
                       "merge_facts": merge_facts(project, record, attempt.get("target_after"))}
        record.setdefault("observations", []).append(observation)


def load_receipt(project, state, receipt_id):
    pointer = state.get("evidence", {}).get(receipt_id)
    require(pointer is not None, "Missing evidence receipt: " + receipt_id)
    directory = project.runtime / "evidence"
    require(not directory.is_symlink(), "Evidence directory is a symlink")
    receipt = read_json(directory / (receipt_id + ".json"))
    require(digest(encoded(receipt)) == pointer["sha256"], "Evidence receipt was tampered: " + receipt_id)
    return receipt


def checkpoint_records(project, state, snapshot):
    records = {}
    logs = set()
    for receipt_id in state.get("evidence", {}):
        receipt = load_receipt(project, state, receipt_id)
        relative = "evidence/" + receipt_id + ".json"
        records[relative] = snapshot.file(project.runtime, relative)
        if receipt["source"]["kind"] == "attempt":
            logs.add(receipt["source"]["attempt"])
    logs.update(record["attempt"] for record in state.get("integrations", {}).values() if record.get("attempt"))
    logs.update(observation["attempt"] for record in state.get("integrations", {}).values() for observation in record.get("observations", []))
    for attempt_id in sorted(logs):
        identifier(attempt_id, "evidence attempt")
        relative = "logs/" + attempt_id + ".log"
        records[relative] = snapshot.file(project.runtime, relative)
        require(records[relative]["kind"] == "file", "Verification log is unavailable for recovery")
    return {"evidence": copy.deepcopy(state.get("evidence", {})), "integrations": copy.deepcopy(state.get("integrations", {})),
            "required_integrations": copy.deepcopy(state.get("required_integrations", {})), "files": records}


def review_required(config, task):
    return config["review"].get("independent", False) or task["spec"]["review"]["independent"]


def check_reviewer(config, task, receipt):
    if receipt["source"]["kind"] == "manual":
        require(config["review"].get("allow_manual", False), "Project review policy does not permit manual evidence")
    if review_required(config, task):
        require(receipt.get("role") == "reviewer" and receipt.get("reviewer") not in receipt.get("implementers", []),
                "Independent review requires a distinct declared reviewer and reviewer role")


def receipt_artifacts(project, receipt):
    root = task_worktree(project, receipt["content_root"]) if receipt["artifacts"] else None
    budget = Snapshot()
    for artifact in receipt["artifacts"]:
        require(budget.file(root, artifact["path"]) == artifact["content"], "Evidence artifact is missing or tampered: " + artifact["path"])
    if receipt["source"]["kind"] == "attempt":
        attempt_id = receipt["source"]["attempt"]
        identifier(attempt_id, "evidence attempt")
        require(budget.file(project.runtime, "logs/" + attempt_id + ".log") == receipt["source"]["log_sha256"], "Evidence verification log is missing or tampered")


def applicable(project, state, config, task_id, receipt_id, check_content=True):
    task = state["tasks"][task_id]
    receipt = load_receipt(project, state, receipt_id)
    require(receipt["task"] == task_id and receipt["result"] == "passed", "Evidence is not a passing receipt for this task")
    require(receipt["spec_hash"] == task.get("spec_hash") and receipt["spec_revision"] == task.get("spec_revision"), "Evidence requirements are stale")
    require(receipt["dependencies"] == dependency_snapshot(project, state, task["spec"]), "Evidence dependencies are stale")
    integrated_baseline(project, state, receipt["dependencies"], task_root(project, task))
    check_reviewer(config, task, receipt)
    receipt_artifacts(project, receipt)
    if check_content:
        root = task_root(project, task)
        require(content_matches(receipt["content"], fingerprint(project, root, task["spec"]["paths"])), "Evidence content is stale")
    return receipt


def acceptance(project, state, config, task_id):
    task = state["tasks"][task_id]
    errors = []
    for receipt_id in reversed(task.get("evidence", [])):
        try:
            return applicable(project, state, config, task_id, receipt_id)
        except (Failure, OSError) as exc:
            errors.append(str(exc))
    raise Failure("Task has no applicable structured evidence: " + ("; ".join(errors) or "missing receipt"))


def evidence_status(project, state, config, task_id):
    task = state["tasks"].get(task_id)
    require(task is not None, "Unknown task: " + task_id)
    results = []
    for receipt_id in task.get("evidence", []):
        try:
            receipt = applicable(project, state, config, task_id, receipt_id)
            results.append({"id": receipt_id, "applicable": True, "receipt": receipt})
        except (Failure, OSError) as exc:
            results.append({"id": receipt_id, "applicable": False, "reason": str(exc)})
    return {"task": task_id, "protocol": "structured" if task.get("spec") else "legacy-note-only", "evidence": results, "read_only": True}


def evidence(project, args):
    with project.lock(shared=args.operation == "status"):
        state = project.load()
        config = project.settings(state)
        if args.operation == "status":
            return evidence_status(project, state, config, args.task)
        project.owned(state, args.session, args.epoch)
        api_required(config)
        task = state["tasks"].get(args.task)
        require(task and task.get("spec"), "Evidence requires a structured task")
        require(not any(a["task"] == args.task and outstanding(a) for a in state["attempts"]), "Cannot accept evidence while task work is outstanding")
        require(args.manual != bool(args.attempt), "Choose exactly one of --attempt or --manual")
        identifier(args.reviewer, "reviewer")
        text(args.note, "evidence note")
        root = task_root(project, task)
        dependencies = dependency_snapshot(project, state, task["spec"])
        integrated_baseline(project, state, dependencies, root)
        content = fingerprint(project, root, task["spec"]["paths"])
        if args.manual:
            require(config["review"].get("allow_manual", False), "Project review policy does not permit manual evidence")
            require(args.artifact, "Manual evidence requires at least one explicit artifact")
            source = {"kind": "manual", "declared_by": args.session}
            implementers = implementation_sources(state, args.task, task)
        else:
            attempt = next((a for a in state["attempts"] if a["id"] == args.attempt), None)
            require(attempt and attempt["task"] == args.task and attempt["action"] == "verify", "Machine evidence requires this task's managed verification attempt")
            require(attempt.get("returncode") == 0 and attempt["state"] == "reported" and not attempt.get("cancelled") and not attempt.get("reconciled"), "Machine evidence requires completed successful verification")
            require(attempt.get("spec_hash") == task["spec_hash"] and attempt.get("spec_revision") == task["spec_revision"]
                    and attempt.get("dependencies") == dependencies, "Verification requirements/dependencies are stale")
            require(content_matches(attempt.get("content_before"), attempt.get("content_after"), content) and not attempt.get("content_error"),
                    "Verification content changed or is stale; do not rebind old results")
            require(args.reviewer == attempt["reviewer"] and args.role == attempt["role"], "Evidence reviewer/role must match the verification declaration")
            require(attempt.get("log_snapshot") == Snapshot().file(project.runtime, "logs/" + attempt["id"] + ".log"), "Verification log changed after completion")
            require(attempt.get("implementers") is not None or not review_required(config, task),
                    "Verification lacks frozen implementation provenance; run a new independent verification")
            implementers = attempt.get("implementers", implementation_sources(state, args.task, task))
            source = {"kind": "attempt", "attempt": attempt["id"], "log_sha256": attempt["log_snapshot"]}
        artifacts = []
        budget = Snapshot()
        for path in args.artifact:
            scope_path(path)
            record = budget.file(root, path)
            require(record["kind"] == "file", "Evidence artifacts must be existing regular files")
            artifacts.append({"path": path, "content": record})
        receipt = {"id": uuid.uuid4().hex, "task": args.task, "spec_hash": task["spec_hash"], "spec_revision": task["spec_revision"],
                   "dependencies": dependencies, "content": content, "content_root": str(root), "source": source, "result": args.result, "reviewer": args.reviewer,
                   "role": args.role, "implementers": implementers, "artifacts": artifacts, "note": args.note,
                   "created_at": timestamp(), "session": args.session, "epoch": args.epoch}
        check_reviewer(config, task, receipt)
        directory = project.runtime / "evidence"
        require(not directory.is_symlink(), "Refusing symlink evidence directory")
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / (receipt["id"] + ".json")
        with path.open("xb") as stream:
            stream.write(encoded(receipt))
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(directory)
        state.setdefault("evidence", {})[receipt["id"]] = {"sha256": digest(encoded(receipt)), "task": args.task}
        task.setdefault("evidence", []).append(receipt["id"])
        project.save(state)
        return {"evidence": receipt, "accepted": False}


def bindings_current(project, state, record, seen=()):
    for binding in record["participants"]:
        task = state["tasks"].get(binding["task"])
        require(task and task.get("spec_hash") == binding["spec_hash"] and task.get("spec_revision") == binding["spec_revision"], "Integration participant requirements changed")
        historical = record["state"] == "passed"
        dependencies = dependency_snapshot(project, state, task["spec"], seen,
                                           bindings=binding["dependencies"] if historical else None)
        require(dependencies == binding["dependencies"], "Integration participant dependencies changed")
        # Before acceptance the live source must still contain its prerequisites.
        # Afterwards the immutable record and retained assembly are authoritative;
        # an approved cleanup may have removed the original worker checkout.
        if not historical and any(dep["kind"] == "integrated" for dep in dependencies):
            integrated_baseline(project, state, dependencies, task_root(project, task))
        receipt = load_receipt(project, state, binding["evidence"])
        require(digest(encoded(receipt)) == binding["evidence_hash"], "Integration participant evidence changed")
        check_reviewer(project.settings(state), task, receipt)
        receipt_artifacts(project, receipt)


def integration_current(project, state, record, seen=(), check_target=True):
    require(record["state"] == "passed", "Integration result is not accepted")
    require(digest(encoded({key: value for key, value in record.items() if key != "result_hash"})) == record.get("result_hash"), "Integration result record is corrupt")
    require(Snapshot().file(project.runtime, "logs/" + record["attempt"] + ".log") == record["verification_log"], "Integration verification log is missing or tampered")
    bindings_current(project, state, record, seen)
    if check_target:
        root = task_worktree(project, record["target"])
        require(target_identity(project, root) == record["result_target"], "Integration target baseline changed")
        require(content_matches(fingerprint(project, root, record["paths"]), record["result_content"]), "Integration result content is stale")
        for binding in record["participants"]:
            integrated_baseline(project, state, binding["dependencies"], root)
    return record


def integration(project, args):
    with project.lock(shared=args.operation == "status"):
        state = project.load()
        config = project.settings(state)
        records = state.setdefault("integrations", {})
        if args.operation == "status":
            selected = [records[args.id]] if args.id in records else list(records.values()) if not args.id else []
            require(selected or not args.id, "Unknown integration ID")
            results = []
            for record in selected:
                observed = {}
                try:
                    identity = target_identity(project, task_worktree(project, record["target"]))
                    observed = {"observed_target": identity, "observed_merge_facts": merge_facts(project, record, identity)}
                    integration_current(project, state, record, (record["id"],))
                    results.append({**record, **observed, "applicable": True})
                except (Failure, OSError) as exc:
                    results.append({**record, **observed, "applicable": False, "reason": str(exc)})
            return {"integrations": results, "read_only": True}
        project.owned(state, args.session, args.epoch)
        api_required(config)
        identifier(args.id, "integration ID")
        if args.operation == "begin":
            require(args.id not in records, "Integration ID already exists; use a new ID, evidence is retained")
            strings(args.tasks, "integration tasks", nonempty=True)
            target = task_root(project, {"worktree": args.target or str(project.root)})
            participants, paths = [], set()
            for task_id in args.tasks:
                task = state["tasks"].get(task_id)
                require(task and task.get("spec"), "Integration participant needs a structured spec")
                require(task["state"] in ("verified", "integrated"), "Integration participant must be verified first")
                require(not any(a["task"] == task_id and outstanding(a) for a in state["attempts"]), "Integration participant has outstanding work")
                receipt = acceptance(project, state, config, task_id)
                source = task_root(project, task)
                participants.append({"task": task_id, "spec_hash": task["spec_hash"], "spec_revision": task["spec_revision"],
                                     "dependencies": receipt["dependencies"], "evidence": receipt["id"], "evidence_hash": digest(encoded(receipt)),
                                     "source": str(source), "source_target": target_identity(project, source)})
                paths.update(task["spec"]["paths"])
            # Extra assembly scopes may widen, never silently narrow participant scopes.
            paths.update(scope_path(path) for path in args.paths)
            identity = target_identity(project, target)
            if args.require_push:
                require(project.is_git and identity["branch"] == config["git"]["integration_branch"], "Required push result must target the configured integration branch")
            record = {"id": args.id, "state": "begun", "participants": participants, "target": str(target), "paths": sorted(paths),
                      "begin_target": identity, "begin_content": fingerprint(project, target, sorted(paths)), "require_push": args.require_push,
                      "created_at": timestamp(), "session": args.session, "epoch": args.epoch}
            records[args.id] = record
            if args.require_push:
                state.setdefault("required_integrations", {})[identity["branch"]] = args.id
        else:
            record = records.get(args.id)
            require(record is not None, "Unknown integration ID")
            if record["state"] == "passed":
                require(record["attempt"] == args.attempt, "Integration already finished with another attempt")
                integration_current(project, state, record, (args.id,))
                return {"integration": record, "already_finished": True}
            bindings_current(project, state, record, (args.id,))
            active = [item for item in state["attempts"] if outstanding(item)]
            for item in active:
                require(str(task_root(project, {"worktree": item["cwd"]})) != record["target"], "Integration target has outstanding work")
            covered = {item["task"] for item in active}
            for key, task in state["tasks"].items():
                if key not in covered and task["state"] in ("running", "unknown"):
                    require(str(task_root(project, task)) != record["target"], "Integration target has unknown manual work")
            attempt = next((item for item in state["attempts"] if item["id"] == args.attempt), None)
            require(attempt and attempt.get("integration") == args.id and attempt["action"] == "verify" and attempt.get("returncode") == 0
                    and attempt["state"] == "reported" and not attempt.get("cancelled") and not attempt.get("reconciled"), "Finish requires successful managed integration verification")
            require(attempt.get("integration_bindings") == record["participants"], "Integration verification bindings differ")
            content = fingerprint(project, Path(record["target"]), record["paths"])
            identity = target_identity(project, Path(record["target"]))
            require(content_matches(attempt.get("content_before"), attempt.get("content_after"), content) and not attempt.get("content_error"), "Integration verification content is stale or changed during verification")
            require(attempt.get("target_before") == attempt.get("target_after") == identity, "Integration verification target changed")
            require(attempt.get("log_snapshot") == Snapshot().file(project.runtime, "logs/" + args.attempt + ".log"), "Integration verification log changed after completion")
            require(identity.get("branch") == record["begin_target"].get("branch"), "Integration target branch changed")
            for binding in record["participants"]:
                integrated_baseline(project, state, binding["dependencies"], Path(record["target"]))
            record.update(state="passed", attempt=args.attempt, result_content=content, result_target=identity, merge_facts=merge_facts(project, record, identity),
                          result_committed=committed_scope(project, Path(record["target"]), record["paths"]), verification_log=attempt["log_snapshot"],
                          finished_at=timestamp(), note=text(args.note, "integration membership/result note"))
            record["result_hash"] = digest(encoded(record))
            for binding in record["participants"]:
                state["tasks"][binding["task"]].update(state="integrated", integration=args.id)
        project.save(state)
        return {"integration": record}


def push_gate(project, state, config, command):
    required = state.get("required_integrations", {})
    if not required:
        return
    # Cooperating argv protocol: explicit remote and source:destination refspecs.
    # Ambiguous aliases, shell wrappers, deletion, force and default push mappings
    # cannot establish which result is being published and therefore fail closed.
    require(len(command) >= 4 and Path(command[0]).name == "git" and command[1] == "push"
            and not command[2].startswith("-"), "Required integration gating needs git push REMOTE SOURCE:DESTINATION")
    for refspec in command[3:]:
        require(not refspec.startswith(("-", "+")) and refspec.count(":") == 1, "Push gate requires explicit non-forced SOURCE:DESTINATION refspecs")
        source, destination = refspec.split(":")
        require(source and destination and not any(c in refspec for c in "*^~"), "Unsupported push refspec for integration gating")
        branch = destination.removeprefix("refs/heads/")
        if branch not in required:
            continue
        record = state["integrations"][required[branch]]
        integration_current(project, state, record, (record["id"],))
        require(record["result_target"]["branch"] == branch == config["git"]["integration_branch"], "Push integration branch differs from required result")
        head = os.fsdecode(git_output(project.root, "rev-parse", "--verify", "--end-of-options", source + "^{commit}")).strip()
        require(head == record["result_target"]["head"], "Push source does not match the accepted integration result")
        require(not git_output(Path(record["target"]), "status", "--porcelain", "--untracked-files=normal"), "Accepted integration worktree must be clean before push")
