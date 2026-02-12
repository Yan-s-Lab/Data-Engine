#!/usr/bin/env python
from __future__ import annotations

import argparse
import shutil
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple
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


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def parse_yolo_seg_line(line: str) -> Dict[str, Any]:
    parts = line.strip().split()
    if len(parts) < 7:
        raise ValueError("seg line must contain class_id and at least 3 (x,y) points")

    try:
        class_id = int(float(parts[0]))
    except ValueError as exc:
        raise ValueError(f"invalid class id: {parts[0]}") from exc

    coords: List[float] = []
    for tok in parts[1:]:
        try:
            coords.append(float(tok))
        except ValueError as exc:
            raise ValueError(f"invalid coordinate: {tok}") from exc

    if len(coords) % 2 != 0:
        raise ValueError("coordinate count must be even")
    if len(coords) < 6:
        raise ValueError("polygon requires at least 3 points")

    polygon: List[List[float]] = []
    xs: List[float] = []
    ys: List[float] = []
    for i in range(0, len(coords), 2):
        x = coords[i]
        y = coords[i + 1]
        polygon.append([x, y])
        xs.append(x)
        ys.append(y)

    x_min = min(xs)
    y_min = min(ys)
    x_max = max(xs)
    y_max = max(ys)
    bbox_w = max(0.0, x_max - x_min)
    bbox_h = max(0.0, y_max - y_min)

    return {
        "class_id": class_id,
        "polygon_norm": polygon,
        "bbox_norm_xyxy": [x_min, y_min, x_max, y_max],
        "bbox_norm_xywh": [
            (x_min + x_max) / 2.0,
            (y_min + y_max) / 2.0,
            bbox_w,
            bbox_h,
        ],
        "bbox_area_norm": bbox_w * bbox_h,
    }


