#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_filter_and_pipeline_dirs
from common.manifest_io import read_jsonl, write_json, write_jsonl
from common.siglip2_inference import compute_siglip2_logits_for_image, load_siglip2_runtime
from common.siglip2_margin_threshold import compute_margin


def _resolve_path(raw: str, *, base_dir: Path) -> Path:
    path = Path(str(raw).strip())
    if path.is_absolute():
        return path
    candidate = (base_dir / path).resolve()
    if candidate.exists():
        return candidate
    return (ROOT / path).resolve()


def _resolve_input_manifests(filter_cfg: Dict[str, Any], *, config_path: Path) -> List[Path]:
    raw = filter_cfg.get("input_manifests", [])
    manifests: List[Path] = []
    if isinstance(raw, str) and raw.strip():
        manifests.append(_resolve_path(raw, base_dir=config_path.parent))
    elif isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text:
                manifests.append(_resolve_path(text, base_dir=config_path.parent))
    if not manifests:
        raise ValueError("filter.input_manifests is required")
    return manifests


def _load_rows(manifest_paths: List[Path]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for manifest_path in manifest_paths:
        rows.extend(read_jsonl(manifest_path))
    return rows


def _normalize_row(row: Dict[str, Any], *, row_index: int, base_dir: Path) -> Dict[str, Any]:
    image_raw = str(row.get("image_path", row.get("imagepath", row.get("path", "")))).strip()
    if not image_raw:
        raise ValueError(f"row {row_index} missing image path")
    sample_id = str(row.get("sample_id", "")).strip()
    if not sample_id:
        sample_id = f"row_{row_index:07d}"
    return {
        "sample_id": sample_id,
        "image_path": str(_resolve_path(image_raw, base_dir=base_dir)),
    }


def _resolve_threshold(
    *,
    cli_threshold: float | None,
    threshold_report_path: str,
    filter_cfg: Dict[str, Any],
    config_path: Path,
) -> tuple[float, str]:
    if cli_threshold is not None:
        return float(cli_threshold), "cli.threshold"

    report_text = str(threshold_report_path).strip()
    if report_text:
        report_path = _resolve_path(report_text, base_dir=config_path.parent)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if "best_threshold" not in report:
            raise ValueError(f"best_threshold missing in report: {report_path}")
        return float(report["best_threshold"]), "cli.threshold_report.best_threshold"

    if "siglip2_margin_threshold" in filter_cfg:
        return float(filter_cfg["siglip2_margin_threshold"]), "filter.siglip2_margin_threshold"

    raise ValueError("threshold not provided: pass --threshold or --threshold-report, or set filter.siglip2_margin_threshold")


def _is_dir_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return False
    probe = path / ".write_probe.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _resolve_output_dir(
    *,
    explicit_output_dir: str,
    default_output_dir: Path,
    config: Dict[str, Any],
) -> tuple[Path, str]:
    if str(explicit_output_dir).strip():
        out = Path(explicit_output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        return out, "cli.output_dir"

    if _is_dir_writable(default_output_dir):
        return default_output_dir, "default.filter_dir"

    run_cfg = dict(config.get("run", {}))
    run_id = str(run_cfg.get("run_id", "m1_local_run")).strip() or "m1_local_run"
    fallback = (ROOT / "artifacts" / "tmp" / "filter1" / run_id).resolve()
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, "fallback.artifacts_tmp_filter1"


def _decide_rows(
    *,
    rows: List[Dict[str, Any]],
    threshold: float,
    model: Any,
    processor: Any,
    device: str,
    positive_prompts: List[str],
    negative_prompts: List[str],
    top_k: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    all_prompts = positive_prompts + negative_prompts
    score_rows: List[Dict[str, Any]] = []
    counters = {"accept": 0, "reject": 0}

    for row in rows:
        logits = compute_siglip2_logits_for_image(
            model=model,
            processor=processor,
            image_path=Path(row["image_path"]),
            prompts=all_prompts,
            device=device,
        )
        pos_logits = logits[: len(positive_prompts)]
        neg_logits = logits[len(positive_prompts) :]
        stats = compute_margin(pos_logits, neg_logits, top_k=top_k)
        margin = float(stats["margin"])
        decision = "accept" if margin >= threshold else "reject"
        counters[decision] += 1

        score_rows.append(
            {
                "sample_id": row["sample_id"],
                "image_path": row["image_path"],
                "margin": margin,
                "threshold": threshold,
                "decision": decision,
            }
        )
    return score_rows, counters


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter stage1: apply SigLIP2 margin threshold on input manifests")
    parser.add_argument("--config", required=True, help="Config yaml/json")
    parser.add_argument("--threshold", type=float, default=None, help="Explicit threshold override")
    parser.add_argument("--threshold-report", default="", help="JSON path containing best_threshold")
    parser.add_argument("--top-k", type=int, default=3, help="Top-k for logits aggregation")
    parser.add_argument("--output-dir", default="", help="Optional output dir override")
    args = parser.parse_args()

    if args.top_k <= 0:
        raise ValueError("--top-k must be > 0")

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    run_paths = resolve_filter_and_pipeline_dirs(config)
    run_dir = run_paths["run_dir"]
    filter_dir = run_paths["filter_dir"]
    filter_cfg = dict(config.get("filter", {}))
    clip_cfg = dict(filter_cfg.get("clip", {}))
    compared_prompt = dict(clip_cfg.get("compared_prompt", {}))
    positive_prompts = [str(x).strip() for x in compared_prompt.get("positive", []) if str(x).strip()]
    negative_prompts = [str(x).strip() for x in compared_prompt.get("negative", []) if str(x).strip()]
    if not positive_prompts or not negative_prompts:
        raise ValueError("filter.clip.compared_prompt.positive and negative must be non-empty lists")

    threshold, threshold_source = _resolve_threshold(
        cli_threshold=args.threshold,
        threshold_report_path=args.threshold_report,
        filter_cfg=filter_cfg,
        config_path=config_path,
    )
    manifest_paths = _resolve_input_manifests(filter_cfg, config_path=config_path)
    raw_rows = _load_rows(manifest_paths)
    rows = [_normalize_row(r, row_index=i, base_dir=config_path.parent) for i, r in enumerate(raw_rows)]

    model_id = str(clip_cfg.get("model_id", "google/siglip2-so400m-patch16-naflex")).strip()
    model, processor, device = load_siglip2_runtime(model_id=model_id, device_cfg=str(clip_cfg.get("device", "auto")))

    score_rows, counters = _decide_rows(
        rows=rows,
        threshold=threshold,
        model=model,
        processor=processor,
        device=device,
        positive_prompts=positive_prompts,
        negative_prompts=negative_prompts,
        top_k=int(args.top_k),
    )

    accept_rows = [r for r in score_rows if r.get("decision") == "accept"]
    reject_rows = [r for r in score_rows if r.get("decision") == "reject"]

    default_output_dir = filter_dir
    output_dir, output_dir_source = _resolve_output_dir(
        explicit_output_dir=str(args.output_dir),
        default_output_dir=default_output_dir,
        config=config,
    )
    splits_dir = output_dir / "splits"
    output_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(output_dir / "filter1_scores.jsonl", score_rows)
    write_jsonl(splits_dir / "accept.jsonl", accept_rows)
    write_jsonl(splits_dir / "reject.jsonl", reject_rows)

    report = {
        "stage": "filter1",
        "run_dir": str(run_dir),
        "filter_dir": str(run_paths["filter_dir"]),
        "pipeline_dir": str(run_paths["pipeline_dir"]),
        "pipline_dir": str(run_paths["pipline_dir"]),
        "pipline_dir_available": bool(run_paths.get("pipline_dir_available", True)),
        "model_id": model_id,
        "device": device,
        "top_k": int(args.top_k),
        "threshold": threshold,
        "threshold_source": threshold_source,
        "output_dir_source": output_dir_source,
        "input_manifest_count": len(manifest_paths),
        "input_row_count": len(rows),
        "accept": len(accept_rows),
        "reject": len(reject_rows),
    }
    write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
