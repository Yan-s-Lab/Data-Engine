#!/usr/bin/env python
"""Merge real_dataset + ai_dataset into mixed_dataset for Condition C training."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import write_json

COCO_FLIP_IDX = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
COCO_KPT_SHAPE = [17, 3]


def copy_split(src_root: Path, dst_root: Path, split: str, prefix: str) -> int:
    """Copy images + labels from src split into dst split, prefixing filenames."""
    copied = 0
    for kind in ["images", "labels"]:
        src_dir = src_root / kind / split
        dst_dir = dst_root / kind / split
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not src_dir.exists():
            continue
        for f in src_dir.iterdir():
            dst = dst_dir / f"{prefix}_{f.name}"
            shutil.copy2(f, dst)
            copied += 1
    return copied // 2  # images + labels counted together


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge real + synth into mixed YOLO-pose dataset")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    mix_cfg: Dict[str, Any] = config.get("build_mixed", {})

    real_root = Path(str(mix_cfg["real_dataset"]))    # real_dataset/ root
    synth_root = Path(str(mix_cfg["synth_dataset"]))  # ai_dataset/ root
    out_dir = run_dir / "label" / "mixed_dataset"

    n_real = n_synth = 0
    for split in ["train", "val"]:
        n_real += copy_split(real_root, out_dir, split, prefix="real")
        n_synth += copy_split(synth_root, out_dir, split, prefix="synth")

    import yaml  # type: ignore
    dataset_yaml: Dict[str, Any] = {
        "path": str(out_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "kpt_shape": COCO_KPT_SHAPE,
        "flip_idx": COCO_FLIP_IDX,
        "names": {0: "person"},
    }
    (out_dir / "dataset.yaml").write_text(
        yaml.dump(dataset_yaml, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    report = {
        "stage": "build_mixed_dataset",
        "real_dataset": str(real_root),
        "synth_dataset": str(synth_root),
        "out_dir": str(out_dir),
        "real_images": n_real,
        "synth_images": n_synth,
        "total_images": n_real + n_synth,
    }
    write_json(out_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
