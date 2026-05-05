#!/usr/bin/env python
"""Convert COCO keypoint annotation JSON → YOLO-pose dataset layout.

Input:  COCO-format annotations JSON (person_keypoints_*.json)
        Image directory (COCO images)
Output:
    Legacy mode:
      YOLO-pose dataset with images/train, images/val, labels/train, labels/val, dataset.yaml
    Fair-protocol mode:
      real_train_anchor dataset + shared real_test_holdout dataset

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


def resolve_split_count(
    total: int,
    *,
    ratio: float | None = None,
    count: int | None = None,
    ensure_minimum_one: bool = False,
) -> int:
    if ratio is not None and count is not None:
        raise ValueError("specify either ratio or count, not both")
    if count is not None:
        if count < 0 or count > total:
            raise ValueError(f"count must be within [0, {total}], got {count}")
        return count
    if ratio is None:
        return 0
    if ratio < 0.0 or ratio >= 1.0:
        raise ValueError("ratio must be in [0, 1)")
    n_items = int(total * ratio)
    if ensure_minimum_one and ratio > 0.0 and total > 0:
        n_items = max(1, n_items)
    return min(total, n_items)


def split_ids_with_holdout(
    ids: List[int],
    *,
    seed: int,
    anchor_val_ratio: float,
    test_ratio: float | None = None,
    test_count: int | None = None,
) -> Dict[str, List[int]]:
    rng = random.Random(seed)
    shuffled = ids[:]
    rng.shuffle(shuffled)

    n_test = resolve_split_count(
        len(shuffled),
        ratio=test_ratio,
        count=test_count,
        ensure_minimum_one=True,
    )
    test_ids = shuffled[:n_test]
    anchor_pool = shuffled[n_test:]
    train_ids, val_ids = split_ids(anchor_pool, anchor_val_ratio, seed + 1)
    return {
        "train": train_ids,
        "val": val_ids,
        "test": test_ids,
    }


def build_label_lines(meta: Dict[str, Any], anns: List[Dict[str, Any]]) -> List[str]:
    img_w = float(meta["width"])
    img_h = float(meta["height"])
    label_lines: List[str] = []
    for ann in anns:
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
    return label_lines


def write_dataset_yaml(root: Path, *, val_split: str | None, test_split: str | None) -> None:
    import yaml  # type: ignore

    dataset_yaml: Dict[str, Any] = {
        "path": str(root.resolve()),
        "kpt_shape": COCO_KPT_SHAPE,
        "flip_idx": COCO_FLIP_IDX,
        "names": {0: "person"},
    }
    train_dir = root / "images" / "train"
    if train_dir.exists():
        dataset_yaml["train"] = "images/train"
    if val_split is not None:
        dataset_yaml["val"] = f"images/{val_split}"
    if test_split is not None:
        dataset_yaml["test"] = f"images/{test_split}"
    (root / "dataset.yaml").write_text(
        yaml.dump(dataset_yaml, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def materialize_split_dataset(
    *,
    root: Path,
    split_name: str,
    image_ids: List[int],
    images_meta: Dict[int, Dict[str, Any]],
    ann_by_image: Dict[int, List[Dict[str, Any]]],
    images_dir: Path,
) -> int:
    (root / "images" / split_name).mkdir(parents=True, exist_ok=True)
    (root / "labels" / split_name).mkdir(parents=True, exist_ok=True)

    written = 0
    for img_id in image_ids:
        meta = images_meta[img_id]
        img_file = images_dir / meta["file_name"]
        dst_img = root / "images" / split_name / img_file.name
        shutil.copy2(img_file, dst_img)

        label_lines = build_label_lines(meta, ann_by_image[img_id])
        lbl_path = root / "labels" / split_name / f"{img_file.stem}.txt"
        lbl_path.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
        written += 1
    return written


def collect_pose_annotations(
    data: Dict[str, Any],
    *,
    min_keypoints: int,
) -> Tuple[Dict[int, Dict[str, Any]], Dict[int, List[Dict[str, Any]]]]:
    images_meta = {img["id"]: img for img in data["images"]}
    ann_by_image: Dict[int, List[Dict[str, Any]]] = {}
    for ann in data["annotations"]:
        if ann.get("iscrowd", 0):
            continue
        if ann.get("category_id") != 1:
            continue
        kps = ann.get("keypoints", [])
        visible = sum(1 for i in range(2, len(kps), 3) if kps[i] > 0)
        if visible < min_keypoints:
            continue
        ann_by_image.setdefault(ann["image_id"], []).append(ann)
    ann_by_image = {iid: anns for iid, anns in ann_by_image.items() if iid in images_meta}
    return images_meta, ann_by_image


def main() -> None:
    parser = argparse.ArgumentParser(description="COCO keypoints JSON → YOLO-pose dataset")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    prep_cfg: Dict[str, Any] = config.get("coco_to_yolo_pose", {})

    ann_json = Path(str(prep_cfg["annotation_json"]))   # COCO keypoints JSON
    images_dir = Path(str(prep_cfg["images_dir"]))       # COCO images root
    output_name = str(prep_cfg.get("output_name", "real_dataset")).strip() or "real_dataset"
    holdout_output_name = str(
        prep_cfg.get("holdout_output_name", "real_test_holdout")
    ).strip() or "real_test_holdout"
    out_dir = run_dir / "label" / output_name
    val_ratio = float(prep_cfg.get("val_ratio", 0.15))
    anchor_val_ratio = float(prep_cfg.get("anchor_val_ratio", val_ratio))
    test_ratio_raw = prep_cfg.get("test_ratio")
    test_count_raw = prep_cfg.get("test_count")
    test_ratio = float(test_ratio_raw) if test_ratio_raw is not None else None
    test_count = int(test_count_raw) if test_count_raw is not None else None
    seed = int(prep_cfg.get("seed", 42))
    min_keypoints = int(prep_cfg.get("min_keypoints", 5))  # skip crowd/low-quality anns

    data = json.loads(ann_json.read_text(encoding="utf-8"))
    images_meta, ann_by_image = collect_pose_annotations(data, min_keypoints=min_keypoints)

    valid_image_ids = []
    skipped_img = 0
    for img_id in sorted(ann_by_image):
        img_file = images_dir / images_meta[img_id]["file_name"]
        if img_file.exists():
            valid_image_ids.append(img_id)
        else:
            skipped_img += 1

    has_fair_holdout = test_ratio is not None or test_count is not None
    if has_fair_holdout:
        split_map = split_ids_with_holdout(
            valid_image_ids,
            seed=seed,
            anchor_val_ratio=anchor_val_ratio,
            test_ratio=test_ratio,
            test_count=test_count,
        )
        holdout_root = run_dir / "label" / holdout_output_name

        written_train = materialize_split_dataset(
            root=out_dir,
            split_name="train",
            image_ids=split_map["train"],
            images_meta=images_meta,
            ann_by_image=ann_by_image,
            images_dir=images_dir,
        )
        written_val = materialize_split_dataset(
            root=out_dir,
            split_name="val",
            image_ids=split_map["val"],
            images_meta=images_meta,
            ann_by_image=ann_by_image,
            images_dir=images_dir,
        )
        written_test = materialize_split_dataset(
            root=holdout_root,
            split_name="test",
            image_ids=split_map["test"],
            images_meta=images_meta,
            ann_by_image=ann_by_image,
            images_dir=images_dir,
        )

        write_dataset_yaml(out_dir, val_split="val", test_split=None)
        write_dataset_yaml(holdout_root, val_split="test", test_split="test")

        anchor_report = {
            "stage": "coco_to_yolo_pose_train_anchor",
            "annotation_json": str(ann_json),
            "images_dir": str(images_dir),
            "dataset_root": str(out_dir),
            "total_images": len(valid_image_ids),
            "written": written_train + written_val,
            "skipped_missing_image": skipped_img,
            "train_images": written_train,
            "val_images": written_val,
            "test_images": written_test,
            "holdout_dataset_root": str(holdout_root),
        }
        holdout_report = {
            "stage": "coco_to_yolo_pose_holdout",
            "annotation_json": str(ann_json),
            "images_dir": str(images_dir),
            "dataset_root": str(holdout_root),
            "total_images": len(valid_image_ids),
            "written": written_test,
            "skipped_missing_image": skipped_img,
            "train_images": 0,
            "val_images": 0,
            "test_images": written_test,
            "anchor_dataset_root": str(out_dir),
        }
        combined_report = {
            "stage": "coco_to_yolo_pose_fair_split",
            "annotation_json": str(ann_json),
            "images_dir": str(images_dir),
            "total_images": len(valid_image_ids),
            "skipped_missing_image": skipped_img,
            "train_anchor_images": written_train,
            "anchor_val_images": written_val,
            "holdout_test_images": written_test,
            "train_anchor_root": str(out_dir),
            "holdout_root": str(holdout_root),
        }
        write_json(out_dir / "report.json", anchor_report)
        write_json(holdout_root / "report.json", holdout_report)
        write_json(run_dir / "label" / "real_split_report.json", combined_report)
        print(json.dumps(combined_report, ensure_ascii=False, indent=2))
        return

    train_ids, val_ids = split_ids(valid_image_ids, val_ratio, seed)
    written_train = materialize_split_dataset(
        root=out_dir,
        split_name="train",
        image_ids=train_ids,
        images_meta=images_meta,
        ann_by_image=ann_by_image,
        images_dir=images_dir,
    )
    written_val = materialize_split_dataset(
        root=out_dir,
        split_name="val",
        image_ids=val_ids,
        images_meta=images_meta,
        ann_by_image=ann_by_image,
        images_dir=images_dir,
    )
    write_dataset_yaml(out_dir, val_split="val", test_split=None)

    report = {
        "stage": "coco_to_yolo_pose",
        "annotation_json": str(ann_json),
        "images_dir": str(images_dir),
        "dataset_root": str(out_dir),
        "total_images": len(valid_image_ids),
        "written": written_train + written_val,
        "skipped_missing_image": skipped_img,
        "train_images": written_train,
        "val_images": written_val,
    }
    write_json(out_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
