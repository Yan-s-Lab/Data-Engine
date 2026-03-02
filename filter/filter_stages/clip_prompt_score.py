from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .clip_embed_cache import ClipRuntime, cosine_similarity, image_text_logits, text_embedding


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _reduce_group_scores(values: List[float], reduce_mode: str) -> float:
    if not values:
        return 0.0
    mode = str(reduce_mode).strip().lower()
    if mode == "mean":
        return float(sum(values) / len(values))
    if mode == "p75":
        arr = sorted(float(v) for v in values)
        if len(arr) == 1:
            return arr[0]
        pos = 0.75 * (len(arr) - 1)
        lo = int(pos)
        hi = min(lo + 1, len(arr) - 1)
        frac = pos - lo
        return arr[lo] * (1.0 - frac) + arr[hi] * frac
    return float(max(values))


def _weighted_mean(group_scores: Dict[str, float], groups: List[str], group_weights: Dict[str, float]) -> float:
    selected = [g for g in groups if g in group_scores]
    if not selected:
        return 0.0
    total = 0.0
    weight_sum = 0.0
    for g in selected:
        w = float(group_weights.get(g, 1.0))
        if w <= 0.0:
            w = 1.0
        total += w * float(group_scores[g])
        weight_sum += w
    if weight_sum <= 0.0:
        return 0.0
    return total / weight_sum


def aggregate_compare_texts_group_scores(
    group_scores: Dict[str, float],
    *,
    group_weights: Dict[str, float],
    negative_groups: List[str],
    negative_scale: float,
) -> Dict[str, float]:
    negative_set = {str(g).strip() for g in negative_groups if str(g).strip()}
    pos_groups = [g for g in group_scores.keys() if g not in negative_set]
    neg_groups = [g for g in group_scores.keys() if g in negative_set]

    s_pos = _weighted_mean(group_scores, pos_groups, group_weights)
    s_neg = _weighted_mean(group_scores, neg_groups, group_weights)
    neg_scale = max(0.0, float(negative_scale))
    if neg_groups:
        # Weighted blend of positive evidence and inverse negative evidence.
        s_final = (s_pos + neg_scale * (1.0 - s_neg)) / (1.0 + neg_scale)
    else:
        s_final = s_pos
    return {
        "s_prompt_pos": _clamp01(s_pos),
        "s_prompt_neg": _clamp01(s_neg),
        "s_prompt": _clamp01(s_final),
    }


def compute_compare_texts_prompt_scores(
    rows: List[Dict[str, Any]],
    runtime: ClipRuntime,
    *,
    compare_texts: Dict[str, List[str]],
    group_weights: Dict[str, float],
    group_reduce: str = "max",
    negative_groups: List[str] | None = None,
    negative_scale: float = 1.0,
) -> tuple[Dict[str, float], Dict[str, Any]]:
    from PIL import Image

    out: Dict[str, float] = {}
    negative_set = {
        str(g).strip()
        for g in (negative_groups if negative_groups is not None else [])
        if str(g).strip()
    }
    if not negative_set:
        negative_set = {g for g in compare_texts.keys() if g.strip().lower().startswith("neg")}

    non_empty_groups = {
        group: [str(x).strip() for x in texts if str(x).strip()]
        for group, texts in compare_texts.items()
        if isinstance(texts, list)
    }
    non_empty_groups = {k: v for k, v in non_empty_groups.items() if v}
    if not non_empty_groups:
        return {str(r.get("sample_id", "")): 0.0 for r in rows}, {
            "enabled": False,
            "reason": "compare_texts_empty",
            "groups": [],
        }

    miss_image_count = 0
    for row in rows:
        sid = str(row.get("sample_id", ""))
        image_path = Path(str(row.get("image_path", "")))
        if not image_path.exists():
            out[sid] = 0.0
            miss_image_count += 1
            continue

        flat_texts: List[str] = []
        group_spans: Dict[str, tuple[int, int]] = {}
        for group, texts in non_empty_groups.items():
            start = len(flat_texts)
            flat_texts.extend(texts)
            group_spans[group] = (start, len(flat_texts))

        with Image.open(image_path) as img:
            image = img.convert("RGB")
            logits = image_text_logits(images=image, texts=flat_texts, runtime=runtime)
        probs = runtime.torch_mod.sigmoid(logits)[0].tolist()

        group_scores: Dict[str, float] = {}
        for group, (start, end) in group_spans.items():
            group_scores[group] = _clamp01(_reduce_group_scores([float(x) for x in probs[start:end]], group_reduce))

        agg = aggregate_compare_texts_group_scores(
            group_scores,
            group_weights=group_weights,
            negative_groups=list(negative_set),
            negative_scale=negative_scale,
        )
        out[sid] = agg["s_prompt"]

    return out, {
        "enabled": True,
        "reason": "",
        "groups": list(non_empty_groups.keys()),
        "group_reduce": str(group_reduce).strip().lower() or "max",
        "group_weights": {k: float(group_weights.get(k, 1.0)) for k in non_empty_groups.keys()},
        "negative_groups": sorted(negative_set),
        "negative_scale": float(max(0.0, negative_scale)),
        "missing_image_count": miss_image_count,
    }


