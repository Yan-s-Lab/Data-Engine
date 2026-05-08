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


def build_siglip2_filter_inputs(*, filter_cfg: Dict[str, Any], config_path: Path) -> List[Dict[str, str]]:
    input_manifest_paths = _collect_input_manifest_paths(filter_cfg=filter_cfg, config_path=config_path)

    rows_out: List[Dict[str, str]] = []

    for manifest_path in input_manifest_paths:
        if not manifest_path.exists():
            raise FileNotFoundError(f"input_manifest not found: {manifest_path}")

        for row_index, row in enumerate(read_jsonl(manifest_path)):
            image_path = str(row.get("synthetic_image_path", "")).strip() or str(row.get("image_path", "")).strip()
            if not image_path:
                raise ValueError(f"missing image path in manifest row: {manifest_path}")
            sample_id = str(row.get("sample_id", "")).strip()
            if not sample_id:
                sample_id = f"row_{row_index:07d}"

            rows_out.append(
                {
                    "sample_id": sample_id,
                    "image_path": str(_resolve_path(image_path, base_dir=manifest_path.parent)),
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
