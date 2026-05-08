from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from PIL import Image

from synth.run_generate import filter_anchor_rows_by_size


class GenerateAnchorFilterTest(unittest.TestCase):
    def test_skip_oversized_anchors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="anchor_filter_") as td:
            root = Path(td)
            small = root / "small.png"
            large = root / "large.png"
            Image.new("RGB", (1024, 768), color=(128, 128, 128)).save(small)
            Image.new("RGB", (3500, 2333), color=(128, 128, 128)).save(large)

            rows = [
                {"sample_id": "s1", "image_path": str(small)},
                {"sample_id": "s2", "image_path": str(large)},
            ]
            comfy_cfg = {
                "anchor_filter": {
                    "max_long_edge": 1536,
                }
            }
            anchor_cfgs = [{"node_id": "17", "path_field": "image_path"}]

            kept, stats = filter_anchor_rows_by_size(rows, comfy_cfg, anchor_cfgs)
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["sample_id"], "s1")
            self.assertTrue(stats["anchor_filter_enabled"])
            self.assertEqual(stats["anchor_total_count"], 2)
            self.assertEqual(stats["anchor_eligible_count"], 1)
            self.assertEqual(stats["anchor_skipped_count"], 1)


if __name__ == "__main__":
    unittest.main()
