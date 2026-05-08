from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bbox_area_ratio(box: Sequence[float], image_width: int, image_height: int) -> float:
    if image_width <= 0 or image_height <= 0 or len(box) < 4:
        return 0.0
    x1 = _safe_float(box[0])
    y1 = _safe_float(box[1])
    x2 = _safe_float(box[2])
    y2 = _safe_float(box[3])
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    return float((w * h) / float(image_width * image_height))


def count_valid_keypoints(keypoints: Sequence[Sequence[float]], *, threshold: float) -> int:
    count = 0
    for kp in keypoints:
        if len(kp) < 3:
            continue
        if _safe_float(kp[2], default=-1.0) >= threshold:
            count += 1
    return count


def select_best_person_detection(
    detections: Sequence[Mapping[str, Any]],
    *,
    min_person_score: float,
) -> Dict[str, Any] | None:
    best: Dict[str, Any] | None = None
    best_score = float("-inf")
    for item in detections:
        label = int(_safe_float(item.get("label", 0), default=0.0))
        score = _safe_float(item.get("score", 0.0), default=0.0)
        if label != 1 or score < float(min_person_score):
            continue
        if score > best_score:
            best_score = score
            best = dict(item)
    return best


def evaluate_pose_roi_gate(
    person_detection: Mapping[str, Any] | None,
    pose_detection: Mapping[str, Any] | None,
    *,
    image_size: tuple[int, int],
    min_person_score: float,
    min_keypoints: int,
    keypoint_score_threshold: float,
    min_bbox_area_ratio: float,
    max_bbox_area_ratio: float,
    roi_area_ratio_override: float | None = None,
) -> Dict[str, Any]:
    width, height = image_size
    reject_reasons: List[str] = []

    person_ok = (
        person_detection is not None
        and _safe_float(person_detection.get("score", 0.0), default=0.0) >= float(min_person_score)
    )
    pose_ok = (
        pose_detection is not None
        and _safe_float(pose_detection.get("score", 0.0), default=0.0) >= float(min_person_score)
    )
    if not person_ok and not pose_ok:
        reject_reasons.append("no_person_detected")

    # Prefer detector bbox when available, otherwise use pose bbox.
    chosen = person_detection if person_ok else pose_detection
    box = [] if chosen is None else chosen.get("box", [])

    if roi_area_ratio_override is None:
        area_ratio = bbox_area_ratio(box, width, height)
        roi_source = "bbox"
    else:
        area_ratio = float(roi_area_ratio_override)
        roi_source = "segmentation"
    if area_ratio < float(min_bbox_area_ratio):
        reject_reasons.append("bbox_too_small")
    if area_ratio > float(max_bbox_area_ratio):
        reject_reasons.append("bbox_too_large")

    valid_keypoints = 0
    if pose_ok:
        keypoints = pose_detection.get("keypoints", []) if pose_detection is not None else []
        valid_keypoints = count_valid_keypoints(
            keypoints if isinstance(keypoints, list) else [],
            threshold=float(keypoint_score_threshold),
        )
        if valid_keypoints < int(min_keypoints):
            reject_reasons.append("insufficient_keypoints")
    else:
        reject_reasons.append("pose_missing")

    person_score = _safe_float(person_detection.get("score", 0.0), default=0.0) if person_detection else 0.0
    pose_score = _safe_float(pose_detection.get("score", 0.0), default=0.0) if pose_detection else 0.0

    return {
        "decision": "accept" if not reject_reasons else "reject",
        "person_score": float(person_score),
        "pose_score": float(pose_score),
        "bbox_area_ratio": float(area_ratio),
        "roi_source": roi_source,
        "valid_keypoints": int(valid_keypoints),
        "min_person_score": float(min_person_score),
        "min_keypoints": int(min_keypoints),
        "keypoint_score_threshold": float(keypoint_score_threshold),
        "reject_reasons": reject_reasons,
    }


def evaluate_single_detection_pose_roi_gate(
    detection: Mapping[str, Any],
    *,
    image_size: tuple[int, int],
    min_keypoints: int,
    keypoint_score_threshold: float,
    min_bbox_area_ratio: float,
    max_bbox_area_ratio: float,
) -> Dict[str, Any]:
    width, height = image_size
    box = detection.get("box", [])
    keypoints = detection.get("keypoints", [])

    area_ratio = bbox_area_ratio(box, width, height)
    valid_keypoints = count_valid_keypoints(
        keypoints if isinstance(keypoints, list) else [],
        threshold=float(keypoint_score_threshold),
    )

    reject_reasons: List[str] = []
    if area_ratio < float(min_bbox_area_ratio):
        reject_reasons.append("bbox_too_small")
    if area_ratio > float(max_bbox_area_ratio):
        reject_reasons.append("bbox_too_large")
    if valid_keypoints < int(min_keypoints):
        reject_reasons.append("insufficient_keypoints")

    return {
        "decision": "accept" if not reject_reasons else "reject",
        "person_score": _safe_float(detection.get("score", 0.0), default=0.0),
        "bbox_area_ratio": float(area_ratio),
        "valid_keypoints": int(valid_keypoints),
        "min_keypoints": int(min_keypoints),
        "keypoint_score_threshold": float(keypoint_score_threshold),
        "reject_reasons": reject_reasons,
    }
