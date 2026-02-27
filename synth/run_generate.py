#!/usr/bin/env python
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import random
import string
import sys
import time
import uuid
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode, urlparse, urlunparse

from PIL import Image, ImageEnhance, ImageOps
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import read_jsonl, write_json, write_jsonl


def _normalize_manifest_cfg(gen_cfg: Dict[str, Any]) -> Dict[str, Any]:
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
    out["trace_synth_name"] = str(manifest_cfg.get("trace_synth_name", "synth_trace_manifest.jsonl")).strip() or "synth_trace_manifest.jsonl"
    return out


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

        trace: Dict[str, Any] = {
            "synthetic_id": synthetic_id,
            "synthetic_image_name": Path(image_path).name if image_path else "",
            "synthetic_image_path": image_path,
            "width": row.get("width"),
            "height": row.get("height"),
            "prompt_text": prompt_text,
            "seed": row.get("seed"),
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


def synthesize_image(src_path: Path, out_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    with Image.open(src_path) as img:
        out = img.convert("RGB")
        if rng.random() > 0.5:
            out = ImageOps.mirror(out)
        angle = rng.uniform(-8.0, 8.0)
        out = out.rotate(angle)
        brightness = 0.85 + rng.random() * 0.4
        out = ImageEnhance.Brightness(out).enhance(brightness)
        out.save(out_path)


def image_size(path: Path) -> Tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def submit_prompt(
    base_url: str,
    workflow: Dict[str, Any],
    client_id: str,
    extra_data: Dict[str, Any] | None = None,
) -> str:
    payload: Dict[str, Any] = {"prompt": workflow, "client_id": client_id}
    if extra_data:
        payload["extra_data"] = extra_data
    resp = requests.post(f"{base_url}/prompt", json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return str(data["prompt_id"])


def upload_input_image(
    base_url: str,
    image_path: Path,
    overwrite: bool = True,
    subfolder: str = "",
) -> str:
    with image_path.open("rb") as f:
        files = {"image": (image_path.name, f, "application/octet-stream")}
        data = {"type": "input", "overwrite": str(bool(overwrite)).lower()}
        if subfolder:
            data["subfolder"] = subfolder
        resp = requests.post(f"{base_url}/upload/image", files=files, data=data, timeout=120)
    resp.raise_for_status()
    body = resp.json()
    name = body.get("name")
    if not name:
        raise RuntimeError("ComfyUI /upload/image returned payload without `name`")
    return str(name)


def wait_history(
    base_url: str, prompt_id: str, timeout_sec: int = 300, poll_interval_sec: float = 1.0
) -> Dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = requests.get(f"{base_url}/history/{prompt_id}", timeout=30)
        resp.raise_for_status()
        history = resp.json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(poll_interval_sec)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} timeout after {timeout_sec}s")


def fetch_history_once(base_url: str, prompt_id: str) -> Dict[str, Any] | None:
    resp = requests.get(f"{base_url}/history/{prompt_id}", timeout=30)
    resp.raise_for_status()
    history = resp.json()
    if prompt_id in history:
        return history[prompt_id]
    return None


def to_ws_url(base_url: str, client_id: str) -> str:
    p = urlparse(base_url)
    scheme = "wss" if p.scheme == "https" else "ws"
    query = urlencode({"clientId": client_id})
    path = p.path.rstrip("/") + "/ws"
    return urlunparse((scheme, p.netloc, path, "", query, ""))


def wait_websocket_executing_done(
    base_url: str,
    client_id: str,
    prompt_id: str,
    timeout_sec: int = 300,
) -> None:
    try:
        from websockets.sync.client import connect  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "websocket wait mode requires `websockets` package with sync client support"
        ) from exc

    ws_url = to_ws_url(base_url, client_id)
    deadline = time.time() + timeout_sec
    with connect(ws_url, open_timeout=15, close_timeout=3) as ws:
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"ComfyUI websocket wait timeout for prompt_id={prompt_id}"
                )
            message = ws.recv(timeout=remaining)
            if isinstance(message, bytes):
                continue
            msg = json.loads(message)
            if msg.get("type") != "executing":
                continue
            data = msg.get("data", {})
            if data.get("node") is None and str(data.get("prompt_id")) == prompt_id:
                return


