from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import resolve_filter_and_pipeline_dirs


class ConfigIoRunDirsTest(unittest.TestCase):
    def test_resolve_filter_and_pipeline_dirs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="config_io_dirs_") as td:
            root = Path(td)
            cfg = {
                "run": {
                    "run_id": "r001",
                    "artifacts_root": str(root / "artifacts"),
                }
            }
            out = resolve_filter_and_pipeline_dirs(cfg)
            self.assertTrue(out["run_dir"].exists())
            self.assertTrue(out["filter_dir"].exists())
            self.assertTrue(out["pipeline_dir"].exists())
            self.assertEqual(out["filter_dir"], out["run_dir"] / "filter")
            self.assertEqual(out["pipeline_dir"], out["run_dir"] / "pipeline")
            self.assertEqual(out["pipline_dir"], out["run_dir"] / "pipline")
            self.assertIn("pipline_dir_available", out)


if __name__ == "__main__":
    unittest.main()
