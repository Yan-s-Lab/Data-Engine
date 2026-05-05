#!/usr/bin/env python
"""Aggregate pose ablation train/eval reports into one compact summary table."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import write_json


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_group_row(group_cfg: Dict[str, Any]) -> Dict[str, Any]:
    train_report = read_json(Path(str(group_cfg["train_report"])))
    eval_report = read_json(Path(str(group_cfg["eval_report"])))
    dataset_summary = train_report.get("dataset_summary", {})
    metrics = eval_report.get("metrics", {})
    return {
        "group_id": str(group_cfg["group_id"]),
        "label": str(group_cfg.get("label", group_cfg["group_id"])),
        "train_report": str(group_cfg["train_report"]),
        "eval_report": str(group_cfg["eval_report"]),
        "real_train_images": int(dataset_summary.get("real_train_images", 0)),
        "synth_train_images": int(dataset_summary.get("synth_train_images", 0)),
        "train_images": int(dataset_summary.get("train_images", 0)),
        "val_images": int(dataset_summary.get("val_images", 0)),
        "pose_mAP50": float(metrics.get("metrics/mAP50(P)", 0.0)),
        "pose_mAP50_95": float(metrics.get("metrics/mAP50-95(P)", 0.0)),
        "box_mAP50": float(metrics.get("metrics/mAP50(B)", 0.0)),
    }


def write_markdown_table(rows: List[Dict[str, Any]], path: Path) -> None:
    lines = [
        "| Group | Label | Real Train | Synth Train | Pose mAP50 | Pose mAP50-95 | Box mAP50 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {group_id} | {label} | {real_train_images} | {synth_train_images} | "
            "{pose_mAP50:.4f} | {pose_mAP50_95:.4f} | {box_mAP50:.4f} |".format(**row)
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv_table(rows: List[Dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate pose ablation train/eval reports")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    agg_cfg = config.get("aggregate_pose_ablation", {})
    groups = agg_cfg.get("groups", [])
    if not isinstance(groups, list) or not groups:
        raise ValueError("aggregate_pose_ablation.groups must be a non-empty list")

    rows = [build_group_row(group_cfg) for group_cfg in groups]
    out_dir = run_dir / "pose_ablation_summary"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "stage": "aggregate_pose_ablation",
        "run_dir": str(run_dir),
        "rows": rows,
    }
    write_json(out_dir / "summary.json", summary)
    write_csv_table(rows, out_dir / "summary.csv")
    write_markdown_table(rows, out_dir / "summary.md")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
