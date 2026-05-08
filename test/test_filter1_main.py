from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "filter" / "filter_stages" / "filter1" / "main.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("filter1_main", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load filter1 main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Filter1MainTest(unittest.TestCase):
    def test_resolve_threshold_precedence(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="filter1_threshold_") as td:
            root = Path(td)
            report_path = root / "threshold_report.json"
            report_path.write_text(json.dumps({"best_threshold": 0.73}), encoding="utf-8")

            cfg = {"siglip2_margin_threshold": 0.61}
            t, source = mod._resolve_threshold(
                cli_threshold=0.9,
                threshold_report_path=str(report_path),
                filter_cfg=cfg,
                config_path=root / "config.yaml",
            )
            self.assertAlmostEqual(t, 0.9, places=6)
            self.assertEqual(source, "cli.threshold")

            t2, source2 = mod._resolve_threshold(
                cli_threshold=None,
                threshold_report_path=str(report_path),
                filter_cfg=cfg,
                config_path=root / "config.yaml",
            )
            self.assertAlmostEqual(t2, 0.73, places=6)
            self.assertEqual(source2, "cli.threshold_report.best_threshold")

            t3, source3 = mod._resolve_threshold(
                cli_threshold=None,
                threshold_report_path="",
                filter_cfg=cfg,
                config_path=root / "config.yaml",
            )
            self.assertAlmostEqual(t3, 0.61, places=6)
            self.assertEqual(source3, "filter.siglip2_margin_threshold")

    def test_normalize_row_contract(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="filter1_row_") as td:
            root = Path(td)
            image_path = root / "a.png"
            image_path.write_text("x", encoding="utf-8")

            row = {"imagepath": str(image_path)}
            out = mod._normalize_row(row, row_index=7, base_dir=root)
            self.assertEqual(out["sample_id"], "row_0000007")
            self.assertEqual(out["image_path"], str(image_path))

    def test_resolve_output_dir_fallback_when_default_unwritable(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="filter1_out_") as td:
            root = Path(td)
            default_dir = root / "default_filter_dir"
            default_dir.mkdir(parents=True, exist_ok=True)
            default_dir.chmod(0o555)
            try:
                out, source = mod._resolve_output_dir(
                    explicit_output_dir="",
                    default_output_dir=default_dir,
                    config={"run": {"run_id": "demo"}},
                )
                self.assertTrue(out.exists())
                self.assertEqual(source, "fallback.artifacts_tmp_filter1")
            finally:
                # Restore permissions so tempfile cleanup can remove the directory.
                default_dir.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
