#!/usr/bin/env python
"""Convert COCO keypoint annotation JSON → YOLO-pose dataset layout.

Input:  COCO-format annotations JSON (person_keypoints_*.json)
        Image directory (COCO images)
Output: YOLO-pose dataset with images/train, images/val, labels/train, labels/val, dataset.yaml

Usage:
    python label/build_coco_yolo_pose.py --config configs/.../train/body_pose_real_only_prep.yaml
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import write_json

COCO_FLIP_IDX = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
COCO_KPT_SHAPE = [17, 3]


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def split_ids(ids: List[int], val_ratio: float, seed: int) -> Tuple[List[int], List[int]]:
    rng = random.Random(seed)
    shuffled = ids[:]
    rng.shuffle(shuffled)
    n_val = max(1, int(len(shuffled) * val_ratio)) if shuffled else 0
    return shuffled[n_val:], shuffled[:n_val]


def main() -> None:
    parser = argparse.ArgumentParser(description="COCO keypoints JSON → YOLO-pose dataset")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    prep_cfg: Dict[str, Any] = config.get("coco_to_yolo_pose", {})

    ann_json = Path(str(prep_cfg["annotation_json"]))   # COCO keypoints JSON
    images_dir = Path(str(prep_cfg["images_dir"]))       # COCO images root
    out_dir = run_dir / "label" / "real_dataset"
    val_ratio = float(prep_cfg.get("val_ratio", 0.15))
    seed = int(prep_cfg.get("seed", 42))
    min_keypoints = int(prep_cfg.get("min_keypoints", 5))  # skip crowd/low-quality anns

    for split in ["train", "val"]:
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    data = json.loads(ann_json.read_text(encoding="utf-8"))
    images_meta = {img["id"]: img for img in data["images"]}

    # group annotations by image_id, skip crowd
    ann_by_image: Dict[int, List[Dict]] = {}
    for ann in data["annotations"]:
        if ann.get("iscrowd", 0):
            continue
        if ann.get("category_id") != 1:  # person
            continue
        kps = ann.get("keypoints", [])
        visible = sum(1 for i in range(2, len(kps), 3) if kps[i] > 0)
        if visible < min_keypoints:
            continue
        ann_by_image.setdefault(ann["image_id"], []).append(ann)

    valid_image_ids = [iid for iid in ann_by_image if iid in images_meta]
    train_ids, val_ids = split_ids(valid_image_ids, val_ratio, seed)
    val_set = set(val_ids)

    written = 0
    skipped_img = 0
    for img_id in valid_image_ids:
        meta = images_meta[img_id]
        img_file = images_dir / meta["file_name"]
        if not img_file.exists():
            skipped_img += 1
            continue

        split = "val" if img_id in val_set else "train"
        dst_img = out_dir / "images" / split / img_file.name
        shutil.copy2(img_file, dst_img)

        img_w = float(meta["width"])
        img_h = float(meta["height"])
        label_lines: List[str] = []

        for ann in ann_by_image[img_id]:
            bbox = ann["bbox"]  # [x, y, w, h] absolute
            cx = clamp01((bbox[0] + bbox[2] / 2) / img_w)
            cy = clamp01((bbox[1] + bbox[3] / 2) / img_h)
            bw = clamp01(bbox[2] / img_w)
            bh = clamp01(bbox[3] / img_h)

            kps = ann["keypoints"]  # [x, y, v, x, y, v, ...] × 17
            parts = [f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"]
            for k in range(17):
                kx = clamp01(float(kps[k * 3]) / img_w)
                ky = clamp01(float(kps[k * 3 + 1]) / img_h)
                kv = int(kps[k * 3 + 2])  # 0/1/2 from COCO
                parts.append(f"{kx:.6f} {ky:.6f} {kv}")
            label_lines.append(" ".join(parts))

        lbl_path = out_dir / "labels" / split / f"{img_file.stem}.txt"
        lbl_path.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
        written += 1

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
        "stage": "coco_to_yolo_pose",
        "annotation_json": str(ann_json),
        "images_dir": str(images_dir),
        "dataset_root": str(out_dir),
        "total_images": len(valid_image_ids),
        "written": written,
        "skipped_missing_image": skipped_img,
        "train_images": len(train_ids),
        "val_images": len(val_ids),
    }
    write_json(out_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
