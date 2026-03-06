from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = Path(
    "artifacts/datasets/rawdatasets/coco_pose/build_single_person_pose_subset.py"
)

spec = importlib.util.spec_from_file_location("coco_subset_builder", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)


class CocoPoseSubsetBuilderTest(unittest.TestCase):
    def test_select_single_person_samples_and_build_subset(self) -> None:
        data = {
            "info": {"description": "mini"},
            "licenses": [{"id": 1, "name": "cc"}, {"id": 2, "name": "cc2"}],
            "images": [
                {
                    "id": 1,
                    "file_name": "a.jpg",
                    "coco_url": "http://example.com/a.jpg",
                    "license": 1,
                },
                {
                    "id": 2,
                    "file_name": "b.jpg",
                    "coco_url": "http://example.com/b.jpg",
                    "license": 2,
                },
                {
                    "id": 3,
                    "file_name": "c.jpg",
                    "coco_url": "http://example.com/c.jpg",
                    "license": 1,
                },
            ],
            "annotations": [
                {
                    "id": 10,
                    "image_id": 1,
                    "category_id": 1,
                    "iscrowd": 0,
                    "num_keypoints": 12,
                    "bbox": [0, 0, 10, 10],
                },
                {
                    "id": 11,
                    "image_id": 2,
                    "category_id": 1,
                    "iscrowd": 0,
                    "num_keypoints": 12,
                    "bbox": [0, 0, 8, 8],
                },
                {
                    "id": 12,
                    "image_id": 2,
                    "category_id": 1,
                    "iscrowd": 0,
                    "num_keypoints": 12,
                    "bbox": [0, 0, 7, 7],
                },
                {
                    "id": 13,
                    "image_id": 3,
                    "category_id": 1,
                    "iscrowd": 0,
                    "num_keypoints": 0,
                    "bbox": [0, 0, 30, 30],
                },
            ],
            "categories": [{"id": 1, "name": "person"}],
        }

        selected = module.select_single_person_samples(
            data=data,
            max_download=300,
            min_num_keypoints=1,
            category_id=1,
            keep_crowd=False,
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["image_id"], 1)
        self.assertEqual(selected[0]["file_name"], "a.jpg")

        subset = module.build_subset_coco(data, selected)
        self.assertEqual(len(subset["images"]), 1)
        self.assertEqual(subset["images"][0]["id"], 1)
        self.assertEqual(len(subset["annotations"]), 1)
        self.assertEqual(subset["annotations"][0]["id"], 10)
        self.assertEqual(len(subset["licenses"]), 1)
        self.assertEqual(subset["licenses"][0]["id"], 1)


if __name__ == "__main__":
    unittest.main()
