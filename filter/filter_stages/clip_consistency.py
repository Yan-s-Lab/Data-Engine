from __future__ import annotations

import hashlib
from pathlib import Path
import random
from typing import Any, Dict, List, Tuple

from .clip_embed_cache import ClipRuntime, cosine_similarity, image_embedding


def _grid_boxes(width: int, height: int, rows: int, cols: int) -> List[Tuple[int, int, int, int]]:
    boxes: List[Tuple[int, int, int, int]] = []
    for r in range(rows):
        y0 = (height * r) // rows
        y1 = (height * (r + 1)) // rows
        for c in range(cols):
            x0 = (width * c) // cols
            x1 = (width * (c + 1)) // cols
            boxes.append((x0, y0, x1, y1))
    return boxes


def perturb_image_by_block_shuffle(
    image_path: Path,
    out_path: Path,
    rng: random.Random,
    grid_rows: int,
    grid_cols: int,
    swap_ratio: float,
    min_swaps: int,
    max_swaps: int,
) -> None:
    from PIL import Image

    with Image.open(image_path) as img:
        image = img.convert("RGB")
        width, height = image.size
        boxes = _grid_boxes(width, height, max(1, grid_rows), max(1, grid_cols))
        total = len(boxes)
        target = int(round(total * max(0.0, min(1.0, swap_ratio))))
        swaps = max(min_swaps, target)
        swaps = min(swaps, max_swaps, total)
        if swaps < 2:
            swaps = 2 if total >= 2 else 1

        picked = list(range(total))
        rng.shuffle(picked)
        picked = picked[:swaps]

        out = image.copy()
        patches = {idx: image.crop(boxes[idx]) for idx in picked}
        size_groups: Dict[Tuple[int, int], List[int]] = {}
        for idx in picked:
            box = boxes[idx]
            key = (box[2] - box[0], box[3] - box[1])
            size_groups.setdefault(key, []).append(idx)
        for group in size_groups.values():
            shuffled_group = group[:]
            rng.shuffle(shuffled_group)
            for src_idx, dst_idx in zip(group, shuffled_group):
                out.paste(patches[src_idx], boxes[dst_idx])
        out.save(out_path)


def compute_consistency_scores(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    runtime: ClipRuntime,
    cfg: Dict[str, Any],
    work_dir: Path,
) -> Dict[str, Dict[str, float]]:
    repeats = int(cfg.get("repeats", 4))
    grid_rows = int(cfg.get("grid_rows", 4))
    grid_cols = int(cfg.get("grid_cols", 4))
    swap_ratio = float(cfg.get("swap_ratio", 0.4))
    min_swaps = int(cfg.get("min_swaps", 2))
    max_swaps = int(cfg.get("max_swaps", 8))
    seed_base = int(cfg.get("seed_base", 20260214))
    keep_perturbed_images = bool(cfg.get("keep_perturbed_images", False))

    perturb_dir = work_dir / "perturb_preview"
    if keep_perturbed_images:
        perturb_dir.mkdir(parents=True, exist_ok=True)

    out: Dict[str, Dict[str, float]] = {}
    for row in rows:
        sid = str(row.get("sample_id", ""))
        image_path = Path(str(row.get("image_path", "")))
        orig_emb = image_embeddings.get(sid)

        if orig_emb is None or not image_path.exists():
            out[sid] = {
                "s_consistency": 0.0,
                "pcs_similarity_min": 0.0,
                "pcs_similarity_max": 0.0,
                "pcs_similarity_mean": 0.0,
                "pcs_repeats": 0.0,
            }
            continue

        sims: List[float] = []
        for k in range(max(1, repeats)):
            digest = hashlib.sha256(f"{sid}|{seed_base}|{k}".encode("utf-8")).hexdigest()
            rng = random.Random(int(digest[:8], 16))
            tmp_path = (
                perturb_dir / f"{sid}.perturb_{k:02d}.png"
                if keep_perturbed_images
                else work_dir / f".tmp_{sid}_{k}.png"
            )
            perturb_image_by_block_shuffle(
                image_path=image_path,
                out_path=tmp_path,
                rng=rng,
                grid_rows=grid_rows,
                grid_cols=grid_cols,
                swap_ratio=swap_ratio,
                min_swaps=min_swaps,
                max_swaps=max_swaps,
            )
            emb = image_embedding(image_path=tmp_path, runtime=runtime)
            sims.append(cosine_similarity(orig_emb, emb))
            if not keep_perturbed_images and tmp_path.exists():
                tmp_path.unlink()

        mean_sim = sum(sims) / len(sims) if sims else 0.0
        out[sid] = {
            "s_consistency": mean_sim,
            "pcs_similarity_min": min(sims) if sims else 0.0,
            "pcs_similarity_max": max(sims) if sims else 0.0,
            "pcs_similarity_mean": mean_sim,
            "pcs_repeats": float(len(sims)),
        }
    return out


