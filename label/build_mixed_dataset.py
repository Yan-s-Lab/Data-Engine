#!/usr/bin/env python
"""Build mixed YOLO-pose datasets under a shared real evaluation holdout."""
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


def copy_split(
    src_root: Path,
    dst_root: Path,
    *,
    src_split: str,
    dst_split: str,
    prefix: str | None,
) -> int:
    """Copy images + labels from src split into dst split, prefixing filenames."""
    copied = 0
    for kind in ["images", "labels"]:
        src_dir = src_root / kind / src_split
        dst_dir = dst_root / kind / dst_split
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not src_dir.exists():
            continue
        for f in src_dir.iterdir():
            dst_name = f"{prefix}_{f.name}" if prefix else f.name
            dst = dst_dir / dst_name
            shutil.copy2(f, dst)
            copied += 1
    return copied // 2  # images + labels counted together


def detect_eval_split(dataset_root: Path) -> str:
    for split in ("test", "val"):
        if (dataset_root / "images" / split).exists():
            return split
    raise FileNotFoundError(
        f"shared eval dataset must contain images/test or images/val: {dataset_root}"
    )


def write_dataset_yaml(root: Path, *, val_split: str, test_split: str) -> None:
    import yaml  # type: ignore

    dataset_yaml: Dict[str, Any] = {
        "path": str(root.resolve()),
        "train": "images/train",
        "val": f"images/{val_split}",
        "test": f"images/{test_split}",
        "kpt_shape": COCO_KPT_SHAPE,
        "flip_idx": COCO_FLIP_IDX,
        "names": {0: "person"},
    }
    (root / "dataset.yaml").write_text(
        yaml.dump(dataset_yaml, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge real + synth into mixed YOLO-pose dataset")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    mix_cfg: Dict[str, Any] = config.get("build_mixed", {})

    output_name = str(mix_cfg.get("output_name", "mixed_dataset")).strip() or "mixed_dataset"
    out_dir = run_dir / "label" / output_name

    real_train_root_raw = mix_cfg.get("real_train_dataset", mix_cfg.get("real_dataset"))
    synth_train_root_raw = mix_cfg.get("synth_train_dataset", mix_cfg.get("synth_dataset"))
    shared_eval_root_raw = mix_cfg.get("shared_eval_dataset")

    if real_train_root_raw is None or synth_train_root_raw is None:
        raise ValueError("build_mixed requires real_train_dataset and synth_train_dataset")

    real_train_root = Path(str(real_train_root_raw))
    synth_train_root = Path(str(synth_train_root_raw))

    has_shared_eval = shared_eval_root_raw is not None
    if has_shared_eval:
        shared_eval_root = Path(str(shared_eval_root_raw))
        shared_eval_split = detect_eval_split(shared_eval_root)
        real_train_images = copy_split(
            real_train_root,
            out_dir,
            src_split="train",
            dst_split="train",
            prefix="real",
        )
        synth_train_images = copy_split(
            synth_train_root,
            out_dir,
            src_split="train",
            dst_split="train",
            prefix="synth",
        )
        eval_images = copy_split(
            shared_eval_root,
            out_dir,
            src_split=shared_eval_split,
            dst_split="val",
            prefix=None,
        )
        write_dataset_yaml(out_dir, val_split="val", test_split="val")
        report = {
            "stage": "build_mixed_dataset",
            "real_train_dataset": str(real_train_root),
            "synth_train_dataset": str(synth_train_root),
            "shared_eval_dataset": str(shared_eval_root),
            "shared_eval_split": shared_eval_split,
            "out_dir": str(out_dir),
            "real_train_images": real_train_images,
            "synth_train_images": synth_train_images,
            "eval_images": eval_images,
            "total_train_images": real_train_images + synth_train_images,
        }
        write_json(out_dir / "report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # Legacy compatibility: merge train+val from both datasets into one mixed dataset.
    n_real = n_synth = 0
    for split in ["train", "val"]:
        n_real += copy_split(
            real_train_root,
            out_dir,
            src_split=split,
            dst_split=split,
            prefix="real",
        )
        n_synth += copy_split(
            synth_train_root,
            out_dir,
            src_split=split,
            dst_split=split,
            prefix="synth",
        )

    write_dataset_yaml(out_dir, val_split="val", test_split="val")
    report = {
        "stage": "build_mixed_dataset",
        "real_dataset": str(real_train_root),
        "synth_dataset": str(synth_train_root),
        "out_dir": str(out_dir),
        "real_images": n_real,
        "synth_images": n_synth,
        "total_images": n_real + n_synth,
    }
    write_json(out_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
