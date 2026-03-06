from __future__ import annotations

from typing import Any, Dict, List, Sequence


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("values must not be empty")
    return float(sum(float(v) for v in values) / len(values))


def _top_k_mean(values: Sequence[float], k: int) -> tuple[float, int]:
    if not values:
        raise ValueError("logits list must not be empty")
    if k <= 0:
        raise ValueError("k must be > 0")
    sorted_desc = sorted((float(v) for v in values), reverse=True)
    effective_k = min(k, len(sorted_desc))
    return _mean(sorted_desc[:effective_k]), effective_k


def compute_margin(pos_logits: Sequence[float], neg_logits: Sequence[float], *, top_k: int = 3) -> Dict[str, float | int]:
    if not pos_logits:
        raise ValueError("positive logits must not be empty")
    if not neg_logits:
        raise ValueError("negative logits must not be empty")
    pos_score, effective_k = _top_k_mean(pos_logits, top_k)
    neg_score, _ = _top_k_mean(neg_logits, top_k)
    margin = float(pos_score - neg_score)
    return {
        "pos_score": pos_score,
        "neg_score": neg_score,
        "margin": margin,
        "effective_k": effective_k,
    }


def _confusion(margins: Sequence[float], labels: Sequence[int], threshold: float) -> tuple[int, int, int, int]:
    tn = fp = fn = tp = 0
    for margin, label in zip(margins, labels):
        pred = 1 if float(margin) >= float(threshold) else 0
        if pred == 1 and label == 1:
            tp += 1
        elif pred == 1 and label == 0:
            fp += 1
        elif pred == 0 and label == 1:
            fn += 1
        else:
            tn += 1
    return tn, fp, fn, tp


def _metrics_from_confusion(tn: int, fp: int, fn: int, tp: int) -> Dict[str, float]:
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float((2.0 * precision * recall) / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
    }


def sweep_best_f1_threshold(margins: Sequence[float], labels: Sequence[int]) -> Dict[str, Any]:
    if not margins:
        raise ValueError("margins must not be empty")
    if len(margins) != len(labels):
        raise ValueError("margins and labels must have same length")
    for label in labels:
        if label not in (0, 1):
            raise ValueError("labels must be binary 0/1")

    candidates = sorted(set(float(x) for x in margins))
    best: Dict[str, Any] | None = None
    for threshold in candidates:
        tn, fp, fn, tp = _confusion(margins, labels, threshold)
        metrics = _metrics_from_confusion(tn, fp, fn, tp)
        current = {
            "threshold": float(threshold),
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "confusion_matrix": [[tn, fp], [fn, tp]],
        }
        if best is None:
            best = current
            continue
        # Deterministic tie break:
        # 1) higher F1, 2) higher recall, 3) higher precision, 4) smaller threshold.
        if (
            (current["f1"] > best["f1"])
            or (current["f1"] == best["f1"] and current["recall"] > best["recall"])
            or (
                current["f1"] == best["f1"]
                and current["recall"] == best["recall"]
                and current["precision"] > best["precision"]
            )
            or (
                current["f1"] == best["f1"]
                and current["recall"] == best["recall"]
                and current["precision"] == best["precision"]
                and current["threshold"] < best["threshold"]
            )
        ):
            best = current

    if best is None:
        raise RuntimeError("failed to compute threshold")
    return best
