#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import write_json
from common.siglip2_inference import compute_siglip2_logits_for_image, load_siglip2_runtime
from common.siglip2_margin_threshold import (
    compute_margin,
    sweep_best_f1_threshold,
    sweep_best_threshold_at_min_precision,
)


def _resolve_path(raw: str, *, base_dir: Path) -> Path:
    path = Path(str(raw).strip())
    if path.is_absolute():
        return path
    candidate = (base_dir / path).resolve()
    if candidate.exists():
        return candidate
    return (ROOT / path).resolve()


def _load_labeled_rows(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"labeled data must be a list: {path}")
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"invalid row at index {idx}: must be object")
        imagepath = str(
            item.get("imagepath", item.get("image_path", item.get("path", "")))
        ).strip()
        label = str(item.get("label", "")).strip().lower()
        if not imagepath:
            raise ValueError(
                f"invalid row at index {idx}: one of imagepath/image_path/path is required"
            )
        if label not in {"accept", "reject"}:
            raise ValueError(f"invalid row at index {idx}: label must be accept/reject")
        out.append({"imagepath": imagepath, "label": label})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Find best F1 threshold from SigLIP2 logits margins")
    parser.add_argument("--config", required=True, help="Filter yaml/json config path")
    parser.add_argument("--top-k", type=int, default=3, help="Top-k for positive/negative logits aggregation")
    parser.add_argument(
        "--min-precision",
        type=float,
        default=None,
        help="Optional precision constraint in [0,1]. If set, choose threshold with max recall under precision>=min_precision.",
    )
    parser.add_argument("--output", default="", help="Optional output report JSON path")
    args = parser.parse_args()

    if args.top_k <= 0:
        raise ValueError("--top-k must be > 0")
    if args.min_precision is not None and not (0.0 <= float(args.min_precision) <= 1.0):
        raise ValueError("--min-precision must be within [0,1]")

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    run_dir = resolve_run_dir(config)

    filter_cfg = dict(config.get("filter", {}))
    clip_cfg = dict(filter_cfg.get("clip", {}))
    compared_prompt = dict(clip_cfg.get("compared_prompt", {}))
    positive_prompts = [str(x).strip() for x in compared_prompt.get("positive", []) if str(x).strip()]
    negative_prompts = [str(x).strip() for x in compared_prompt.get("negative", []) if str(x).strip()]
    if not positive_prompts or not negative_prompts:
        raise ValueError("filter.clip.compared_prompt.positive and negative must be non-empty lists")

    labeled_raw = str(filter_cfg.get("siglip2_baseline_labeled", "")).strip()
    if not labeled_raw:
        raise ValueError("filter.siglip2_baseline_labeled is required")
    labeled_path = _resolve_path(labeled_raw, base_dir=config_path.parent)
    rows = _load_labeled_rows(labeled_path)

    model_id = str(clip_cfg.get("model_id", "google/siglip2-so400m-patch16-naflex")).strip()
    model, processor, device = load_siglip2_runtime(model_id=model_id, device_cfg=str(clip_cfg.get("device", "auto")))

    all_prompts = positive_prompts + negative_prompts
    samples: List[Dict[str, Any]] = []
    margins: List[float] = []
    labels: List[int] = []

    for row in rows:
        image_path = _resolve_path(row["imagepath"], base_dir=labeled_path.parent)
        logits = compute_siglip2_logits_for_image(
            model=model,
            processor=processor,
            image_path=image_path,
            prompts=all_prompts,
            device=device,
        )
        pos_logits = logits[: len(positive_prompts)]
        neg_logits = logits[len(positive_prompts) :]
        margin_stats = compute_margin(pos_logits, neg_logits, top_k=args.top_k)

        label_binary = 1 if row["label"] == "accept" else 0
        result_row = {
            "imagepath": str(image_path),
            "label": row["label"],
            "label_binary": label_binary,
            "margin": float(margin_stats["margin"]),
            "pos_score": float(margin_stats["pos_score"]),
            "neg_score": float(margin_stats["neg_score"]),
        }
        samples.append(result_row)
        margins.append(float(margin_stats["margin"]))
        labels.append(label_binary)

    if args.min_precision is None:
        best = sweep_best_f1_threshold(margins=margins, labels=labels)
        selection_policy = "max_f1"
    else:
        best = sweep_best_threshold_at_min_precision(
            margins=margins,
            labels=labels,
            min_precision=float(args.min_precision),
        )
        selection_policy = "max_recall_at_min_precision"
    report = {
        "model_id": model_id,
        "device": device,
        "top_k": int(args.top_k),
        "selection_policy": selection_policy,
        "min_precision": args.min_precision,
        "total": len(samples),
        "best_threshold": float(best["threshold"]),
        "precision": float(best["precision"]),
        "recall": float(best["recall"]),
        "f1": float(best["f1"]),
        "confusion_matrix": best["confusion_matrix"],
        "samples": samples,
    }

    out_path = Path(args.output) if str(args.output).strip() else (run_dir / "filter" / "siglip2_margin_threshold_report.json")
    write_json(out_path, report)
    print(json.dumps({k: report[k] for k in ["best_threshold", "precision", "recall", "f1", "confusion_matrix"]}, ensure_ascii=False, indent=2))
    print(f"wrote: {out_path}")


if __name__ == "__main__":
    main()
