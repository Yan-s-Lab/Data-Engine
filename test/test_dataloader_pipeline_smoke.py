from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DataLoaderPipelineSmokeTest(unittest.TestCase):
    def _run(self, script: str, config_path: Path) -> None:
        subprocess.run(
            [sys.executable, script, "--config", str(config_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def _prepare_raw_dataset(self, temp_root: Path, with_labels: bool) -> Path:
        src_dir = ROOT / "test" / "testfilter" / "real_raw" / "images"
        raw_root = temp_root / "raw"
        image_dir = raw_root / "images"
        label_dir = raw_root / "labels"
        image_dir.mkdir(parents=True, exist_ok=True)
        if with_labels:
            label_dir.mkdir(parents=True, exist_ok=True)

        for image_path in sorted(src_dir.glob("*.png")):
            shutil.copy2(image_path, image_dir / image_path.name)
            if with_labels:
                label_path = label_dir / f"{image_path.stem}.txt"
                label_path.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        return raw_root

    def test_dataloader_norm_cli_smoke(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dataloader_cli_smoke_") as td:
            temp_root = Path(td)
            raw_root = self._prepare_raw_dataset(temp_root, with_labels=True)

            cfg = {
                "run": {
                    "run_id": "dataloader_cli_smoke",
                    "artifacts_root": str(temp_root / "artifacts"),
                },
                "dataloader": {
                    "real_dir": str(raw_root),
                    "image_dir": str(raw_root / "images"),
                    "label_dir": str(raw_root / "labels"),
                    "label_ext": ".txt",
                    "require_labels": True,
                    "patterns": ["*.png"],
                    "output": {
                        "root_dir": str(temp_root / "normalized" / "${services_id}_${task_name}"),
                        "images_subdir": "images",
                        "labels_subdir": "labels",
                    },
                    "naming": {
                        "canonicalize_names": True,
                        "services_id": "yk-001",
                        "task_name": "arm_deltoid_muscle_seg",
                        "filename_template": "${services_id}_${task_name}_${seq_id_padded}",
                        "id_width": 4,
                        "id_start": 1,
                        "target_image_ext": ".png",
                        "materialize_mode": "copy",
                    },
                },
            }

            config_path = temp_root / "dataloader_cli_smoke.json"
            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

            self._run("ingest/run_dataloader.py", config_path)

            run_dir = temp_root / "artifacts" / "dataloader_cli_smoke" / "dataloader"
            manifest_path = run_dir / "real_manifest.jsonl"
            report_path = run_dir / "report.json"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(report_path.exists())

            rows = [
                json.loads(line)
                for line in manifest_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["sample_id"], "yk-001_arm_deltoid_muscle_seg_0001")
            self.assertEqual(rows[1]["sample_id"], "yk-001_arm_deltoid_muscle_seg_0002")
            for row in rows:
                self.assertTrue(Path(row["image_path"]).exists())
                self.assertTrue(Path(row["label_path"]).exists())

    def test_yaml_pipeline_dataloader_only_smoke(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dataloader_pipeline_smoke_") as td:
            temp_root = Path(td)
            raw_root = self._prepare_raw_dataset(temp_root, with_labels=False)

            cfg = {
                "run": {
                    "run_id": "dataloader_pipeline_smoke",
                    "artifacts_root": str(temp_root / "artifacts"),
                },
                "pipeline": {"steps": ["dataloader"]},
                "dataloader": {
                    "real_dir": str(raw_root),
                    "image_dir": str(raw_root / "images"),
                    "require_labels": False,
                    "patterns": ["*.png"],
                    "naming": {
                        "canonicalize_names": True,
                        "services_id": "yk-001",
                        "task_name": "arm_deltoid_muscle_seg",
                        "filename_template": "${services_id}_${task_name}_${seq_id_padded}",
                        "id_width": 4,
                        "id_start": 1,
                        "target_image_ext": ".png",
                        "materialize_mode": "copy",
                    },
                },
            }

            config_path = temp_root / "dataloader_pipeline_smoke.json"
            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

            self._run("pipelines/run_yaml_pipeline.py", config_path)

            run_root = temp_root / "artifacts" / "dataloader_pipeline_smoke"
            manifest_path = run_root / "dataloader" / "real_manifest.jsonl"
            summary_path = run_root / "pipeline" / "summary.json"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(summary_path.exists())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["steps"], ["dataloader"])


if __name__ == "__main__":
    unittest.main()
