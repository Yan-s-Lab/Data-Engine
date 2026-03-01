from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from common.config_io import load_config
from common.manifest_io import read_jsonl
from filter.manifest_builder import build_input_manifest_from_config


ROOT = Path(__file__).resolve().parents[2]


def build_stub_manifest(total_count: int, real_ratio: float) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    real_count = int(total_count * real_ratio)
    synth_count = total_count - real_count
    for i in range(real_count):
        sample_id = f"real_{i:04d}"
        rows.append({"sample_id": sample_id, "source": "real", "image_path": f"data/real/{sample_id}.jpg"})
    for i in range(synth_count):
        sample_id = f"synth_{i:04d}"
        rows.append({"sample_id": sample_id, "source": "synthetic", "image_path": f"data/synth/{sample_id}.jpg"})
    return rows


def resolve_path_with_workspace_fallback(raw_path: str, *, base_dir: Path) -> Path:
    p = Path(str(raw_path).strip())
    if p.is_absolute():
        return p
    preferred = (base_dir / p).resolve()
    workspace = (ROOT / p).resolve()
    if preferred.exists():
        return preferred
    if workspace.exists():
        return workspace
    return preferred


def resolve_filter_prompt_text(filter_cfg: Dict[str, Any], *, config_path: Path) -> str:
    clip_cfg = filter_cfg.get("clip")
    if not isinstance(clip_cfg, dict):
        return ""

    prompt_text = str(clip_cfg.get("prompt_text", "")).strip()
    if prompt_text:
        return "clip.prompt_text"

    template_file = str(clip_cfg.get("prompt_template_file", "")).strip()
    if template_file:
        path = resolve_path_with_workspace_fallback(template_file, base_dir=config_path.parent)
        clip_cfg["prompt_text"] = path.read_text(encoding="utf-8").strip()
        return "clip.prompt_template_file"

    generate_cfg_path = str(clip_cfg.get("prompt_from_generate_config", "")).strip()
    if not generate_cfg_path:
        return ""

    gen_path = resolve_path_with_workspace_fallback(generate_cfg_path, base_dir=config_path.parent)
    gen_cfg = load_config(gen_path)
    prompt_cfg = gen_cfg.get("generate", {}).get("comfyui", {}).get("prompt", {})
    if not isinstance(prompt_cfg, dict):
        return ""

    gen_template_file = str(prompt_cfg.get("template_file", "")).strip()
    if gen_template_file:
        p = resolve_path_with_workspace_fallback(gen_template_file, base_dir=gen_path.parent)
        clip_cfg["prompt_text"] = p.read_text(encoding="utf-8").strip()
        return "clip.prompt_from_generate_config.template_file"

    gen_text_template = prompt_cfg.get("text_template")
    if isinstance(gen_text_template, str) and gen_text_template.strip():
        clip_cfg["prompt_text"] = gen_text_template.strip()
        return "clip.prompt_from_generate_config.text_template"

    gen_text = str(prompt_cfg.get("text", "")).strip()
    if gen_text:
        clip_cfg["prompt_text"] = gen_text
        return "clip.prompt_from_generate_config.text"
    return ""


def resolve_filter_input_manifest(
    *,
    filter_cfg: Dict[str, Any],
    run_dir: Path,
    config_path: Path | None = None,
) -> tuple[Path | None, str]:
    base_dir = config_path.parent if config_path is not None else ROOT
    input_manifest = filter_cfg.get("input_manifest")
    if input_manifest:
        return resolve_path_with_workspace_fallback(str(input_manifest), base_dir=base_dir), "filter.input_manifest"

    auto_from_generate = bool(
        filter_cfg.get("auto_input_from_generate_synth", filter_cfg.get("auto_input_from_generate_mixed", True))
    )
    if auto_from_generate:
        synth_manifest = run_dir / "generate" / "synth_manifest.jsonl"
        if synth_manifest.exists():
            return synth_manifest, "run_dir/generate/synth_manifest.jsonl"
        mixed_manifest = run_dir / "generate" / "mixed_manifest.jsonl"
        if mixed_manifest.exists():
            return mixed_manifest, "run_dir/generate/mixed_manifest.jsonl"

    return None, ""


def resolve_filter_input_manifests(
    *,
    filter_cfg: Dict[str, Any],
    run_dir: Path,
    config_path: Path | None = None,
) -> tuple[List[Path], str]:
    base_dir = config_path.parent if config_path is not None else ROOT
    raw_many = filter_cfg.get("input_manifests", [])
    manifests: List[Path] = []

    if isinstance(raw_many, list):
        for item in raw_many:
            path_text = str(item).strip()
            if not path_text:
                continue
            manifests.append(resolve_path_with_workspace_fallback(path_text, base_dir=base_dir))
    elif isinstance(raw_many, str) and raw_many.strip():
        manifests.append(resolve_path_with_workspace_fallback(raw_many.strip(), base_dir=base_dir))

    if manifests:
        return manifests, "filter.input_manifests"

    single_path, source = resolve_filter_input_manifest(
        filter_cfg=filter_cfg,
        run_dir=run_dir,
        config_path=config_path,
    )
    if single_path is None:
        return [], source
    return [single_path], source


