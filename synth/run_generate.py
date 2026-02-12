#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, List

from PIL import Image, ImageEnhance, ImageOps

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate stage: local synthetic expansion from real manifest"
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

    synth_per_real = int(gen_cfg.get("synth_per_real", 1))
    max_synth = int(gen_cfg.get("max_synth_samples", 0))
    seed_base = int(gen_cfg.get("seed_base", 20260212))

    gen_dir = run_dir / "generate"
    img_dir = gen_dir / "images"
    gen_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

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
            out_name = f"{sample_id}.png"
            out_path = img_dir / out_name
            synthesize_image(src, out_path, seed_base + real_idx * 100 + k)
            synth_rows.append(
                {
                    "sample_id": sample_id,
                    "source": "synthetic",
                    "image_path": str(out_path),
                    "anchor_real_sample_id": row.get("sample_id"),
                }
            )
            synth_idx += 1
        if max_synth > 0 and synth_idx >= max_synth:
            break

    mixed_rows = [*real_rows, *synth_rows]

    synth_manifest = gen_dir / "synth_manifest.jsonl"
    mixed_manifest = gen_dir / "mixed_manifest.jsonl"
    write_jsonl(synth_manifest, synth_rows)
    write_jsonl(mixed_manifest, mixed_rows)

    report = {
        "stage": "generate",
        "run_dir": str(run_dir),
        "real_manifest": str(real_manifest),
        "synth_manifest": str(synth_manifest),
        "mixed_manifest": str(mixed_manifest),
        "real_count": len(real_rows),
        "synthetic_count": len(synth_rows),
        "mixed_count": len(mixed_rows),
        "synth_per_real": synth_per_real,
    }
    write_json(gen_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
