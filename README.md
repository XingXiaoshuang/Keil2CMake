# Keil2CMake

`keil2cmake` is a Codex Skill for migrating a selected Keil uVision/Arm Compiler target into a reproducible Arm GCC + CMake build.

It is designed for embedded projects where a successful migration must preserve more than a green build: the source manifest, preprocessor state, startup path, scatter/linker semantics, ABI, file encodings, and hardware-visible behavior all matter.

## Features

- Read-only `.uvprojx` inventory extraction for targets, groups, sources, includes, defines, CPU/FPU text, custom commands, and scatter files.
- Byte-preserving text-encoding audits for project XML, C/C++, assembly, linker scripts, generated files, and runtime text.
- Practical Arm Compiler-to-GCC and uVision-to-CMake mapping guidance.
- Startup and Keil scatter-file migration rules for GNU linker scripts.
- ELF/map/vector/memory-layout and board-level verification gates.
- Copyable CMake, Arm GNU Toolchain, and conversion-report templates.

## Requirements

- Codex with Skill support.
- Python 3.10 or newer for the bundled audit scripts.
- An Arm GNU Toolchain when performing an actual firmware conversion:
  `arm-none-eabi-gcc`, `g++`, `ar`, `objcopy`, and `size`.
- CMake 3.20 or newer for the generated build.

## Install

The repository root is the Skill directory.

In Codex, ask:

```text
Use $skill-installer to install https://github.com/XingXiaoshuang/Keil2CMake as the skill keil2cmake.
```

For manual installation, clone this repository into a Codex user skill location and name the destination `keil2cmake`.

Windows:

```powershell
git clone https://github.com/XingXiaoshuang/Keil2CMake.git "$HOME\.agents\skills\keil2cmake"
```

macOS/Linux:

```bash
git clone https://github.com/XingXiaoshuang/Keil2CMake.git "$HOME/.agents/skills/keil2cmake"
```

Codex scans user, repository, and system Skill locations. If a newly installed Skill is not visible immediately, restart Codex. See the [official Codex Skills documentation](https://developers.openai.com/codex/skills) for supported Skill locations and distribution guidance.

## Invoke

```text
Use $keil2cmake to convert the selected uVision project target to an Arm GCC + CMake build and verify the migration.
```

For repository-scoped use, clone/copy the repository root to `.agents/skills/keil2cmake` inside the consuming repository.

## Repository layout

```text
SKILL.md
agents/openai.yaml
assets/templates/
references/
scripts/
scripts/tests/
```

Start with `SKILL.md`. Detailed procedures live under `references/`, deterministic helpers live under `scripts/`, and migration scaffolding lives under `assets/templates/`.

## Validate

From the repository root:

```powershell
python -m unittest discover -s scripts/tests -v
```

Validate the Skill structure with Codex `skill-creator`'s `quick_validate.py`, or any compatible validator that checks the `SKILL.md` frontmatter and scaffold state.

## Scope

This Skill supports build-system migration and evidence-based verification. It does not claim that a linked ELF is flashable or hardware-correct without startup/linker review and target testing. Custom build steps, Keil RTE packs, overlays, TrustZone/MPU layouts, incompatible external libraries, and binary-identity requirements remain explicit review gates.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Acknowledgements

Developed with assistance from OpenAI Codex.