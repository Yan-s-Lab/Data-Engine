from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    q = max(0.0, min(1.0, q))
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    pos = q * (len(arr) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(arr) - 1)
    frac = pos - lo
    return arr[lo] * (1.0 - frac) + arr[hi] * frac


def _reduce_similarity(values: List[float], reduce_name: str) -> float:
    if not values:
        return 0.0
    rn = reduce_name.strip().lower()
    if rn == "mean":
        return float(sum(values) / len(values))
    if rn == "p25":
        return _quantile(values, 0.25)
    if rn == "p75":
        return _quantile(values, 0.75)
    # default: robust center estimator.
    return _quantile(values, 0.5)


def compute_anchor_semantic_scores(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    cfg: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Any]]:
    """
    Phase-1 semantic score aligned with filter.tex:
      s_sem(x) = median_{r in X_real} Sim(E(x), E(r))
    """
    anchor_from_source_real = bool(cfg.get("anchor_from_source_real", True))
    reduce_name = str(cfg.get("reduce", "median"))
    self_exclude_for_real = bool(cfg.get("self_exclude_for_real", True))
    min_anchor_count = int(cfg.get("min_anchor_count", 4))
    max_anchor_samples = int(cfg.get("max_anchor_samples", 2000))

    anchor_ids: List[str] = []
    if anchor_from_source_real:
        for row in rows:
            if str(row.get("source", "")) != "real":
                continue
            sid = str(row.get("sample_id", ""))
            if sid and sid in image_embeddings:
                anchor_ids.append(sid)

    if max_anchor_samples > 0 and len(anchor_ids) > max_anchor_samples:
        anchor_ids = anchor_ids[:max_anchor_samples]

    out: Dict[str, Dict[str, float]] = {}
    if len(anchor_ids) < max(1, min_anchor_count):
        for row in rows:
            sid = str(row.get("sample_id", ""))
            out[sid] = {
                "s_semantic_anchor_raw": 0.0,
                "s_semantic_anchor": 0.0,
            }
        return out, {
            "enabled": False,
            "reason": "insufficient_anchor_embeddings",
            "anchor_count": len(anchor_ids),
            "reduce": reduce_name,
        }

    anchor_embs = [image_embeddings[sid] for sid in anchor_ids]
    for row in rows:
        sid = str(row.get("sample_id", ""))
        emb = image_embeddings.get(sid)
        if emb is None:
            out[sid] = {
                "s_semantic_anchor_raw": 0.0,
                "s_semantic_anchor": 0.0,
            }
            continue

        sims: List[float] = []
        for aid, aemb in zip(anchor_ids, anchor_embs):
            if self_exclude_for_real and sid == aid:
                continue
            sims.append(float((emb * aemb).sum().item()))
        s_raw = _reduce_similarity(sims, reduce_name) if sims else 0.0
        out[sid] = {
            "s_semantic_anchor_raw": s_raw,
            # map cosine range [-1, 1] to [0, 1]
            "s_semantic_anchor": max(0.0, min(1.0, (s_raw + 1.0) * 0.5)),
        }

    anchor_self = [out[sid]["s_semantic_anchor_raw"] for sid in anchor_ids if sid in out]
    return out, {
        "enabled": True,
        "reason": "",
        "anchor_count": len(anchor_ids),
        "reduce": reduce_name,
        "self_exclude_for_real": self_exclude_for_real,
        "min_anchor_count": min_anchor_count,
        "anchor_sem_raw_p50": _quantile(anchor_self, 0.50),
        "anchor_sem_raw_p95": _quantile(anchor_self, 0.95),
        "anchor_sem_raw_p99": _quantile(anchor_self, 0.99),
    }


def compute_paired_anchor_semantic_scores(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    cfg: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Pair-wise semantic score for real-guided synthetic samples:
      s_pair(x) = Sim(E(x), E(anchor(x)))
    where anchor(x) is resolved from row fields, typically `anchor_real_sample_id`.
    """
    anchor_sid_fields = [str(x) for x in cfg.get("anchor_sid_fields", ["anchor_real_sample_id"])]

    out: Dict[str, Dict[str, Any]] = {}
    hit = 0
    miss = 0

    for row in rows:
        sid = str(row.get("sample_id", ""))
        emb = image_embeddings.get(sid)
        if emb is None:
            out[sid] = {
                "s_semantic_pair_raw": 0.0,
                "s_semantic_pair": 0.0,
                "s_semantic_pair_hit": 0.0,
                "anchor_sid_resolved": "",
                "pair_miss_reason": "sample_embedding_missing",
            }
            miss += 1
            continue

        anchor_sid = ""
        for field in anchor_sid_fields:
            val = str(row.get(field, "")).strip()
            if val:
                anchor_sid = val
                break
        if not anchor_sid:
            out[sid] = {
                "s_semantic_pair_raw": 0.0,
                "s_semantic_pair": 0.0,
                "s_semantic_pair_hit": 0.0,
                "anchor_sid_resolved": "",
                "pair_miss_reason": "anchor_sid_missing",
            }
            miss += 1
            continue

        aemb = image_embeddings.get(anchor_sid)
        if aemb is None:
            out[sid] = {
                "s_semantic_pair_raw": 0.0,
                "s_semantic_pair": 0.0,
                "s_semantic_pair_hit": 0.0,
                "anchor_sid_resolved": anchor_sid,
                "pair_miss_reason": "anchor_embedding_missing",
            }
            miss += 1
            continue

        s_raw = float((emb * aemb).sum().item())
        out[sid] = {
            "s_semantic_pair_raw": s_raw,
            "s_semantic_pair": max(0.0, min(1.0, (s_raw + 1.0) * 0.5)),
            "s_semantic_pair_hit": 1.0,
            "anchor_sid_resolved": anchor_sid,
            "pair_miss_reason": "",
        }
        hit += 1

    return out, {
        "enabled": True,
        "anchor_sid_fields": anchor_sid_fields,
        "pair_hit_count": hit,
        "pair_miss_count": miss,
    }
