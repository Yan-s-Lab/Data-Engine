from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml  # type: ignore


SCRIPT_PATH = Path("label/build_coco_yolo_pose.py")
spec = importlib.util.spec_from_file_location("build_coco_yolo_pose", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)


class BuildCocoYoloPoseTest(unittest.TestCase):
    def test_split_ids_with_holdout_is_deterministic_and_disjoint(self) -> None:
        ids = [1, 2, 3, 4, 5]
        split_a = module.split_ids_with_holdout(
            ids,
            seed=7,
            anchor_val_ratio=0.34,
            test_count=2,
        )
        split_b = module.split_ids_with_holdout(
            ids,
            seed=7,
            anchor_val_ratio=0.34,
            test_count=2,
        )

        self.assertEqual(split_a, split_b)
        self.assertEqual(len(split_a["train"]), 2)
        self.assertEqual(len(split_a["val"]), 1)
        self.assertEqual(len(split_a["test"]), 2)
        self.assertEqual(
            len(set(split_a["train"]) | set(split_a["val"]) | set(split_a["test"])),
            5,
        )

    def test_main_writes_anchor_and_holdout_datasets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pose_real_split_") as tmp:
            tmp_root = Path(tmp)
            images_dir = tmp_root / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            for idx in range(1, 6):
                (images_dir / f"img_{idx}.jpg").write_bytes(b"test")

            ann_json = tmp_root / "annotations.json"
            images = []
            annotations = []
            for idx in range(1, 6):
                images.append(
                    {
                        "id": idx,
                        "file_name": f"img_{idx}.jpg",
                        "width": 100,
                        "height": 200,
                    }
                )
                annotations.append(
                    {
                        "id": idx,
                        "image_id": idx,
                        "category_id": 1,
                        "iscrowd": 0,
                        "bbox": [10, 20, 30, 40],
                        "keypoints": [10, 20, 2] * 17,
                    }
                )
            ann_json.write_text(
                json.dumps(
                    {
                        "images": images,
                        "annotations": annotations,
                        "categories": [{"id": 1, "name": "person"}],
                    }
                ),
                encoding="utf-8",
            )

            config_path = tmp_root / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "run": {
                            "run_id": "pose_real",
                            "artifacts_root": str(tmp_root / "artifacts"),
                        },
                        "coco_to_yolo_pose": {
                            "annotation_json": str(ann_json),
                            "images_dir": str(images_dir),
                            "output_name": "real_train_anchor",
                            "holdout_output_name": "real_test_holdout",
                            "anchor_val_ratio": 0.34,
                            "test_count": 2,
                            "seed": 7,
                            "min_keypoints": 5,
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

            run_root = tmp_root / "artifacts" / "pose_real" / "label"
            anchor_root = run_root / "real_train_anchor"
            holdout_root = run_root / "real_test_holdout"
            self.assertTrue((anchor_root / "dataset.yaml").exists())
            self.assertTrue((holdout_root / "dataset.yaml").exists())

            self.assertEqual(len(list((anchor_root / "images" / "train").iterdir())), 2)
            self.assertEqual(len(list((anchor_root / "images" / "val").iterdir())), 1)
            self.assertEqual(len(list((holdout_root / "images" / "test").iterdir())), 2)

            anchor_yaml = yaml.safe_load((anchor_root / "dataset.yaml").read_text(encoding="utf-8"))
            holdout_yaml = yaml.safe_load(
                (holdout_root / "dataset.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(anchor_yaml["train"], "images/train")
            self.assertEqual(anchor_yaml["val"], "images/val")
            self.assertNotIn("test", anchor_yaml)
            self.assertEqual(holdout_yaml["val"], "images/test")
            self.assertEqual(holdout_yaml["test"], "images/test")


if __name__ == "__main__":
    unittest.main()