def normalize_generate_manifest_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        normalized = dict(row)
        if not str(normalized.get("sample_id", "")).strip():
            normalized["sample_id"] = str(normalized.get("synthetic_id", "")).strip()
        if not str(normalized.get("image_path", "")).strip():
            normalized["image_path"] = str(normalized.get("synthetic_image_path", "")).strip()
        if not str(normalized.get("guide_image_id", "")).strip():
            normalized["guide_image_id"] = str(normalized.get("guide_image", "")).strip()
        if not str(normalized.get("guide_image_id", "")).strip():
            normalized["guide_image_id"] = str(normalized.get("anchor_real_sample_id", "")).strip()
        if not str(normalized.get("source", "")).strip():
            normalized["source"] = "synthetic"
        out.append(normalized)
    return out


def is_real_guided_synth(row: Dict[str, Any], phase1_cfg: Dict[str, Any]) -> bool:
    if str(row.get("source", "")) != "synthetic":
        return False
    guide_type = str(row.get("guide_type", "")).strip().lower()
    if guide_type:
        if guide_type == "prompt":
            return False
        if guide_type == "image_guided":
            return bool(str(row.get("guide_image_id", "")).strip())
    marker_fields = [
        str(x)
        for x in phase1_cfg.get(
            "guided_marker_fields",
            [
                "guide_image_id",
                "anchor_real_sample_id",
                "anchor_real_image_path",
                "effective_anchor_input",
                "effective_anchor_inputs",
            ],
        )
    ]
    for field in marker_fields:
        val = row.get(field)
        if isinstance(val, str) and val.strip():
            return True
        if isinstance(val, dict) and val:
            return True
    return False


def resolve_anchor_real_manifest(
    *,
    filter_cfg: Dict[str, Any],
    config_path: Path,
    input_manifest_paths: List[Path],
) -> Tuple[Path | None, str]:
    explicit = str(filter_cfg.get("anchor_real_manifest", "")).strip()
    if explicit:
        return resolve_path_with_workspace_fallback(explicit, base_dir=config_path.parent), "filter.anchor_real_manifest"

    clip_cfg = filter_cfg.get("clip")
    if isinstance(clip_cfg, dict):
        from_gen_cfg = str(clip_cfg.get("prompt_from_generate_config", "")).strip()
        if from_gen_cfg and bool(filter_cfg.get("auto_anchor_real_manifest_from_generate_config", True)):
            gen_cfg_path = resolve_path_with_workspace_fallback(from_gen_cfg, base_dir=config_path.parent)
            if gen_cfg_path.exists():
                gen_cfg = load_config(gen_cfg_path)
                gen_real_manifest = str(gen_cfg.get("generate", {}).get("real_manifest", "")).strip()
                if gen_real_manifest:
                    return (
                        resolve_path_with_workspace_fallback(gen_real_manifest, base_dir=gen_cfg_path.parent),
                        "clip.prompt_from_generate_config.generate.real_manifest",
                    )

    if bool(filter_cfg.get("auto_anchor_real_manifest_from_generate_report", True)):
        for input_manifest_path in input_manifest_paths:
            report_path = input_manifest_path.parent / "report.json"
            if not report_path.exists():
                continue
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                real_manifest = str(report.get("real_manifest", "")).strip()
                if real_manifest:
                    return (
                        resolve_path_with_workspace_fallback(real_manifest, base_dir=report_path.parent),
                        f"input_manifest_sibling_report.real_manifest:{input_manifest_path}",
                    )
            except json.JSONDecodeError:
                continue
    return None, ""


