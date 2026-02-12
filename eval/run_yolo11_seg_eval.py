#!/usr/bin/env python
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
        raise RuntimeError(
            "missing ultralytics. install with: pip install ultralytics"
        ) from exc
    return YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate YOLO11 segmentation model")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    eval_cfg: Dict[str, Any] = config.get("eval_yolo", {})

    dataset_yaml = Path(str(eval_cfg.get("dataset_yaml", "")))
    ckpt = Path(str(eval_cfg.get("checkpoint", run_dir / "train_yolo" / "exp" / "weights" / "best.pt")))
    if not dataset_yaml.exists():
        raise FileNotFoundError(f"dataset_yaml not found: {dataset_yaml}")
    if not ckpt.exists():
        raise FileNotFoundError(f"checkpoint not found: {ckpt}")

    YOLO = ensure_ultralytics()
    model = YOLO(str(ckpt))
    result = model.val(data=str(dataset_yaml), split=str(eval_cfg.get("split", "val")))

    metrics = getattr(result, "results_dict", {})
    m = metrics.get("metrics/seg(mAP50)", 0.0)
    target = float(eval_cfg.get("target_seg_map50", 0.65))
    action = "tighten_filter" if float(m) < target else "relax_filter"

    eval_dir = run_dir / "eval_yolo"
    eval_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "stage": "eval_yolo",
        "run_dir": str(run_dir),
        "checkpoint": str(ckpt),
        "dataset_yaml": str(dataset_yaml),
        "metrics": metrics,
    }
    feedback = {
        "action": action,
        "reason": "seg_map50_gap_to_target",
        "target_seg_map50": target,
        "observed_seg_map50": m,
    }
    write_json(eval_dir / "report.json", report)
    write_json(eval_dir / "policy_feedback.json", feedback)
    print(json.dumps({"report": report, "policy_feedback": feedback}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
