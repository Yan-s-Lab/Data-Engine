#!/usr/bin/env python
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import sys
import time
import uuid
from typing import Any, Dict, List
from urllib.parse import urlencode, urlparse, urlunparse

from PIL import Image, ImageEnhance, ImageOps
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import read_jsonl, write_json, write_jsonl


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
    sample_start_idx: int,
    max_outputs_per_job: int,
) -> List[Dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
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
            resp = requests.get(
                f"{base_url}/view",
                params={"filename": filename, "subfolder": subfolder, "type": img_type},
                timeout=60,
            )
            resp.raise_for_status()

            suffix = Path(filename).suffix or ".png"
            sample_id = f"synth_{sample_start_idx + output_idx:05d}"
            out_name = f"{sample_id}{suffix}"
            out_path = out_dir / out_name
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
) -> str:
    node_id = str(prompt_cfg.get("node_id", "")).strip()
    if not node_id:
        return ""
    input_key = str(prompt_cfg.get("input_key", "text"))
    text_template = prompt_cfg.get("text_template")
    text = str(prompt_cfg.get("text", ""))
    if text_template is not None:
        if not isinstance(text_template, str):
            raise ValueError("generate.comfyui.prompt.text_template must be a string")
        context: Dict[str, Any] = {
            "sample_index": sample_idx,
            **{k: v for k, v in anchor_row.items() if isinstance(v, (str, int, float, bool))},
        }
        try:
            text = text_template.format(**context)
        except KeyError as exc:
            raise ValueError(
                f"generate.comfyui.prompt.text_template missing field in anchor row: {exc}"
            ) from exc
    workflow.setdefault(node_id, {}).setdefault("inputs", {})[input_key] = text
    return text


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
    wait_mode = str(comfy_cfg.get("wait_mode", "history")).strip().lower()
    ws_fallback_to_history = bool(comfy_cfg.get("ws_fallback_to_history", True))
    seed_node_id = str(comfy_cfg.get("seed_node_id", ""))
    seed_input_key = str(comfy_cfg.get("seed_input_key", "seed"))
    max_outputs_per_job = int(comfy_cfg.get("max_outputs_per_job", 1))
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
    prompt_graph_template, prompt_graph_source = load_prompt_graph(comfy_cfg)
    non_blocking = bool(comfy_cfg.get("non_blocking", False))
    max_inflight = int(comfy_cfg.get("max_inflight", 4))
    if max_inflight <= 0:
        raise ValueError("generate.comfyui.max_inflight must be > 0")

    synth_per_real = int(gen_cfg.get("synth_per_real", 1))
    max_synth = int(gen_cfg.get("max_synth_samples", 0))
    seed_base = int(gen_cfg.get("seed_base", 20260212))

    target_count = len(real_rows) * max(synth_per_real, 0)
    if max_synth > 0:
        target_count = min(target_count, max_synth) if target_count > 0 else max_synth
    if target_count <= 0:
        raise ValueError("target synthetic sample count must be > 0")

    synth_rows: List[Dict[str, Any]] = []
    local_idx = 0
    job_idx = 0
    outputs_per_job = max(max_outputs_per_job, 1)

    def prepare_job(idx: int) -> Dict[str, Any]:
        seed = seed_base + idx
        anchor = real_rows[idx % len(real_rows)]
        workflow = deepcopy(prompt_graph_template)
        set_workflow_seed(workflow, seed_node_id, seed_input_key, seed)
        effective_prompt_text = set_workflow_prompt_text(
            workflow=workflow,
            prompt_cfg=prompt_cfg,
            anchor_row=anchor,
            sample_idx=idx,
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
            "seed": seed,
            "anchor": anchor,
            "effective_prompt_text": effective_prompt_text,
            "effective_anchor_inputs": effective_anchor_inputs,
            "submitted_at": time.time(),
        }

    def append_rows(
        out_rows: List[Dict[str, Any]],
        meta: Dict[str, Any],
        current_local_idx: int,
    ) -> int:
        next_local_idx = current_local_idx
        for row in out_rows:
            if next_local_idx >= target_count:
                break
            row["anchor_real_sample_id"] = meta["anchor"].get("sample_id")
            row["anchor_real_image_path"] = meta["anchor"].get("image_path")
            row["comfy_prompt_id"] = meta["prompt_id"]
            row["seed"] = meta["seed"]
            row["comfy_prompt_graph_source"] = prompt_graph_source
            if meta["effective_prompt_text"]:
                row["effective_prompt_text"] = meta["effective_prompt_text"]
            effective_anchor_inputs = meta["effective_anchor_inputs"]
            if effective_anchor_inputs:
                if len(effective_anchor_inputs) == 1:
                    row["effective_anchor_input"] = next(iter(effective_anchor_inputs.values()))
                row["effective_anchor_inputs"] = effective_anchor_inputs
            synth_rows.append(row)
            next_local_idx += 1
        return next_local_idx

    if non_blocking:
        if wait_mode == "websocket":
            raise ValueError(
                "generate.comfyui.non_blocking=true only supports wait_mode=history"
            )
        inflight: List[Dict[str, Any]] = []
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

            ready_jobs: List[tuple[int, Dict[str, Any], Dict[str, Any]]] = []
            now = time.time()
            for idx, meta in enumerate(inflight):
                if now - float(meta["submitted_at"]) > timeout_sec:
                    raise TimeoutError(
                        f"ComfyUI prompt {meta['prompt_id']} timeout after {timeout_sec}s"
                    )
                history_entry = fetch_history_once(base_url, str(meta["prompt_id"]))
                if history_entry is not None:
                    ready_jobs.append((idx, meta, history_entry))

            if not ready_jobs:
                time.sleep(poll_interval_sec)
                continue

            for idx, meta, history_entry in reversed(ready_jobs):
                out_rows = download_history_outputs(
                    base_url=base_url,
                    history_entry=history_entry,
                    out_dir=img_dir,
                    sample_start_idx=local_idx,
                    max_outputs_per_job=max_outputs_per_job,
                )
                if out_rows:
                    local_idx = append_rows(out_rows, meta, local_idx)
                print(
                    f"[comfyui] prompt_id={meta['prompt_id']} accumulated={len(synth_rows)}/{target_count}"
                )
                inflight.pop(idx)
    else:
        while local_idx < target_count:
            meta = prepare_job(job_idx)
            prompt_id = str(meta["prompt_id"])
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
            out_rows = download_history_outputs(
                base_url=base_url,
                history_entry=history_entry,
                out_dir=img_dir,
                sample_start_idx=local_idx,
                max_outputs_per_job=max_outputs_per_job,
            )
            if out_rows:
                local_idx = append_rows(out_rows, meta, local_idx)
            print(f"[comfyui] prompt_id={prompt_id} accumulated={len(synth_rows)}/{target_count}")
            job_idx += 1

    return synth_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate stage: synthetic expansion from real manifest"
    )
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    gen_cfg = config.get("generate", {})

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
    img_dir.mkdir(parents=True, exist_ok=True)

    if backend == "local_stub":
        synth_rows = generate_with_local_stub(real_rows, gen_cfg, img_dir)
    elif backend == "comfyui":
        synth_rows = generate_with_comfyui(real_rows, gen_cfg, img_dir)
    else:
        raise ValueError(f"unsupported generate.backend: {backend}")

    mixed_rows = [*real_rows, *synth_rows]

    synth_manifest = gen_dir / "synth_manifest.jsonl"
    mixed_manifest = gen_dir / "mixed_manifest.jsonl"
    write_jsonl(synth_manifest, synth_rows)
    write_jsonl(mixed_manifest, mixed_rows)

    report = {
        "stage": "generate",
        "run_dir": str(run_dir),
        "backend": backend,
        "real_manifest": str(real_manifest),
        "synth_manifest": str(synth_manifest),
        "mixed_manifest": str(mixed_manifest),
        "real_count": len(real_rows),
        "synthetic_count": len(synth_rows),
        "mixed_count": len(mixed_rows),
        "synth_per_real": int(gen_cfg.get("synth_per_real", 1)),
    }
    if backend == "comfyui":
        comfy_cfg = gen_cfg.get("comfyui", {})
        if isinstance(comfy_cfg, dict):
            report["non_blocking"] = bool(comfy_cfg.get("non_blocking", False))
            report["max_inflight"] = int(comfy_cfg.get("max_inflight", 4))
    write_json(gen_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
