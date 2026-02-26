#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.manifest_io import read_jsonl, write_json
from filter.filter_stages import build_image_embeddings, compute_prompt_margin_scores, compute_prompt_scores


def _summary(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0, "std": 0.0}
    return {
        "count": len(values),
        "min": float(min(values)),
        "max": float(max(values)),
        "avg": float(statistics.mean(values)),
        "std": float(statistics.pstdev(values)),
    }


def _resolve_manifest(config: Dict[str, Any], run_dir: Path, explicit_manifest: str) -> Path:
    if explicit_manifest.strip():
        return Path(explicit_manifest)

    run_manifest = run_dir / "filter" / "manifest_in.jsonl"
    if run_manifest.exists():
        return run_manifest

    filter_cfg = dict(config.get("filter", {}))
    input_manifest = str(filter_cfg.get("input_manifest", "")).strip()
    if input_manifest:
        return Path(input_manifest)
    raise FileNotFoundError("unable to resolve manifest path; pass --manifest explicitly")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose SigLIP2 prompt scoring behavior on a manifest")
    parser.add_argument("--config", required=True, help="Path to filter yaml config")
    parser.add_argument("--manifest", default="", help="Optional manifest jsonl; defaults to run/filter/manifest_in.jsonl")
    parser.add_argument("--focus-sample-id", default="", help="Optional sample_id to highlight")
    parser.add_argument("--output", default="", help="Optional output json path")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    run_cfg = dict(config.get("run", {}))
    run_dir = Path(str(run_cfg.get("artifacts_root", "artifacts"))) / str(run_cfg.get("run_id", "run"))
    filter_cfg = dict(config.get("filter", {}))
    clip_cfg = dict(filter_cfg.get("clip", {}))
    phase1_cfg = dict(filter_cfg.get("phase1_semantic", {}))

    manifest_path = _resolve_manifest(config=config, run_dir=run_dir, explicit_manifest=args.manifest)
    rows = read_jsonl(manifest_path)
    if not rows:
        raise RuntimeError(f"manifest is empty: {manifest_path}")

    model_id = str(clip_cfg.get("model_id", "google/siglip2-base-patch16-224"))
    device = str(clip_cfg.get("device", "auto"))
    prompt_text = str(clip_cfg.get("prompt_text", "")).strip()
    negative_prompts = [str(x).strip() for x in clip_cfg.get("negative_prompts", []) if str(x).strip()]
    prompt_field = str(phase1_cfg.get("prompt_field", "effective_prompt_text"))
    cache_path = run_dir / "filter" / "clip_embed_cache.json"

    image_embeddings, runtime, cache_stats = build_image_embeddings(
        rows=rows,
        model_id=model_id,
        device_cfg=device,
        cache_path=cache_path,
    )
    prompt_sigmoid = compute_prompt_scores(
        rows=rows,
        image_embeddings=image_embeddings,
        runtime=runtime,
        prompt_text=prompt_text,
        prompt_score_mode="siglip_sigmoid",
        prompt_field=prompt_field,
    )
    prompt_cosine = compute_prompt_scores(
        rows=rows,
        image_embeddings=image_embeddings,
        runtime=runtime,
        prompt_text=prompt_text,
        prompt_score_mode="cosine",
        prompt_field=prompt_field,
    )
    margin_cosine = compute_prompt_margin_scores(
        rows=rows,
        image_embeddings=image_embeddings,
        runtime=runtime,
        pos_prompt=prompt_text,
        neg_prompts=negative_prompts,
        prompt_score_mode="cosine",
    )
    margin_sigmoid = compute_prompt_margin_scores(
        rows=rows,
        image_embeddings=image_embeddings,
        runtime=runtime,
        pos_prompt=prompt_text,
        neg_prompts=negative_prompts,
        prompt_score_mode="siglip_sigmoid",
    )

    per_sample: List[Dict[str, Any]] = []
    for row in rows:
        sid = str(row.get("sample_id", ""))
        source = str(row.get("source", ""))
        sigmoid_prob = float(prompt_sigmoid.get(sid, 0.0))
        cosine_mapped = float(prompt_cosine.get(sid, 0.0))
        cosine_raw = (cosine_mapped * 2.0) - 1.0
        mcos = dict(margin_cosine.get(sid, {}))
        msig = dict(margin_sigmoid.get(sid, {}))
        per_sample.append(
            {
                "sample_id": sid,
                "source": source,
                "image_path": str(row.get("image_path", "")),
                "prompt_text_active": str(row.get(prompt_field, "")).strip() or prompt_text,
                "siglip_sigmoid_prob": sigmoid_prob,
                "siglip_logit_pos": float(msig.get("s_prompt_pos", 0.0)),
                "siglip_logit_neg_max": float(msig.get("s_prompt_neg_max", 0.0)),
                "siglip_logit_margin": float(msig.get("s_prompt_margin", 0.0)),
                "siglip_margin_norm": float(msig.get("s_prompt_margin_norm", 0.0)),
                "cosine_mapped_01": cosine_mapped,
                "cosine_raw_neg1_pos1": cosine_raw,
                "cosine_neg_max": float(mcos.get("s_prompt_neg_max", 0.0)),
                "cosine_margin": float(mcos.get("s_prompt_margin", 0.0)),
                "cosine_margin_norm": float(mcos.get("s_prompt_margin_norm", 0.0)),
            }
        )

    def _vals(key: str, src: str | None = None) -> List[float]:
        items = per_sample if src is None else [r for r in per_sample if r["source"] == src]
        return [float(r[key]) for r in items]

    summary = {
        "model_id": model_id,
        "device": runtime.device,
        "manifest_path": str(manifest_path),
        "cache_stats": cache_stats,
        "counts": {
            "total": len(per_sample),
            "real": sum(1 for r in per_sample if r["source"] == "real"),
            "synthetic": sum(1 for r in per_sample if r["source"] == "synthetic"),
        },
        "metrics": {
            "siglip_sigmoid_prob": {
                "all": _summary(_vals("siglip_sigmoid_prob")),
                "synthetic": _summary(_vals("siglip_sigmoid_prob", "synthetic")),
            },
            "siglip_logit_pos": {
                "all": _summary(_vals("siglip_logit_pos")),
                "synthetic": _summary(_vals("siglip_logit_pos", "synthetic")),
            },
            "cosine_raw_neg1_pos1": {
                "all": _summary(_vals("cosine_raw_neg1_pos1")),
                "synthetic": _summary(_vals("cosine_raw_neg1_pos1", "synthetic")),
            },
            "cosine_margin": {
                "all": _summary(_vals("cosine_margin")),
                "synthetic": _summary(_vals("cosine_margin", "synthetic")),
            },
        },
    }

    focus = str(args.focus_sample_id).strip()
    if focus:
        match = next((r for r in per_sample if r["sample_id"] == focus), None)
        summary["focus_sample"] = match if match is not None else {"sample_id": focus, "found": False}

    out_path = Path(args.output) if args.output.strip() else (run_dir / "filter" / "siglip2_prompt_diagnostic.json")
    report = {
        "summary": summary,
        "per_sample": per_sample,
    }
    write_json(out_path, report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote: {out_path}")


if __name__ == "__main__":
    main()
