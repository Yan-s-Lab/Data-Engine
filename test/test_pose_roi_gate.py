from __future__ import annotations

import unittest

from common.pose_roi_gate import evaluate_pose_roi_gate, select_best_person_detection


class PoseRoiGateTest(unittest.TestCase):
    def test_select_best_person_detection(self) -> None:
        detections = [
            {"label": 1, "score": 0.45, "box": [0, 0, 10, 10]},
            {"label": 2, "score": 0.99, "box": [0, 0, 10, 10]},
            {"label": 1, "score": 0.88, "box": [0, 0, 20, 20]},
        ]
        best = select_best_person_detection(detections, min_person_score=0.5)
        self.assertIsNotNone(best)
        assert best is not None
        self.assertAlmostEqual(float(best["score"]), 0.88, places=6)

    def test_evaluate_pose_roi_gate_accept(self) -> None:
        person = {"score": 0.9, "box": [10, 10, 90, 90]}
        keypoints = [[20.0 + i, 30.0 + i, 0.9] for i in range(17)]
        pose = {"score": 0.8, "box": [12, 12, 88, 88], "keypoints": keypoints}

        out = evaluate_pose_roi_gate(
            person_detection=person,
            pose_detection=pose,
            image_size=(100, 100),
            min_person_score=0.5,
            min_keypoints=12,
            keypoint_score_threshold=0.5,
            min_bbox_area_ratio=0.05,
            max_bbox_area_ratio=1.0,
        )
        self.assertEqual(out["decision"], "accept")
        self.assertEqual(out["reject_reasons"], [])
        self.assertEqual(out["valid_keypoints"], 17)

    def test_evaluate_pose_roi_gate_rejects_missing_pose(self) -> None:
        person = {"score": 0.9, "box": [10, 10, 90, 90]}
        out = evaluate_pose_roi_gate(
            person_detection=person,
            pose_detection=None,
            image_size=(100, 100),
            min_person_score=0.5,
            min_keypoints=12,
            keypoint_score_threshold=0.5,
            min_bbox_area_ratio=0.05,
            max_bbox_area_ratio=1.0,
        )
        self.assertEqual(out["decision"], "reject")
        self.assertIn("pose_missing", out["reject_reasons"])

    def test_evaluate_pose_roi_gate_rejects_small_bbox_and_low_keypoints(self) -> None:
        keypoints = [[10.0, 10.0, 0.6] for _ in range(8)]
        pose = {"score": 0.8, "box": [0, 0, 15, 15], "keypoints": keypoints}

        out = evaluate_pose_roi_gate(
            person_detection=None,
            pose_detection=pose,
            image_size=(200, 200),
            min_person_score=0.5,
            min_keypoints=12,
            keypoint_score_threshold=0.5,
            min_bbox_area_ratio=0.05,
            max_bbox_area_ratio=1.0,
        )
        self.assertEqual(out["decision"], "reject")
        self.assertIn("bbox_too_small", out["reject_reasons"])
        self.assertIn("insufficient_keypoints", out["reject_reasons"])

    def test_evaluate_pose_roi_gate_uses_segmentation_ratio_override(self) -> None:
        keypoints = [[10.0 + i, 20.0 + i, 0.9] for i in range(17)]
        pose = {"score": 0.9, "box": [0, 0, 10, 10], "keypoints": keypoints}
        out = evaluate_pose_roi_gate(
            person_detection=None,
            pose_detection=pose,
            image_size=(200, 200),
            min_person_score=0.5,
            min_keypoints=12,
            keypoint_score_threshold=0.5,
            min_bbox_area_ratio=0.05,
            max_bbox_area_ratio=0.9,
            roi_area_ratio_override=0.2,
        )
        self.assertEqual(out["decision"], "accept")
        self.assertEqual(out["roi_source"], "segmentation")


if __name__ == "__main__":
    unittest.main()
