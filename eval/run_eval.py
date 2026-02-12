#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import read_json, read_jsonl, write_json, write_jsonl


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval stage stub with feedback artifact")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    eval_cfg = config.get("eval", {})

    model_stub_path = Path(str(eval_cfg.get("model_stub", run_dir / "train" / "model_stub.json")))
    if not model_stub_path.exists():
        raise FileNotFoundError(f"missing train artifact: {model_stub_path}")

    model_stub = read_json(model_stub_path)
    train_metric = float(model_stub.get("train_metric", 0.5))

    filter_scores_path = run_dir / "filter" / "filter_scores.jsonl"
    if not filter_scores_path.exists():
        raise FileNotFoundError(f"missing filter artifact: {filter_scores_path}")
    scores = read_jsonl(filter_scores_path)

    by_source: Dict[str, List[float]] = {"real": [], "synthetic": []}
    for row in scores:
        src = str(row.get("source"))
        if src in by_source:
            by_source[src].append(float(row.get("score_asf", 0.0)))

    mean_real = sum(by_source["real"]) / len(by_source["real"]) if by_source["real"] else 0.0
    mean_synth = (
        sum(by_source["synthetic"]) / len(by_source["synthetic"])
        if by_source["synthetic"]
        else 0.0
    )

    mAP50 = round(clamp(0.4 + train_metric * 0.5 + mean_real * 0.08), 4)
    mAP50_95 = round(clamp(mAP50 - 0.13), 4)
    iou_mean = round(clamp(0.35 + train_metric * 0.4 + mean_synth * 0.12), 4)

    eval_dir = run_dir / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "mAP50": mAP50,
        "mAP50_95": mAP50_95,
        "iou_mean": iou_mean,
        "calibration_error": round(clamp(0.35 - train_metric * 0.25, 0.01, 1.0), 4),
    }

    slice_report = {
        "source_slice": {
            "real": {
                "count": len(by_source["real"]),
                "mean_score_asf": round(mean_real, 4),
            },
            "synthetic": {
                "count": len(by_source["synthetic"]),
                "mean_score_asf": round(mean_synth, 4),
            },
        }
    }

    hard_cases = sorted(scores, key=lambda x: float(x.get("score_asf", 0.0)))[: int(eval_cfg.get("hard_case_topk", 5))]
    failure_rows = [
        {
            "sample_id": row.get("sample_id"),
            "source": row.get("source"),
            "reason": "low_asf_score",
            "score_asf": row.get("score_asf"),
        }
        for row in hard_cases
    ]

    target_map50 = float(eval_cfg.get("target_map50", 0.75))
    current_accept_threshold = float(config.get("filter", {}).get("accept_threshold", 0.6))
    if mAP50 < target_map50:
        suggested_threshold = round(clamp(current_accept_threshold + 0.05), 4)
        action = "tighten_filter"
    else:
        suggested_threshold = round(clamp(current_accept_threshold - 0.03), 4)
        action = "relax_filter"

    policy_feedback = {
        "action": action,
        "reason": "mAP50_gap_to_target",
        "target_map50": target_map50,
        "observed_map50": mAP50,
        "current_filter_accept_threshold": current_accept_threshold,
        "suggested_filter_accept_threshold": suggested_threshold,
    }

    write_json(eval_dir / "metrics.json", metrics)
    write_json(eval_dir / "slice_report.json", slice_report)
    write_jsonl(eval_dir / "failure_cases.jsonl", failure_rows)
    write_json(eval_dir / "policy_feedback.json", policy_feedback)

    out = {
        "stage": "eval",
        "run_dir": str(run_dir),
        "metrics": metrics,
        "policy_feedback": policy_feedback,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
