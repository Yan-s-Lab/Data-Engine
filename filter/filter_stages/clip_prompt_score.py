from __future__ import annotations

from typing import Any, Dict, List

from .clip_embed_cache import ClipRuntime, cosine_similarity, text_embedding


def compute_prompt_scores(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    runtime: ClipRuntime,
    prompt_text: str,
) -> Dict[str, float]:
    if not prompt_text.strip():
        return {str(r.get("sample_id", "")): 0.0 for r in rows}

    txt_emb = text_embedding(prompt_text, runtime=runtime)
    out: Dict[str, float] = {}
    for row in rows:
        sid = str(row.get("sample_id", ""))
        emb = image_embeddings.get(sid)
        if emb is None:
            out[sid] = 0.0
            continue
        sim = cosine_similarity(emb, txt_emb)
        # map [-1,1] -> [0,1]
        out[sid] = max(0.0, min(1.0, (sim + 1.0) * 0.5))
    return out


def compute_prompt_margin_scores(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    runtime: ClipRuntime,
    pos_prompt: str,
    neg_prompts: List[str],
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