def download_history_outputs(
    base_url: str,
    history_entry: Dict[str, Any],
    out_dir: Path,
    max_outputs_per_job: int,
    persist_outputs: bool,
    comfy_output_dir: Path,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    outputs = history_entry.get("outputs", {})
    output_idx = 0

    for node_id, node_out in outputs.items():
        images = node_out.get("images", [])
        for image in images:
            if max_outputs_per_job > 0 and output_idx >= max_outputs_per_job:
                return rows
            filename = str(image["filename"])
            subfolder = str(image.get("subfolder", ""))
            img_type = str(image.get("type", "output"))
            sample_id = Path(filename).stem
            out_path = comfy_output_dir / subfolder / filename if subfolder else comfy_output_dir / filename

            if persist_outputs:
                out_dir.mkdir(parents=True, exist_ok=True)
                resp = requests.get(
                    f"{base_url}/view",
                    params={"filename": filename, "subfolder": subfolder, "type": img_type},
                    timeout=60,
                )
                resp.raise_for_status()
                out_path = out_dir / filename
                out_path.write_bytes(resp.content)
            elif not out_path.exists():
                # Fallback: if output dir mapping is unavailable, keep pipeline usable by downloading.
                out_dir.mkdir(parents=True, exist_ok=True)
                resp = requests.get(
                    f"{base_url}/view",
                    params={"filename": filename, "subfolder": subfolder, "type": img_type},
                    timeout=60,
                )
                resp.raise_for_status()
                out_path = out_dir / filename
                out_path.write_bytes(resp.content)

            rows.append(
                {
                    "sample_id": sample_id,
                    "image_path": str(out_path),
                    "source": "synthetic",
                    "generation_backend": "comfyui",
                    "comfy_node_id": str(node_id),
                    "comfy_filename": filename,
                    "comfy_subfolder": subfolder,
                    "comfy_type": img_type,
                }
            )
            output_idx += 1
    return rows


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


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _simple_context(src: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in src.items() if isinstance(v, (str, int, float, bool))}


def _inject_anchor_name_context(context: Dict[str, Any], anchor_row: Dict[str, Any]) -> None:
    raw_image_path = str(anchor_row.get("original_image_path", "")).strip()
    norm_image_path = str(anchor_row.get("image_path", "")).strip()
    preferred_image_path = raw_image_path or norm_image_path

    if preferred_image_path:
        preferred_path = Path(preferred_image_path)
        context["anchor_image_name"] = preferred_path.name
        context["anchor_image_stem"] = preferred_path.stem

    if raw_image_path:
        raw_path = Path(raw_image_path)
        context["anchor_image_name_raw"] = raw_path.name
        context["anchor_image_stem_raw"] = raw_path.stem

    if norm_image_path:
        norm_path = Path(norm_image_path)
        context["anchor_image_name_norm"] = norm_path.name
        context["anchor_image_stem_norm"] = norm_path.stem


def set_workflow_filename_prefix(
    workflow: Dict[str, Any],
    filename_prefix_cfg: Dict[str, Any],
    anchor_row: Dict[str, Any],
    sample_idx: int,
    seed: int,
) -> str:
    node_id = str(filename_prefix_cfg.get("node_id", "")).strip()
    if not node_id:
        return ""
    input_key = str(filename_prefix_cfg.get("input_key", "filename_prefix")).strip() or "filename_prefix"
    value = str(filename_prefix_cfg.get("value", "")).strip()
    template = filename_prefix_cfg.get("template")
    dataloader_config_path = str(filename_prefix_cfg.get("dataloader_config", "")).strip()

    context: Dict[str, Any] = {"sample_index": sample_idx, "seed": seed, **_simple_context(anchor_row)}
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
        width, height = image_size(image_path)
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


def generate_with_local_stub(
    real_rows: List[Dict[str, Any]], gen_cfg: Dict[str, Any], img_dir: Path
) -> List[Dict[str, Any]]:
    synth_per_real = int(gen_cfg.get("synth_per_real", 1))
    max_synth = int(gen_cfg.get("max_synth_samples", 0))
    seed_base = int(gen_cfg.get("seed_base", 20260212))
    synth_rows: List[Dict[str, Any]] = []
    synth_idx = 0

    for real_idx, row in enumerate(real_rows):
        src = Path(str(row.get("image_path", "")))
        if not src.exists():
            continue
        for k in range(synth_per_real):
            if max_synth > 0 and synth_idx >= max_synth:
                break
            sample_id = f"synth_{synth_idx:05d}"
            out_path = img_dir / f"{sample_id}.png"
            synthesize_image(src, out_path, seed_base + real_idx * 100 + k)
            synth_rows.append(
                {
                    "sample_id": sample_id,
                    "source": "synthetic",
                    "generation_backend": "local_stub",
                    "image_path": str(out_path),
                    "anchor_real_sample_id": row.get("sample_id"),
                }
            )
            synth_idx += 1
        if max_synth > 0 and synth_idx >= max_synth:
            break
    return synth_rows


def generate_with_comfyui(
    real_rows: List[Dict[str, Any]], gen_cfg: Dict[str, Any], img_dir: Path
) -> List[Dict[str, Any]]:
    comfy_cfg = gen_cfg.get("comfyui", {})
    if not isinstance(comfy_cfg, dict):
        raise ValueError("generate.comfyui must be a mapping")

    base_url = str(comfy_cfg.get("base_url", "http://127.0.0.1:8188")).rstrip("/")
    timeout_sec = int(comfy_cfg.get("timeout_sec", 300))
    poll_interval_sec = float(comfy_cfg.get("poll_interval_sec", 1.0))
    timeout_policy = str(comfy_cfg.get("on_timeout", "fail")).strip().lower()
    timeout_retries = int(comfy_cfg.get("timeout_retries", 0))
    if timeout_policy not in {"fail", "skip", "retry"}:
        raise ValueError("generate.comfyui.on_timeout must be one of: fail, skip, retry")
    if timeout_retries < 0:
        raise ValueError("generate.comfyui.timeout_retries must be >= 0")
    wait_mode = str(comfy_cfg.get("wait_mode", "history")).strip().lower()
    ws_fallback_to_history = bool(comfy_cfg.get("ws_fallback_to_history", True))
    seed_node_id = str(comfy_cfg.get("seed_node_id", ""))
    seed_input_key = str(comfy_cfg.get("seed_input_key", "seed"))
    max_outputs_per_job = int(comfy_cfg.get("max_outputs_per_job", 1))
    persist_outputs = bool(comfy_cfg.get("persist_outputs", False))
    comfy_output_dir = Path(str(comfy_cfg.get("output_dir", "data/comfyui/output")).strip() or "data/comfyui/output")
    client_id = str(comfy_cfg.get("client_id", "")).strip() or str(uuid.uuid4())
    extra_data = comfy_cfg.get("extra_data", {})
    if extra_data is None:
        extra_data = {}
    if not isinstance(extra_data, dict):
        raise ValueError("generate.comfyui.extra_data must be a dict when provided")
    prompt_cfg = comfy_cfg.get("prompt", {})
    if prompt_cfg is None:
        prompt_cfg = {}
    if not isinstance(prompt_cfg, dict):
        raise ValueError("generate.comfyui.prompt must be a dict when provided")
    anchor_cfgs = normalize_anchor_configs(comfy_cfg)
    eligible_real_rows, anchor_filter_stats = filter_anchor_rows_by_size(
        real_rows=real_rows,
        comfy_cfg=comfy_cfg,
        anchor_cfgs=anchor_cfgs,
    )
    if not eligible_real_rows:
        raise RuntimeError("all real anchors were skipped by generate.comfyui.anchor_filter")
    filename_prefix_cfg = comfy_cfg.get("filename_prefix", {})
    if filename_prefix_cfg is None:
        filename_prefix_cfg = {}
    if not isinstance(filename_prefix_cfg, dict):
        raise ValueError("generate.comfyui.filename_prefix must be a dict when provided")
    prompt_graph_template, prompt_graph_source = load_prompt_graph(comfy_cfg)
    non_blocking = bool(comfy_cfg.get("non_blocking", False))
    max_inflight = int(comfy_cfg.get("max_inflight", 4))
    if max_inflight <= 0:
        raise ValueError("generate.comfyui.max_inflight must be > 0")

    synth_per_real = int(gen_cfg.get("synth_per_real", 1))
    max_synth = int(gen_cfg.get("max_synth_samples", 0))
    seed_base = int(gen_cfg.get("seed_base", 20260212))

    target_count = len(eligible_real_rows) * max(synth_per_real, 0)
    if max_synth > 0:
        target_count = min(target_count, max_synth) if target_count > 0 else max_synth
    if target_count <= 0:
        raise ValueError("target synthetic sample count must be > 0")

    synth_rows: List[Dict[str, Any]] = []
    timeout_stats = {
        "timeout_count": 0,
        "timeout_retry_count": 0,
        "timeout_skip_count": 0,
    }
    local_idx = 0
    job_idx = 0
    outputs_per_job = max(max_outputs_per_job, 1)

    def prepare_job(idx: int, retry_count: int = 0) -> Dict[str, Any]:
        seed = seed_base + idx
        anchor = eligible_real_rows[idx % len(eligible_real_rows)]
        workflow = deepcopy(prompt_graph_template)
        set_workflow_seed(workflow, seed_node_id, seed_input_key, seed)
        effective_prompt_text = set_workflow_prompt_text(
            workflow=workflow,
            prompt_cfg=prompt_cfg,
            anchor_row=anchor,
            sample_idx=idx,
            seed=seed,
        )
        effective_filename_prefix = set_workflow_filename_prefix(
            workflow=workflow,
            filename_prefix_cfg=filename_prefix_cfg,
            anchor_row=anchor,
            sample_idx=idx,
            seed=seed,
        )
        effective_anchor_inputs = apply_anchor_images(
            workflow=workflow,
            anchor_cfgs=anchor_cfgs,
            anchor_row=anchor,
            base_url=base_url,
        )
        prompt_id = submit_prompt(
            base_url=base_url,
            workflow=workflow,
            client_id=client_id,
            extra_data=extra_data,
        )
        return {
            "prompt_id": prompt_id,
            "logical_idx": idx,
            "retry_count": retry_count,
            "seed": seed,
            "anchor": anchor,
            "effective_prompt_text": effective_prompt_text,
            "effective_filename_prefix": effective_filename_prefix,
            "effective_anchor_inputs": effective_anchor_inputs,
            "submitted_at": time.time(),
        }

    def append_rows(
        out_rows: List[Dict[str, Any]],
        meta: Dict[str, Any],
        current_local_idx: int,
    ) -> int:
        next_local_idx = current_local_idx
        job_image_ids = [str(item.get("sample_id", "")).strip() for item in out_rows if str(item.get("sample_id", "")).strip()]
        for row in out_rows:
            if next_local_idx >= target_count:
                break
            row["anchor_real_sample_id"] = meta["anchor"].get("sample_id")
            row["comfy_prompt_id"] = meta["prompt_id"]
            row["seed"] = meta["seed"]
            row["comfy_prompt_graph_source"] = prompt_graph_source
            row["synthetic_image_ids"] = job_image_ids
            if meta["effective_prompt_text"]:
                row["effective_prompt_text"] = meta["effective_prompt_text"]
                row["prompt_text"] = meta["effective_prompt_text"]
            if meta["effective_filename_prefix"]:
                row["effective_filename_prefix"] = meta["effective_filename_prefix"]
            effective_anchor_inputs = meta["effective_anchor_inputs"]
            if effective_anchor_inputs:
                if len(effective_anchor_inputs) == 1:
                    row["effective_anchor_input"] = next(iter(effective_anchor_inputs.values()))
                row["effective_anchor_inputs"] = effective_anchor_inputs
            synth_rows.append(row)
            next_local_idx += 1
        return next_local_idx

    if non_blocking:
        use_ws_events = wait_mode == "websocket"
        ws = None
        if use_ws_events:
            try:
                from websockets.sync.client import connect  # type: ignore

                ws = connect(
                    to_ws_url(base_url, client_id),
                    open_timeout=15,
                    close_timeout=3,
                )
                print("[comfyui] websocket event stream connected for non-blocking mode")
            except Exception:
                if ws_fallback_to_history:
                    use_ws_events = False
                    ws = None
                    print("[comfyui] websocket unavailable, fallback to history polling")
                else:
                    raise
        inflight: List[Dict[str, Any]] = []
        try:
            while local_idx < target_count:
                remaining = target_count - local_idx
                required_inflight = min(max_inflight, math.ceil(remaining / outputs_per_job))
                while len(inflight) < required_inflight:
                    meta = prepare_job(job_idx)
                    inflight.append(meta)
                    print(
                        f"[comfyui] submitted prompt_id={meta['prompt_id']} inflight={len(inflight)}"
                    )
                    job_idx += 1

                if not inflight:
                    raise RuntimeError(
                        "non-blocking generation cannot continue: no inflight jobs and target not reached"
                    )

                ready_prompt_ids: set[str] = set()
                if use_ws_events and ws is not None:
                    try:
                        message = ws.recv(timeout=poll_interval_sec)
                        if isinstance(message, str):
                            msg = json.loads(message)
                            if msg.get("type") == "executing":
                                data = msg.get("data", {})
                                pid = str(data.get("prompt_id", ""))
                                if data.get("node") is None and pid:
                                    ready_prompt_ids.add(pid)
                    except TimeoutError:
                        pass
                    except Exception:
                        if ws_fallback_to_history:
                            use_ws_events = False
                            print("[comfyui] websocket disconnected, fallback to history polling")
                        else:
                            raise

                ready_jobs: List[tuple[int, Dict[str, Any], Dict[str, Any]]] = []
                timeout_jobs: List[tuple[int, Dict[str, Any]]] = []
                now = time.time()
                for idx, meta in enumerate(inflight):
                    if now - float(meta["submitted_at"]) > timeout_sec:
                        timeout_jobs.append((idx, meta))
                        continue

                    prompt_id = str(meta["prompt_id"])
                    if use_ws_events and prompt_id not in ready_prompt_ids:
                        continue

                    history_entry = fetch_history_once(base_url, prompt_id)
                    if history_entry is not None:
                        ready_jobs.append((idx, meta, history_entry))

                if timeout_jobs:
                    timeout_stats["timeout_count"] += len(timeout_jobs)
                    for idx, meta in reversed(timeout_jobs):
                        logical_idx = int(meta["logical_idx"])
                        retry_count = int(meta["retry_count"])
                        if timeout_policy == "retry" and retry_count < timeout_retries:
                            retry_meta = prepare_job(logical_idx, retry_count=retry_count + 1)
                            inflight[idx] = retry_meta
                            timeout_stats["timeout_retry_count"] += 1
                            print(
                                f"[comfyui] timeout prompt_id={meta['prompt_id']} retry={retry_count + 1}/{timeout_retries} resubmitted={retry_meta['prompt_id']}"
                            )
                        elif timeout_policy == "skip":
                            inflight.pop(idx)
                            timeout_stats["timeout_skip_count"] += 1
                            print(
                                f"[comfyui] timeout prompt_id={meta['prompt_id']} skipped"
                            )
                        else:
                            raise TimeoutError(
                                f"ComfyUI prompt {meta['prompt_id']} timeout after {timeout_sec}s"
                            )

                if not ready_jobs:
                    if not use_ws_events:
                        time.sleep(poll_interval_sec)
                    continue

                for idx, meta, history_entry in reversed(ready_jobs):
                    out_rows = download_history_outputs(
                        base_url=base_url,
                        history_entry=history_entry,
                        out_dir=img_dir,
                        max_outputs_per_job=max_outputs_per_job,
                        persist_outputs=persist_outputs,
                        comfy_output_dir=comfy_output_dir,
                    )
                    if out_rows:
                        local_idx = append_rows(out_rows, meta, local_idx)
                    print(
                        f"[comfyui] prompt_id={meta['prompt_id']} accumulated={len(synth_rows)}/{target_count}"
                    )
                    inflight.pop(idx)
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass
    else:
        while local_idx < target_count:
            meta = prepare_job(job_idx)
            prompt_id = str(meta["prompt_id"])
            try:
                if wait_mode == "websocket":
                    try:
                        wait_websocket_executing_done(
                            base_url=base_url,
                            client_id=client_id,
                            prompt_id=prompt_id,
                            timeout_sec=timeout_sec,
                        )
                    except Exception:
                        if not ws_fallback_to_history:
                            raise
                history_entry = wait_history(
                    base_url=base_url,
                    prompt_id=prompt_id,
                    timeout_sec=timeout_sec,
                    poll_interval_sec=poll_interval_sec,
                )
            except TimeoutError:
                timeout_stats["timeout_count"] += 1
                retry_count = int(meta["retry_count"])
                if timeout_policy == "retry" and retry_count < timeout_retries:
                    timeout_stats["timeout_retry_count"] += 1
                    print(
                        f"[comfyui] timeout prompt_id={prompt_id} retry={retry_count + 1}/{timeout_retries}"
                    )
                    retry_meta = prepare_job(int(meta["logical_idx"]), retry_count=retry_count + 1)
                    meta = retry_meta
                    prompt_id = str(meta["prompt_id"])
                    history_entry = wait_history(
                        base_url=base_url,
                        prompt_id=prompt_id,
                        timeout_sec=timeout_sec,
                        poll_interval_sec=poll_interval_sec,
                    )
                elif timeout_policy == "skip":
                    timeout_stats["timeout_skip_count"] += 1
                    print(f"[comfyui] timeout prompt_id={prompt_id} skipped")
                    job_idx += 1
                    continue
                else:
                    raise
            out_rows = download_history_outputs(
                base_url=base_url,
                history_entry=history_entry,
                out_dir=img_dir,
                max_outputs_per_job=max_outputs_per_job,
                persist_outputs=persist_outputs,
                comfy_output_dir=comfy_output_dir,
            )
            if out_rows:
                local_idx = append_rows(out_rows, meta, local_idx)
            print(f"[comfyui] prompt_id={prompt_id} accumulated={len(synth_rows)}/{target_count}")
            job_idx += 1

    gen_cfg["_timeout_stats"] = timeout_stats
    gen_cfg["_anchor_filter_stats"] = anchor_filter_stats

    return synth_rows


def enrich_synth_rows_with_dimensions(
    synth_rows: List[Dict[str, Any]], real_rows: List[Dict[str, Any]]
) -> Dict[str, int]:
    real_dim_map: Dict[str, tuple[int, int]] = {}
    for row in real_rows:
        sample_id = str(row.get("sample_id", "")).strip()
        width = row.get("width")
        height = row.get("height")
        if sample_id and isinstance(width, int) and isinstance(height, int):
            real_dim_map[sample_id] = (width, height)

    counted = 0
    matched = 0
    mismatched = 0

    for row in synth_rows:
        image_path = Path(str(row.get("image_path", "")).strip())
        if image_path.exists():
            width, height = image_size(image_path)
            row["width"] = width
            row["height"] = height
        else:
            width = row.get("width")
            height = row.get("height")

        anchor_id = str(row.get("anchor_real_sample_id", "")).strip()
        if not anchor_id:
            continue
        anchor_dim = real_dim_map.get(anchor_id)
        if anchor_dim is None:
            continue
        anchor_w, anchor_h = anchor_dim
        row["anchor_width"] = anchor_w
        row["anchor_height"] = anchor_h
        if isinstance(width, int) and isinstance(height, int):
            row["size_match_anchor"] = bool(width == anchor_w and height == anchor_h)
            counted += 1
            if row["size_match_anchor"]:
                matched += 1
            else:
                mismatched += 1

    return {
        "size_checked_count": counted,
        "size_match_count": matched,
        "size_mismatch_count": mismatched,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate stage: synthetic expansion from real manifest"
    )
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    gen_cfg = config.get("generate", {})
    manifest_cfg = _normalize_manifest_cfg(gen_cfg if isinstance(gen_cfg, dict) else {})

    real_manifest = Path(
        str(gen_cfg.get("real_manifest", run_dir / "dataloader" / "real_manifest.jsonl"))
    )
    if not real_manifest.exists():
        raise FileNotFoundError(f"missing real manifest: {real_manifest}")

    real_rows = read_jsonl(real_manifest)
    if not real_rows:
        raise RuntimeError(f"empty real manifest: {real_manifest}")
    backend = str(gen_cfg.get("backend", "local_stub"))

    gen_dir = run_dir / "generate"
    img_dir = gen_dir / "images"
    gen_dir.mkdir(parents=True, exist_ok=True)

    if backend == "local_stub":
        img_dir.mkdir(parents=True, exist_ok=True)
        synth_rows = generate_with_local_stub(real_rows, gen_cfg, img_dir)
    elif backend == "comfyui":
        synth_rows = generate_with_comfyui(real_rows, gen_cfg, img_dir)
    else:
        raise ValueError(f"unsupported generate.backend: {backend}")

    size_stats = enrich_synth_rows_with_dimensions(synth_rows, real_rows)

    prompt_text_fallback = ""
    comfy_cfg = gen_cfg.get("comfyui", {})
    if isinstance(comfy_cfg, dict):
        prompt_cfg = comfy_cfg.get("prompt", {})
        if isinstance(prompt_cfg, dict):
            prompt_text_fallback = str(prompt_cfg.get("text", "")).strip()
    trace_synth_rows = build_synth_manifest_rows(
        synth_rows,
        default_config_ref=str(Path(args.config).resolve()),
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

    if bool(manifest_cfg["write_trace_artifacts"]):
        write_jsonl(trace_synth_manifest, trace_synth_rows)

    report = {
        "stage": "generate",
        "run_dir": str(run_dir),
        "backend": backend,
        "real_manifest": str(real_manifest),
        "synth_manifest": str(synth_manifest),
        "real_count": len(real_rows),
        "synthetic_count": len(synth_rows),
        "synth_per_real": int(gen_cfg.get("synth_per_real", 1)),
        "manifest_profile": profile,
        "manifest_guide_type": str(manifest_cfg["guide_type"]),
        **size_stats,
    }
    if bool(manifest_cfg["write_trace_artifacts"]):
        report["trace_synth_manifest"] = str(trace_synth_manifest)
    if backend == "comfyui":
        comfy_cfg = gen_cfg.get("comfyui", {})
        if isinstance(comfy_cfg, dict):
            report["non_blocking"] = bool(comfy_cfg.get("non_blocking", False))
            report["max_inflight"] = int(comfy_cfg.get("max_inflight", 4))
            report["on_timeout"] = str(comfy_cfg.get("on_timeout", "fail"))
            report["timeout_retries"] = int(comfy_cfg.get("timeout_retries", 0))
    timeout_stats = gen_cfg.get("_timeout_stats", {})
    if isinstance(timeout_stats, dict):
        report.update(timeout_stats)
    anchor_filter_stats = gen_cfg.get("_anchor_filter_stats", {})
    if isinstance(anchor_filter_stats, dict):
        report.update(anchor_filter_stats)
    write_json(gen_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
