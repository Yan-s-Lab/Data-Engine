from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.siglip2_margin_threshold import compute_margin, sweep_best_f1_threshold


class Siglip2MarginThresholdTest(unittest.TestCase):
    def test_compute_margin_uses_top_k_mean(self) -> None:
        stats = compute_margin(
            pos_logits=[0.1, 0.8, 0.2, 0.5],
            neg_logits=[-0.3, 0.2, 0.1, 0.0],
            top_k=3,
        )
        self.assertAlmostEqual(stats["pos_score"], (0.8 + 0.5 + 0.2) / 3.0, places=6)
        self.assertAlmostEqual(stats["neg_score"], (0.2 + 0.1 + 0.0) / 3.0, places=6)
        self.assertAlmostEqual(stats["margin"], 0.4, places=6)

    def test_compute_margin_k_larger_than_group_size(self) -> None:
        stats = compute_margin(
            pos_logits=[0.4, 0.2],
            neg_logits=[0.1],
            top_k=3,
        )
        self.assertAlmostEqual(stats["pos_score"], 0.3, places=6)
        self.assertAlmostEqual(stats["neg_score"], 0.1, places=6)
        self.assertAlmostEqual(stats["margin"], 0.2, places=6)

    def test_sweep_best_threshold_returns_expected_metrics(self) -> None:
        margins = [0.9, 0.8, 0.6, 0.4, 0.2, -0.1]
        labels = [1, 1, 1, 0, 0, 0]
        best = sweep_best_f1_threshold(margins, labels)
        self.assertAlmostEqual(best["threshold"], 0.6, places=6)
        self.assertAlmostEqual(best["precision"], 1.0, places=6)
        self.assertAlmostEqual(best["recall"], 1.0, places=6)
        self.assertAlmostEqual(best["f1"], 1.0, places=6)
        self.assertEqual(best["confusion_matrix"], [[3, 0], [0, 3]])

    def test_sweep_threshold_input_validation(self) -> None:
        with self.assertRaises(ValueError):
            sweep_best_f1_threshold([], [])
        with self.assertRaises(ValueError):
            sweep_best_f1_threshold([0.1], [1, 0])
        with self.assertRaises(ValueError):
            sweep_best_f1_threshold([0.1], [2])


if __name__ == "__main__":
    unittest.main()
