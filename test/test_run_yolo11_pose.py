from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml  # type: ignore


SCRIPT_PATH = Path("train/run_yolo11_pose.py")
spec = importlib.util.spec_from_file_location("run_yolo11_pose", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)


class RunYolo11PoseHelpersTest(unittest.TestCase):
    def test_summarize_dataset_sources_counts_real_and_synth_prefixes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pose_dataset_summary_") as tmp:
            root = Path(tmp)
            (root / "images" / "train").mkdir(parents=True, exist_ok=True)
            (root / "images" / "val").mkdir(parents=True, exist_ok=True)
            for name in ("real_a.jpg", "synth_b.jpg", "synth_c.jpg"):
                (root / "images" / "train" / name).write_bytes(b"x")
            (root / "images" / "val" / "shared.jpg").write_bytes(b"x")
            dataset_yaml = root / "dataset.yaml"
            dataset_yaml.write_text(
                yaml.safe_dump(
                    {
                        "path": str(root),
                        "train": "images/train",
                        "val": "images/val",
                    }
                ),
                encoding="utf-8",
            )

            summary = module.summarize_dataset_sources(dataset_yaml)
            self.assertEqual(summary["train_images"], 3)
            self.assertEqual(summary["val_images"], 1)
            self.assertEqual(summary["real_train_images"], 1)
            self.assertEqual(summary["synth_train_images"], 2)


if __name__ == "__main__":
    unittest.main()
