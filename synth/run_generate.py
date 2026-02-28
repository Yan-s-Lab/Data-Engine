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
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import read_jsonl
from synth.comfyui_client import (
    download_history_outputs,
    fetch_history_once,
    submit_prompt,
    to_ws_url,
    wait_history,
    wait_websocket_executing_done,
)
from synth.comfyui_workflow import (
    apply_anchor_images,
    filter_anchor_rows_by_size,
    load_prompt_graph,
    normalize_anchor_configs,
    set_workflow_batch_size,
    set_workflow_filename_prefix,
    set_workflow_prompt_text,
    set_workflow_seed,
)
from synth.generate_manifest import (
    allow_prompt_only_without_real_manifest as _allow_prompt_only_without_real_manifest,
    build_synth_manifest_rows,
    normalize_manifest_cfg as _normalize_manifest_cfg,
    synthetic_job_count,
    write_generate_outputs,
)


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
                    "guide_image_id": row.get("sample_id"),
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
    batch_size_cfg = comfy_cfg.get("batch_size", {})
    if batch_size_cfg is None:
        batch_size_cfg = {}
    if not isinstance(batch_size_cfg, dict):
        raise ValueError("generate.comfyui.batch_size must be a dict when provided")
    batch_size_node_id = str(batch_size_cfg.get("node_id", "")).strip()
    configured_batch_size = 1
    if batch_size_node_id:
        raw_batch_size = batch_size_cfg.get("value", None)
        if raw_batch_size is None:
            raise ValueError(
                "generate.comfyui.batch_size.value is required when batch_size.node_id is set"
            )
        configured_batch_size = int(raw_batch_size)
        if configured_batch_size <= 0:
            raise ValueError("generate.comfyui.batch_size.value must be > 0")
    persist_outputs = bool(comfy_cfg.get("persist_outputs", False))
    comfy_output_dir = Path(
        str(comfy_cfg.get("output_dir", "data/comfyui/output")).strip() or "data/comfyui/output"
    )
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
    if real_rows:
        eligible_real_rows, anchor_filter_stats = filter_anchor_rows_by_size(
            real_rows=real_rows,
            comfy_cfg=comfy_cfg,
            anchor_cfgs=anchor_cfgs,
        )
        if not eligible_real_rows:
            raise RuntimeError("all real anchors were skipped by generate.comfyui.anchor_filter")
    else:
        if anchor_cfgs:
            raise RuntimeError(
                "generate.comfyui.anchor_image/anchor_images requires non-empty real_manifest"
            )
        eligible_real_rows = [{}]
        anchor_filter_stats = {
            "anchor_filter_enabled": False,
            "anchor_total_count": 0,
            "anchor_eligible_count": 0,
            "anchor_skipped_count": 0,
            "anchor_filter_max_width": 0,
            "anchor_filter_max_height": 0,
            "anchor_filter_max_long_edge": 0,
            "prompt_only_no_real_manifest": True,
        }

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
    run_id = str(gen_cfg.get("_run_id", "")).strip()

    virtual_anchor_mode = (not real_rows) and (len(anchor_cfgs) == 0)
    if virtual_anchor_mode:
        target_count = max_synth if max_synth > 0 else max(synth_per_real, 1)
    else:
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
    outputs_per_job = max(configured_batch_size, 1)

    def prepare_job(idx: int, retry_count: int = 0) -> Dict[str, Any]:
        seed = seed_base + idx
        anchor = eligible_real_rows[idx % len(eligible_real_rows)]
        workflow = deepcopy(prompt_graph_template)
        set_workflow_seed(workflow, seed_node_id, seed_input_key, seed)
        set_workflow_batch_size(workflow, batch_size_cfg)
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
            run_id=run_id,
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
        job_image_ids = [
            str(item.get("sample_id", "")).strip()
            for item in out_rows
            if str(item.get("sample_id", "")).strip()
        ]
        for row in out_rows:
            if next_local_idx >= target_count:
                break
            anchor_sample_id = meta["anchor"].get("sample_id")
            row["guide_image_id"] = str(anchor_sample_id).strip() if anchor_sample_id is not None else ""
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
                            print(f"[comfyui] timeout prompt_id={meta['prompt_id']} skipped")
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

        anchor_id = str(row.get("guide_image_id", "")).strip()
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
    if isinstance(gen_cfg, dict):
        run_cfg = config.get("run", {})
        if isinstance(run_cfg, dict):
            gen_cfg["_run_id"] = str(run_cfg.get("run_id", "")).strip()
    manifest_cfg = _normalize_manifest_cfg(gen_cfg if isinstance(gen_cfg, dict) else {})

    backend = str(gen_cfg.get("backend", "local_stub"))
    real_manifest = Path(
        str(gen_cfg.get("real_manifest", run_dir / "dataloader" / "real_manifest.jsonl"))
    )
    allow_empty_real_manifest = _allow_prompt_only_without_real_manifest(
        backend=backend,
        guide_type=str(manifest_cfg["guide_type"]),
    )
    real_rows: List[Dict[str, Any]] = []
    if real_manifest.exists():
        real_rows = read_jsonl(real_manifest)
        if not real_rows and not allow_empty_real_manifest:
            raise RuntimeError(f"empty real manifest: {real_manifest}")
    elif not allow_empty_real_manifest:
        raise FileNotFoundError(f"missing real manifest: {real_manifest}")
    else:
        print(
            f"[generate] prompt-only mode without real_manifest enabled: {real_manifest}"
        )

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

    report = {
        "stage": "generate",
        "run_dir": str(run_dir),
        "backend": backend,
        "real_manifest": str(real_manifest) if real_manifest.exists() else "",
        "real_count": len(real_rows),
        "synthetic_count": len(synth_rows),
        "synthetic_job_count": synthetic_job_count(synth_rows),
        "synth_per_real": int(gen_cfg.get("synth_per_real", 1)),
        "manifest_profile": str(manifest_cfg["profile"]),
        "manifest_guide_type": str(manifest_cfg["guide_type"]),
        **size_stats,
    }
    if backend == "comfyui":
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

    write_generate_outputs(
        gen_dir=gen_dir,
        synth_rows=synth_rows,
        manifest_cfg=manifest_cfg,
        config_ref=str(Path(args.config).resolve()),
        prompt_text_fallback=prompt_text_fallback,
        report=report,
    )


if __name__ == "__main__":
    main()
