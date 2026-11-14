#!/usr/bin/env python3
"""Check local package manifest identities, versions and referenced resources.

Standard-library, read-only checks; this does not substitute for a client's native
plugin validator, discovery, authentication or task execution. Invoke with -I.
"""
import argparse
import json
from pathlib import Path
import re
import sys


PACKAGE = "orchestrator-playbook"
VERSION = "3.1.0-dev.1"
SKILLS = ("playbook", "playbook-start", "playbook-resume", "playbook-handoff", "playbook-takeover")
MANIFESTS = (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
             ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json")


class ManifestError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ManifestError(message)


def local_path(root, value):
    require(isinstance(value, str) and value and "\0" not in value,
            "local references must be nonempty path strings")
    relative = Path(value)
    require(not relative.is_absolute() and ".." not in relative.parts,
            "local references must stay inside the package: " + value)
    path = root
    for part in relative.parts:
        path = path / part
        require(not path.is_symlink(), "symlink reference is not allowed: " + value)
    return path


def read_file(root, value):
    path = local_path(root, value)
    require(path.is_file(), "missing required file: " + value)
    return path.read_bytes()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ManifestError("invalid JSON constant: " + value)


def read_manifest(root, value):
    try:
        data = json.loads(read_file(root, value).decode("utf-8"),
                          object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, UnicodeError) as exc:
        raise ManifestError("invalid JSON in {}: {}".format(value, exc)) from exc
    require(isinstance(data, dict), value + " must contain a JSON object")
    return data


def object_field(data, key, label):
    value = data.get(key)
    require(isinstance(value, dict), label + "." + key + " must be an object")
    return value


def check_identity(data, label, version=True):
    require(data.get("name") == PACKAGE, label + " has the wrong package name")
    if version:
        require(data.get("version") == VERSION, label + " must declare version " + VERSION)


def plugin_entry(data, label):
    entries = data.get("plugins")
    require(isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict),
            label + " must select exactly one package plugin")
    return entries[0]


def check_skill_selection(root, value, label):
    if isinstance(value, str):
        directory = local_path(root, value)
        require(directory == root / "skills" and directory.is_dir(),
                label + " must reference the generated skills directory")
        paths = [child for child in directory.iterdir() if (child / "SKILL.md").is_file()]
        for path in paths:
            local_path(root, path.relative_to(root).as_posix())
    else:
        require(isinstance(value, list) and value, label + " must select generated skills")
        paths = [local_path(root, entry) for entry in value]
    expected = {root / "skills" / name for name in SKILLS}
    require(len(paths) == len(expected) and set(paths) == expected,
            label + " must select exactly the five lifecycle skills")
    for path in paths:
        require(path.is_dir() and (path / "SKILL.md").is_file(),
                "missing generated skill: " + path.relative_to(root).as_posix())


def check_entry(root, relative, name):
    content = read_file(root, relative).decode("utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.DOTALL)
    require(match is not None, "missing skill frontmatter: " + relative)
    # This package uses simple top-level scalar keys and one metadata mapping.
    # Refuse unsupported YAML rather than overlooking quoted/escaped duplicate
    # keys, merges or explicit-key syntax that a native parser may interpret.
    fields, metadata, section = {}, set(), None
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            nested = re.fullmatch(r"  ([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)", line)
            require(section == "metadata" and nested is not None,
                    "unsupported frontmatter mapping syntax: " + relative)
            key = nested.group(1)
            require(key not in metadata, "duplicate metadata key: " + key)
            metadata.add(key)
            continue
        entry = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)", line)
        require(entry is not None, "unsupported frontmatter key syntax: " + relative)
        key, value = entry.groups()
        require(key not in fields, "duplicate frontmatter key: " + key)
        fields[key] = value.strip()
        section = key
        if key == "metadata":
            require(not value.strip(), "metadata must use the package's simple block mapping: " + relative)
    require(fields.get("name") in (name, '"' + name + '"', "'" + name + "'"),
            "incorrect skill name: " + relative)
    require(fields.get("disable-model-invocation") == "true", "skill must require explicit invocation: " + relative)


def check_manifests(root):
    data = {name: read_manifest(root, name) for name in MANIFESTS}
    for name in (MANIFESTS[0], MANIFESTS[2]):
        check_identity(data[name], name)
        check_skill_selection(root, data[name].get("skills"), name + ".skills")
    marketplace = data[MANIFESTS[1]]
    check_identity(marketplace, MANIFESTS[1], version=False)
    metadata = object_field(marketplace, "metadata", MANIFESTS[1])
    require(metadata.get("version") == VERSION, "Claude marketplace version must be " + VERSION)
    entry = plugin_entry(marketplace, MANIFESTS[1])
    check_identity(entry, MANIFESTS[1] + ".plugins[0]", version=False)
    if "version" in entry:
        require(entry["version"] == VERSION, "Claude marketplace plugin version must be " + VERSION)
    require(local_path(root, entry.get("source")) == root,
            "Claude marketplace source must reference this package")
    check_skill_selection(root, entry.get("skills"), "Claude marketplace plugin.skills")

    catalog = data[MANIFESTS[3]]
    check_identity(catalog, MANIFESTS[3], version=False)
    entry = plugin_entry(catalog, MANIFESTS[3])
    check_identity(entry, MANIFESTS[3] + ".plugins[0]")
    source = object_field(entry, "source", MANIFESTS[3] + ".plugins[0]")
    require(source.get("source") == "url" and local_path(root, source.get("url")) == root,
            "agent catalog source must reference this package")

    for name in SKILLS:
        for filename in ("SKILL.md", "SKILL.zh.md"):
            check_entry(root, "skills/" + name + "/" + filename, name)
    for filename in ("SKILL.md", "SKILL.zh.md"):
        check_entry(root, filename, PACKAGE)
    require(read_file(root, "assets/icon.png").startswith(b"\x89PNG\r\n\x1a\n"),
            "assets/icon.png must retain the package PNG icon")
    return {"ok": True, "check": "local-package-manifests", "package": PACKAGE,
            "version": VERSION, "manifests": list(MANIFESTS), "skills": list(SKILLS),
            "native_validation": "not_run"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Package root to validate (default: this script's package)")
    args = parser.parse_args(argv)
    try:
        result = check_manifests(args.root.resolve())
    except (ManifestError, OSError, UnicodeError) as exc:
        print("check-manifests: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
