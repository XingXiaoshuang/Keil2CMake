#!/usr/bin/env python3
"""Audit text encodings without changing file bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import locale
import re
import sys
from pathlib import Path
from typing import Any


BOMS = (
    ("utf-32-le", b"\xff\xfe\x00\x00"),
    ("utf-32-be", b"\x00\x00\xfe\xff"),
    ("utf-8", b"\xef\xbb\xbf"),
    ("utf-16-le", b"\xff\xfe"),
    ("utf-16-be", b"\xfe\xff"),
)
SKIP_DIRS = {
    ".git",
    ".svn",
    ".vs",
    "__pycache__",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "debug",
    "objects",
    "listings",
    "out",
    "release",
}


def detect_bom(data: bytes) -> tuple[str, int]:
    for encoding, marker in BOMS:
        if data.startswith(marker):
            return encoding, len(marker)
    return "", 0


def declared_encoding(data: bytes) -> str:
    prefix = data[:8192]
    xml = re.match(
        br"^\s*<\?xml[^>]*encoding=[\"']([^\"']+)[\"']",
        prefix,
        re.I,
    )
    if xml:
        return xml.group(1).decode("ascii", errors="ignore").strip()
    for meta in re.finditer(br"<meta\b[^>]{0,1024}>", prefix, re.I):
        charset = re.search(br"charset\s*=\s*[\"']?\s*([a-zA-Z0-9._-]+)", meta.group(0), re.I)
        if charset:
            return charset.group(1).decode("ascii", errors="ignore").strip()
    return ""


def candidate_encodings(preferred: str) -> list[str]:
    encodings: list[str] = []
    for item in (preferred, locale.getpreferredencoding(False), "utf-8", "gb18030", "cp1252"):
        normalized = item.lower().replace("_", "-")
        if normalized and normalized not in encodings:
            encodings.append(normalized)
    return encodings


def normalize_codec_name(name: str) -> str:
    lowered = name.lower().replace("_", "-")
    aliases = {
        "utf8": "utf-8",
        "gb2312": "gbk",
        "cp936": "gbk",
        "windows-936": "gbk",
    }
    return aliases.get(lowered, lowered)


def audit_file(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    bom, bom_length = detect_bom(data)
    declared = declared_encoding(data)
    body = data[bom_length:] if bom else data
    is_ascii = not bom and all(byte < 128 for byte in body)

    candidates: list[str] = []
    failures: dict[str, str] = {}
    candidate_names: list[str] = []
    if bom:
        candidate_names = [normalize_codec_name(bom)]
    else:
        candidate_names = [normalize_codec_name(item) for item in candidate_encodings(declared)]

    for name in candidate_names:
        codec = bom or name
        try:
            body.decode(codec, errors="strict")
        except (LookupError, UnicodeDecodeError) as exc:
            failures[name] = str(exc)
        else:
            if name not in candidates:
                candidates.append(name)

    if is_ascii:
        detected = "ascii (utf-8 compatible)"
        confidence = "high"
    elif bom:
        detected = normalize_codec_name(bom)
        confidence = "high"
    elif declared and normalize_codec_name(declared) in candidates:
        detected = normalize_codec_name(declared)
        confidence = "high"
    elif candidates == ["utf-8"]:
        detected = "utf-8"
        confidence = "high"
    elif "utf-8" in candidates:
        detected = "utf-8"
        confidence = "high"
    elif len(candidates) == 1:
        detected = candidates[0]
        confidence = "heuristic"
    elif candidates:
        detected = candidates[0]
        confidence = "ambiguous"
    else:
        detected = "unknown"
        confidence = "undecodable"

    return {
        "path": path.as_posix(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bom": bom or None,
        "bom_length": bom_length,
        "declared_encoding": declared or None,
        "strict_candidates": candidates,
        "detected_encoding": detected,
        "confidence": confidence,
        "ascii_only": is_ascii,
        "decode_failures": failures,
    }


def inventory_files(path: Path) -> list[Path]:
    data = json.loads(path.read_text(encoding="utf-8"))
    project_dir = Path(data["project"]["directory"])
    files: list[Path] = []

    def add(value: Any) -> None:
        if not isinstance(value, dict):
            return
        resolved = value.get("resolved") or value.get("original") or value.get("normalized")
        if not resolved:
            return
        candidate = Path(str(resolved).replace("\\", "/"))
        if not candidate.is_absolute():
            candidate = project_dir / candidate
        files.append(candidate)

    project_path = Path(data["project"]["path"])
    if not project_path.is_absolute():
        project_path = project_dir / project_path
    files.append(project_path)

    target = data.get("target", {})
    for source in target.get("sources", []):
        add(source.get("path"))
    tooling = target.get("tooling", {})
    add(tooling.get("linker", {}).get("scatter_file"))
    return files


def collect_inputs(args: argparse.Namespace) -> list[Path]:
    if args.inventory:
        return inventory_files(args.inventory)
    files: list[Path] = []
    for raw in args.paths:
        path = raw.expanduser()
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if not child.is_file():
                    continue
                relative_parts = {part.lower() for part in child.relative_to(path).parts[:-1]}
                if relative_parts & SKIP_DIRS:
                    continue
                files.append(child)
        else:
            raise ValueError(f"Path does not exist: {path}")
    return files


def to_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Text encoding audit",
        "",
        "| File | Size | BOM | Declared | Detected | Confidence | Candidates |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        values = [
            item["path"],
            str(item["size"]),
            item["bom"] or "-",
            item["declared_encoding"] or "-",
            item["detected_encoding"],
            item["confidence"],
            ", ".join(item["strict_candidates"]) or "-",
        ]
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")

    uncertain = [item for item in results if item["confidence"] in {"ambiguous", "heuristic", "undecodable"}]
    lines.extend(["", "## Review required", ""])
    if uncertain:
        for item in uncertain:
            lines.append(f"- `{item['path']}`: {item['confidence']} as {item['detected_encoding']}")
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Files or directories to audit")
    parser.add_argument(
        "--inventory",
        type=Path,
        help="JSON output from inventory_keil_project.py; audit its known files instead of paths",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.paths) == bool(args.inventory):
        print("error: provide either paths or --inventory, not both", file=sys.stderr)
        return 2

    try:
        paths = collect_inputs(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve(strict=False)
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in unique:
        if not path.is_file():
            errors.append(f"Missing or non-file input: {path.as_posix()}")
            continue
        try:
            results.append(audit_file(path))
        except OSError as exc:
            errors.append(f"Cannot read {path.as_posix()}: {exc}")

    payload: dict[str, Any] = {"files": results, "errors": errors}
    rendered = (
        json.dumps(payload, ensure_ascii=False, indent=2)
        if args.format == "json"
        else to_markdown(results)
        + (("\n## Errors\n\n" + "\n".join(f"- {item}" for item in errors) + "\n") if errors else "")
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
        print(rendered)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())