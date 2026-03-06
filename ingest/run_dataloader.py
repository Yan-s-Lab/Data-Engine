#!/usr/bin/env python
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import string
import sys
from typing import Any, Dict, List
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, parse_bool, resolve_run_dir
from common.manifest_io import write_json, write_jsonl


def _load_coco_annotation_index(label_file: Path) -> Dict[str, Any]:
    data = json.loads(label_file.read_text(encoding="utf-8"))
    images = data.get("images")
    annotations = data.get("annotations")
    if not isinstance(images, list) or not isinstance(annotations, list):
        raise ValueError(f"invalid COCO annotation file (missing images/annotations list): {label_file}")

    image_ids_by_file_name: Dict[str, List[int]] = defaultdict(list)
    image_ids_by_stem: Dict[str, List[int]] = defaultdict(list)
    for image in images:
        if not isinstance(image, dict):
            continue
        image_id = image.get("id")
        file_name_raw = image.get("file_name")
        if not isinstance(image_id, int) or not isinstance(file_name_raw, str) or not file_name_raw.strip():
            continue
        file_name = file_name_raw.strip()
        image_ids_by_file_name[file_name].append(image_id)
        image_ids_by_file_name[Path(file_name).name].append(image_id)
        image_ids_by_stem[Path(file_name).stem].append(image_id)

    ann_count_by_image_id: Dict[int, int] = defaultdict(int)
    for ann in annotations:
        if not isinstance(ann, dict):
            continue
        image_id = ann.get("image_id")
        if isinstance(image_id, int):
            ann_count_by_image_id[image_id] += 1

    return {
        "image_ids_by_file_name": image_ids_by_file_name,
        "image_ids_by_stem": image_ids_by_stem,
        "ann_count_by_image_id": ann_count_by_image_id,
    }


def _resolve_coco_label_for_image(image_path: Path, index: Dict[str, Any]) -> Dict[str, Any] | None:
    image_ids_by_file_name = index["image_ids_by_file_name"]
    image_ids_by_stem = index["image_ids_by_stem"]
    ann_count_by_image_id = index["ann_count_by_image_id"]

    candidates = image_ids_by_file_name.get(image_path.name, [])
    if not candidates:
        candidates = image_ids_by_stem.get(image_path.stem, [])

    unique_image_ids = sorted(set(candidates))
    if len(unique_image_ids) != 1:
        return None

    image_id = unique_image_ids[0]
    ann_count = int(ann_count_by_image_id.get(image_id, 0))
    if ann_count <= 0:
        return None
    return {"image_id": image_id, "annotation_count": ann_count}


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


def normalize_image_ext(value: Any) -> str | None:
    if value is None:
        return None
    ext = str(value).strip().lower()
    if not ext:
        return None
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext == ".jpeg":
        return ".jpg"
    return ext


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_template(template: str, context: Dict[str, Any]) -> str:
    str_context = {k: str(v) for k, v in context.items()}
    step1 = string.Template(template).safe_substitute(str_context)
    return step1.format_map(_SafeFormatDict(str_context))


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


def materialize_image(src: Path, dst: Path, mode: str, target_ext: str | None) -> None:
    src_ext = src.suffix.lower()
    if target_ext is None or target_ext == src_ext:
        materialize_file(src, dst, mode=mode)
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()

    if target_ext == ".jpg":
        save_format = "JPEG"
    elif target_ext == ".png":
        save_format = "PNG"
    elif target_ext == ".webp":
        save_format = "WEBP"
    else:
        raise ValueError(f"unsupported target image extension: {target_ext}")

    with Image.open(src) as img:
        if save_format == "JPEG" and img.mode not in {"RGB", "L"}:
            img = img.convert("RGB")
        img.save(dst, format=save_format)


def resolve_real_dir(loader_cfg: Dict[str, Any], run_dir: Path) -> tuple[Path, Any]:
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
        return real_dir, real_zip

    real_dir = Path(str(loader_cfg.get("real_dir", "data/raw/collection_1")))
    return real_dir, None


