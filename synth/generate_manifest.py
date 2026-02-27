from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from common.manifest_io import write_json, write_jsonl


def normalize_manifest_cfg(gen_cfg: Dict[str, Any]) -> Dict[str, Any]:
    manifest_cfg = gen_cfg.get("manifest", {})
    if manifest_cfg is None:
        manifest_cfg = {}
    if not isinstance(manifest_cfg, dict):
        raise ValueError("generate.manifest must be a mapping when provided")

    profile = str(manifest_cfg.get("profile", "core")).strip().lower() or "core"
    if profile not in {"compat", "core"}:
        raise ValueError("generate.manifest.profile must be one of: compat, core")

    out = dict(manifest_cfg)
    out["profile"] = profile
    guide_type = str(manifest_cfg.get("guide_type", "prompt")).strip().lower() or "prompt"
    if guide_type not in {"prompt", "image_guided"}:
        raise ValueError("generate.manifest.guide_type must be one of: prompt, image_guided")
    out["guide_type"] = guide_type
    out["write_trace_artifacts"] = bool(manifest_cfg.get("write_trace_artifacts", False))
    out["trace_synth_name"] = (
        str(manifest_cfg.get("trace_synth_name", "synth_trace_manifest.jsonl")).strip()
        or "synth_trace_manifest.jsonl"
    )
    return out


def allow_prompt_only_without_real_manifest(*, backend: str, guide_type: str) -> bool:
    return backend == "comfyui" and guide_type == "prompt"


def build_synth_manifest_rows(
    rows: List[Dict[str, Any]],
    *,
    default_config_ref: str,
    guide_type: str,
    default_prompt_text: str = "",
) -> List[Dict[str, Any]]:
    trace_rows: List[Dict[str, Any]] = []
    for row in rows:
        prompt_text = str(row.get("effective_prompt_text", "")).strip()
        if not prompt_text:
            prompt_text = str(row.get("prompt_text", "")).strip()
        if not prompt_text:
            prompt_text = default_prompt_text

        config_ref = str(row.get("comfy_prompt_graph_source", "")).strip() or default_config_ref
        synthetic_id = str(row.get("sample_id", ""))
        image_path = str(row.get("image_path", ""))

        guide_image_id_raw = row.get("guide_image_id")
        guide_image_id = ""
        if guide_image_id_raw is not None:
            guide_image_id = str(guide_image_id_raw).strip()
        if not guide_image_id:
            legacy_anchor_id = row.get("anchor_real_sample_id")
            if legacy_anchor_id is not None:
                guide_image_id = str(legacy_anchor_id).strip()

        trace: Dict[str, Any] = {
            "synthetic_id": synthetic_id,
            "synthetic_image_name": Path(image_path).name if image_path else "",
            "synthetic_image_path": image_path,
            "width": row.get("width"),
            "height": row.get("height"),
            "prompt_text": prompt_text,
            "seed": row.get("seed"),
            "guide_image_id": guide_image_id,
            "guide_type": guide_type,
            "config_ref": config_ref,
            "synthetic_image_ids": (
                [str(x) for x in row.get("synthetic_image_ids", [])]
                if isinstance(row.get("synthetic_image_ids"), list)
                else [synthetic_id]
            ),
        }
        trace_rows.append(trace)
    return trace_rows


def synthetic_job_count(synth_rows: List[Dict[str, Any]]) -> int:
    synthetic_job_ids = {
        str(row.get("comfy_prompt_id", "")).strip()
        for row in synth_rows
        if str(row.get("comfy_prompt_id", "")).strip()
    }
    return len(synthetic_job_ids) if synthetic_job_ids else len(synth_rows)


def write_generate_outputs(
    *,
    gen_dir: Path,
    synth_rows: List[Dict[str, Any]],
    manifest_cfg: Dict[str, Any],
    config_ref: str,
    prompt_text_fallback: str,
    report: Dict[str, Any],
) -> tuple[Path, Path | None]:
    trace_synth_rows = build_synth_manifest_rows(
        synth_rows,
        default_config_ref=config_ref,
        guide_type=str(manifest_cfg["guide_type"]),
        default_prompt_text=prompt_text_fallback,
    )

    synth_manifest = gen_dir / "synth_manifest.jsonl"
    trace_synth_manifest = gen_dir / str(manifest_cfg["trace_synth_name"])

    profile = str(manifest_cfg["profile"])
    if profile == "compat":
        write_jsonl(synth_manifest, synth_rows)
    else:
        write_jsonl(synth_manifest, trace_synth_rows)

    trace_path: Path | None = None
    report["synth_manifest"] = str(synth_manifest)
    if bool(manifest_cfg["write_trace_artifacts"]):
        write_jsonl(trace_synth_manifest, trace_synth_rows)
        trace_path = trace_synth_manifest
        report["trace_synth_manifest"] = str(trace_synth_manifest)

    write_json(gen_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return synth_manifest, trace_path
