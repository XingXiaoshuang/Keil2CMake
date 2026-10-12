from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "scripts" / "inventory_keil_project.py"
ENCODING = ROOT / "scripts" / "audit_text_encoding.py"
FIXTURE = ROOT / "scripts" / "tests" / "fixtures" / "minimal.uvprojx"


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class InventoryTests(unittest.TestCase):
    def test_extracts_selected_target_and_flags_evidence(self) -> None:
        result = run_script(INVENTORY, str(FIXTURE), "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["target"]["name"], "Board Debug")
        self.assertEqual(data["target"]["common"]["device"], "STM32F407VG")
        self.assertEqual(data["target"]["cpu"]["core"], "Cortex-M4")
        self.assertEqual(data["target"]["summary"]["source_count"], 4)
        self.assertEqual(data["target"]["summary"]["included_source_count"], 3)
        self.assertEqual(data["target"]["summary"]["missing_included_source_count"], 1)
        self.assertTrue(any("missing.c" in item for item in data["target"]["warnings"]))
        self.assertTrue(any("BUILD_GEN" in item for item in data["target"]["warnings"]))
        self.assertEqual(data["target"]["tooling"]["c"]["defines"][0], "STM32F407xx")

    def test_markdown_contains_reviewable_mapping_inputs(self) -> None:
        result = run_script(INVENTORY, str(FIXTURE), "--format", "markdown")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Keil inventory: Board Debug", result.stdout)
        self.assertIn("| Application | main.c | c | yes |", result.stdout)
        self.assertIn("Scatter file: `./fixed.sct`", result.stdout)
        self.assertIn("echo before-build", result.stdout)


class EncodingAuditTests(unittest.TestCase):
    def test_reports_bom_and_mixed_text_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            ascii_path = temp / "ascii.c"
            utf8_path = temp / "utf8.c"
            gbk_path = temp / "gbk.c"
            utf16_path = temp / "utf16.c"

            ascii_path.write_bytes(b"int value = 1;\n")
            utf8_path.write_bytes(b"\xef\xbb\xbfconst char *s = \"\xe4\xb8\xad\xe6\x96\x87\";\n")
            original_gbk = "const char *s = \"中文\";\n".encode("gbk")
            gbk_path.write_bytes(original_gbk)
            utf16_path.write_bytes("int value = 2;\n".encode("utf-16"))

            result = run_script(
                ENCODING,
                str(ascii_path),
                str(utf8_path),
                str(gbk_path),
                str(utf16_path),
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            files = {Path(item["path"]).name: item for item in json.loads(result.stdout)["files"]}

            self.assertEqual(files["ascii.c"]["confidence"], "high")
            self.assertEqual(files["utf8.c"]["bom"], "utf-8")
            self.assertEqual(files["utf8.c"]["detected_encoding"], "utf-8")
            self.assertEqual(files["utf16.c"]["detected_encoding"], "utf-16-le")
            self.assertIn(files["gbk.c"]["detected_encoding"], {"gbk", "gb18030"})
            self.assertEqual(gbk_path.read_bytes(), original_gbk)

    def test_source_code_is_not_mistaken_for_a_text_declaration(self) -> None:
        result = run_script(ENCODING, str(ENCODING), "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)["files"][0]
        self.assertIsNone(item["declared_encoding"])
        self.assertEqual(item["confidence"], "high")
    def test_inventory_mode_includes_known_scatter_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            inventory_path = Path(temp_dir) / "inventory.json"
            result = run_script(
                INVENTORY,
                str(FIXTURE),
                "--format",
                "json",
                "--output",
                str(inventory_path),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result = run_script(
                ENCODING,
                "--inventory",
                str(inventory_path),
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            payload = json.loads(result.stdout)
            paths = {Path(item["path"]).name for item in payload["files"]}
            self.assertIn("minimal.uvprojx", paths)
            self.assertIn("main.c", paths)
            self.assertIn("fixed.sct", paths)
            self.assertTrue(any("missing.c" in item for item in payload["errors"]))


if __name__ == "__main__":
    unittest.main()