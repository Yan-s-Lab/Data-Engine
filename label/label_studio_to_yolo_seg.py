#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import shutil
import sys
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.manifest_io import read_jsonl


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def find_image_path(image_ref: str, images_dir: Path) -> Path | None:
    name = Path(image_ref).name
    candidate = images_dir / name
    if candidate.exists():
        return candidate
    return None


def parse_polygon_results(
    result_items: List[Dict[str, Any]], class_to_id: Dict[str, int]
) -> List[Tuple[int, List[float]]]:
    rows: List[Tuple[int, List[float]]] = []
    for item in result_items:
        if item.get("type") != "polygonlabels":
            continue
        value = item.get("value", {})
        labels = value.get("polygonlabels", [])
        points = value.get("points", [])
        if not labels or not points:
            continue
        label = str(labels[0])
        if label not in class_to_id:
            continue

        seg: List[float] = []
        for point in points:
            if not isinstance(point, list) or len(point) < 2:
                continue
            x = clamp01(float(point[0]) / 100.0)
            y = clamp01(float(point[1]) / 100.0)
            seg.extend([x, y])
        if len(seg) >= 6:
            rows.append((class_to_id[label], seg))
    return rows


def split_ids(ids: List[str], val_ratio: float, seed: int) -> Tuple[set[str], set[str]]:
    rng = random.Random(seed)
    shuffled = ids[:]
    rng.shuffle(shuffled)
    val_count = max(1, int(len(shuffled) * val_ratio)) if shuffled else 0
    val_ids = set(shuffled[:val_count])
    train_ids = set(shuffled[val_count:])
    return train_ids, val_ids


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Label Studio pulled JSONL to YOLO segmentation dataset"
    )
    parser.add_argument("--annotations", type=Path, required=True, help="Label Studio pull jsonl")
    parser.add_argument("--images-dir", type=Path, required=True, help="Directory of source images")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output YOLO dataset root")
    parser.add_argument(
        "--class-names",
        default="deltoid",
        help="Comma-separated class names; example: deltoid",
    )
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    class_names = [x.strip() for x in args.class_names.split(",") if x.strip()]
    if not class_names:
        raise ValueError("class-names cannot be empty")
    class_to_id = {name: i for i, name in enumerate(class_names)}

    rows = read_jsonl(args.annotations)
    dataset_rows: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        if not row.get("has_annotation"):
            continue
        data = row.get("data", {})
        image_ref = str(data.get("image", ""))
        if not image_ref:
            continue
        img_path = find_image_path(image_ref, args.images_dir)
        if img_path is None:
            continue

        sample_id = img_path.stem
        seg_rows = parse_polygon_results(list(row.get("result", [])), class_to_id)
        if not seg_rows:
            continue

        obj = dataset_rows.setdefault(
            sample_id,
            {"image_path": img_path, "segments": []},
        )
        obj["segments"].extend(seg_rows)

    all_ids = sorted(dataset_rows.keys())
    train_ids, val_ids = split_ids(all_ids, args.val_ratio, args.seed)

    for split in ["train", "val"]:
        (args.out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    copied = 0
    for sample_id, obj in dataset_rows.items():
        split = "val" if sample_id in val_ids else "train"
        src_img = Path(str(obj["image_path"]))
        dst_img = args.out_dir / "images" / split / src_img.name
        shutil.copy2(src_img, dst_img)

        label_path = args.out_dir / "labels" / split / f"{sample_id}.txt"
        lines: List[str] = []
        for class_id, seg in obj["segments"]:
            lines.append(f"{class_id} " + " ".join(f"{v:.6f}" for v in seg))
        label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        copied += 1

    dataset_yaml = {
        "path": str(args.out_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": {i: name for i, name in enumerate(class_names)},
    }
    (args.out_dir / "dataset.yaml").write_text(
        json.dumps(dataset_yaml, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = {
        "annotations_in": str(args.annotations),
        "images_dir": str(args.images_dir),
        "dataset_root": str(args.out_dir),
        "samples_total": len(all_ids),
        "train_samples": len(train_ids),
        "val_samples": len(val_ids),
        "classes": class_names,
    }
    (args.out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
