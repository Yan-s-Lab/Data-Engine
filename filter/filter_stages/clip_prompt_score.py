from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .clip_embed_cache import ClipRuntime, cosine_similarity, image_text_logits, text_embedding


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _reduce_group_scores(values: List[float], reduce_mode: str) -> float:
    if not values:
        return 0.0
    mode = str(reduce_mode).strip().lower()
    if mode == "mean":
        return float(sum(values) / len(values))
    if mode == "median":
        arr = sorted(float(v) for v in values)
        mid = len(arr) // 2
        if len(arr) % 2 == 1:
            return arr[mid]
        return float((arr[mid - 1] + arr[mid]) * 0.5)
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


def aggregate_compare_texts_group_scores(
    *,
    positive_logits: List[float],
    negative_logits: List[float],
    reduce_mode: str,
) -> Dict[str, float]:
    if positive_logits and negative_logits:
        pairwise: List[float] = []
        win_score = 0.0
        for s_pos in positive_logits:
            for s_neg in negative_logits:
                margin = float(s_pos - s_neg)
                pairwise.append(margin)
                if margin > 0.0:
                    win_score += 1.0
                elif margin == 0.0:
                    win_score += 0.5
        s_pos = _reduce_group_scores(positive_logits, reduce_mode)
        s_neg = _reduce_group_scores(negative_logits, reduce_mode)
        s_margin = _reduce_group_scores(pairwise, reduce_mode)
        s_win_rate = win_score / len(pairwise) if pairwise else 0.0
        s_final = _clamp01(s_win_rate)
        return {
            "s_prompt_pos": float(s_pos),
            "s_prompt_neg": float(s_neg),
            "s_prompt_margin": float(s_margin),
            "s_prompt_win_rate": float(s_win_rate),
            "s_prompt": float(s_final),
        }

    if positive_logits:
        s_pos = _reduce_group_scores(positive_logits, reduce_mode)
        s_final = _clamp01((1.0 + float(s_pos) / (1.0 + abs(float(s_pos)))) * 0.5)
        return {
            "s_prompt_pos": float(s_pos),
            "s_prompt_neg": 0.0,
            "s_prompt_margin": float(s_pos),
            "s_prompt_win_rate": float(s_final),
            "s_prompt": float(s_final),
        }
    if negative_logits:
        s_neg = _reduce_group_scores(negative_logits, reduce_mode)
        s_final = _clamp01(1.0 - (1.0 + float(s_neg) / (1.0 + abs(float(s_neg)))) * 0.5)
        return {
            "s_prompt_pos": 0.0,
            "s_prompt_neg": float(s_neg),
            "s_prompt_margin": -float(s_neg),
            "s_prompt_win_rate": float(s_final),
            "s_prompt": float(s_final),
        }
    return {
        "s_prompt_pos": 0.0,
        "s_prompt_neg": 0.0,
        "s_prompt_margin": -1.0,
        "s_prompt_win_rate": 0.0,
        "s_prompt": 0.0,
    }


def _build_prompt_debug_rows(
    *,
    flat_texts: List[str],
    flat_groups: List[str],
    positive_indices: List[int],
    negative_indices: List[int],
    row_logits: List[float],
    row_sigmoid: List[float],
) -> List[Dict[str, Any]]:
    pos_set = set(positive_indices)
    neg_set = set(negative_indices)
    details: List[Dict[str, Any]] = []
    for idx, text in enumerate(flat_texts):
        if idx in pos_set:
            polarity = "positive"
        elif idx in neg_set:
            polarity = "negative"
        else:
            polarity = "neutral"
        details.append(
            {
                "index": idx,
                "group": flat_groups[idx],
                "polarity": polarity,
                "text": text,
                "logit": float(row_logits[idx]),
                "sigmoid": float(row_sigmoid[idx]),
            }
        )
    return details


def _build_pairwise_matrix(
    *,
    positive_indices: List[int],
    negative_indices: List[int],
    row_logits: List[float],
) -> Tuple[List[List[float]], List[float]]:
    matrix: List[List[float]] = []
    flat: List[float] = []
    for pos_idx in positive_indices:
        row: List[float] = []
        for neg_idx in negative_indices:
            margin = float(row_logits[pos_idx] - row_logits[neg_idx])
            row.append(margin)
            flat.append(margin)
        matrix.append(row)
    return matrix, flat


def compute_compare_texts_prompt_scores(
    rows: List[Dict[str, Any]],
    runtime: ClipRuntime,
    *,
    compare_texts: Dict[str, List[str]],
    group_reduce: str = "max",
    negative_groups: List[str] | None = None,
) -> tuple[Dict[str, float], Dict[str, Any]]:
    from PIL import Image

    out: Dict[str, float] = {}
    sample_details: Dict[str, Dict[str, Any]] = {}
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
        flat_groups: List[str] = []
        positive_indices: List[int] = []
        negative_indices: List[int] = []
        for group, texts in non_empty_groups.items():
            for text in texts:
                idx = len(flat_texts)
                flat_texts.append(text)
                flat_groups.append(group)
                if group in negative_set:
                    negative_indices.append(idx)
                else:
                    positive_indices.append(idx)

        with Image.open(image_path) as img:
            image = img.convert("RGB")
            logits = image_text_logits(images=image, texts=flat_texts, runtime=runtime)
        row_logits = [float(x) for x in logits[0].tolist()]
        row_sigmoid = [float(x) for x in runtime.torch_mod.sigmoid(logits)[0].tolist()]

        agg = aggregate_compare_texts_group_scores(
            positive_logits=[row_logits[i] for i in positive_indices],
            negative_logits=[row_logits[i] for i in negative_indices],
            reduce_mode=group_reduce,
        )
        out[sid] = agg["s_prompt"]
        pairwise_matrix, pairwise_flat = _build_pairwise_matrix(
            positive_indices=positive_indices,
            negative_indices=negative_indices,
            row_logits=row_logits,
        )
        sample_details[sid] = {
            "algorithm": "pairwise_logit_margin_win_rate",
            "reduce_mode": str(group_reduce).strip().lower() or "max",
            "s_prompt": float(agg["s_prompt"]),
            "s_prompt_pos": float(agg["s_prompt_pos"]),
            "s_prompt_neg": float(agg["s_prompt_neg"]),
            "s_prompt_margin": float(agg["s_prompt_margin"]),
            "s_prompt_win_rate": float(agg["s_prompt_win_rate"]),
            "direct_prompt_scores": _build_prompt_debug_rows(
                flat_texts=flat_texts,
                flat_groups=flat_groups,
                positive_indices=positive_indices,
                negative_indices=negative_indices,
                row_logits=row_logits,
                row_sigmoid=row_sigmoid,
            ),
            "pairwise_margins": pairwise_matrix,
            "pairwise_margins_flat": pairwise_flat,
        }

    return out, {
        "enabled": True,
        "reason": "",
        "groups": list(non_empty_groups.keys()),
        "algorithm": "pairwise_logit_margin_win_rate",
        "group_reduce": str(group_reduce).strip().lower() or "max",
        "negative_groups": sorted(negative_set),
        "missing_image_count": miss_image_count,
        "sample_details": sample_details,
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
