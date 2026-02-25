from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ManagedPipelineSmokeTest(unittest.TestCase):
    def _run(self, config_path: Path, artifacts_root: Path) -> dict:
        subprocess.run(
            [
                sys.executable,
                "pipelines/run_managed_pipeline.py",
                "--config",
                str(config_path),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        summary_path = artifacts_root / "managed_pipeline_smoke" / "pipeline" / "summary.json"
        return json.loads(summary_path.read_text(encoding="utf-8"))

    def _prepare_raw_dataset(self, temp_root: Path) -> Path:
        src_dir = ROOT / "test" / "test-filters" / "real_raw" / "images"
        raw_root = temp_root / "raw"
        image_dir = raw_root / "images"
        image_dir.mkdir(parents=True, exist_ok=True)

        for image_path in sorted(src_dir.glob("*.png")):
            shutil.copy2(image_path, image_dir / image_path.name)
        return raw_root

    def test_managed_pipeline_resume_skip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="managed_pipeline_smoke_") as td:
            temp_root = Path(td)
            raw_root = self._prepare_raw_dataset(temp_root)

            cfg = {
                "run": {
                    "run_id": "managed_pipeline_smoke",
                    "artifacts_root": str(temp_root / "artifacts"),
                },
                "pipeline": {
                    "steps": ["dataloader"],
                    "resume_from_artifacts": True,
                },
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

            config_path = temp_root / "managed_pipeline_smoke.json"
            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

            first = self._run(config_path, temp_root / "artifacts")
            self.assertEqual(first["status"], "ok")
            self.assertEqual(first["completed_steps"], ["dataloader"])
            self.assertEqual(first["skipped_steps"], [])

            second = self._run(config_path, temp_root / "artifacts")
            self.assertEqual(second["status"], "ok")
            self.assertEqual(second["completed_steps"], [])
            self.assertEqual(second["skipped_steps"], ["dataloader"])


if __name__ == "__main__":
    unittest.main()