def _gen_multicrop_boxes(
    width: int,
    height: int,
    n_random: int,
    crop_frac: float,
    rng: random.Random,
) -> List[Tuple[int, int, int, int]]:
    crop_frac = max(0.05, min(0.95, crop_frac))
    cw = max(1, int(width * crop_frac))
    ch = max(1, int(height * crop_frac))

    boxes: List[Tuple[int, int, int, int]] = []
    cx1 = max(0, (width - cw) // 2)
    cy1 = max(0, (height - ch) // 2)
    boxes.append((cx1, cy1, cx1 + cw, cy1 + ch))

    for _ in range(max(0, n_random)):
        x1 = rng.randint(0, max(0, width - cw))
        y1 = rng.randint(0, max(0, height - ch))
        boxes.append((x1, y1, x1 + cw, y1 + ch))
    return boxes


def _extract_feature_tensor(feat: Any) -> Any:
    if hasattr(feat, "shape"):
        return feat
    for key in ("image_embeds", "text_embeds", "pooler_output"):
        val = getattr(feat, key, None)
        if val is not None and hasattr(val, "shape"):
            return val
    raise RuntimeError(
        "unable to extract feature tensor from model output in multicrop stage; "
        "expected tensor-like output or one of image_embeds/text_embeds/pooler_output."
    )


def compute_multicrop_consistency_scores(
    rows: List[Dict[str, Any]],
    runtime: ClipRuntime,
    cfg: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    from PIL import Image

    n_random = int(cfg.get("n_random", 6))
    crop_frac = float(cfg.get("crop_frac", 0.45))
    seed_base = int(cfg.get("seed_base", 20260214))

    out: Dict[str, Dict[str, float]] = {}
    for row in rows:
        sid = str(row.get("sample_id", ""))
        image_path = Path(str(row.get("image_path", "")))
        if not image_path.exists():
            out[sid] = {
                "s_multicrop_consistency": 0.0,
                "multicrop_pair_sim_min": 0.0,
                "multicrop_pair_sim_max": 0.0,
                "multicrop_pair_sim_mean": 0.0,
                "multicrop_views": 0.0,
            }
            continue

        with Image.open(image_path) as img:
            image = img.convert("RGB")
            width, height = image.size
            digest = hashlib.sha256(f"{sid}|{seed_base}".encode("utf-8")).hexdigest()
            rng = random.Random(int(digest[:8], 16))
            boxes = _gen_multicrop_boxes(
                width,
                height,
                n_random=n_random,
                crop_frac=crop_frac,
                rng=rng,
            )
            views = [image.crop(box) for box in boxes]
            inputs = runtime.processor(images=views, return_tensors="pt")
        inputs = {k: v.to(runtime.device) for k, v in inputs.items()}
        with runtime.torch_mod.no_grad():
            feats = _extract_feature_tensor(runtime.model.get_image_features(**inputs))
            feats = feats / feats.norm(dim=-1, keepdim=True).clamp(min=1e-12)

            sim = feats @ feats.T
            n = int(sim.shape[0])
            if n <= 1:
                mean_pair = 0.0
                min_pair = 0.0
                max_pair = 0.0
            else:
                tri = runtime.torch_mod.triu_indices(n, n, offset=1, device=sim.device)
                vals = sim[tri[0], tri[1]]
                mean_pair = float(vals.mean().item())
                min_pair = float(vals.min().item())
                max_pair = float(vals.max().item())

        out[sid] = {
            "s_multicrop_consistency": mean_pair,
            "multicrop_pair_sim_min": min_pair,
            "multicrop_pair_sim_max": max_pair,
            "multicrop_pair_sim_mean": mean_pair,
            "multicrop_views": float(len(views)),
        }
    return out
