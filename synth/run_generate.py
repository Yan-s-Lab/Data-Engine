#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
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
from common.manifest_io import read_json, read_jsonl, write_json, write_jsonl


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


def set_workflow_seed(
    workflow: Dict[str, Any], seed_node_id: str, seed_input_key: str, seed: int
) -> None:
    if not seed_node_id:
        return
    workflow.setdefault(seed_node_id, {}).setdefault("inputs", {})[seed_input_key] = seed


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
    workflow_path = Path(str(comfy_cfg.get("workflow", "")))
    if not workflow_path.exists():
        raise FileNotFoundError(
            "generate.backend=comfyui requires generate.comfyui.workflow to exist"
        )

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

    while local_idx < target_count:
        seed = seed_base + job_idx
        workflow = read_json(workflow_path)
        set_workflow_seed(workflow, seed_node_id, seed_input_key, seed)
        prompt_id = submit_prompt(
            base_url=base_url,
            workflow=workflow,
            client_id=client_id,
            extra_data=extra_data,
        )
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
        if not out_rows:
            job_idx += 1
            continue

        for row in out_rows:
            if local_idx >= target_count:
                break
            anchor = real_rows[local_idx % len(real_rows)]
            row["anchor_real_sample_id"] = anchor.get("sample_id")
            row["comfy_prompt_id"] = prompt_id
            row["seed"] = seed
            synth_rows.append(row)
            local_idx += 1
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
    write_json(gen_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
