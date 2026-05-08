from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "filter" / "filter_stages" / "filter2" / "main.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("filter2_main", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load filter2 main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Filter2MainTest(unittest.TestCase):
    def test_route_decision_with_uncertain_keypoint(self) -> None:
        mod = _load_module()
        phase2 = {
            "keypoint_fail_action": "uncertain",
            "bbox_fail_action": "reject",
            "no_person_fail_action": "reject",
            "pose_missing_action": "uncertain",
        }
        decision = mod._route_decision_from_reasons(["insufficient_keypoints"], phase2=phase2)
        self.assertEqual(decision, "uncertain")

    def test_route_decision_prefers_reject(self) -> None:
        mod = _load_module()
        phase2 = {
            "keypoint_fail_action": "uncertain",
            "bbox_fail_action": "reject",
            "no_person_fail_action": "reject",
            "pose_missing_action": "uncertain",
        }
        decision = mod._route_decision_from_reasons(
            ["insufficient_keypoints", "bbox_too_small"],
            phase2=phase2,
        )
        self.assertEqual(decision, "reject")

    def test_resolve_phase2_defaults(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="filter2_cfg_") as td:
            root = Path(td)
            cfg = {"filter": {"phase2_roi_pose": {"enabled": True}}}
            out = mod._resolve_phase2_cfg(cfg, config_path=root / "config.yaml", run_filter_dir=root / "run" / "filter")
            self.assertTrue(bool(out["enabled"]))
            self.assertTrue(str(out["input_manifest"]).endswith("run/filter/splits/accept.jsonl"))
            self.assertTrue(str(out["pose_model"]).endswith("third_party/yolo26x-pose.pt"))
            self.assertFalse(bool(out["det_enabled"]))

    def test_extract_segmentation_area_ratio(self) -> None:
        mod = _load_module()
        row = {"raw": {"person_mask_area_ratio": 0.31}}
        ratio = mod._extract_segmentation_area_ratio(
            row,
            enabled=True,
            field="person_mask_area_ratio",
        )
        self.assertAlmostEqual(float(ratio), 0.31, places=6)

    def test_extract_segmentation_area_ratio_disabled(self) -> None:
        mod = _load_module()
        row = {"raw": {"person_mask_area_ratio": 0.31}}
        ratio = mod._extract_segmentation_area_ratio(
            row,
            enabled=False,
            field="person_mask_area_ratio",
        )
        self.assertIsNone(ratio)


if __name__ == "__main__":
    unittest.main()