def compute_prompt_scores(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    runtime: ClipRuntime,
    prompt_text: str,
    prompt_score_mode: str = "cosine",
    prompt_field: str = "effective_prompt_text",
) -> Dict[str, float]:
    mode = str(prompt_score_mode).strip().lower()
    if mode == "siglip_sigmoid":
        from PIL import Image

        out_sigmoid: Dict[str, float] = {}
        for row in rows:
            sid = str(row.get("sample_id", ""))
            image_path = Path(str(row.get("image_path", "")))
            row_prompt = str(row.get(prompt_field, "")).strip() if prompt_field else ""
            active_prompt = row_prompt or prompt_text
            if not active_prompt.strip():
                out_sigmoid[sid] = 0.0
                continue
            if not image_path.exists():
                out_sigmoid[sid] = 0.0
                continue
            with Image.open(image_path) as img:
                image = img.convert("RGB")
                logits = image_text_logits(images=image, texts=[active_prompt], runtime=runtime)
            prob = runtime.torch_mod.sigmoid(logits)[0, 0].item()
            out_sigmoid[sid] = _clamp01(prob)
        return out_sigmoid

    out: Dict[str, float] = {}
    txt_emb_cache: Dict[str, Any] = {}
    for row in rows:
        sid = str(row.get("sample_id", ""))
        row_prompt = str(row.get(prompt_field, "")).strip() if prompt_field else ""
        active_prompt = row_prompt or prompt_text
        if not active_prompt.strip():
            out[sid] = 0.0
            continue
        emb = image_embeddings.get(sid)
        if emb is None:
            out[sid] = 0.0
            continue
        txt_emb = txt_emb_cache.get(active_prompt)
        if txt_emb is None:
            txt_emb = text_embedding(active_prompt, runtime=runtime)
            txt_emb_cache[active_prompt] = txt_emb
        sim = cosine_similarity(emb, txt_emb)
        # map [-1,1] -> [0,1]
        out[sid] = _clamp01((sim + 1.0) * 0.5)
    return out


def compute_prompt_margin_scores(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    runtime: ClipRuntime,
    pos_prompt: str,
    neg_prompts: List[str],
    prompt_score_mode: str = "cosine",
) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    sid_default = {
        str(r.get("sample_id", "")): {
            "s_prompt_pos": 0.0,
            "s_prompt_neg_max": 0.0,
            "s_prompt_margin": -1.0,
            "s_prompt_margin_norm": 0.0,
        }
        for r in rows
    }
    if not pos_prompt.strip():
        return sid_default

    mode = str(prompt_score_mode).strip().lower()
    if mode == "siglip_sigmoid":
        from PIL import Image

        neg_texts = [txt for txt in neg_prompts if str(txt).strip()]
        texts = [pos_prompt] + neg_texts
        for row in rows:
            sid = str(row.get("sample_id", ""))
            image_path = Path(str(row.get("image_path", "")))
            if not image_path.exists():
                out[sid] = sid_default.get(sid, {})
                continue

            with Image.open(image_path) as img:
                image = img.convert("RGB")
                logits = image_text_logits(images=image, texts=texts, runtime=runtime)
            row_logits = logits[0]
            s_pos = float(row_logits[0].item())
            if len(texts) > 1:
                s_neg_max = float(row_logits[1:].max().item())
            else:
                s_neg_max = 0.0
            margin = s_pos - s_neg_max

            out[sid] = {
                "s_prompt_pos": s_pos,
                "s_prompt_neg_max": s_neg_max,
                "s_prompt_margin": float(margin),
                "s_prompt_margin_norm": float(runtime.torch_mod.sigmoid(runtime.torch_mod.tensor(margin)).item()),
            }
        return out

    pos_emb = text_embedding(pos_prompt, runtime=runtime)
    neg_texts = [txt for txt in neg_prompts if str(txt).strip()]
    neg_embs = [text_embedding(txt, runtime=runtime) for txt in neg_texts]

    for row in rows:
        sid = str(row.get("sample_id", ""))
        emb = image_embeddings.get(sid)
        if emb is None:
            out[sid] = sid_default.get(sid, {})
            continue

        s_pos = cosine_similarity(emb, pos_emb)
        if neg_embs:
            neg_sims = [cosine_similarity(emb, nemb) for nemb in neg_embs]
            s_neg_max = max(neg_sims)
        else:
            s_neg_max = -1.0
        margin = s_pos - s_neg_max

        out[sid] = {
            "s_prompt_pos": float(s_pos),
            "s_prompt_neg_max": float(s_neg_max),
            "s_prompt_margin": float(margin),
            # CLIP cosine margin range is approximately [-2, 2].
            "s_prompt_margin_norm": max(0.0, min(1.0, (margin + 2.0) * 0.25)),
        }

    return out
