#!/usr/bin/env python
"""Train YOLO11-pose model. Wrapper around ultralytics YOLO.train() for pose task."""
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
    parser = argparse.ArgumentParser(description="Train YOLO11 pose model")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    train_cfg: Dict[str, Any] = config.get("train_yolo", {})

    dataset_yaml = Path(str(train_cfg.get("dataset_yaml", "")))
    if not dataset_yaml.exists():
        raise FileNotFoundError(f"dataset_yaml not found: {dataset_yaml}")

    YOLO = ensure_ultralytics()
    model_name = str(train_cfg.get("model", "yolo11n-pose.pt"))
    epochs = int(train_cfg.get("epochs", 100))
    imgsz = int(train_cfg.get("imgsz", 640))
    batch = int(train_cfg.get("batch", 16))
    device = str(train_cfg.get("device", "0"))
    workers = int(train_cfg.get("workers", 4))
    patience = int(train_cfg.get("patience", 30))

    train_dir = run_dir / "train_yolo_pose"
    train_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(model_name)
    result = model.train(
        data=str(dataset_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=workers,
        patience=patience,
        project=str(train_dir),
        name="exp",
        exist_ok=True,
    )

    metrics = getattr(result, "results_dict", {})
    save_dir = str(getattr(result, "save_dir", train_dir / "exp"))
    best_ckpt = Path(save_dir) / "weights" / "best.pt"

    report = {
        "stage": "train_yolo_pose",
        "run_dir": str(run_dir),
        "dataset_yaml": str(dataset_yaml),
        "model": model_name,
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "device": device,
        "save_dir": save_dir,
        "best_ckpt": str(best_ckpt),
        "metrics": metrics,
    }
    write_json(train_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
