from __future__ import annotations

import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
_PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnQZt0AAAAASUVORK5CYII="
)


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

        image_paths = sorted(src_dir.glob("*.png")) if src_dir.exists() else []
        if image_paths:
            for image_path in image_paths:
                shutil.copy2(image_path, image_dir / image_path.name)
                if with_labels:
                    label_path = label_dir / f"{image_path.stem}.txt"
                    label_path.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        else:
            for idx in range(2):
                image_path = image_dir / f"sample_{idx + 1:04d}.png"
                image_path.write_bytes(base64.b64decode(_PNG_1X1_BASE64))
                if with_labels:
                    label_path = label_dir / f"{image_path.stem}.txt"
                    label_path.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        return raw_root

    def _prepare_coco_ann_file(self, raw_root: Path) -> Path:
        image_dir = raw_root / "images"
        image_paths = sorted(image_dir.glob("*.png"))
        self.assertGreaterEqual(len(image_paths), 2)
        coco = {
            "images": [
                {
                    "id": 1,
                    "file_name": image_paths[0].name,
                    "width": 128,
                    "height": 128,
                },
                {
                    "id": 2,
                    "file_name": image_paths[1].name,
                    "width": 128,
                    "height": 128,
                },
            ],
            "annotations": [
                {
                    "id": 10,
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [0, 0, 10, 10],
                    "num_keypoints": 5,
                    "iscrowd": 0,
                    "keypoints": [0] * 51,
                }
            ],
            "categories": [{"id": 1, "name": "person"}],
        }
        ann_path = raw_root / "pose_annotations.json"
        ann_path.write_text(json.dumps(coco, ensure_ascii=False, indent=2), encoding="utf-8")
        return ann_path

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

    def test_dataloader_norm_cli_coco_label_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dataloader_cli_coco_smoke_") as td:
            temp_root = Path(td)
            raw_root = self._prepare_raw_dataset(temp_root, with_labels=False)
            ann_path = self._prepare_coco_ann_file(raw_root)

            cfg = {
                "run": {
                    "run_id": "dataloader_cli_coco_smoke",
                    "artifacts_root": str(temp_root / "artifacts"),
                },
                "dataloader": {
                    "real_dir": str(raw_root),
                    "image_dir": str(raw_root / "images"),
                    "label_format": "coco",
                    "label_file": str(ann_path),
                    "require_labels": True,
                    "patterns": ["*.png"],
                    "naming": {
                        "canonicalize_names": True,
                        "services_id": "yk-001",
                        "task_name": "body_pose_coco",
                        "filename_template": "${services_id}_${task_name}_${seq_id_padded}",
                        "id_width": 4,
                        "id_start": 1,
                        "target_image_ext": ".png",
                        "materialize_mode": "copy",
                    },
                },
            }

            config_path = temp_root / "dataloader_cli_coco_smoke.json"
            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

            self._run("ingest/run_dataloader.py", config_path)

            run_dir = temp_root / "artifacts" / "dataloader_cli_coco_smoke" / "dataloader"
            manifest_path = run_dir / "real_manifest.jsonl"
            report_path = run_dir / "report.json"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(report_path.exists())

            rows = [
                json.loads(line)
                for line in manifest_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["label_format"], "coco")
            self.assertEqual(row["coco_image_id"], 1)
            self.assertEqual(row["coco_annotation_count"], 1)
            self.assertEqual(Path(row["label_path"]), ann_path)


if __name__ == "__main__":
    unittest.main()
