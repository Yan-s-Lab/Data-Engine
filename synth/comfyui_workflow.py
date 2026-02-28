from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import random
import string
from typing import Any, Dict, List, Tuple

from PIL import Image

from common.config_io import load_config
from synth.comfyui_client import upload_input_image


def is_comfy_api_prompt_graph(obj: Any) -> bool:
    if not isinstance(obj, dict) or not obj:
        return False
    for _, node in obj.items():
        if not isinstance(node, dict):
            return False
        if "class_type" not in node:
            return False
        if "inputs" not in node or not isinstance(node.get("inputs"), dict):
            return False
    return True


def is_comfy_ui_workflow(obj: Any) -> bool:
    return isinstance(obj, dict) and "nodes" in obj and "links" in obj and "last_node_id" in obj


def load_prompt_graph(comfy_cfg: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
    inline_graph = comfy_cfg.get("prompt_graph")
    workflow_path_str = str(comfy_cfg.get("workflow", "")).strip()
    if inline_graph is not None and workflow_path_str:
        raise ValueError("generate.comfyui.prompt_graph and generate.comfyui.workflow are mutually exclusive")
    if inline_graph is None and not workflow_path_str:
        raise ValueError("generate.comfyui requires either `workflow` or `prompt_graph`")

    if inline_graph is not None:
        graph = inline_graph
        source = "inline:generate.comfyui.prompt_graph"
    else:
        workflow_path = Path(workflow_path_str)
        if not workflow_path.exists():
            raise FileNotFoundError(
                "generate.backend=comfyui requires generate.comfyui.workflow to exist"
            )
        graph = load_config(workflow_path)
        source = str(workflow_path)

    if is_comfy_ui_workflow(graph):
        raise ValueError(
            "ComfyUI workflow is UI format; /prompt needs API prompt graph format "
            "(node_id -> {class_type, inputs})"
        )
    if not is_comfy_api_prompt_graph(graph):
        raise ValueError(
            "invalid ComfyUI API prompt graph format; expected mapping of node ids to "
            "{class_type, inputs}"
        )
    return deepcopy(graph), source


def set_workflow_seed(
    workflow: Dict[str, Any], seed_node_id: str, seed_input_key: str, seed: int
) -> None:
    if not seed_node_id:
        return
    workflow.setdefault(seed_node_id, {}).setdefault("inputs", {})[seed_input_key] = seed


def set_workflow_batch_size(workflow: Dict[str, Any], batch_size_cfg: Dict[str, Any]) -> int | None:
    node_id = str(batch_size_cfg.get("node_id", "")).strip()
    if not node_id:
        return None
    input_key = str(batch_size_cfg.get("input_key", "batch_size")).strip() or "batch_size"
    raw_value = batch_size_cfg.get("value", None)
    if raw_value is None:
        raise ValueError("generate.comfyui.batch_size.value is required when batch_size.node_id is set")
    try:
        value = int(raw_value)
    except Exception as exc:
        raise ValueError("generate.comfyui.batch_size.value must be an integer") from exc
    if value <= 0:
        raise ValueError("generate.comfyui.batch_size.value must be > 0")
    workflow.setdefault(node_id, {}).setdefault("inputs", {})[input_key] = value
    return value


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def set_workflow_prompt_text(
    workflow: Dict[str, Any],
    prompt_cfg: Dict[str, Any],
    anchor_row: Dict[str, Any],
    sample_idx: int,
    seed: int,
) -> str:
    node_id = str(prompt_cfg.get("node_id", "")).strip()
    if not node_id:
        return ""
    input_key = str(prompt_cfg.get("input_key", "text"))
    text_template = prompt_cfg.get("text_template")
    template_file = str(prompt_cfg.get("template_file", "")).strip()
    if template_file:
        text_template = Path(template_file).read_text(encoding="utf-8").strip()
    text = str(prompt_cfg.get("text", ""))
    render_template = bool(prompt_cfg.get("render_template", True))
    dynamic_vars = prompt_cfg.get("dynamic_vars", {})
    if dynamic_vars is None:
        dynamic_vars = {}
    if not isinstance(dynamic_vars, dict):
        raise ValueError("generate.comfyui.prompt.dynamic_vars must be a mapping when provided")
    dynamic_seed_salt = str(prompt_cfg.get("dynamic_seed_salt", ""))

    dynamic_key = (
        f"{dynamic_seed_salt}|{sample_idx}|{seed}|{anchor_row.get('sample_id', '')}|"
        f"{anchor_row.get('image_path', '')}"
    )
    dynamic_seed = int(hashlib.sha256(dynamic_key.encode("utf-8")).hexdigest(), 16) & 0xFFFFFFFF
    dynamic_rng = random.Random(dynamic_seed)

    resolved_dynamic_vars: Dict[str, str] = {}
    for key, value in dynamic_vars.items():
        if isinstance(value, list):
            if not value:
                raise ValueError(
                    f"generate.comfyui.prompt.dynamic_vars[{key}] list cannot be empty"
                )
            resolved_dynamic_vars[key] = str(dynamic_rng.choice(value))
        else:
            resolved_dynamic_vars[key] = str(value)

    if text_template is not None:
        if not isinstance(text_template, str):
            raise ValueError("generate.comfyui.prompt.text_template must be a string")
        if render_template:
            context: Dict[str, Any] = {
                "sample_index": sample_idx,
                "seed": seed,
                **{k: v for k, v in anchor_row.items() if isinstance(v, (str, int, float, bool))},
                **resolved_dynamic_vars,
            }
            str_context = {k: str(v) for k, v in context.items()}
            step1 = string.Template(text_template).safe_substitute(str_context)
            text = step1.format_map(_SafeFormatDict(str_context))
        else:
            text = text_template
    workflow.setdefault(node_id, {}).setdefault("inputs", {})[input_key] = text
    return text


def _simple_context(src: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in src.items() if isinstance(v, (str, int, float, bool))}


def _inject_anchor_name_context(context: Dict[str, Any], anchor_row: Dict[str, Any]) -> None:
    norm_image_path = str(anchor_row.get("image_path", "")).strip()

    if norm_image_path:
        norm_path = Path(norm_image_path)
        context["anchor_image_name"] = norm_path.name
        context["anchor_image_stem"] = norm_path.stem
        context["anchor_image_name_norm"] = norm_path.name
        context["anchor_image_stem_norm"] = norm_path.stem


def set_workflow_filename_prefix(
    workflow: Dict[str, Any],
    filename_prefix_cfg: Dict[str, Any],
    anchor_row: Dict[str, Any],
    sample_idx: int,
    seed: int,
    run_id: str = "",
) -> str:
    node_id = str(filename_prefix_cfg.get("node_id", "")).strip()
    if not node_id:
        return ""
    input_key = str(filename_prefix_cfg.get("input_key", "filename_prefix")).strip() or "filename_prefix"
    value = str(filename_prefix_cfg.get("value", "")).strip()
    template = filename_prefix_cfg.get("template")
    dataloader_config_path = str(filename_prefix_cfg.get("dataloader_config", "")).strip()

    context: Dict[str, Any] = {
        "run_id": str(run_id).strip(),
        "sample_index": sample_idx,
        "seed": seed,
        **_simple_context(anchor_row),
    }
    _inject_anchor_name_context(context, anchor_row)
    if dataloader_config_path:
        dataloader_cfg = load_config(Path(dataloader_config_path))
        naming_cfg = (
            dataloader_cfg.get("dataloader", {}).get("naming", {})
            if isinstance(dataloader_cfg.get("dataloader", {}), dict)
            else {}
        )
        if isinstance(naming_cfg, dict):
            context.update(_simple_context(naming_cfg))

    if template is not None:
        if not isinstance(template, str):
            raise ValueError("generate.comfyui.filename_prefix.template must be a string")
        str_context = {k: str(v) for k, v in context.items()}
        step1 = string.Template(template).safe_substitute(str_context)
        value = step1.format_map(_SafeFormatDict(str_context))

    if not value:
        services_id = str(context.get("services_id", "")).strip()
        task_name = str(context.get("task_name", "")).strip()
        if services_id and task_name:
            value = f"{services_id}_{task_name}"
        elif task_name:
            value = task_name
        elif services_id:
            value = services_id
        else:
            value = "ComfyUI"

    workflow.setdefault(node_id, {}).setdefault("inputs", {})[input_key] = value
    return value


def set_workflow_anchor_image(
    workflow: Dict[str, Any],
    anchor_cfg: Dict[str, Any],
    anchor_row: Dict[str, Any],
    base_url: str,
) -> str:
    node_id = str(anchor_cfg.get("node_id", "")).strip()
    if not node_id:
        return ""
    input_key = str(anchor_cfg.get("input_key", "image"))
    path_field = str(anchor_cfg.get("path_field", "image_path"))
    image_path_val = str(anchor_row.get(path_field, "")).strip()
    if not image_path_val:
        raise ValueError(
            f"generate.comfyui.anchor_image cannot find `{path_field}` in anchor row {anchor_row.get('sample_id')}"
        )
    image_path = Path(image_path_val)
    if not image_path.exists():
        raise FileNotFoundError(f"anchor image path not found: {image_path}")

    upload = bool(anchor_cfg.get("upload", True))
    if upload:
        upload_overwrite = bool(anchor_cfg.get("upload_overwrite", True))
        upload_subfolder = str(anchor_cfg.get("upload_subfolder", ""))
        value = upload_input_image(
            base_url=base_url,
            image_path=image_path,
            overwrite=upload_overwrite,
            subfolder=upload_subfolder,
        )
    else:
        value = str(image_path)

    workflow.setdefault(node_id, {}).setdefault("inputs", {})[input_key] = value
    return value


def normalize_anchor_configs(comfy_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    cfgs: List[Dict[str, Any]] = []
    single_cfg = comfy_cfg.get("anchor_image", {})
    if single_cfg is None:
        single_cfg = {}
    if not isinstance(single_cfg, dict):
        raise ValueError("generate.comfyui.anchor_image must be a dict when provided")
    if str(single_cfg.get("node_id", "")).strip():
        cfgs.append(single_cfg)

    multi_cfg = comfy_cfg.get("anchor_images", [])
    if multi_cfg is None:
        multi_cfg = []
    if not isinstance(multi_cfg, list):
        raise ValueError("generate.comfyui.anchor_images must be a list when provided")
    for idx, item in enumerate(multi_cfg):
        if not isinstance(item, dict):
            raise ValueError(
                f"generate.comfyui.anchor_images[{idx}] must be a mapping"
            )
        if str(item.get("node_id", "")).strip():
            cfgs.append(item)
    return cfgs


def _anchor_size_filter_thresholds(comfy_cfg: Dict[str, Any]) -> Tuple[int, int, int]:
    anchor_filter = comfy_cfg.get("anchor_filter", {})
    if anchor_filter is None:
        anchor_filter = {}
    if not isinstance(anchor_filter, dict):
        raise ValueError("generate.comfyui.anchor_filter must be a dict when provided")
    max_width = int(anchor_filter.get("max_width", 0))
    max_height = int(anchor_filter.get("max_height", 0))
    max_long_edge = int(anchor_filter.get("max_long_edge", 0))
    if max_width < 0 or max_height < 0 or max_long_edge < 0:
        raise ValueError("generate.comfyui.anchor_filter thresholds must be >= 0")
    return max_width, max_height, max_long_edge


def _image_size(path: Path) -> Tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def filter_anchor_rows_by_size(
    real_rows: List[Dict[str, Any]],
    comfy_cfg: Dict[str, Any],
    anchor_cfgs: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    max_width, max_height, max_long_edge = _anchor_size_filter_thresholds(comfy_cfg)
    enabled = any(v > 0 for v in (max_width, max_height, max_long_edge))
    if not enabled:
        return real_rows, {
            "anchor_filter_enabled": False,
            "anchor_total_count": len(real_rows),
            "anchor_eligible_count": len(real_rows),
            "anchor_skipped_count": 0,
            "anchor_filter_max_width": max_width,
            "anchor_filter_max_height": max_height,
            "anchor_filter_max_long_edge": max_long_edge,
        }

    path_field = "image_path"
    if anchor_cfgs:
        path_field = str(anchor_cfgs[0].get("path_field", "image_path"))

    kept: List[Dict[str, Any]] = []
    skipped_samples: List[Dict[str, Any]] = []
    for row in real_rows:
        sample_id = str(row.get("sample_id", "")).strip()
        image_path_val = str(row.get(path_field, "")).strip()
        if not image_path_val:
            skipped_samples.append(
                {"sample_id": sample_id, "reason": f"missing_path_field:{path_field}"}
            )
            continue
        image_path = Path(image_path_val)
        if not image_path.exists():
            skipped_samples.append(
                {"sample_id": sample_id, "reason": "missing_file", "image_path": str(image_path)}
            )
            continue
        width, height = _image_size(image_path)
        reasons: List[str] = []
        if max_width > 0 and width > max_width:
            reasons.append(f"width>{max_width}")
        if max_height > 0 and height > max_height:
            reasons.append(f"height>{max_height}")
        if max_long_edge > 0 and max(width, height) > max_long_edge:
            reasons.append(f"long_edge>{max_long_edge}")
        if reasons:
            skipped_samples.append(
                {
                    "sample_id": sample_id,
                    "image_path": str(image_path),
                    "width": width,
                    "height": height,
                    "reason": ",".join(reasons),
                }
            )
            continue
        kept.append(row)

    for item in skipped_samples[:10]:
        print(
            "[comfyui] anchor skipped by size filter: "
            f"sample_id={item.get('sample_id', '')} reason={item.get('reason', '')}"
        )

    stats: Dict[str, Any] = {
        "anchor_filter_enabled": True,
        "anchor_total_count": len(real_rows),
        "anchor_eligible_count": len(kept),
        "anchor_skipped_count": len(skipped_samples),
        "anchor_filter_max_width": max_width,
        "anchor_filter_max_height": max_height,
        "anchor_filter_max_long_edge": max_long_edge,
    }
    if skipped_samples:
        stats["anchor_skipped_samples_preview"] = skipped_samples[:10]
    return kept, stats


def apply_anchor_images(
    workflow: Dict[str, Any],
    anchor_cfgs: List[Dict[str, Any]],
    anchor_row: Dict[str, Any],
    base_url: str,
) -> Dict[str, str]:
    effective: Dict[str, str] = {}
    for idx, cfg in enumerate(anchor_cfgs):
        injected = set_workflow_anchor_image(
            workflow=workflow,
            anchor_cfg=cfg,
            anchor_row=anchor_row,
            base_url=base_url,
        )
        if not injected:
            continue
        name = str(cfg.get("name", "")).strip() or f"anchor_{idx}"
        node_id = str(cfg.get("node_id", "")).strip()
        input_key = str(cfg.get("input_key", "image")).strip()
        key = f"{name}:{node_id}.{input_key}"
        effective[key] = injected
    return effective
