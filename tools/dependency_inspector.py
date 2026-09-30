"""TOOL-005 Dependency Inspector for common Python project manifests."""
from __future__ import annotations

import configparser
import os
import re

from security.workspace import Workspace, WorkspaceSecurityError

MAX_MANIFEST_BYTES = 1024 * 1024
REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]+\])?\s*(.*)$")


def _parse_requirement_lines(text: str, group: str = "dependencies") -> list:
    dependencies = []
    for line in text.splitlines():
        entry = line.split("#", 1)[0].strip()
        if not entry or entry.startswith(("-", "--")):
            continue
        match = REQUIREMENT_RE.match(entry)
        if match:
            dependencies.append({"name": match.group(1), "constraint": match.group(2).strip(), "group": group})
    return dependencies


def _toml_dependencies(data: dict) -> list:
    found = []
    project = data.get("project", {})
    for entry in project.get("dependencies", []):
        found.extend(_parse_requirement_lines(entry))
    for group, entries in project.get("optional-dependencies", {}).items():
        for entry in entries:
            found.extend(_parse_requirement_lines(entry, group))

    poetry = data.get("tool", {}).get("poetry", {})
    for group, entries in {"dependencies": poetry.get("dependencies", {})}.items():
        for name, details in entries.items():
            if name.lower() == "python":
                continue
            constraint = details if isinstance(details, str) else details.get("version", "")
            found.append({"name": name, "constraint": str(constraint), "group": group})
    for group, group_data in poetry.get("group", {}).items():
        for name, details in group_data.get("dependencies", {}).items():
            constraint = details if isinstance(details, str) else details.get("version", "")
            found.append({"name": name, "constraint": str(constraint), "group": group})
    return found


def inspect_dependencies(workspace: Workspace) -> dict:
    """Parse requirements.txt, pyproject.toml, and setup.cfg without installing code."""
    dependencies = []
    manifests = []
    notes = []
    for manifest in ("requirements.txt", "pyproject.toml", "setup.cfg"):
        try:
            path = workspace.resolve(manifest)
            if not os.path.isfile(path):
                continue
            if os.path.getsize(path) > MAX_MANIFEST_BYTES:
                notes.append(f"{manifest} exceeds the 1 MB inspection limit.")
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as source:
                text = source.read()
        except (OSError, WorkspaceSecurityError):
            continue

        manifests.append(manifest)
        try:
            if manifest == "requirements.txt":
                dependencies.extend(_parse_requirement_lines(text))
            elif manifest == "pyproject.toml":
                try:
                    import tomllib
                except ImportError:
                    try:
                        import tomli as tomllib
                    except ImportError:
                        notes.append("Install tomli to inspect pyproject.toml on Python 3.10.")
                        continue
                dependencies.extend(_toml_dependencies(tomllib.loads(text)))
            else:
                config = configparser.ConfigParser()
                config.read_string(text)
                requirements = config.get("options", "install_requires", fallback="")
                dependencies.extend(_parse_requirement_lines(requirements))
        except (ValueError, configparser.Error) as error:
            notes.append(f"Could not parse {manifest}: {error}")

    return {
        "manifests": manifests,
        "dependencies": dependencies,
        "note": "; ".join(notes) if notes else ("No recognized dependency manifests found." if not manifests else ""),
    }