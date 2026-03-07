#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping

from PIL import Image
import torch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, parse_bool, resolve_filter_and_pipeline_dirs
from common.manifest_io import read_jsonl, write_json, write_jsonl
from common.pose_roi_gate import evaluate_pose_roi_gate, select_best_person_detection


def ensure_ultralytics() -> Any:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("missing ultralytics. install with: pip install ultralytics") from exc
    return YOLO


def _resolve_path(raw: str, *, base_dir: Path) -> Path:
    path = Path(str(raw).strip())
    if path.is_absolute():
        return path
    candidate = (base_dir / path).resolve()
    if candidate.exists():
        return candidate
    return (ROOT / path).resolve()


def _resolve_device(raw: str) -> str:
    device = str(raw).strip().lower()
    if device in {"", "auto"}:
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        return "cuda:0"
    return device


def _resolve_phase2_cfg(config: Mapping[str, Any], *, config_path: Path, run_filter_dir: Path) -> Dict[str, Any]:
    filter_cfg = dict(config.get("filter", {}))
    phase2_cfg = dict(filter_cfg.get("phase2_roi_pose", {}))
    enabled = parse_bool(phase2_cfg.get("enabled", False), False)
    input_raw = str(phase2_cfg.get("input_manifest", "")).strip()
    if input_raw:
        input_manifest = _resolve_path(input_raw, base_dir=config_path.parent)
    else:
        input_manifest = (run_filter_dir / "splits" / "accept.jsonl").resolve()

    pose_cfg = dict(phase2_cfg.get("pose", {}))
    det_cfg = dict(phase2_cfg.get("detection", {}))
    routing_cfg = dict(phase2_cfg.get("routing", {}))
    seg_cfg = dict(phase2_cfg.get("segmentation", {}))

    pose_model_raw = str(pose_cfg.get("model", "third_party/yolo26x-pose.pt")).strip() or "third_party/yolo26x-pose.pt"
    det_model_raw = str(det_cfg.get("model", "yolo11n.pt")).strip() or "yolo11n.pt"
    pose_model = _resolve_path(pose_model_raw, base_dir=config_path.parent)
    det_model = _resolve_path(det_model_raw, base_dir=config_path.parent)

    return {
        "enabled": enabled,
        "input_manifest": input_manifest,
        "device": _resolve_device(str(phase2_cfg.get("device", "auto"))),
        "min_person_score": float(phase2_cfg.get("min_person_score", 0.25)),
        "min_keypoints": int(phase2_cfg.get("min_keypoints", 12)),
        "keypoint_score_threshold": float(phase2_cfg.get("keypoint_score_threshold", 0.5)),
        "min_bbox_area_ratio": float(phase2_cfg.get("min_bbox_area_ratio", 0.05)),
        "max_bbox_area_ratio": float(phase2_cfg.get("max_bbox_area_ratio", 1.0)),
        "pose_enabled": parse_bool(pose_cfg.get("enabled", True), True),
        "pose_model": str(pose_model),
        "pose_conf": float(pose_cfg.get("conf", 0.25)),
        "pose_iou": float(pose_cfg.get("iou", 0.45)),
        "det_enabled": parse_bool(det_cfg.get("enabled", False), False),
        "det_model": str(det_model),
        "det_conf": float(det_cfg.get("conf", 0.25)),
        "det_iou": float(det_cfg.get("iou", 0.45)),
        "keypoint_fail_action": str(routing_cfg.get("keypoint_fail_action", "uncertain")).strip().lower() or "uncertain",
        "bbox_fail_action": str(routing_cfg.get("bbox_fail_action", "reject")).strip().lower() or "reject",
        "no_person_fail_action": str(routing_cfg.get("no_person_fail_action", "reject")).strip().lower() or "reject",
        "pose_missing_action": str(routing_cfg.get("pose_missing_action", "uncertain")).strip().lower() or "uncertain",
        "segmentation_enabled": parse_bool(seg_cfg.get("enabled", False), False),
        "segmentation_area_ratio_field": str(seg_cfg.get("area_ratio_field", "person_mask_area_ratio")).strip()
        or "person_mask_area_ratio",
    }


def _normalize_row(row: Dict[str, Any], *, row_index: int, base_dir: Path) -> Dict[str, Any]:
    image_raw = str(row.get("image_path", row.get("imagepath", row.get("path", "")))).strip()
    if not image_raw:
        raise ValueError(f"row {row_index} missing image path")
    sample_id = str(row.get("sample_id", "")).strip() or f"row_{row_index:07d}"
    return {
        "sample_id": sample_id,
        "image_path": str(_resolve_path(image_raw, base_dir=base_dir)),
        "raw": dict(row),
    }