def inject_anchor_real_rows(
    *,
    rows: List[Dict[str, Any]],
    filter_cfg: Dict[str, Any],
    config_path: Path,
    input_manifest_paths: List[Path],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    phase1_cfg = dict(filter_cfg.get("phase1_semantic", {}))
    anchor_sid_fields = [str(x) for x in phase1_cfg.get("anchor_sid_fields", ["guide_image_id", "anchor_real_sample_id"])]
    existing_ids: Set[str] = {str(r.get("sample_id", "")).strip() for r in rows if str(r.get("sample_id", "")).strip()}

    required_anchor_ids: Set[str] = set()
    for row in rows:
        if not is_real_guided_synth(row=row, phase1_cfg=phase1_cfg):
            continue
        for field in anchor_sid_fields:
            anchor_sid = str(row.get(field, "")).strip()
            if anchor_sid:
                required_anchor_ids.add(anchor_sid)
                break

    missing_anchor_ids = sorted(sid for sid in required_anchor_ids if sid not in existing_ids)
    if not missing_anchor_ids:
        return rows, {
            "enabled": True,
            "anchor_sid_fields": anchor_sid_fields,
            "required_anchor_count": len(required_anchor_ids),
            "missing_anchor_count": 0,
            "injected_anchor_count": 0,
            "anchor_manifest_path": "",
            "anchor_manifest_source": "",
            "unresolved_anchor_count": 0,
        }

    anchor_manifest_path, anchor_manifest_source = resolve_anchor_real_manifest(
        filter_cfg=filter_cfg,
        config_path=config_path,
        input_manifest_paths=input_manifest_paths,
    )
    if anchor_manifest_path is None or not anchor_manifest_path.exists():
        return rows, {
            "enabled": True,
            "anchor_sid_fields": anchor_sid_fields,
            "required_anchor_count": len(required_anchor_ids),
            "missing_anchor_count": len(missing_anchor_ids),
            "injected_anchor_count": 0,
            "anchor_manifest_path": str(anchor_manifest_path) if anchor_manifest_path is not None else "",
            "anchor_manifest_source": anchor_manifest_source,
            "unresolved_anchor_count": len(missing_anchor_ids),
            "reason": "anchor_manifest_missing",
        }

    anchor_rows = normalize_generate_manifest_rows(read_jsonl(anchor_manifest_path))
    anchor_index: Dict[str, Dict[str, Any]] = {}
    for row in anchor_rows:
        sid = str(row.get("sample_id", "")).strip()
        if sid:
            normalized_row = dict(row)
            normalized_row["source"] = "real"
            anchor_index[sid] = normalized_row

    injected_rows: List[Dict[str, Any]] = []
    unresolved = 0
    for sid in missing_anchor_ids:
        row = anchor_index.get(sid)
        if row is None:
            unresolved += 1
            continue
        injected_rows.append(row)

    return rows + injected_rows, {
        "enabled": True,
        "anchor_sid_fields": anchor_sid_fields,
        "required_anchor_count": len(required_anchor_ids),
        "missing_anchor_count": len(missing_anchor_ids),
        "injected_anchor_count": len(injected_rows),
        "anchor_manifest_path": str(anchor_manifest_path),
        "anchor_manifest_source": anchor_manifest_source,
        "unresolved_anchor_count": unresolved,
    }


def load_input_rows(
    *,
    filter_cfg: Dict[str, Any],
    run_dir: Path,
    config_path: Path,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    input_manifest_paths, input_manifest_source = resolve_filter_input_manifests(
        filter_cfg=filter_cfg,
        run_dir=run_dir,
        config_path=config_path,
    )
    builder_cfg = dict(filter_cfg.get("manifest_builder", {}))
    builder_enabled = bool(builder_cfg.get("enabled", False))
    builder_force = bool(builder_cfg.get("force_rebuild", False))
    primary_input_manifest_path = input_manifest_paths[0] if input_manifest_paths else None
    missing_input_paths = [p for p in input_manifest_paths if not p.exists()]

    if builder_enabled and (builder_force or (not input_manifest_paths) or missing_input_paths):
        rows = build_input_manifest_from_config(filter_cfg=filter_cfg, input_manifest_path=primary_input_manifest_path)
        if not input_manifest_source:
            input_manifest_source = "filter.manifest_builder"
    elif input_manifest_paths:
        rows = []
        for path in input_manifest_paths:
            rows.extend(read_jsonl(path))
    else:
        rows = build_stub_manifest(
            total_count=int(filter_cfg.get("stub_total_count", 24)),
            real_ratio=float(filter_cfg.get("stub_real_ratio", 0.5)),
        )
        input_manifest_source = "stub_manifest"

    dedupe_by = str(filter_cfg.get("input_merge_dedupe_by", "sample_id")).strip()
    dedupe_keep = str(filter_cfg.get("input_merge_dedupe_keep", "first")).strip().lower()
    if input_manifest_paths and dedupe_by:
        if dedupe_keep not in {"first", "last"}:
            raise ValueError("filter.input_merge_dedupe_keep must be one of: first, last")
        deduped: Dict[str, Dict[str, Any]] = {}
        passthrough: List[Dict[str, Any]] = []
        for row in rows:
            key = str(row.get(dedupe_by, "")).strip()
            if not key:
                passthrough.append(row)
                continue
            if dedupe_keep == "last" or key not in deduped:
                deduped[key] = row
        rows = [*passthrough, *deduped.values()]

    rows = normalize_generate_manifest_rows(rows)
    input_rows_count = len(rows)
    rows, anchor_real_injection = inject_anchor_real_rows(
        rows=rows,
        filter_cfg=filter_cfg,
        config_path=config_path,
        input_manifest_paths=input_manifest_paths,
    )

    state = {
        "input_manifest_paths": [str(p) for p in input_manifest_paths],
        "input_manifest_path": str(primary_input_manifest_path) if primary_input_manifest_path is not None else "",
        "input_manifest_source": input_manifest_source,
        "input_total": input_rows_count,
        "anchor_real_injection": anchor_real_injection,
    }
    return rows, state
