#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.manifest_io import read_json, write_jsonl


def submit_prompt(base_url: str, workflow: Dict[str, Any]) -> str:
    resp = requests.post(f"{base_url}/prompt", json={"prompt": workflow}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["prompt_id"]


def wait_history(base_url: str, prompt_id: str, timeout_sec: int = 300) -> Dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = requests.get(f"{base_url}/history/{prompt_id}", timeout=30)
        resp.raise_for_status()
        history = resp.json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(1)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} timeout after {timeout_sec}s")


def save_outputs(base_url: str, out_dir: Path, history_entry: Dict[str, Any], seed: int) -> List[Dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []

    outputs = history_entry.get("outputs", {})
    for node_id, node_out in outputs.items():
        images = node_out.get("images", [])
        for idx, image in enumerate(images):
            filename = image["filename"]
            subfolder = image.get("subfolder", "")
            img_type = image.get("type", "output")
            resp = requests.get(
                f"{base_url}/view",
                params={"filename": filename, "subfolder": subfolder, "type": img_type},
                timeout=60,
            )
            resp.raise_for_status()

            local_name = f"seed_{seed}_n{node_id}_{idx}_{filename}"
            path = out_dir / local_name
            path.write_bytes(resp.content)

            rows.append(
                {
                    "file_name": local_name,
                    "seed": seed,
                    "source": "comfyui",
                    "node_id": str(node_id),
                    "comfy_filename": filename,
                    "comfy_subfolder": subfolder,
                    "comfy_type": img_type,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate images via ComfyUI HTTP API")
    parser.add_argument("--workflow", type=Path, required=True, help="ComfyUI workflow JSON file")
    parser.add_argument("--base-url", default="http://127.0.0.1:8188", help="ComfyUI base URL")
    parser.add_argument("--out-dir", type=Path, required=True, help="Image output directory")
    parser.add_argument("--num-images", type=int, default=1, help="How many jobs")
    parser.add_argument("--seed-start", type=int, default=1, help="Base seed")
    parser.add_argument(
        "--seed-node-id",
        default="",
        help="Optional workflow node id whose inputs.seed will be updated",
    )
    parser.add_argument(
        "--seed-input-key",
        default="seed",
        help="Seed field key under inputs, default seed",
    )
    args = parser.parse_args()

    all_rows: List[Dict[str, Any]] = []

    for i in range(args.num_images):
        seed = args.seed_start + i
        workflow = read_json(args.workflow)

        if args.seed_node_id:
            workflow.setdefault(args.seed_node_id, {}).setdefault("inputs", {})[args.seed_input_key] = seed

        prompt_id = submit_prompt(args.base_url, workflow)
        history_entry = wait_history(args.base_url, prompt_id)
        rows = save_outputs(args.base_url, args.out_dir, history_entry, seed)
        all_rows.extend(rows)
        print(f"[{i + 1}/{args.num_images}] prompt_id={prompt_id} outputs={len(rows)}")

    manifest_path = args.out_dir / "manifest.jsonl"
    write_jsonl(manifest_path, all_rows)
    print(f"saved manifest: {manifest_path}")


if __name__ == "__main__":
    main()
