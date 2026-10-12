# Project inventory

## Source of truth

Read the selected Keil target from its `.uvprojx` XML. The directory tree is supporting evidence, not the build manifest. A file can be present on disk and excluded from the target, while a configured file may be missing.

Use the bundled inventory script before writing CMake:

```powershell
python scripts/inventory_keil_project.py path\to\project.uvprojx `
  --target TargetName `
  --format markdown `
  --output cmake\keil-inventory.md

python scripts/inventory_keil_project.py path\to\project.uvprojx `
  --target TargetName `
  --format json `
  --output cmake\keil-inventory.json
```

If there is exactly one target, `--target` may be omitted. Multiple targets require an explicit selection.

## What the inventory establishes

- target name and raw `Device`, `Vendor`, and `Cpu` values;
- output directory/name and create-executable settings;
- groups and file entries, including raw `FileType` and build inclusion flags;
- resolved-looking source paths, missing files, duplicate paths, and unresolved Keil/environment macros;
- C, assembler, and linker include paths, defines, miscellaneous controls, and scatter-file references;
- before/after-build user commands when they are present;
- the project XML declaration and text-encoding warnings.

The JSON output is intended for further automation. The Markdown output is for review. Both preserve raw option strings because uVision schemas vary.

## Manual inspection still required

Check these items directly in uVision or the XML:

1. **Per-file options** — optimization, include paths, defines, code generation, or custom build commands can override target settings.
2. **Custom build steps** — run conditions, command lines, input/output dependencies, and whether generated files are compiled.
3. **RTE/Software Packs** — identify actual generated headers, sources, libraries, memory definitions, and flash/debug components. Do not treat pack names as portable source.
4. **Object and library inputs** — verify architecture, ABI, floating-point ABI, and whether a GCC-compatible replacement exists.
5. **Conditionally selected files** — source list differences between Debug/Release or board variants may be encoded in target names rather than in conditional code.
6. **Path macros** — `$(...)` and `%...%` values may originate in uVision, Windows, or custom environment settings. Record their resolved values before conversion.
7. **Generated or excluded files** — a `FileType` or `IncludeInBuild` value is not enough when custom steps mutate the source set.

## Encoding

The project file and every text source require encoding-aware handling. Use `scripts/audit_text_encoding.py` after inventory, and follow `references/file-encoding.md`. The inventory reports the XML declaration and obvious decode problems but does not rewrite files.

## Known parser limits

The bundled parser is deliberately read-only and tolerant. It extracts stable fields across common Keil 5 schemas, but it does not simulate uVision. If the target contains custom build logic, pack-generated configuration, unusual XML elements, or source lists that disagree with the known project behavior, inspect those areas manually and record the difference in the conversion report.