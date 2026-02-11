#!/usr/bin/env python
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="One CLI-first closed-loop round skeleton")
    parser.add_argument("--workflow", type=Path, required=True, help="ComfyUI workflow JSON")
    parser.add_argument("--out-dir", type=Path, required=True, help="Synthetic image output dir")
    parser.add_argument("--collection-name", required=True)
    parser.add_argument("--comfy-base-url", default="http://127.0.0.1:8188")
    parser.add_argument("--num-images", type=int, default=5)
    args = parser.parse_args()

    run([
        "python",
        "synth/comfyui_generate.py",
        "--workflow",
        str(args.workflow),
        "--base-url",
        args.comfy_base_url,
        "--out-dir",
        str(args.out_dir),
        "--num-images",
        str(args.num_images),
    ])

    run([
        "python",
        "synth/comfyui_to_collection.py",
        "--images-dir",
        str(args.out_dir),
        "--collection-name",
        args.collection_name,
        "--source-type",
        "manual",
    ])

    print("closed-loop round skeleton done: synth -> ingest")


if __name__ == "__main__":
    main()