def parse_yolo_seg_file(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    anns: List[Dict[str, Any]] = []
    errors: List[str] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            anns.append(parse_yolo_seg_line(line))
        except ValueError as exc:
            errors.append(f"{path.name}:line{line_no}:{exc}")
    return anns, errors


def load_class_names(classes_path: Path) -> List[str]:
    names: List[str] = []
    for line in classes_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            names.append(line)
    return names


def materialize_file(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if mode == "copy":
        shutil.copy2(src, dst)
        return
    if mode == "hardlink":
        dst.hardlink_to(src)
        return
    if mode == "symlink":
        dst.symlink_to(src.resolve())
        return
    raise ValueError(f"unsupported naming.materialize_mode: {mode}")


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

    label_dir_raw = loader_cfg.get("label_dir")
    label_dir = Path(str(label_dir_raw)) if label_dir_raw else None
    label_ext = str(loader_cfg.get("label_ext", ".txt"))
    if not label_ext.startswith("."):
        label_ext = f".{label_ext}"
    require_labels = _to_bool(loader_cfg.get("require_labels"), default=label_dir is not None)
    naming_cfg = loader_cfg.get("naming", {})
    canonicalize_names = _to_bool(
        naming_cfg.get("canonicalize_names"), default=False
    )
    task_name = str(naming_cfg.get("task_name", "task"))
    id_width = int(naming_cfg.get("id_width", 5))
    id_start = int(naming_cfg.get("id_start", 1))
    materialize_mode = str(naming_cfg.get("materialize_mode", "copy"))
    normalized_root = run_dir / "dataloader" / "normalized"
    normalized_image_dir = normalized_root / "images"
    normalized_label_dir = normalized_root / "labels"
    if canonicalize_names:
        normalized_image_dir.mkdir(parents=True, exist_ok=True)
        normalized_label_dir.mkdir(parents=True, exist_ok=True)

    classes_path_raw = loader_cfg.get("classes_path")
    if classes_path_raw:
        classes_path = Path(str(classes_path_raw))
    elif label_dir is not None:
        classes_path = label_dir / "classes.txt"
    else:
        classes_path = None

    class_names: List[str] = []
    if classes_path is not None and classes_path.exists():
        class_names = load_class_names(classes_path)

    rows: List[Dict[str, Any]] = []
    widths: List[int] = []
    heights: List[int] = []
    class_hist: Dict[str, int] = {}
    total_instances = 0
    bbox_areas: List[float] = []
    samples_missing_label: List[str] = []
    parse_errors: List[str] = []

    normalized_counter = 0
    for idx, path in enumerate(files):
        width, height = image_size(path)
        widths.append(width)
        heights.append(height)
        sample_id = path.stem
        canonical_stem = ""
        row: Dict[str, Any] = {
            "sample_id": sample_id,
            "source": "real",
            "image_path": str(path),
            "width": width,
            "height": height,
        }

        if label_dir is not None:
            label_path = label_dir / f"{path.stem}{label_ext}"
            if not label_path.exists():
                samples_missing_label.append(path.stem)
                if require_labels:
                    continue
            else:
                anns, errs = parse_yolo_seg_file(label_path)
                row["label_path"] = str(label_path)
                row["annotations"] = anns
                row["num_instances"] = len(anns)
                if errs:
                    parse_errors.extend(errs)
                total_instances += len(anns)
                for ann in anns:
                    class_id = ann["class_id"]
                    class_hist[str(class_id)] = class_hist.get(str(class_id), 0) + 1
                    bbox_areas.append(float(ann["bbox_area_norm"]))

        if canonicalize_names:
            canonical_id = id_start + normalized_counter
            canonical_stem = f"{task_name}-{canonical_id:0{id_width}d}"
            img_dst = normalized_image_dir / f"{canonical_stem}{path.suffix.lower()}"
            materialize_file(path, img_dst, mode=materialize_mode)
            if "label_path" in row:
                label_src = Path(str(row["label_path"]))
                label_dst = normalized_label_dir / f"{canonical_stem}{label_ext}"
                materialize_file(label_src, label_dst, mode=materialize_mode)
                row["label_path"] = str(label_dst)
            row["original_sample_id"] = sample_id
            row["original_image_path"] = str(path)
            row["sample_id"] = canonical_stem
            row["image_path"] = str(img_dst)
            normalized_counter += 1

        rows.append(row)

    loader_dir = run_dir / "dataloader"
    loader_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = loader_dir / "real_manifest.jsonl"
    write_jsonl(manifest_path, rows)

    stats: Dict[str, Any] = {
        "real_sample_count": len(rows),
        "total_instances": total_instances,
        "class_histogram": class_hist,
    }
    if class_names:
        class_name_map: Dict[str, str] = {}
        for class_id_str in class_hist:
            class_id = int(class_id_str)
            class_name_map[class_id_str] = (
                class_names[class_id] if 0 <= class_id < len(class_names) else f"unknown_{class_id}"
            )
        stats["class_name_map"] = class_name_map
    if bbox_areas:
        stats["bbox_area_norm"] = {
            "mean": round(sum(bbox_areas) / len(bbox_areas), 6),
            "min": round(min(bbox_areas), 6),
            "max": round(max(bbox_areas), 6),
        }
    write_json(loader_dir / "anchor_stats.json", stats)

    report = {
        "stage": "dataloader",
        "run_dir": str(run_dir),
        "real_dir": str(real_dir),
        "real_zip": str(real_zip) if real_zip else None,
        "total_real_samples": len(rows),
        "label_dir": str(label_dir) if label_dir is not None else None,
        "require_labels": require_labels,
        "canonicalize_names": canonicalize_names,
        "naming_task_name": task_name if canonicalize_names else None,
        "normalized_image_dir": str(normalized_image_dir) if canonicalize_names else None,
        "normalized_label_dir": str(normalized_label_dir) if canonicalize_names else None,
        "samples_missing_label_count": len(samples_missing_label),
        "samples_missing_label_preview": samples_missing_label[:20],
        "parse_error_count": len(parse_errors),
        "parse_error_preview": parse_errors[:20],
        "resolution": {
            "mean_width": round(sum(widths) / len(widths), 2),
            "mean_height": round(sum(heights) / len(heights), 2),
            "min_width": min(widths),
            "max_width": max(widths),
            "min_height": min(heights),
            "max_height": max(heights),
        },
        "manifest": str(manifest_path),
        "anchor_stats": str(loader_dir / "anchor_stats.json"),
    }
    write_json(loader_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
