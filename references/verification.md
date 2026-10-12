# Verification and reporting

## Evidence hierarchy

Use the strongest available evidence and state the level reached:

1. **Binary/runtime equivalence** — same external behavior and board tests across representative states.
2. **Executable comparison** — ELF/map/section/vector comparison plus project tests or target smoke tests.
3. **Build equivalence** — same intended sources and configuration compile and link with documented warnings.
4. **Static migration** — CMake inventory and mapping are complete, but no original or target build exists.

Do not describe level 3 or 4 as functionally verified.

## Before/after baseline

When Keil is available, retain:

- exact uVision and Arm Compiler versions;
- target configuration and global preprocessor/include options;
- full build log and warnings;
- `.axf`, `.map`, disassembly/listing, and symbol data;
- the built binary size by category;
- representative output strings or interface traces.

If Keil cannot run, extract all available XML evidence and mark every comparison that requires the original artifact as unavailable.

## Comparison checks

At minimum, compare or review:

- source membership and exclusion state;
- include search decisions for duplicated header names;
- preprocessor feature branches and generated configuration headers;
- CPU/FPU/ABI compatibility for every object/library;
- entry point and vector table;
- memory-region boundaries and section assignments;
- initialized and zero-initialized data behavior;
- interrupt/fault handler reachability;
- C/C++ runtime initialization and heap/stack ownership;
- compile/link warnings introduced by GCC;
- ELF sections, program headers, symbols, and size deltas;
- serialization/string/enum sizes where external protocols depend on them.

A section-size increase is not automatically a defect, but it must have an explanation. Investigate unexpected libc, exception/RTTI, debug, or retention sections.

## Tests

Use the project's existing tests first. If none exist, define the smallest hardware-visible smoke test from the original purpose, such as reset-to-main, UART output, timer tick, flash write, or external interrupt. Do not invent broad test infrastructure unless requested.

## Conversion report

Create `cmake/keil-conversion-report.md` using `assets/templates/conversion-report.md.in`. Keep it concise and factual. It must include:

- selected source project/target and source revision;
- conversion level achieved;
- toolchain and CMake versions;
- source/define/include/ABI mapping decisions;
- startup/linker ownership;
- encoding decisions and file changes;
- baseline availability and comparison results;
- warnings and known differences;
- unresolved hardware/toolchain gates.

The report is part of the migration deliverable. A green configure or link alone is not completion.