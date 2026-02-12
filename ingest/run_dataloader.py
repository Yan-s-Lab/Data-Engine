#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import write_json, write_jsonl


def collect_images(real_dir: Path, patterns: List[str], max_samples: int) -> List[Path]:
    files: List[Path] = []
    for pattern in patterns:
        files.extend(sorted(real_dir.glob(pattern)))
    if max_samples > 0:
        files = files[:max_samples]
    return files


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.width, img.height


def main() -> None:
    parser = argparse.ArgumentParser(description="DataLoader: normalize real data into manifest")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    loader_cfg = config.get("dataloader", {})

    real_zip = loader_cfg.get("real_zip")
    if real_zip:
        zip_path = Path(str(real_zip))
        if not zip_path.exists():
            raise FileNotFoundError(f"real_zip not found: {zip_path}")
        extracted_dir = run_dir / "dataloader" / "extracted_real"
        extracted_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extracted_dir)
        nested_dir = extracted_dir / zip_path.stem
        real_dir = nested_dir if nested_dir.exists() else extracted_dir
    else:
        real_dir = Path(str(loader_cfg.get("real_dir", "data/raw/collection_1")))

    if not real_dir.exists():
        raise FileNotFoundError(f"real_dir not found: {real_dir}")

    patterns = list(loader_cfg.get("patterns", ["*.png", "*.jpg", "*.jpeg"]))
    max_samples = int(loader_cfg.get("max_samples", 0))
    files = collect_images(real_dir, patterns, max_samples)
    if not files:
        raise RuntimeError(f"no images found under {real_dir} with patterns={patterns}")

    rows: List[Dict[str, Any]] = []
    widths: List[int] = []
    heights: List[int] = []

    for idx, path in enumerate(files):
        width, height = image_size(path)
        widths.append(width)
        heights.append(height)
        sample_id = f"real_{idx:05d}"
        rows.append(
            {
                "sample_id": sample_id,
                "source": "real",
                "image_path": str(path),
                "width": width,
                "height": height,
            }
        )

    loader_dir = run_dir / "dataloader"
    loader_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = loader_dir / "real_manifest.jsonl"
    write_jsonl(manifest_path, rows)

    report = {
        "stage": "dataloader",
        "run_dir": str(run_dir),
        "real_dir": str(real_dir),
        "real_zip": str(real_zip) if real_zip else None,
        "total_real_samples": len(rows),
        "resolution": {
            "mean_width": round(sum(widths) / len(widths), 2),
            "mean_height": round(sum(heights) / len(heights), 2),
            "min_width": min(widths),
            "max_width": max(widths),
            "min_height": min(heights),
            "max_height": max(heights),
        },
        "manifest": str(manifest_path),
    }
    write_json(loader_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
