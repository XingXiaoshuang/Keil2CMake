# GCC and CMake mapping

Translate behavior and intent, not individual Keil option spellings.

## Cross-compilation baseline

Use a toolchain file before `project()`:

- `CMAKE_SYSTEM_NAME=Generic`
- `CMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY`
- `arm-none-eabi-gcc/g++/ar/objcopy/size`
- an explicitly selected CPU, floating-point unit, and float ABI
- CMake 3.20 or newer unless the host environment requires an older version

The template at `assets/templates/arm-none-eabi-gcc.cmake.in` contains only stable host/tool discovery. Target instruction and ABI flags must be derived from the project and device evidence.

## CPU and floating point

Map only after the device and ABI are known:

| Keil evidence | GCC starting point |
| --- | --- |
| Cortex-M0/M0+ | `-mcpu=cortex-m0` or `-mcpu=cortex-m0plus -mthumb` |
| Cortex-M3 | `-mcpu=cortex-m3 -mthumb` |
| Cortex-M4 without FPU | `-mcpu=cortex-m4 -mthumb` |
| Cortex-M4 with FPv4-SP | `-mcpu=cortex-m4 -mfpu=fpv4-sp-d16` plus verified ABI |
| Cortex-M7 with FPv5-SP | `-mcpu=cortex-m7 -mfpu=fpv5-sp-d16` plus verified ABI |
| other core | use the device/toolchain documentation, not a guessed CPU name |

Choose `-mfloat-abi=hard`, `softfp`, or `soft` from the complete application/library ABI. A successful local link does not prove that external libraries use the same ABI.

## Options

| Keil intent | GCC/CMake handling |
| --- | --- |
| global defines | `target_compile_definitions` using the exact values and order-dependent behavior |
| include paths | `target_include_directories`; preserve priority when macros cause path shadowing |
| C dialect/extensions | explicit `-std=...` or `-std=gnu...`; document every GNU extension that becomes necessary |
| warnings | `-Wall -Wextra` as a migration aid, not as a claim of Keil warning equivalence |
| optimization | start debuggable with `-Og -g3`; tune only after behavior and size comparison |
| split sections | `-ffunction-sections -fdata-sections` and linker `--gc-sections` when that matches the intended dead-code elimination |
| run-time library selection | explicit newlib/newlib-nano, `--specs=...`, and required system calls |
| enumerations/char/wchar behavior | explicit GCC flags only when the existing ABI or serialization behavior requires them |
| link map/listings | generated after build from GNU `ld`/`objdump`, not copied from Keil |

Do not define `__CC_ARM`, `__ARMCC_VERSION`, or other Arm Compiler identity macros merely to make conditional code compile. Determine which logical configuration the selected branch represents and, if needed, define a project-owned feature macro.

## Assembler

Arm Compiler startup files may use `AREA`, `THUMB`, `EXPORT`, `IMPORT`, `DCD`, or divided syntax. Choose one path:

1. use a verified GNU-syntax startup source for the same device;
2. convert the assembly with a reviewed, behavior-preserving rewrite; or
3. retain an Arm Compiler assembly file only through a documented supported preprocessor/assembler route.

Do not rename `.s` to `.S` and assume compatibility. Check macro preprocessing, register-width directives, vector alignment, weak symbols, and section attributes.

## CMake shape

Keep the target explicit:

```cmake
add_executable(firmware
  # exact inventory-derived source list
)

target_include_directories(firmware PRIVATE ...)
target_compile_definitions(firmware PRIVATE ...)
target_compile_options(firmware PRIVATE ...)
target_link_options(firmware PRIVATE ...)
```

Use source properties only for genuinely source-specific options such as a non-UTF-8 input charset. Do not create an option matrix or multiple toolchain abstraction layers that the migration does not need.

## Runtime and library issues

- Identify semihosting, retarget file (`syscalls.c`, retarget, microlib equivalents), and standard I/O expectations.
- Replace Keil microlib only after checking allocation, printf, locale, and stack/heap semantics.
- Keep `assert`, fault handlers, low-power waits, and debug I/O behavior explicit.
- C++ migrations must account for static constructors, exception/RTTI configuration, operator-new ownership, and destructors.
- Newlib/libc may introduce sections and symbols absent from a microlib map; inspect the final map and heap behavior.