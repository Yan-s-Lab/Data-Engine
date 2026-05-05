#!/usr/bin/env python
"""AI annotation: run YOLO-pose on filter2_accept images → YOLO-pose label files + dataset.yaml."""
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
from common.manifest_io import read_jsonl, write_json, write_jsonl

# COCO 17-keypoint flip pairs (left↔right) for dataset.yaml
COCO_FLIP_IDX = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
COCO_KPT_SHAPE = [17, 3]  # 17 keypoints × (x, y, visibility)


def ensure_ultralytics() -> Any:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pip install ultralytics") from exc
    return YOLO


def build_pose_label(
    boxes_xywhn: Any,
    kpts_xyn: Any,
    kpts_conf: Any,
    vis_threshold: float,
) -> List[str]:
    """Return YOLO-pose label lines for all detected persons in one image.

    Format per line: class cx cy w h kp0x kp0y kp0v ... kp16x kp16y kp16v
    All coords normalized 0-1. Visibility: 2=visible, 1=occluded, 0=absent.
    """
    lines: List[str] = []
    n = len(boxes_xywhn)
    for i in range(n):
        cx, cy, w, h = (float(v) for v in boxes_xywhn[i])
        parts = [f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"]
        for k in range(17):
            kx = float(kpts_xyn[i][k][0])
            ky = float(kpts_xyn[i][k][1])
            kv_raw = float(kpts_conf[i][k]) if kpts_conf is not None else 0.0
            if kv_raw >= vis_threshold:
                kv = 2
            elif kv_raw > 0.0:
                kv = 1
            else:
                kv = 0
            parts.append(f"{kx:.6f} {ky:.6f} {kv}")
        lines.append(" ".join(parts))
    return lines


def split_ids(ids: List[str], val_ratio: float, seed: int) -> Tuple[List[str], List[str]]:
    rng = random.Random(seed)
    shuffled = ids[:]
    rng.shuffle(shuffled)
    n_val = max(1, int(len(shuffled) * val_ratio)) if shuffled else 0
    return shuffled[n_val:], shuffled[:n_val]  # train, val


def resolve_manifest_image_path(row: Dict[str, Any]) -> Path:
    for key in ("image_path", "synthetic_image_path", "imagepath", "path"):
        raw_value = str(row.get(key, "")).strip()
        if not raw_value:
            continue
        path = Path(raw_value)
        if path.is_absolute():
            return path
        return ROOT / path
    raise ValueError("manifest row is missing an image path field")


def resolve_sample_id(row: Dict[str, Any], image_path: Path) -> str:
    for key in ("sample_id", "synthetic_id", "image_id", "guide_image_id"):
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return image_path.stem


def main() -> None:
    parser = argparse.ArgumentParser(description="AI pose annotation via YOLO-pose inference")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    ann_cfg: Dict[str, Any] = config.get("annotation", {})

    input_manifest = Path(str(ann_cfg["input_manifest"]))
    model_path = str(ann_cfg.get("model", "third_party/yolo26x-pose.pt"))
    device = str(ann_cfg.get("device", "0"))
    conf = float(ann_cfg.get("conf", 0.25))
    iou = float(ann_cfg.get("iou", 0.45))
    vis_threshold = float(ann_cfg.get("vis_threshold", 0.5))
    val_ratio = float(ann_cfg.get("val_ratio", 0.2))
    seed = int(ann_cfg.get("seed", 42))

    out_dir = run_dir / "label" / "ai_dataset"
    label_dir = run_dir / "label" / "ai_labels"
    for split in ["train", "val"]:
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(input_manifest)
    YOLO = ensure_ultralytics()
    model = YOLO(model_path)

    annotated: List[Dict[str, Any]] = []
    skipped = 0

    for row in rows:
        img_path = resolve_manifest_image_path(row)
        if not img_path.exists():
            skipped += 1
            continue

        results = model.predict(
            source=str(img_path),
            conf=conf,
            iou=iou,
            device=device,
            verbose=False,
        )
        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            skipped += 1
            continue

        kpts_xyn = result.keypoints.xyn if result.keypoints is not None else None
        kpts_conf = result.keypoints.conf if result.keypoints is not None else None
        if kpts_xyn is None:
            skipped += 1
            continue

        label_lines = build_pose_label(
            result.boxes.xywhn, kpts_xyn, kpts_conf, vis_threshold
        )
        if not label_lines:
            skipped += 1
            continue

        label_txt = label_dir / f"{img_path.stem}.txt"
        label_txt.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
        sample_id = resolve_sample_id(row, img_path)

        annotated.append({
            "sample_id": sample_id,
            "image_path": str(img_path),
            "label_path": str(label_txt),
            "n_persons": len(label_lines),
        })

    # train/val split + copy into dataset layout
    all_ids = [a["sample_id"] for a in annotated]
    train_ids, val_ids = split_ids(all_ids, val_ratio, seed)
    val_set = set(val_ids)
    annotated_by_id = {a["sample_id"]: a for a in annotated}

    for sample_id, obj in annotated_by_id.items():
        split = "val" if sample_id in val_set else "train"
        src_img = Path(obj["image_path"])
        shutil.copy2(src_img, out_dir / "images" / split / src_img.name)
        src_lbl = Path(obj["label_path"])
        shutil.copy2(src_lbl, out_dir / "labels" / split / src_lbl.name)
        obj["split"] = split

    # YOLO-pose dataset.yaml
    dataset_yaml_path = out_dir / "dataset.yaml"
    dataset_yaml: Dict[str, Any] = {
        "path": str(out_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "kpt_shape": COCO_KPT_SHAPE,
        "flip_idx": COCO_FLIP_IDX,
        "names": {0: "person"},
    }
    import yaml  # type: ignore
    dataset_yaml_path.write_text(
        yaml.dump(dataset_yaml, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    manifest_path = run_dir / "label" / "ai_annotations_manifest.jsonl"
    write_jsonl(manifest_path, annotated)

    report = {
        "stage": "ai_annotation",
        "run_dir": str(run_dir),
        "input_manifest": str(input_manifest),
        "model": model_path,
        "total_input": len(rows),
        "annotated": len(annotated),
        "skipped": skipped,
        "train_samples": len(train_ids),
        "val_samples": len(val_ids),
        "dataset_root": str(out_dir),
        "dataset_yaml": str(dataset_yaml_path),
        "manifest": str(manifest_path),
    }
    write_json(run_dir / "label" / "ai_annotation_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