def resolve_output_dirs(
    loader_cfg: Dict[str, Any], run_dir: Path, has_labels: bool, template_ctx: Dict[str, Any]
) -> tuple[Path, Path, Path | None]:
    output_cfg = loader_cfg.get("output", {})
    root_raw = output_cfg.get("root_dir")
    if root_raw:
        output_root = Path(render_template(str(root_raw), template_ctx))
    else:
        output_root = run_dir / "dataloader" / "normalized"
    image_dirname = render_template(str(output_cfg.get("images_subdir", "images")), template_ctx)
    label_dirname = render_template(str(output_cfg.get("labels_subdir", "labels")), template_ctx)
    output_images_dir = output_root / image_dirname
    output_labels_dir = (output_root / label_dirname) if has_labels else None
    return output_root, output_images_dir, output_labels_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="DataLoader: normalize real data into manifest")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    loader_cfg = config.get("dataloader", {})

    real_dir, real_zip = resolve_real_dir(loader_cfg, run_dir)
    if not real_dir.exists():
        raise FileNotFoundError(f"real_dir not found: {real_dir}")

    image_dir_raw = loader_cfg.get("image_dir")
    if image_dir_raw:
        image_dir = Path(str(image_dir_raw))
    else:
        candidate = real_dir / "images"
        image_dir = candidate if candidate.exists() else real_dir

    if not image_dir.exists():
        raise FileNotFoundError(f"image_dir not found: {image_dir}")

    patterns = list(loader_cfg.get("patterns", ["*.png", "*.jpg", "*.jpeg"]))
    max_samples = int(loader_cfg.get("max_samples", 0))
    files = collect_images(image_dir, patterns, max_samples)
    if not files:
        raise RuntimeError(f"no images found under {image_dir} with patterns={patterns}")

    label_format = str(loader_cfg.get("label_format", "per_file")).strip().lower()
    if label_format not in {"per_file", "coco"}:
        raise ValueError(
            f"unsupported dataloader.label_format `{label_format}`: expected `per_file` or `coco`"
        )

    label_dir_raw = loader_cfg.get("label_dir")
    label_dir: Path | None = None
    label_file: Path | None = None
    coco_index: Dict[str, Any] | None = None
    if label_format == "coco":
        label_file_raw = loader_cfg.get("label_file") or label_dir_raw
        if label_file_raw:
            label_file = Path(str(label_file_raw))
        else:
            candidate = real_dir / "annotations.json"
            label_file = candidate if candidate.exists() else None
        if label_file is not None and not label_file.exists():
            raise FileNotFoundError(f"label_file not found: {label_file}")
        if label_file is not None:
            coco_index = _load_coco_annotation_index(label_file)
    else:
        if label_dir_raw:
            label_dir = Path(str(label_dir_raw))
        else:
            candidate = real_dir / "labels"
            label_dir = candidate if candidate.exists() else None
        if label_dir is not None and not label_dir.exists():
            raise FileNotFoundError(f"label_dir not found: {label_dir}")

    label_ext = str(loader_cfg.get("label_ext", ".txt"))
    if not label_ext.startswith("."):
        label_ext = f".{label_ext}"
    default_require_labels = label_file is not None if label_format == "coco" else label_dir is not None
    require_labels = parse_bool(loader_cfg.get("require_labels"), default=default_require_labels)

    naming_cfg = loader_cfg.get("naming", {})
    canonicalize_names = parse_bool(naming_cfg.get("canonicalize_names"), default=False)
    task_name = str(naming_cfg.get("task_name", "task"))
    services_id = str(naming_cfg.get("services_id", "svc"))
    id_width = int(naming_cfg.get("id_width", 5))
    id_start = int(naming_cfg.get("id_start", 1))
    materialize_mode = str(naming_cfg.get("materialize_mode", "copy"))
    filename_template_raw = naming_cfg.get("filename_template")
    if filename_template_raw is None:
        # Backward-compatible fallback: older configs may place this under output.*
        filename_template_raw = loader_cfg.get("output", {}).get("filename_template")
    filename_template = str(filename_template_raw) if filename_template_raw else None

    target_image_ext = normalize_image_ext(
        naming_cfg.get("target_image_ext", loader_cfg.get("target_image_ext"))
    )
    normalize_outputs = canonicalize_names or target_image_ext is not None or filename_template is not None

    base_template_ctx: Dict[str, Any] = {
        "task_name": task_name,
        "services_id": services_id,
        "id_width": id_width,
        "id_start": id_start,
    }

    has_labels = (label_file is not None) if label_format == "coco" else (label_dir is not None)
    normalized_root, normalized_image_dir, normalized_label_dir = resolve_output_dirs(
        loader_cfg, run_dir, has_labels=has_labels and label_format == "per_file", template_ctx=base_template_ctx
    )
    if normalize_outputs:
        normalized_image_dir.mkdir(parents=True, exist_ok=True)
        if normalized_label_dir is not None:
            normalized_label_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    widths: List[int] = []
    heights: List[int] = []
    samples_missing_label: List[str] = []
    stem_owner: Dict[str, str] = {}

    normalized_counter = 0
    for path in files:
        sample_id = path.stem
        label_src: Path | None = None
        coco_label: Dict[str, Any] | None = None

        if label_format == "coco":
            if label_file is not None and coco_index is not None:
                coco_label = _resolve_coco_label_for_image(path, coco_index)
            if coco_label is None and label_file is not None:
                samples_missing_label.append(sample_id)
                if require_labels:
                    continue
        else:
            if label_dir is not None:
                candidate = label_dir / f"{sample_id}{label_ext}"
                if candidate.exists():
                    label_src = candidate
                else:
                    samples_missing_label.append(sample_id)
                    if require_labels:
                        continue

        width, height = image_size(path)
        widths.append(width)
        heights.append(height)

        row: Dict[str, Any] = {
            "sample_id": sample_id,
            "source": "real",
            "image_path": str(path),
            "width": width,
            "height": height,
        }
        if label_src is not None:
            row["label_path"] = str(label_src)
        elif coco_label is not None and label_file is not None:
            row["label_path"] = str(label_file)
            row["label_format"] = "coco"
            row["coco_image_id"] = coco_label["image_id"]
            row["coco_annotation_count"] = coco_label["annotation_count"]

        if normalize_outputs:
            seq_id = id_start + normalized_counter
            seq_id_padded = f"{seq_id:0{id_width}d}"

            if filename_template is not None:
                sample_ctx: Dict[str, Any] = {
                    **base_template_ctx,
                    "sample_id": sample_id,
                    "raw_sample_id": sample_id,
                    "seq_id": seq_id,
                    "seq_id_padded": seq_id_padded,
                    # compatibility alias for user configs like $task_name_id
                    "task_name_id": seq_id_padded,
                }
                target_stem = render_template(filename_template, sample_ctx).strip()
                if not target_stem:
                    raise ValueError("naming.filename_template rendered empty stem")
            else:
                target_stem = f"{task_name}-{seq_id_padded}" if canonicalize_names else sample_id

            if any(sep in target_stem for sep in ("/", "\\")):
                raise ValueError(f"invalid rendered file stem `{target_stem}`: path separator is not allowed")
            if target_stem in stem_owner:
                owner = stem_owner[target_stem]
                raise ValueError(
                    f"duplicate output stem `{target_stem}` from sample `{sample_id}`; "
                    f"already used by sample `{owner}`"
                )
            stem_owner[target_stem] = sample_id

            out_ext = target_image_ext or path.suffix.lower()
            img_dst = normalized_image_dir / f"{target_stem}{out_ext}"
            materialize_image(path, img_dst, mode=materialize_mode, target_ext=target_image_ext)

            row["original_sample_id"] = sample_id
            row["original_image_path"] = str(path)
            row["sample_id"] = target_stem
            row["image_path"] = str(img_dst)

            if label_src is not None:
                if normalized_label_dir is None:
                    raise RuntimeError("internal error: label output dir is not initialized")
                label_dst = normalized_label_dir / f"{target_stem}{label_ext}"
                materialize_file(label_src, label_dst, mode=materialize_mode)
                row["label_path"] = str(label_dst)

            normalized_counter += 1

        rows.append(row)

    if not rows:
        raise RuntimeError("all samples were filtered out (e.g. require_labels=true with missing labels)")

    loader_dir = run_dir / "dataloader"
    loader_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = loader_dir / "real_manifest.jsonl"
    write_jsonl(manifest_path, rows)

    with_label_count = sum(1 for row in rows if "label_path" in row)
    stats: Dict[str, Any] = {
        "real_sample_count": len(rows),
        "with_label_count": with_label_count,
        "missing_label_count": len(samples_missing_label),
    }
    write_json(loader_dir / "anchor_stats.json", stats)

    report = {
        "stage": "dataloader",
        "run_dir": str(run_dir),
        "real_dir": str(real_dir),
        "image_dir": str(image_dir),
        "real_zip": str(real_zip) if real_zip else None,
        "total_real_samples": len(rows),
        "label_format": label_format,
        "label_dir": str(label_dir) if label_dir is not None else None,
        "label_file": str(label_file) if label_file is not None else None,
        "require_labels": require_labels,
        "canonicalize_names": canonicalize_names,
        "services_id": services_id,
        "filename_template": filename_template,
        "target_image_ext": target_image_ext,
        "naming_task_name": task_name if canonicalize_names else None,
        "normalized_root_dir": str(normalized_root) if normalize_outputs else None,
        "normalized_image_dir": str(normalized_image_dir) if normalize_outputs else None,
        "normalized_label_dir": str(normalized_label_dir) if (normalize_outputs and normalized_label_dir is not None) else None,
        "samples_missing_label_count": len(samples_missing_label),
        "samples_missing_label_preview": samples_missing_label[:20],
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
