from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml  # type: ignore


SCRIPT_PATH = Path("label/build_mixed_dataset.py")


def _write_dataset(root: Path, *, split: str, stem: str) -> None:
    (root / "images" / split).mkdir(parents=True, exist_ok=True)
    (root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (root / "images" / split / f"{stem}.jpg").write_bytes(b"img")
    (root / "labels" / split / f"{stem}.txt").write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")


class BuildMixedDatasetTest(unittest.TestCase):
    def test_main_builds_train_only_mix_with_shared_eval_holdout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mixed_pose_") as tmp:
            tmp_root = Path(tmp)
            real_root = tmp_root / "real_train_anchor"
            synth_root = tmp_root / "filtered_synth_dataset"
            holdout_root = tmp_root / "real_test_holdout"

            _write_dataset(real_root, split="train", stem="real_pose")
            _write_dataset(real_root, split="val", stem="real_internal_val")
            _write_dataset(synth_root, split="train", stem="synth_pose")
            _write_dataset(synth_root, split="val", stem="synth_internal_val")
            _write_dataset(holdout_root, split="test", stem="shared_eval")

            config_path = tmp_root / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "run": {
                            "run_id": "mixed_run",
                            "artifacts_root": str(tmp_root / "artifacts"),
                        },
                        "build_mixed": {
                            "output_name": "real_plus_filtered_synth_dataset",
                            "real_train_dataset": str(real_root),
                            "synth_train_dataset": str(synth_root),
                            "shared_eval_dataset": str(holdout_root),
                        },
                    }
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--config", str(config_path)],
                check=True,
                cwd=Path.cwd(),
            )

            out_root = (
                tmp_root
                / "artifacts"
                / "mixed_run"
                / "label"
                / "real_plus_filtered_synth_dataset"
            )
            train_files = sorted(p.name for p in (out_root / "images" / "train").iterdir())
            val_files = sorted(p.name for p in (out_root / "images" / "val").iterdir())
            self.assertEqual(train_files, ["real_real_pose.jpg", "synth_synth_pose.jpg"])
            self.assertEqual(val_files, ["shared_eval.jpg"])
            self.assertFalse((out_root / "images" / "val" / "real_internal_val.jpg").exists())
            self.assertFalse((out_root / "images" / "val" / "synth_internal_val.jpg").exists())

            dataset_yaml = yaml.safe_load((out_root / "dataset.yaml").read_text(encoding="utf-8"))
            self.assertEqual(dataset_yaml["train"], "images/train")
            self.assertEqual(dataset_yaml["val"], "images/val")
            self.assertEqual(dataset_yaml["test"], "images/val")

            report = json.loads((out_root / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["real_train_images"], 1)
            self.assertEqual(report["synth_train_images"], 1)
            self.assertEqual(report["eval_images"], 1)


if __name__ == "__main__":
    unittest.main()
