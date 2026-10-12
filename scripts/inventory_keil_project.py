#!/usr/bin/env python3
"""Read-only inventory extractor for a selected target in a Keil .uvprojx file."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
FILE_TYPES = {
    "1": "c",
    "2": "assembly",
    "3": "cpp",
    "4": "object",
    "5": "library",
    "6": "text",
    "7": "custom",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element | None, name: str) -> str:
    if element is None:
        return ""
    for child in element:
        if local_name(child.tag) == name:
            return (child.text or "").strip()
    return ""


def descendants(element: ET.Element | None, name: str) -> Iterable[ET.Element]:
    if element is None:
        return
    for child in element.iter():
        if local_name(child.tag) == name:
            yield child


def first_descendant(element: ET.Element | None, name: str) -> ET.Element | None:
    return next(descendants(element, name), None)


def split_semicolon(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def macro_names(value: str) -> list[str]:
    names = re.findall(r"\$\(([^)]+)\)|%([^%]+)%", value)
    return sorted({first or second for first, second in names})


def expand_known_environment(value: str) -> str:
    def replace_dollar(match: re.Match[str]) -> str:
        name = match.group(1)
        return os.environ.get(name, match.group(0))

    def replace_percent(match: re.Match[str]) -> str:
        name = match.group(1)
        return os.environ.get(name, match.group(0))

    value = re.sub(r"\$\(([^)]+)\)", replace_dollar, value)
    value = re.sub(r"%([^%]+)%", replace_percent, value)
    return os.path.expandvars(value)


def normalize_path(raw: str, project_dir: Path) -> dict[str, Any]:
    original = raw.strip()
    normalized = original.replace("\\", "/")
    macros = macro_names(original)
    expanded = expand_known_environment(original)
    expanded_macros = macro_names(expanded)
    resolvable = not expanded_macros

    resolved = ""
    exists = None
    if resolvable:
        candidate = Path(expanded.replace("\\", "/"))
        if not candidate.is_absolute():
            candidate = project_dir / candidate
        try:
            resolved = candidate.resolve(strict=False).as_posix()
        except OSError:
            resolved = candidate.as_posix()
        exists = candidate.exists()

    return {
        "original": original,
        "normalized": normalized,
        "macros": macros,
        "resolved": resolved,
        "resolvable": resolvable,
        "exists": exists,
    }


def declared_xml_encoding(data: bytes) -> str:
    prefix = data[:512]
    try:
        text = prefix.decode("ascii", errors="ignore")
    except Exception:
        return ""
    match = re.match(r"^\s*<\?xml[^>]*encoding=[\"']([^\"']+)[\"']", text, re.I)
    return match.group(1).strip() if match else ""


def parse_cpu(raw: str) -> dict[str, Any]:
    values: dict[str, Any] = {"raw": raw}

    def scalar(name: str, pattern: str, transform=lambda value: value):
        match = re.search(pattern, raw, re.I)
        if match:
            values[name] = transform(match.group(1))

    scalar("core", r'CPUTYPE\s*\(\s*"([^"]+)"\s*\)')
    scalar("clock_hz", r"CLOCK\s*\(\s*([^)]+)\)", lambda value: int(value.strip()) if value.strip().isdigit() else value.strip())
    scalar("fpu", r"FPU\s*\(\s*([^)]+)\)")
    scalar("fpu2", r"FPU2\s*\(\s*([^)]+)\)")
    scalar("iram", r"IRAM\s*\(\s*([^)]+)\)")
    scalar("irom", r"IROM\s*\(\s*([^)]+)\)")
    scalar("endian", r"\b(E?LITTLE|E?BIG)\b", lambda value: value.upper())
    return values


def is_included(file_element: ET.Element) -> bool:
    values: list[str] = []
    for name in ("IncludeInBuild", "AlwaysBuild"):
        for element in descendants(file_element, name):
            values.append((element.text or "").strip())
    if not values:
        return True
    return values[0] not in {"0", "false", "False", "no", "NO"}


def custom_commands(element: ET.Element | None) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    if element is None:
        return commands
    for custom in descendants(element, "CustomRun"):
        for phase in ("BeforeCompile", "AfterCompile", "BeforeBuild", "AfterBuild"):
            value = child_text(custom, phase)
            if value:
                commands.append({"phase": phase, "command": value})
    for name in (
        "RunUserProg1",
        "RunUserProg2",
        "UserProg1Name",
        "UserProg2Name",
        "BeforeCompile",
        "AfterCompile",
        "BeforeMake",
        "AfterMake",
    ):
        for item in descendants(element, name):
            value = (item.text or "").strip()
            if value:
                commands.append({"phase": name, "command": value})
    return commands


def collect_sources(target: ET.Element, project_dir: Path, warnings: list[str]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def walk(group: ET.Element, inherited_group: str, inherited_path: str) -> None:
        group_name = child_text(group, "GroupName") or inherited_group
        group_path = child_text(group, "GroupPath") or inherited_path

        files_parent = next(
            (child for child in group if local_name(child.tag) == "Files"), None
        )
        file_elements = (
            [child for child in files_parent if local_name(child.tag) == "File"]
            if files_parent is not None
            else []
        )
        for file_element in file_elements:
            file_name = child_text(file_element, "FileName")
            raw_path = child_text(file_element, "FilePath")
            raw_type = child_text(file_element, "FileType")
            key = (group_name, raw_path or file_name)
            if key in seen:
                continue
            seen.add(key)

            path_info = normalize_path(raw_path or file_name, project_dir)
            include_in_build = is_included(file_element)
            source = {
                "group": group_name,
                "group_path": group_path,
                "name": file_name,
                "type_code": raw_type,
                "type": FILE_TYPES.get(raw_type, "unknown"),
                "include_in_build": include_in_build,
                "path": path_info,
                "custom_commands": custom_commands(file_element),
            }
            sources.append(source)
            if include_in_build and path_info["exists"] is False:
                warnings.append(f"Configured source is missing: {raw_path or file_name}")
            if path_info["macros"]:
                warnings.append(
                    f"Source path contains unresolved or external macro(s): {raw_path or file_name} -> {', '.join(path_info['macros'])}"
                )

        # Keil normally nests groups as Group/Groups/Group.
        groups_container = next(
            (child for child in group if local_name(child.tag) == "Groups"), None
        )
        if groups_container is not None:
            for nested in groups_container:
                if local_name(nested.tag) == "Group":
                    walk(nested, group_name, group_path)

    groups_parent = first_descendant(target, "Groups")
    if groups_parent is not None:
        top_groups = [child for child in groups_parent if local_name(child.tag) == "Group"]
        for group in top_groups:
            walk(group, "", "")

    return sources


def controls_for(parent: ET.Element | None) -> dict[str, list[str]]:
    various = first_descendant(parent, "VariousControls")
    return {
        "include_paths": split_semicolon(child_text(various, "IncludePath")),
        "defines": split_semicolon(child_text(various, "Define")),
        "misc": split_semicolon(child_text(various, "MiscControls")),
    }


def collect_tooling(target: ET.Element, project_dir: Path) -> dict[str, Any]:
    arm = first_descendant(target, "TargetArmAds")
    cads = first_descendant(arm, "Cads")
    aads = first_descendant(arm, "Aads")
    ldads = first_descendant(arm, "LDads")

    scatter_raw = child_text(ldads, "ScatterFile")
    linker_misc = split_semicolon(child_text(ldads, "MiscControls"))
    return {
        "c": controls_for(cads),
        "assembler": controls_for(aads),
        "linker": {
            "scatter_file": normalize_path(scatter_raw, project_dir) if scatter_raw else None,
            "misc": linker_misc,
        },
    }


def collect_target(
    target: ET.Element,
    project_dir: Path,
    all_target_names: list[str],
) -> dict[str, Any]:
    warnings: list[str] = []
    common = first_descendant(target, "TargetCommonOption")
    output_dir = child_text(common, "OutputDirectory")
    output_name = child_text(common, "OutputName")
    cpu_raw = child_text(common, "Cpu")
    sources = collect_sources(target, project_dir, warnings)
    tooling = collect_tooling(target, project_dir)

    included = sum(1 for source in sources if source["include_in_build"])
    missing = sum(
        1
        for source in sources
        if source["include_in_build"] and source["path"]["exists"] is False
    )
    unresolved = sum(1 for source in sources if source["path"]["macros"])

    if tooling["linker"]["scatter_file"] and tooling["linker"]["scatter_file"]["exists"] is False:
        warnings.append(
            "Scatter file is configured but missing: "
            + tooling["linker"]["scatter_file"]["original"]
        )

    return {
        "name": child_text(target, "TargetName"),
        "available_targets": all_target_names,
        "common": {
            "device": child_text(common, "Device"),
            "vendor": child_text(common, "Vendor"),
            "cpu": cpu_raw,
            "output_directory": normalize_path(output_dir, project_dir) if output_dir else None,
            "output_name": output_name,
            "create_executable": child_text(common, "CreateExecutable"),
            "create_hex_file": child_text(common, "CreateHexFile"),
        },
        "cpu": parse_cpu(cpu_raw),
        "sources": sources,
        "summary": {
            "source_count": len(sources),
            "included_source_count": included,
            "missing_included_source_count": missing,
            "source_paths_with_macros": unresolved,
        },
        "tooling": tooling,
        "custom_commands": custom_commands(first_descendant(target, "TargetOption")),
        "warnings": warnings,
    }


def load_project(path: Path) -> tuple[ET.Element, str, list[str]]:
    data = path.read_bytes()
    warnings: list[str] = []
    declared = declared_xml_encoding(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Cannot parse UVPROJX XML: {exc}") from exc

    if not declared:
        warnings.append("Project XML has no declared encoding.")
    if data.startswith(b"\xef\xbb\xbf") and declared and declared.lower().replace("-", "") != "utf8":
        warnings.append("UTF-8 BOM disagrees with the XML declaration.")
    return root, declared, warnings


def find_target(root: ET.Element, requested: str | None) -> ET.Element:
    targets: list[ET.Element] = []
    for element in root.iter():
        if local_name(element.tag) == "Target":
            targets.append(element)
    if not targets:
        raise ValueError("No Keil target found in project.")

    names = [child_text(target, "TargetName") for target in targets]
    if requested:
        for target, name in zip(targets, names):
            if name == requested:
                return target
        raise ValueError(
            f"Target {requested!r} not found. Available targets: " + ", ".join(names)
        )
    if len(targets) != 1:
        raise ValueError(
            "Multiple targets found; pass --target explicitly. Available targets: "
            + ", ".join(names)
        )
    return targets[0]


def build_inventory(project_path: Path, requested_target: str | None) -> dict[str, Any]:
    project_path = project_path.resolve()
    if not project_path.is_file():
        raise ValueError(f"Project file does not exist: {project_path}")

    root, declared, warnings = load_project(project_path)
    target = find_target(root, requested_target)
    all_names = [child_text(item, "TargetName") for item in root.iter() if local_name(item.tag) == "Target"]
    target_inventory = collect_target(target, project_path.parent, all_names)
    warnings.extend(target_inventory["warnings"])
    target_inventory["warnings"] = list(dict.fromkeys(warnings))

    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "path": project_path.as_posix(),
            "directory": project_path.parent.as_posix(),
            "declared_xml_encoding": declared,
        },
        "target": target_inventory,
    }


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    def clean(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    lines = [
        "| " + " | ".join(clean(item) for item in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(clean(item) for item in row) + " |" for row in rows)
    return "\n".join(lines)


def to_markdown(data: dict[str, Any]) -> str:
    project = data["project"]
    target = data["target"]
    common = target["common"]
    summary = target["summary"]
    lines = [
        f"# Keil inventory: {target['name']}",
        "",
        f"- Project: `{project['path']}`",
        f"- Declared XML encoding: `{project['declared_xml_encoding'] or 'not declared'}`",
        f"- Device: `{common['device']}`",
        f"- Vendor: `{common['vendor']}`",
        f"- CPU: `{common['cpu']}`",
        f"- Output: `{common['output_name']}` in `{common['output_directory']['original'] if common['output_directory'] else ''}`",
        f"- Sources: {summary['source_count']} total, {summary['included_source_count']} included",
        "",
        "## Warnings",
        "",
    ]
    if target["warnings"]:
        lines.extend(f"- {warning}" for warning in target["warnings"])
    else:
        lines.append("- None from the static parser.")

    lines.extend(["", "## Sources", ""])
    source_rows = []
    for source in target["sources"]:
        exists = source["path"]["exists"]
        exists_text = "yes" if exists else ("no" if exists is False else "unresolved")
        source_rows.append([
            source["group"],
            source["name"],
            source["type"],
            "yes" if source["include_in_build"] else "no",
            source["path"]["normalized"],
            exists_text,
        ])
    lines.append(markdown_table(["Group", "File", "Type", "Build", "Path", "Exists"], source_rows))

    for label, key in (("C compiler", "c"), ("Assembler", "assembler")):
        controls = target["tooling"][key]
        lines.extend(["", f"## {label}", ""])
        lines.append("Include paths:")
        lines.extend(f"- `{item}`" for item in controls["include_paths"] or ["(none)"])
        lines.append("Defines:")
        lines.extend(f"- `{item}`" for item in controls["defines"] or ["(none)"])
        lines.append("Miscellaneous controls:")
        lines.extend(f"- `{item}`" for item in controls["misc"] or ["(none)"])

    linker = target["tooling"]["linker"]
    lines.extend(["", "## Linker", ""])
    scatter = linker["scatter_file"]
    lines.append(f"- Scatter file: `{scatter['normalized'] if scatter else '(none)'}`")
    lines.append("- Miscellaneous controls:")
    lines.extend(f"  - `{item}`" for item in linker["misc"] or ["(none)"])

    lines.extend(["", "## Build commands", ""])
    commands = target["custom_commands"]
    if commands:
        lines.append(markdown_table(
            ["Phase", "Command"],
            [[item["phase"], item["command"]] for item in commands],
        ))
    else:
        lines.append("None found by the static parser.")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Path to a Keil .uvprojx file")
    parser.add_argument("--target", help="Target name; required when the project has multiple targets")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="Output path; defaults to standard output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        inventory = build_inventory(args.project, args.target)
        rendered = (
            json.dumps(inventory, ensure_ascii=False, indent=2)
            if args.format == "json"
            else to_markdown(inventory)
        )
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())