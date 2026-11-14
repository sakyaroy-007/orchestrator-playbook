#!/usr/bin/env python3
"""Build the five standalone skills; run with python3 -I scripts/build-skills.py.

The output is a skills root, not an installation target. Only named skill
subdirectories bearing a valid .playbook-generated.json are updated. Unknown
siblings/files are retained, local edits are refused, and symlinks are never
followed. An obsolete generated file is removed only if its recorded digest and
mode still match. Sources and all destinations are checked before any writes.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile


SKILLS = {
    "playbook": ("Playbook", "Choose a project lifecycle action"),
    "playbook-start": ("Playbook Start", "Set up or adopt a project after initial questions"),
    "playbook-resume": ("Playbook Resume", "Resume the current session's recorded work"),
    "playbook-handoff": ("Playbook Handoff", "Checkpoint and prepare a session handoff"),
    "playbook-takeover": ("Playbook Takeover", "Accept an explicitly authorized session handoff"),
}
RUNTIME_SCRIPTS = (
    "playbook.py", "playbook_work.py", "playbook-foundation.py", "policy-dispatch.py",
    "hermes-worker.py", "hermes_gateway.py", "init-plan.sh", "wt.sh", "dispatch.sh",
)
REFERENCE_NAMES = (
    "bootstrap", "cards", "configuration", "dispatch", "handoff-files", "hermes",
    "lessons", "lifecycle", "review", "stakeholder", "work-protocol",
)
TEMPLATE_NAMES = (
    "ADR-001.md", "ADR.md", "AGENTS-snippet.md", "HANDOFF.md", "PLAYBOOK.md", "PROJECT-README.md",
    "TEAM.md", "WORKER.md", "changes-README.md", "external.md", "plan-README.md",
    "questions.md", "review.md", "spike-card.md", "status.md", "task-card.md", "tasks.md",
)
MARKER = ".playbook-generated.json"
GENERATOR = "orchestrator-playbook/scripts/build-skills.py"
FORMAT_VERSION = 1


class BuildError(Exception):
    pass


def no_symlinks(path):
    """Check even missing paths and dangling links, without resolving them."""
    for part in reversed((path,) + tuple(path.parents)):
        if part.is_symlink():
            raise BuildError("symlink path is not allowed: {}".format(part))
        if part != path and part.exists() and not part.is_dir():
            raise BuildError("parent is not a directory: {}".format(part))


def regular_file(path):
    no_symlinks(path)
    try:
        info = path.stat()
    except FileNotFoundError:
        raise BuildError("missing required source/file: {}".format(path)) from None
    if not stat.S_ISREG(info.st_mode):
        raise BuildError("expected a regular file: {}".format(path))
    return path.read_bytes()


def digest(content):
    return hashlib.sha256(content).hexdigest()


def record(content, mode):
    return {"sha256": digest(content), "mode": mode}


def manifest_bytes(name, files):
    data = {
        "format_version": FORMAT_VERSION,
        "generator": GENERATOR,
        "skill": name,
        "files": {rel: record(*value) for rel, value in sorted(files.items())},
    }
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def render_entry(path, name):
    content = regular_file(path)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise BuildError("skill source must be UTF-8: {}".format(path)) from None
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        raise BuildError("missing YAML frontmatter: {}".format(path))
    frontmatter = match.group(1)
    names = re.findall(r"^name:\s*([^\r\n]+)", frontmatter, re.MULTILINE)
    explicit = re.findall(
        r"^disable-model-invocation:\s*([^\r\n]+)", frontmatter, re.MULTILINE
    )
    if len(names) != 1 or names[0].strip().strip("\"'") != name:
        raise BuildError("source name must be {}: {}".format(name, path))
    if explicit != ["true"]:
        raise BuildError("source requires disable-model-invocation: true: {}".format(path))
    notice = (
        "\n<!-- Generated from skill-src/{} by scripts/build-skills.py; "
        "edit the source, then rebuild. -->\n"
    ).format(path.name)
    return (text[:match.end()] + notice + text[match.end():]).encode("utf-8")


def resource_tree(source, directory):
    """Only Markdown documentation/templates are runtime resources here."""
    root = source / directory
    no_symlinks(root)
    if not root.is_dir():
        raise BuildError("missing required source directory: {}".format(root))
    files = {}
    for parent, directories, names in os.walk(root, followlinks=False):
        # Hidden/editor files and non-Markdown extras are not package inputs.
        directories[:] = sorted(name for name in directories if not name.startswith("."))
        for name in directories:
            no_symlinks(Path(parent) / name)
        for name in sorted(names):
            if name.startswith(".") or not name.endswith(".md"):
                continue
            path = Path(parent) / name
            files[path.relative_to(source).as_posix()] = (regular_file(path), 0o644)
    return files


def build_spec(source):
    resources = {}
    for name in RUNTIME_SCRIPTS:
        rel = "scripts/" + name
        resources[rel] = (regular_file(source / rel), 0o755)
    resources.update(resource_tree(source, "references"))
    resources.update(resource_tree(source, "templates"))
    required = [
        "references/{}{}.md".format(name, language)
        for name in REFERENCE_NAMES for language in ("", ".zh")
    ] + ["templates/" + name for name in TEMPLATE_NAMES]
    for rel in required:
        if rel not in resources:
            raise BuildError("missing required source: {}".format(source / rel))
    result = {}
    for name, (title, description) in SKILLS.items():
        files = dict(resources)
        for suffix, output in ((".md", "SKILL.md"), (".zh.md", "SKILL.zh.md")):
            files[output] = (render_entry(source / "skill-src" / (name + suffix), name), 0o644)
        yaml = (
            "interface:\n"
            "  display_name: {title}\n"
            "  short_description: {description}\n"
            "  default_prompt: {prompt}\n"
            "policy:\n"
            "  allow_implicit_invocation: false\n"
        ).format(
            title=json.dumps(title), description=json.dumps(description),
            prompt=json.dumps("Use $" + name + " for my explicitly requested project lifecycle action."),
        )
        files["agents/openai.yaml"] = (yaml.encode("utf-8"), 0o644)
        result[name] = files
    return result


def safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    parts = PurePosixPath(value).parts
    return (
        not value.startswith("/") and all(p not in (".", "..") for p in parts)
        and PurePosixPath(value).as_posix() == value and value != MARKER
        and (value in ("SKILL.md", "SKILL.zh.md", "agents/openai.yaml")
             or (len(parts) > 1 and parts[0] in ("scripts", "references", "templates")))
    )


def read_manifest(directory, name):
    marker = directory / MARKER
    if not marker.exists() and not marker.is_symlink():
        raise BuildError("refusing unmarked skill directory: {}".format(directory))
    try:
        data = json.loads(regular_file(marker))
    except (ValueError, UnicodeDecodeError):
        raise BuildError("invalid generated marker: {}".format(marker)) from None
    if (
        not isinstance(data, dict)
        or data.get("format_version") != FORMAT_VERSION
        or data.get("generator") != GENERATOR
        or data.get("skill") != name
        or not isinstance(data.get("files"), dict)
        or not data["files"]
    ):
        raise BuildError("unrecognized generated marker: {}".format(marker))
    for rel, saved in data["files"].items():
        if (
            not safe_relative(rel) or not isinstance(saved, dict)
            or set(saved) != {"sha256", "mode"}
            or not isinstance(saved["sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", saved["sha256"]) is None
            or type(saved["mode"]) is not int or saved["mode"] not in (0o644, 0o755)
        ):
            raise BuildError("invalid file record in {}: {}".format(marker, rel))
    return data["files"]


def scan_destination(directory):
    """Reject links/special files even in retained, unknown subdirectories."""
    no_symlinks(directory)
    if not directory.is_dir():
        raise BuildError("output is not a directory: {}".format(directory))
    for parent, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            path = Path(parent) / name
            no_symlinks(path)
            if not path.is_dir() and not stat.S_ISREG(path.stat().st_mode):
                raise BuildError("output contains a non-regular file: {}".format(path))


def prepare(output, spec, check):
    """Validate the entire batch before returning any proposed mutations."""
    no_symlinks(output)
    if output.exists() and not output.is_dir():
        raise BuildError("output is not a directory: {}".format(output))
    plans = []
    drift = []
    for name, files in spec.items():
        directory = output / name
        old = {}
        if directory.exists() or directory.is_symlink():
            scan_destination(directory)
            old = read_manifest(directory, name)
        else:
            drift.append("missing skill: " + name)
        writes = {}
        deletes = []
        for rel in sorted(set(old) | set(files)):
            path = directory / rel
            no_symlinks(path)
            actual = None
            if path.exists():
                if not path.is_file():
                    raise BuildError("file path is occupied by a directory: {}".format(path))
                actual = record(regular_file(path), stat.S_IMODE(path.stat().st_mode))
            if actual is not None and rel not in old:
                raise BuildError("refusing to overwrite untracked output: {}".format(path))
            if actual is not None and actual != old.get(rel) and not check:
                raise BuildError("generated file was locally modified; preserve it before rebuilding: {}".format(path))
            if rel in files:
                expected = record(*files[rel])
                if actual != expected:
                    drift.append("changed or missing: {}/{}".format(name, rel))
                    writes[rel] = files[rel]
            else:
                drift.append("obsolete generated file: {}/{}".format(name, rel))
                if actual is not None:
                    deletes.append(rel)
        marker = manifest_bytes(name, files)
        marker_path = directory / MARKER
        if not marker_path.exists() or regular_file(marker_path) != marker or stat.S_IMODE(marker_path.stat().st_mode) != 0o644:
            drift.append("changed or missing marker: " + name)
            writes[MARKER] = (marker, 0o644)
        plans.append((directory, writes, deletes))
    return plans, drift


def atomic_write(path, content, mode):
    no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".playbook-build-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, help="skills root to build/check (default: repository skills/); use a physical path without symlink ancestors")
    parser.add_argument("--check", action="store_true", help="read-only check; exit 1 for drift, 2 for invalid/unsafe inputs")
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parent.parent
    raw_output = args.output if args.output is not None else source / "skills"
    if ".." in raw_output.parts:
        parser.error("--output must not contain '..'; supply the physical destination path")
    output = raw_output.absolute()
    try:
        # An output below canonical inputs could recursively package its own output.
        for reserved in ("skill-src", "scripts", "references", "templates", ".git"):
            if output == source / reserved or source / reserved in output.parents:
                raise BuildError("output must not be inside source inputs: {}".format(output))
        spec = build_spec(source)
        plans, drift = prepare(output, spec, args.check)
        if args.check:
            if drift:
                print("Generated skills differ:\n  " + "\n  ".join(drift), file=sys.stderr)
                return 1
            print("All 5 generated skills match their sources.")
            return 0
        for directory, writes, deletes in plans:
            for rel, (content, mode) in writes.items():
                if rel != MARKER:
                    atomic_write(directory / rel, content, mode)
            for rel in deletes:
                no_symlinks(directory / rel)
                (directory / rel).unlink()
            if MARKER in writes:
                atomic_write(directory / MARKER, *writes[MARKER])
        print("Built 5 standalone skills in {} ({} changes).".format(output, len(drift)))
        return 0
    except (BuildError, OSError) as error:
        print("build-skills: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
