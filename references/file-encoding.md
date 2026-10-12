# File encoding

Encoding is part of conversion correctness. Preserve original evidence and make every conversion explicit.

## Encoding domains

Keep these domains separate:

1. **Keil project XML** — `.uvprojx`/`.uvoptx` declarations, element text, paths, defines, and option strings.
2. **Compilation inputs** — C/C++ headers and sources, assembly, linker scripts, configuration headers, generated files, and custom-build scripts.
3. **Generated migration files** — `CMakeLists.txt`, toolchain files, inventories, reports, and logs.
4. **Runtime text** — string literals, lookup tables, protocol bytes, display text, filenames, and console/log output.
5. **Filesystem names** — paths and basenames used by CMake, GCC, make/Ninja, and case-sensitive environments.

A correct source decode does not prove correct runtime bytes.

## Detection policy

Use evidence in this order:

1. byte-order mark;
2. an applicable XML declaration or other authoritative file declaration;
3. explicit user/project documentation;
4. strict decoding candidates;
5. heuristic or locale-based inference.

`scripts/audit_text_encoding.py` reports BOMs, declarations, strict-decoding candidates, and ambiguity. It never rewrites content. A GB18030/GBK guess on a Chinese Windows machine is a candidate, not proof.

Generated migration text should be UTF-8 without BOM. Keep original Keil/source bytes unchanged unless an encoding conversion is intentionally part of the requested migration.

## Safe source handling

- Audit before edits. Record original size and SHA-256 for any source that must be transcoded.
- Do not open-save whole legacy projects through a tool that silently normalizes encodings or line endings.
- Make narrow edits in the file's verified encoding; use byte-preserving methods when tooling defaults to another encoding.
- Prefer preserving existing line endings during source conversion.
- If a file contains UTF-16, transcoding to UTF-8 is usually more portable than trying to feed UTF-16 to every GCC/build tool. Preserve the original and review the byte-level diff.
- Mixed encodings are valid findings. Convert per file or compile per file; do not force one global encoding.
- Preserve non-ASCII identifiers and literals only after compiler and ABI support is verified.

## GCC options

UTF-8 is GCC's normal input assumption. For an unchanged source in another encoding, use source-specific options where supported, for example:

```cmake
set_source_files_properties(legacy_module.c PROPERTIES
  COMPILE_OPTIONS "-finput-charset=GB18030"
)
```

Use the actual verified charset. Avoid setting `-finput-charset` globally when the project mixes encodings.

`-fexec-charset` controls the character encoding of narrow literals in generated object code. Use it only when the runtime interface requires a particular byte encoding, and verify emitted/runtime strings. Source conversion to UTF-8 does not automatically preserve a GBK UART display.

Assembly, linker scripts, command files, and custom tools may not share GCC's `-finput-charset` behavior. Audit and normalize them separately.

## Paths and build systems

- Compare actual filesystem names byte-for-byte; Windows case insensitivity can hide defects that break Linux builds.
- Quote CMake paths containing spaces. Prefer forward slashes in generated CMake syntax.
- Do not normalize the source filename case or Unicode form without confirming the file on disk.
- Ensure Ninja/Make response files, compiler diagnostics, Python scripts, and report output use a defined UTF-8 path where possible.
- If the build must run on Windows and Linux, perform a case-sensitive source-manifest check on the converted tree.

## Runtime verification

For any non-ASCII or byte-sensitive data:

- inspect the object file or memory dump for expected bytes;
- test the actual terminal/display/protocol endpoint;
- verify round trips for persisted data;
- check `sizeof(wchar_t)`, `char` signedness, enum width, and struct packing when text is part of a wire format.

Report every changed file, its before/after encoding, conversion reason, hash evidence, and verification result.