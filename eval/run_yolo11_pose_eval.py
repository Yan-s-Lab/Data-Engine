#!/usr/bin/env python
"""Evaluate a trained YOLO11-pose checkpoint and write metrics report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import write_json


def ensure_ultralytics() -> Any:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pip install ultralytics") from exc
    return YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate YOLO11-pose checkpoint")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    eval_cfg: Dict[str, Any] = config.get("eval_yolo", {})

    dataset_yaml = Path(str(eval_cfg.get("dataset_yaml", "")))
    ckpt = Path(str(eval_cfg.get("checkpoint", "")))
    split = str(eval_cfg.get("split", "val"))

    if not dataset_yaml.exists():
        raise FileNotFoundError(f"dataset_yaml not found: {dataset_yaml}")
    if not ckpt.exists():
        raise FileNotFoundError(f"checkpoint not found: {ckpt}")

    YOLO = ensure_ultralytics()
    model = YOLO(str(ckpt))
    result = model.val(data=str(dataset_yaml), split=split)

    metrics = getattr(result, "results_dict", {})

    eval_dir = run_dir / "eval_yolo_pose"
    eval_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "stage": "eval_yolo_pose",
        "run_dir": str(run_dir),
        "checkpoint": str(ckpt),
        "dataset_yaml": str(dataset_yaml),
        "split": split,
        "metrics": metrics,
        # Key pose metrics from ultralytics results_dict:
        #   metrics/pose(mAP50)    — OKS-based mAP@IoU=0.5
        #   metrics/pose(mAP50-95) — OKS-based mAP@IoU=0.5:0.95
        #   metrics/box(mAP50)     — bounding box mAP@0.5
    }
    write_json(eval_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
