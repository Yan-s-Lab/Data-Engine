from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .clip_embed_cache import ClipRuntime, cosine_similarity, image_text_logits, text_embedding


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    arr = sorted(float(v) for v in values)
    mid = len(arr) // 2
    if len(arr) % 2 == 1:
        return arr[mid]
    return float((arr[mid - 1] + arr[mid]) * 0.5)


def aggregate_compare_texts_group_scores(
    *,
    positive_logits: List[float],
    negative_logits: List[float],
) -> Dict[str, float]:
    if not positive_logits or not negative_logits:
        return {
            "s_prompt_pos": 0.0,
            "s_prompt_neg": 0.0,
            "s_prompt_margin": -1.0,
            "s_prompt_win_rate": 0.0,
            "s_prompt": 0.0,
        }

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
    s_pos = _median(positive_logits)
    s_neg = _median(negative_logits)
    s_margin = _median(pairwise)
    s_win_rate = win_score / len(pairwise) if pairwise else 0.0
    s_final = _clamp01(s_win_rate)
    return {
        "s_prompt_pos": float(s_pos),
        "s_prompt_neg": float(s_neg),
        "s_prompt_margin": float(s_margin),
        "s_prompt_win_rate": float(s_win_rate),
        "s_prompt": float(s_final),
    }


def _build_prompt_debug_rows(
    *,
    texts: List[str],
    polarity: str,
    row_logits: List[float],
    row_sigmoid: List[float],
) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    for idx, text in enumerate(texts):
        details.append(
            {
                "index": idx,
                "polarity": polarity,
                "text": text,
                "logit": float(row_logits[idx]),
                "sigmoid": float(row_sigmoid[idx]),
            }
        )
    return details


def _build_pairwise_matrix(
    *,
    positive_logits: List[float],
    negative_logits: List[float],
) -> Tuple[List[List[float]], List[float]]:
    matrix: List[List[float]] = []
    flat: List[float] = []
    for pos_logit in positive_logits:
        row: List[float] = []
        for neg_logit in negative_logits:
            margin = float(pos_logit - neg_logit)
            row.append(margin)
            flat.append(margin)
        matrix.append(row)
    return matrix, flat


def compute_compare_texts_prompt_scores(
    rows: List[Dict[str, Any]],
    runtime: ClipRuntime,
    *,
    compare_texts: Dict[str, List[str]],
) -> tuple[Dict[str, float], Dict[str, Any]]:
    from PIL import Image

    out: Dict[str, float] = {}
    sample_details: Dict[str, Dict[str, Any]] = {}
    positive_texts = [str(x).strip() for x in compare_texts.get("positive", []) if str(x).strip()]
    negative_texts = [str(x).strip() for x in compare_texts.get("negative", []) if str(x).strip()]
    if not positive_texts or not negative_texts:
        return {str(r.get("sample_id", "")): 0.0 for r in rows}, {
            "enabled": False,
            "reason": "compare_texts_requires_positive_and_negative",
            "groups": ["positive", "negative"],
        }

    miss_image_count = 0
    for row in rows:
        sid = str(row.get("sample_id", ""))
        image_path = Path(str(row.get("image_path", "")))
        if not image_path.exists():
            out[sid] = 0.0
            miss_image_count += 1
            continue

        flat_texts = positive_texts + negative_texts

        with Image.open(image_path) as img:
            image = img.convert("RGB")
            logits = image_text_logits(images=image, texts=flat_texts, runtime=runtime)
        row_logits = [float(x) for x in logits[0].tolist()]
        row_sigmoid = [float(x) for x in runtime.torch_mod.sigmoid(logits)[0].tolist()]

        agg = aggregate_compare_texts_group_scores(
            positive_logits=row_logits[: len(positive_texts)],
            negative_logits=row_logits[len(positive_texts) :],
        )
        out[sid] = agg["s_prompt"]
        pairwise_matrix, pairwise_flat = _build_pairwise_matrix(
            positive_logits=row_logits[: len(positive_texts)],
            negative_logits=row_logits[len(positive_texts) :],
        )
        sample_details[sid] = {
            "algorithm": "pairwise_logit_margin_win_rate",
            "reduce_mode": "median",
            "s_prompt": float(agg["s_prompt"]),
            "s_prompt_pos": float(agg["s_prompt_pos"]),
            "s_prompt_neg": float(agg["s_prompt_neg"]),
            "s_prompt_margin": float(agg["s_prompt_margin"]),
            "s_prompt_win_rate": float(agg["s_prompt_win_rate"]),
            "direct_prompt_scores_positive": _build_prompt_debug_rows(
                texts=positive_texts,
                polarity="positive",
                row_logits=row_logits[: len(positive_texts)],
                row_sigmoid=row_sigmoid[: len(positive_texts)],
            ),
            "direct_prompt_scores_negative": _build_prompt_debug_rows(
                texts=negative_texts,
                polarity="negative",
                row_logits=row_logits[len(positive_texts) :],
                row_sigmoid=row_sigmoid[len(positive_texts) :],
            ),
            "pairwise_margins": pairwise_matrix,
            "pairwise_margins_flat": pairwise_flat,
        }

    return out, {
        "enabled": True,
        "reason": "",
        "groups": ["positive", "negative"],
        "algorithm": "pairwise_logit_margin_win_rate",
        "group_reduce": "median",
        "positive_count": len(positive_texts),
        "negative_count": len(negative_texts),
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
