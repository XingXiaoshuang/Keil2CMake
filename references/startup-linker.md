# Startup and linker migration

## Establish ownership

For every executable, name the owner of these four concerns:

1. reset/initial vector table;
2. stack, heap, and interrupt stack placement;
3. data initialization and zeroization;
4. load-to-execution copying and peripheral/vector relocation, if used.

A CMSIS header does not provide startup or a linker script. A device pack may provide both, but its licensing, version, and generated inputs must be recorded.

## Scatter file semantics

A Keil scatter file is not merely a list of RAM/ROM addresses. Inspect and preserve the relevant semantics:

- load regions versus execution regions;
- `FIXED`, `EMPTY`, `UNINIT`, and alignment attributes;
- `FIRST`/`LAST` placement of vectors, tables, or checksums;
- explicit section selectors and `+RO`, `+RW`, `+ZI` behavior;
- veneers, overlays, and interworking;
- startup-owned symbols such as `Image$$...$$Base/Limit`;
- MPU, TrustZone, ECC, or vendor-specific regions.

If a scatter file uses overlays or custom load/execution relationships, do not flatten it into a simple `.data`/`.bss` linker script without a design decision and validation.

## Linker script requirements

Build the GNU linker script from the device memory map and the selected startup contract. Check:

- `MEMORY` origins/lengths match the actual MCU variant and board configuration;
- `ENTRY(Reset_Handler)` points to the executable reset path;
- vector table is first and aligned as required by the core/vendor;
- stack top satisfies architecture alignment and uses a defined stack symbol;
- initialized data is loaded from flash and copied to RAM;
- zero-initialized data is cleared before C/C++ entry;
- heap boundaries are unambiguous and do not collide with stack/RTOS regions;
- `KEEP` protects vectors, reset tables, init arrays, and intentionally unreferenced records;
- section garbage collection cannot remove required hardware tables;
- C++ `.init_array`/`.fini_array` and toolchain sections have explicit placement where relevant;
- debug, log, no-load, and bootloader-shared sections follow their real runtime rules.

Use `LOADADDR`, `ADDR`, `SIZEOF`, and `ALIGN` to make load/execution relationships explicit. Do not use a template memory map as evidence.

## Startup comparison

Compare Keil and GCC startup behavior instruction by instruction where it affects boot:

- reset value of stack pointer and vector entry order;
- clock/system initialization before data copy or after;
- data copy source/destination/length;
- BSS clear range;
- optional heap/stack fill and zeroing;
- FPU enable timing;
- static constructor call timing;
- interrupt controller/VTOR setup;
- branch to `main`, RTOS entry, or bootloader handoff.

## Validation gate

Before claiming a bootable migration, verify at least:

- `readelf -h -l -S` and the GNU map agree with the intended memory regions;
- vector table address/count and reset entry match the device requirement;
- `.data` load and run addresses are correct;
- `.bss` and stack/heap boundaries do not overlap;
- a board smoke test reaches `main`, initializes a known GPIO/UART path, services one interrupt, and survives a reset;
- a debugger can halt, flash, and inspect the expected symbols;
- any watchdog, low-power, bootloader, or OTA interaction remains functional.

If no board or debugger is available, report linker/startup verification as outstanding even if the ELF links.