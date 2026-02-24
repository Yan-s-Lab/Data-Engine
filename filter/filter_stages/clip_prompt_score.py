from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .clip_embed_cache import ClipRuntime, cosine_similarity, image_text_logits, text_embedding


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
            out_sigmoid[sid] = max(0.0, min(1.0, float(prob)))
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
        out[sid] = max(0.0, min(1.0, (sim + 1.0) * 0.5))
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