def _is_dir_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return False
    probe = path / ".write_probe.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _resolve_output_dir(*, explicit_output_dir: str, default_output_dir: Path, config: Dict[str, Any]) -> tuple[Path, str]:
    if str(explicit_output_dir).strip():
        out = Path(explicit_output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        return out, "cli.output_dir"
    if _is_dir_writable(default_output_dir):
        return default_output_dir, "default.filter_dir"
    run_cfg = dict(config.get("run", {}))
    run_id = str(run_cfg.get("run_id", "m1_local_run")).strip() or "m1_local_run"
    fallback = (ROOT / "artifacts" / "tmp" / "filter2" / run_id).resolve()
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, "fallback.artifacts_tmp_filter2"


def _to_person_candidates(result: Any, *, with_keypoints: bool) -> List[Dict[str, Any]]:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    xyxy = getattr(boxes, "xyxy", None)
    conf = getattr(boxes, "conf", None)
    cls = getattr(boxes, "cls", None)
    if xyxy is None or conf is None or cls is None:
        return []

    keypoints_obj = getattr(result, "keypoints", None)
    xy = getattr(keypoints_obj, "xy", None) if keypoints_obj is not None else None
    kp_conf = getattr(keypoints_obj, "conf", None) if keypoints_obj is not None else None

    out: List[Dict[str, Any]] = []
    n = int(len(xyxy))
    for i in range(n):
        class_id = int(cls[i].item())
        # COCO person class id in YOLO is 0.
        if class_id != 0:
            continue

        row: Dict[str, Any] = {
            "label": 1,
            "score": float(conf[i].item()),
            "box": [float(v) for v in xyxy[i].tolist()],
        }

        if with_keypoints and xy is not None and i < len(xy):
            xy_row = xy[i].tolist()
            conf_row: List[float] = []
            if kp_conf is not None and i < len(kp_conf):
                conf_row = [float(v) for v in kp_conf[i].tolist()]
            keypoints: List[List[float]] = []
            for j, point in enumerate(xy_row):
                score = conf_row[j] if j < len(conf_row) else 0.0
                keypoints.append([float(point[0]), float(point[1]), float(score)])
            row["keypoints"] = keypoints

        out.append(row)
    return out


def _predict_best_person(*, model: Any, image_path: Path, device: str, conf: float, iou: float, with_keypoints: bool, min_person_score: float) -> Dict[str, Any] | None:
    results = model.predict(source=str(image_path), device=device, conf=conf, iou=iou, verbose=False)
    all_candidates: List[Dict[str, Any]] = []
    for result in results:
        all_candidates.extend(_to_person_candidates(result, with_keypoints=with_keypoints))
    return select_best_person_detection(all_candidates, min_person_score=min_person_score)


def _normalize_action(action: str) -> str:
    value = str(action).strip().lower()
    if value not in {"reject", "uncertain"}:
        raise ValueError(f"invalid routing action: {action}. expected reject|uncertain")
    return value


def _extract_segmentation_area_ratio(row: Mapping[str, Any], *, enabled: bool, field: str) -> float | None:
    if not enabled:
        return None
    raw_row = row.get("raw", {}) if isinstance(row, dict) else {}
    if not isinstance(raw_row, dict):
        return None
    value = raw_row.get(field)
    if value is None:
        return None
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return None
    if ratio < 0.0:
        return 0.0
    if ratio > 1.0:
        return 1.0
    return ratio


def _route_decision_from_reasons(reject_reasons: List[str], *, phase2: Dict[str, Any]) -> str:
    if not reject_reasons:
        return "accept"
    actions = {
        "insufficient_keypoints": _normalize_action(str(phase2["keypoint_fail_action"])),
        "bbox_too_small": _normalize_action(str(phase2["bbox_fail_action"])),
        "bbox_too_large": _normalize_action(str(phase2["bbox_fail_action"])),
        "no_person_detected": _normalize_action(str(phase2["no_person_fail_action"])),
        "pose_missing": _normalize_action(str(phase2["pose_missing_action"])),
    }
    routed = [actions.get(reason, "reject") for reason in reject_reasons]
    return "reject" if "reject" in routed else "uncertain"


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter stage2: ROI+pose gate using YOLO pose/detection")
    parser.add_argument("--config", required=True, help="Config yaml/json")
    parser.add_argument("--output-dir", default="", help="Optional output dir override")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    run_paths = resolve_filter_and_pipeline_dirs(config)
    filter_dir = run_paths["filter_dir"]

    phase2 = _resolve_phase2_cfg(config, config_path=config_path, run_filter_dir=filter_dir)
    if not phase2["enabled"]:
        raise ValueError("filter.phase2_roi_pose.enabled must be true to run filter2")

    input_manifest = Path(phase2["input_manifest"])
    if not input_manifest.exists():
        raise FileNotFoundError(f"input manifest not found: {input_manifest}")

    rows = [
        _normalize_row(row, row_index=i, base_dir=input_manifest.parent)
        for i, row in enumerate(read_jsonl(input_manifest))
    ]

    if not phase2["pose_enabled"] and not phase2["det_enabled"]:
        raise ValueError("at least one backend must be enabled: phase2_roi_pose.pose.enabled or detection.enabled")

    YOLO = ensure_ultralytics()
    pose_model = YOLO(phase2["pose_model"]) if phase2["pose_enabled"] else None
    det_model = YOLO(phase2["det_model"]) if phase2["det_enabled"] else None

    score_rows: List[Dict[str, Any]] = []
    for row in rows:
        image_path = Path(row["image_path"])
        with Image.open(image_path) as img:
            width, height = img.size

        pose_det = None
        person_det = None
        if pose_model is not None:
            pose_det = _predict_best_person(
                model=pose_model,
                image_path=image_path,
                device=phase2["device"],
                conf=float(phase2["pose_conf"]),
                iou=float(phase2["pose_iou"]),
                with_keypoints=True,
                min_person_score=float(phase2["min_person_score"]),
            )
        if det_model is not None:
            person_det = _predict_best_person(
                model=det_model,
                image_path=image_path,
                device=phase2["device"],
                conf=float(phase2["det_conf"]),
                iou=float(phase2["det_iou"]),
                with_keypoints=False,
                min_person_score=float(phase2["min_person_score"]),
            )

        gate = evaluate_pose_roi_gate(
            person_detection=person_det,
            pose_detection=pose_det,
            image_size=(width, height),
            min_person_score=float(phase2["min_person_score"]),
            min_keypoints=int(phase2["min_keypoints"]),
            keypoint_score_threshold=float(phase2["keypoint_score_threshold"]),
            min_bbox_area_ratio=float(phase2["min_bbox_area_ratio"]),
            max_bbox_area_ratio=float(phase2["max_bbox_area_ratio"]),
            roi_area_ratio_override=_extract_segmentation_area_ratio(
                row,
                enabled=bool(phase2["segmentation_enabled"]),
                field=str(phase2["segmentation_area_ratio_field"]),
            ),
        )
        routed_decision = _route_decision_from_reasons(list(gate["reject_reasons"]), phase2=phase2)
        score_rows.append(
            {
                "sample_id": row["sample_id"],
                "image_path": row["image_path"],
                "decision": routed_decision,
                "raw_gate_decision": gate["decision"],
                "person_score": gate["person_score"],
                "pose_score": gate["pose_score"],
                "bbox_area_ratio": gate["bbox_area_ratio"],
                "roi_source": gate["roi_source"],
                "valid_keypoints": gate["valid_keypoints"],
                "min_keypoints": gate["min_keypoints"],
                "keypoint_score_threshold": gate["keypoint_score_threshold"],
                "reject_reasons": gate["reject_reasons"],
            }
        )

    accept_rows = [r for r in score_rows if r.get("decision") == "accept"]
    reject_rows = [r for r in score_rows if r.get("decision") == "reject"]
    uncertain_rows = [r for r in score_rows if r.get("decision") == "uncertain"]

    output_dir, output_dir_source = _resolve_output_dir(
        explicit_output_dir=str(args.output_dir),
        default_output_dir=filter_dir,
        config=config,
    )
    splits_dir = output_dir / "splits"
    output_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(output_dir / "filter2_scores.jsonl", score_rows)
    write_jsonl(splits_dir / "filter2_accept.jsonl", accept_rows)
    write_jsonl(splits_dir / "filter2_reject.jsonl", reject_rows)
    write_jsonl(splits_dir / "filter2_uncertain.jsonl", uncertain_rows)

    report = {
        "stage": "filter2",
        "input_manifest": str(input_manifest),
        "input_row_count": len(rows),
        "accept": len(accept_rows),
        "reject": len(reject_rows),
        "uncertain": len(uncertain_rows),
        "device": phase2["device"],
        "pose_enabled": phase2["pose_enabled"],
        "pose_model": phase2["pose_model"],
        "det_enabled": phase2["det_enabled"],
        "det_model": phase2["det_model"],
        "min_person_score": phase2["min_person_score"],
        "min_keypoints": phase2["min_keypoints"],
        "keypoint_score_threshold": phase2["keypoint_score_threshold"],
        "min_bbox_area_ratio": phase2["min_bbox_area_ratio"],
        "max_bbox_area_ratio": phase2["max_bbox_area_ratio"],
        "segmentation_enabled": phase2["segmentation_enabled"],
        "segmentation_area_ratio_field": phase2["segmentation_area_ratio_field"],
        "routing": {
            "keypoint_fail_action": phase2["keypoint_fail_action"],
            "bbox_fail_action": phase2["bbox_fail_action"],
            "no_person_fail_action": phase2["no_person_fail_action"],
            "pose_missing_action": phase2["pose_missing_action"],
        },
        "output_dir_source": output_dir_source,
    }
    write_json(output_dir / "filter2_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
