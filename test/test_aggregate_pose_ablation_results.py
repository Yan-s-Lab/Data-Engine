from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml  # type: ignore


SCRIPT_PATH = Path("eval/aggregate_pose_ablation_results.py")


class AggregatePoseAblationResultsTest(unittest.TestCase):
    def test_aggregate_outputs_summary_tables(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pose_agg_") as tmp:
            tmp_root = Path(tmp)
            train_report = tmp_root / "train_report.json"
            eval_report = tmp_root / "eval_report.json"
            train_report.write_text(
                json.dumps(
                    {
                        "dataset_summary": {
                            "real_train_images": 10,
                            "synth_train_images": 5,
                            "train_images": 15,
                            "val_images": 2,
                        }
                    }
                ),
                encoding="utf-8",
            )
            eval_report.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "metrics/mAP50(P)": 0.8,
                            "metrics/mAP50-95(P)": 0.6,
                            "metrics/mAP50(B)": 0.9,
                        }
                    }
                ),
                encoding="utf-8",
            )

            config_path = tmp_root / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "run": {
                            "run_id": "aggregate_run",
                            "artifacts_root": str(tmp_root / "artifacts"),
                        },
                        "aggregate_pose_ablation": {
                            "groups": [
                                {
                                    "group_id": "E",
                                    "label": "real_plus_filtered_synth",
                                    "train_report": str(train_report),
                                    "eval_report": str(eval_report),
                                }
                            ]
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

            out_dir = tmp_root / "artifacts" / "aggregate_run" / "pose_ablation_summary"
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(len(summary["rows"]), 1)
            row = summary["rows"][0]
            self.assertEqual(row["real_train_images"], 10)
            self.assertEqual(row["synth_train_images"], 5)
            self.assertAlmostEqual(row["pose_mAP50"], 0.8)
            self.assertTrue((out_dir / "summary.csv").exists())
            md = (out_dir / "summary.md").read_text(encoding="utf-8")
            self.assertIn("real_plus_filtered_synth", md)


if __name__ == "__main__":
    unittest.main()
