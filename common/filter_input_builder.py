from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from common.config_io import load_config
from common.manifest_io import read_jsonl, write_jsonl


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _resolve_path(raw_path: str, *, base_dir: Path) -> Path:
    path = Path(str(raw_path).strip())
    if path.is_absolute():
        return path

    preferred = (base_dir / path).resolve()
    workspace = (WORKSPACE_ROOT / path).resolve()

    if preferred.exists():
        return preferred
    if workspace.exists():
        return workspace
    return preferred


def _collect_input_manifest_paths(*, filter_cfg: Dict[str, Any], config_path: Path) -> List[Path]:
    raw = filter_cfg.get("input_manifests", [])
    paths: List[Path] = []

    if isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text:
                paths.append(_resolve_path(text, base_dir=config_path.parent))
    elif isinstance(raw, str) and raw.strip():
        paths.append(_resolve_path(raw.strip(), base_dir=config_path.parent))

    if not paths:
        raise ValueError("filter.input_manifests must be configured for siglip2 input builder")
    return paths


def _build_anchor_image_index(*, filter_cfg: Dict[str, Any], config_path: Path) -> Dict[str, str]:
    anchor_manifest = str(filter_cfg.get("anchor_real_manifest", "")).strip()
    if not anchor_manifest:
        return {}

    anchor_path = _resolve_path(anchor_manifest, base_dir=config_path.parent)
    if not anchor_path.exists():
        raise FileNotFoundError(f"anchor_real_manifest not found: {anchor_path}")

    index: Dict[str, str] = {}
    for row in read_jsonl(anchor_path):
        sample_id = str(row.get("sample_id", "")).strip()
        image_path = str(row.get("image_path", "")).strip()
        if not sample_id or not image_path:
            continue
        index[sample_id] = str(_resolve_path(image_path, base_dir=anchor_path.parent))
    return index


def _normalize_generative_type(row: Dict[str, Any]) -> str:
    guide_type = str(row.get("guide_type", "")).strip().lower()
    if guide_type in {"prompt", "image_guided"}:
        return guide_type

    guide_id = str(row.get("guide_image_id", "")).strip()
    if guide_id:
        return "image_guided"
    return "prompt"


def build_siglip2_filter_inputs(*, filter_cfg: Dict[str, Any], config_path: Path) -> List[Dict[str, str]]:
    input_manifest_paths = _collect_input_manifest_paths(filter_cfg=filter_cfg, config_path=config_path)
    anchor_image_index = _build_anchor_image_index(filter_cfg=filter_cfg, config_path=config_path)

    rows_out: List[Dict[str, str]] = []

    for manifest_path in input_manifest_paths:
        if not manifest_path.exists():
            raise FileNotFoundError(f"input_manifest not found: {manifest_path}")

        for row in read_jsonl(manifest_path):
            image_path = str(row.get("synthetic_image_path", "")).strip() or str(row.get("image_path", "")).strip()
            if not image_path:
                raise ValueError(f"missing image path in manifest row: {manifest_path}")

            generative_type = _normalize_generative_type(row)
            guided_prompt = str(row.get("prompt_text", "")).strip()
            guided_image = ""

            if generative_type == "image_guided":
                guide_id = str(row.get("guide_image_id", "")).strip() or str(row.get("anchor_real_sample_id", "")).strip()
                if guide_id and guide_id in anchor_image_index:
                    guided_image = anchor_image_index[guide_id]
                else:
                    guide_path = str(row.get("anchor_real_image_path", "")).strip() or str(row.get("guide_image_path", "")).strip()
                    if guide_path:
                        guided_image = str(_resolve_path(guide_path, base_dir=manifest_path.parent))

            rows_out.append(
                {
                    "image_path": str(_resolve_path(image_path, base_dir=manifest_path.parent)),
                    "generative_type": generative_type,
                    "guided_image": guided_image,
                    "guided_prompt": guided_prompt,
                }
            )

    return rows_out


def build_siglip2_filter_inputs_from_config(config_path: Path) -> List[Dict[str, str]]:
    config = load_config(config_path)
    filter_cfg = config.get("filter", {})
    if not isinstance(filter_cfg, dict):
        raise ValueError("filter config must be a dict")
    return build_siglip2_filter_inputs(filter_cfg=filter_cfg, config_path=config_path)


def resolve_siglip2_input_output_path(
    *,
    config: Dict[str, Any],
    config_path: Path,
    output_path: Path | None = None,
) -> Path:
    if output_path is not None:
        return output_path if output_path.is_absolute() else _resolve_path(str(output_path), base_dir=config_path.parent)

    filter_cfg = config.get("filter", {})
    if not isinstance(filter_cfg, dict):
        raise ValueError("filter config must be a dict")

    configured_output = str(filter_cfg.get("siglip2_input_manifest_output", "")).strip()
    if configured_output:
        return _resolve_path(configured_output, base_dir=config_path.parent)

    run_cfg = config.get("run", {})
    run_id = str(run_cfg.get("run_id", "m1_local_run")).strip() or "m1_local_run"
    artifacts_root = _resolve_path(str(run_cfg.get("artifacts_root", "artifacts/runs")), base_dir=config_path.parent)
    return (artifacts_root / run_id / "filter" / "siglip2_input_manifest.jsonl").resolve()


def save_siglip2_filter_inputs_from_config(
    config_path: Path,
    *,
    output_path: Path | None = None,
) -> Path:
    config = load_config(config_path)
    rows = build_siglip2_filter_inputs_from_config(config_path)
    out_path = resolve_siglip2_input_output_path(config=config, config_path=config_path, output_path=output_path)
    write_jsonl(out_path, rows)
    return out_path
