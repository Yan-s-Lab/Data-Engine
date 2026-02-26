from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from filter.run_filter import _run_filter_mode


class FilterModeDispatchTest(unittest.TestCase):
    def test_staged_mode_uses_legacy_runner(self) -> None:
        rows = [{"sample_id": "s1", "source": "synthetic", "image_path": "a.png"}]
        with patch("filter.run_filter.run_legacy_staged_clip_filter") as staged_runner:
            staged_runner.return_value = ([{"sample_id": "s1", "decision": "accept"}], {"strategy": "tri_gate"})
            score_rows, report_extra = _run_filter_mode(
                mode="staged_clip",
                rows=rows,
                filter_dir=Path("/tmp/filter"),
                accept_threshold=0.7,
                uncertain_low=0.5,
                uncertain_high=0.7,
                filter_cfg={"mode": "staged_clip"},
            )

        self.assertEqual(score_rows[0]["decision"], "accept")
        self.assertEqual(report_extra["strategy"], "tri_gate")
        staged_runner.assert_called_once()


if __name__ == "__main__":
    unittest.main()
