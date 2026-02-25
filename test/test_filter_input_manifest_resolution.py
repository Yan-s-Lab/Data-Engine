from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from filter.run_filter import _resolve_filter_input_manifest


class FilterInputManifestResolutionTest(unittest.TestCase):
    def test_explicit_input_manifest_wins(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_input_resolve_") as td:
            root = Path(td)
            run_dir = root / "run"
            explicit = root / "explicit.jsonl"
            explicit.write_text("", encoding="utf-8")

            path, source = _resolve_filter_input_manifest(
                filter_cfg={"input_manifest": str(explicit)},
                run_dir=run_dir,
            )
            self.assertEqual(path, explicit)
            self.assertEqual(source, "filter.input_manifest")

    def test_auto_uses_generate_mixed_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_input_resolve_") as td:
            root = Path(td)
            run_dir = root / "run"
            mixed = run_dir / "generate" / "mixed_manifest.jsonl"
            mixed.parent.mkdir(parents=True, exist_ok=True)
            mixed.write_text("", encoding="utf-8")

            path, source = _resolve_filter_input_manifest(
                filter_cfg={},
                run_dir=run_dir,
            )
            self.assertEqual(path, mixed)
            self.assertEqual(source, "run_dir/generate/mixed_manifest.jsonl")

    def test_disable_auto_returns_none(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_input_resolve_") as td:
            root = Path(td)
            run_dir = root / "run"
            mixed = run_dir / "generate" / "mixed_manifest.jsonl"
            mixed.parent.mkdir(parents=True, exist_ok=True)
            mixed.write_text("", encoding="utf-8")

            path, source = _resolve_filter_input_manifest(
                filter_cfg={"auto_input_from_generate_mixed": False},
                run_dir=run_dir,
            )
            self.assertIsNone(path)
            self.assertEqual(source, "")


if __name__ == "__main__":
    unittest.main()
