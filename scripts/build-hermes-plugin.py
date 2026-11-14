#!/usr/bin/env python3
"""Build a self-contained native Hermes plugin, without installing or enabling it.

Run with python3 -I scripts/build-hermes-plugin.py --output /physical/staging/plugin.
The output is the plugin directory itself. --check is read-only (0=current,
1=drift, 2=invalid/unsafe). Rebuilds preserve unknown files and refuse local edits,
unmarked directories and symlinks. The generated marker is provenance, not a
security signature. Build only one writer against an output directory at a time.
"""

import argparse
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys


ROOT = Path(__file__).resolve().parent.parent
MARKER = ".playbook-hermes-generated.json"
GENERATOR = "orchestrator-playbook/scripts/build-hermes-plugin.py"
PLUGIN_FILES = ("__init__.py", "plugin.yaml", "README.md")


def skill_builder(source):
    """Reuse the canonical skill builder's runtime dependency and resource rules."""
    path = source / "scripts" / "build-skills.py"
    spec = importlib.util.spec_from_file_location("playbook_skill_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_spec(source, shared):
    # The canonical builder owns both the resource allowlist and source checks.
    skill_specs = shared.build_spec(source)
    resources = {
        rel: item for rel, item in skill_specs["playbook"].items()
        if rel.startswith(("scripts/", "references/", "templates/"))
    }
    if any(PurePosixPath(rel).name in ("SKILL.md", "SKILL.zh.md") for rel in resources):
        raise shared.BuildError("plugin resources must not contain discoverable SKILL.md files")
    entries = {}
    for name in skill_specs:
        entries[name] = {}
        for language, suffix in (("en", ".md"), ("zh", ".zh.md")):
            rel = "entries/" + name + suffix
            # Keep canonical bytes, including explicit-only frontmatter. These
            # files are private plugin resources, never ordinary skill entries.
            resources[rel] = (shared.regular_file(source / "skill-src" / (name + suffix)), 0o644)
            entries[name][language] = rel
    catalog = {
        "format_version": 1,
        "entries": entries,
        "files": {rel: shared.record(*value) for rel, value in sorted(resources.items())},
    }
    files = {"resources/" + rel: value for rel, value in resources.items()}
    files["resources/catalog.json"] = (json_bytes(catalog), 0o644)
    for name in PLUGIN_FILES:
        files[name] = (shared.regular_file(source / "adapters" / "hermes" / name), 0o644)
    return files


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def safe_relative(value):
    if not isinstance(value, str) or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(p in (".", "..") for p in path.parts):
        return False
    if value in PLUGIN_FILES or value == "resources/catalog.json":
        return True
    return (len(path.parts) >= 3 and path.parts[0] == "resources"
            and path.parts[1] in ("entries", "scripts", "references", "templates")
            and path.name not in ("SKILL.md", "SKILL.zh.md"))


def read_marker(directory, shared):
    path = directory / MARKER
    if not path.exists():
        raise shared.BuildError("refusing unmarked plugin directory: {}".format(directory))
    try:
        data = json.loads(shared.regular_file(path))
    except (ValueError, UnicodeDecodeError):
        raise shared.BuildError("invalid generated marker: {}".format(path)) from None
    if (not isinstance(data, dict) or data.get("format_version") != 1
            or data.get("generator") != GENERATOR or not isinstance(data.get("files"), dict)
            or not data["files"]):
        raise shared.BuildError("unrecognized generated marker: {}".format(path))
    for rel, record in data["files"].items():
        if (not safe_relative(rel) or not isinstance(record, dict)
                or set(record) != {"sha256", "mode"}
                or not isinstance(record["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
                or type(record["mode"]) is not int or record["mode"] not in (0o644, 0o755)):
            raise shared.BuildError("invalid generated file record: {}".format(rel))
    return data["files"]


def prepare(output, files, shared, check):
    shared.no_symlinks(output)
    old = {}
    if output.exists():
        shared.scan_destination(output)
        if any(path.name in ("SKILL.md", "SKILL.zh.md") for path in output.rglob("SKILL*.md")):
            raise shared.BuildError("plugin output contains discoverable skill files; preserve them outside the package")
        old = read_marker(output, shared)
    writes, deletes, drift = {}, [], []
    for rel in sorted(set(old) | set(files)):
        path = output / rel
        shared.no_symlinks(path)
        actual = None
        if path.exists():
            actual = shared.record(shared.regular_file(path), stat.S_IMODE(path.stat().st_mode))
        if actual is not None and rel not in old:
            raise shared.BuildError("refusing to overwrite untracked output: {}".format(path))
        if actual is not None and actual != old.get(rel) and not check:
            raise shared.BuildError("generated file was locally modified; preserve it before rebuilding: {}".format(path))
        if rel in files:
            if actual != shared.record(*files[rel]):
                drift.append("changed or missing: " + rel)
                writes[rel] = files[rel]
        else:
            drift.append("obsolete generated file: " + rel)
            if actual is not None:
                deletes.append(rel)
    marker = json_bytes({
        "format_version": 1, "generator": GENERATOR,
        "files": {rel: shared.record(*value) for rel, value in sorted(files.items())},
    })
    marker_path = output / MARKER
    if (not marker_path.exists() or shared.regular_file(marker_path) != marker
            or stat.S_IMODE(marker_path.stat().st_mode) != 0o644):
        drift.append("changed or missing marker")
        writes[MARKER] = (marker, 0o644)
    return writes, deletes, drift


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, type=Path, help="physical output plugin directory, outside canonical inputs")
    parser.add_argument("--check", action="store_true", help="check generated files without writing")
    args = parser.parse_args(argv)
    if ".." in args.output.parts:
        parser.error("--output must not contain '..'; supply the physical destination path")
    output = args.output.absolute()
    shared = skill_builder(ROOT)
    try:
        for reserved in ("skill-src", "scripts", "references", "templates", "adapters", "skills", ".git"):
            path = ROOT / reserved
            if output == path or path in output.parents:
                raise shared.BuildError("output must not be inside source inputs: {}".format(output))
        if output == ROOT or output in ROOT.parents:
            raise shared.BuildError("output must not contain the source repository")
        files = build_spec(ROOT, shared)
        writes, deletes, drift = prepare(output, files, shared, args.check)
        if args.check:
            if drift:
                print("Generated Hermes plugin differs:\n  " + "\n  ".join(drift), file=sys.stderr)
                return 1
            print("Hermes plugin matches canonical sources.")
            return 0
        for rel, value in writes.items():
            if rel != MARKER:
                shared.atomic_write(output / rel, *value)
        for rel in deletes:
            shared.no_symlinks(output / rel)
            (output / rel).unlink()
        if MARKER in writes:
            shared.atomic_write(output / MARKER, *writes[MARKER])
        print("Built standalone Hermes plugin in {} ({} changes).".format(output, len(drift)))
        return 0
    except (shared.BuildError, OSError) as error:
        print("build-hermes-plugin: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
