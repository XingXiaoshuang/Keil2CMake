---
name: keil2cmake
license: Apache-2.0
description: Convert Keil uVision/Arm Compiler embedded projects into reproducible Arm GCC and CMake builds, including project inventory, compiler/linker migration, startup and scatter-file handling, and build-equivalence verification. Use for migrating or reproducing a Keil target with CMake/Ninja/Make; do not use for merely opening a .uvprojx file or for projects that must remain exclusively Keil-managed.
---

# Keil to CMake

Convert the selected Keil target into a build that another engineer can reproduce without uVision. A successful migration preserves the intended source set, preprocessor state, memory layout, startup behavior, and output artifact—not merely the presence of `CMakeLists.txt`.

## Required boundaries

- Treat the `.uvprojx` file as the primary build manifest. Do not infer the source list from a directory scan.
- Convert one explicitly identified Keil target at a time. If a project has multiple targets and the request does not select one, list the targets and ask.
- Keep the original Keil project unchanged unless the user explicitly requests in-place edits.
- Separate build-system migration from hardware bring-up. Do not claim flash, boot, interrupt, peripheral, or timing correctness from a successful compile/link alone.
- Record unresolved evidence, such as a missing device pack, unavailable Keil baseline, unknown compiler flags, or an unverified linker layout.

## Workflow

1. **Inventory the target** — Locate the project and run `scripts/inventory_keil_project.py` to extract target names, CPU/FPU text, source files, include paths, defines, compiler/assembler/linker options, output settings, and scatter-file references. Review `references/project-inventory.md` for schema limits and manual checks.
2. **Audit text encodings** — Run `scripts/audit_text_encoding.py --inventory ...` and inspect every uncertain result. Preserve original bytes; distinguish project XML, source input, generated files, runtime strings, and filesystem names. Follow `references/file-encoding.md`.
3. **Establish the baseline** — If uVision and the original toolchain are available, build the exact target and retain the `.axf`, `.map`, listing, and preprocessor/build logs. Otherwise, state that conversion fidelity is source-derived only.
4. **Choose the migration shape** — Select a single executable, library, or multi-target CMake layout based on the Keil target. Prefer the simplest structure that preserves the target.
5. **Create the CMake/toolchain files** — Use `assets/templates/` as scaffolding, then derive all source lists, include paths, definitions, CPU/FPU flags, language options, and linker inputs from the inventory. See `references/gcc-cmake-mapping.md`.
6. **Migrate startup and linking** — Decide explicitly among the device vendor startup/Linker-Scatter-Loader route, a portable CMSIS startup plus generated linker script, or a project-owned startup/linker pair. Never silently reinterpret Keil scatter semantics. See `references/startup-linker.md`.
7. **Build with Arm GCC** — Configure an out-of-tree build, compile all intended sources, and resolve migration errors without deleting functional Keil-only code. Keep generated build products outside the source tree when possible.
8. **Verify** — Compare source membership, preprocessor decisions, section/memory assumptions, symbols/entry/reset path, binary size, and byte-sensitive strings or protocol data. Run the project's tests or board-level smoke test when available. Use `references/verification.md` and produce a concise conversion report that distinguishes verified facts from remaining gates.
## Toolchain rules

- Use an Arm GNU Toolchain (`arm-none-eabi-gcc`, `g++`, `ar`, `objcopy`, `size`) and record its version in the report.
- Set `CMAKE_SYSTEM_NAME` to `Generic`, use `CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY`, and configure CMake from a dedicated toolchain file.
- Do not translate Arm Compiler optimization numbers mechanically into GCC optimization levels. Start from a debuggable baseline such as `-Og -g3`, then tune only with comparison evidence.
- Map AC5/AC6 language and extension options explicitly; do not enable GNU extensions merely to suppress syntax errors without documenting the affected source.
- Treat Keil include order, macro values, source-level `#pragma`, `__attribute__`, conditional assembly, and target-specific defines as behavioral inputs.
- Preserve path case, whitespace, line endings, and verified source encoding. Normalize separators only in generated CMake syntax, not in the retained inventory
- Treat source encoding and runtime character encoding as separate decisions; never silently transcode a legacy source or string table.
- Do not copy or claim support for a flash algorithm; that is a flashing/debug concern, not part of the GCC link unless the project truly embeds it.

## Output expectations

At minimum, deliver:

- `CMakeLists.txt` for the selected target;
- a cross-compilation toolchain file;
- the chosen startup and linker inputs, or an explicit dependency on verified vendor/CMSIS sources;
- a machine-readable or human-readable Keil inventory and text-encoding audit;
- a conversion report with toolchain versions, mapping decisions, encoding decisions/changes, build result, comparison results, and outstanding verification gates.

Prefer this layout unless the repository already has a stronger convention:

```text
CMakeLists.txt
cmake/
  arm-none-eabi-gcc.cmake
  keil-inventory.json
  keil-encoding-audit.json
  keil-conversion-report.md
linker/
startup/
```

Do not add speculative abstraction, multiple interchangeable toolchains, package managers, CI, or generated project metadata unless requested.

## Stop and ask

Stop for user direction when any of these cannot be resolved from project evidence:

- multiple plausible target/board configurations;
- a scatter file with overlays, absolute execution regions, MPU/TrustZone setup, or custom load/execution relationships;
- required Keil RTE/Software Packs with no redistributable source;
- startup/vector code written exclusively in Arm Compiler assembly syntax;
- external `.lib`/`.o` inputs with no GCC-compatible replacement;
- a required microcontroller has no known GCC device/startup/linker support;
- the requested output must reproduce binary identity rather than functional equivalence.

## Supporting references

- `references/project-inventory.md` — UVPROJX interpretation, source selection, and inventory script behavior
- `references/file-encoding.md` — project/source/runtime/path encoding detection and safe conversion policy.
- `references/gcc-cmake-mapping.md` — practical compiler, assembler, preprocessor, and CMake mappings.
- `references/startup-linker.md` — startup ownership, scatter-to-linker decisions, and memory-layout rules.
- `references/verification.md` — evidence hierarchy and migration acceptance checks.