from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Dict, List, Sequence, Tuple

import numpy as np


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    q = max(0.0, min(1.0, float(q)))
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    pos = q * (len(arr) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(arr) - 1)
    frac = pos - lo
    return arr[lo] * (1.0 - frac) + arr[hi] * frac


@dataclass
class DinoOodState:
    enabled: bool
    threshold_md2: float
    threshold_quantile: float
    anchor_count: int
    covariance_type: str
    diag_var_floor: float
    anchor_md2_p50: float
    anchor_md2_p95: float
    anchor_md2_p99: float
    reason: str = ""


class DinoV2StructureOODFilter:
    """
    DINOv2-based structure filter:
    1) Anchor Mahalanobis OOD (single-image distribution distance)
    2) Multi-crop consistency (single-image structure coherence)
    """

    def __init__(
        self,
        model_name: str = "facebook/dinov2-base",
        device: str = "cuda",
        eps: float = 1e-6,
        diag_var_floor: float = 1e-3,
    ) -> None:
        import torch  # type: ignore
        from transformers import AutoImageProcessor, AutoModel  # type: ignore

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.torch = torch
        self.device = device
        self.proc = AutoImageProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(device).eval()
        self.eps = float(eps)
        self.diag_var_floor = float(diag_var_floor)
        self.model_name = model_name

        self.mu = None
        self.inv_cov = None
        self.ood_state = DinoOodState(
            enabled=False,
            threshold_md2=0.0,
            threshold_quantile=0.99,
            anchor_count=0,
            covariance_type="",
            diag_var_floor=self.diag_var_floor,
            anchor_md2_p50=0.0,
            anchor_md2_p95=0.0,
            anchor_md2_p99=0.0,
            reason="not_fitted",
        )

    def _embed(self, images: List["Image.Image"]):  # type: ignore[name-defined]
        with self.torch.no_grad():
            inputs = self.proc(images=images, return_tensors="pt").to(self.device)
            out = self.model(**inputs)
            feats = out.last_hidden_state[:, 0, :]  # CLS token
            feats = feats / feats.norm(dim=-1, keepdim=True).clamp(min=1e-12)
        return feats

    def fit_anchor(
        self,
        anchor_images: List["Image.Image"],  # type: ignore[name-defined]
        *,
        max_n: int = 2000,
        batch: int = 64,
        threshold_quantile: float = 0.99,
        threshold_md2: float | None = None,
    ) -> DinoOodState:
        if not anchor_images:
            self.ood_state = DinoOodState(
                enabled=False,
                threshold_md2=0.0,
                threshold_quantile=threshold_quantile,
                anchor_count=0,
                covariance_type="",
                diag_var_floor=self.diag_var_floor,
                anchor_md2_p50=0.0,
                anchor_md2_p95=0.0,
                anchor_md2_p99=0.0,
                reason="empty_anchor_images",
            )
            return self.ood_state

        if len(anchor_images) > max_n:
            anchor_images = list(np.random.choice(anchor_images, max_n, replace=False))

        feats_all = []
        for i in range(0, len(anchor_images), max(1, batch)):
            feats_all.append(self._embed(anchor_images[i : i + batch]).detach().cpu())
        X = self.torch.cat(feats_all, dim=0)  # [N, D]

        if X.shape[0] < 4:
            self.ood_state = DinoOodState(
                enabled=False,
                threshold_md2=0.0,
                threshold_quantile=threshold_quantile,
                anchor_count=int(X.shape[0]),
                covariance_type="",
                diag_var_floor=self.diag_var_floor,
                anchor_md2_p50=0.0,
                anchor_md2_p95=0.0,
                anchor_md2_p99=0.0,
                reason="insufficient_anchor_embeddings",
            )
            return self.ood_state

        mu = X.mean(dim=0, keepdim=True)
        Xc = X - mu
        n, d = int(X.shape[0]), int(X.shape[1])
        if n < d:
            var = Xc.pow(2).mean(dim=0).clamp(min=max(self.eps, self.diag_var_floor))
            inv_cov = self.torch.diag(1.0 / var)
            covariance_type = "diag"
        else:
            cov = (Xc.T @ Xc) / max(1, n - 1)
            cov = cov + self.eps * self.torch.eye(cov.shape[0], dtype=cov.dtype)
            inv_cov = self.torch.linalg.pinv(cov)
            covariance_type = "full_pinv"

        self.mu = mu.squeeze(0)
        self.inv_cov = inv_cov

        md2_anchor: List[float] = []
        for i in range(X.shape[0]):
            dvec = X[i] - self.mu
            md2 = float((dvec.unsqueeze(0) @ self.inv_cov @ dvec.unsqueeze(1)).item())
            md2_anchor.append(md2)

        th_md2 = float(threshold_md2) if threshold_md2 is not None else _quantile(md2_anchor, threshold_quantile)
        self.ood_state = DinoOodState(
            enabled=True,
            threshold_md2=th_md2,
            threshold_quantile=threshold_quantile,
            anchor_count=int(X.shape[0]),
            covariance_type=covariance_type,
            diag_var_floor=self.diag_var_floor,
            anchor_md2_p50=_quantile(md2_anchor, 0.50),
            anchor_md2_p95=_quantile(md2_anchor, 0.95),
            anchor_md2_p99=_quantile(md2_anchor, 0.99),
        )
        return self.ood_state

    def score_ood(self, image: "Image.Image") -> float:  # type: ignore[name-defined]
        assert self.mu is not None and self.inv_cov is not None, "Call fit_anchor() first."
        x = self._embed([image])[0].detach().cpu()
        dvec = x - self.mu
        return float((dvec.unsqueeze(0) @ self.inv_cov @ dvec.unsqueeze(1)).item())

    def score_multicrop_consistency(
        self,
        image: "Image.Image",  # type: ignore[name-defined]
        *,
        n_random: int = 6,
        crop_frac: float = 0.45,
        seed: int = 42,
    ) -> float:
        rng = random.Random(seed)
        w, h = image.size
        crop_frac = max(0.05, min(0.95, float(crop_frac)))
        cw, ch = max(1, int(w * crop_frac)), max(1, int(h * crop_frac))

        crops = []
        cx1, cy1 = max(0, (w - cw) // 2), max(0, (h - ch) // 2)
        crops.append(image.crop((cx1, cy1, cx1 + cw, cy1 + ch)))
        for _ in range(max(0, int(n_random))):
            x1 = rng.randint(0, max(0, w - cw))
            y1 = rng.randint(0, max(0, h - ch))
            crops.append(image.crop((x1, y1, x1 + cw, y1 + ch)))

        feats = self._embed(crops)  # [N, D]
        sim = feats @ feats.T
        n = int(sim.shape[0])
        if n <= 1:
            return 0.0
        tri = self.torch.triu_indices(n, n, offset=1, device=sim.device)
        vals = sim[tri[0], tri[1]]
        return float(vals.mean().item())

    def keep(self, *, md2: float, consistency: float, md2_threshold: float, consistency_threshold: float) -> bool:
        return (md2 <= md2_threshold) and (consistency >= consistency_threshold)


def _load_images_from_rows(rows: List[Dict[str, str]]):
    from PIL import Image

    images = []
    for row in rows:
        p = Path(str(row.get("image_path", "")))
        if not p.exists():
            continue
        with Image.open(p) as img:
            images.append(img.convert("RGB").copy())
    return images


def score_rows_with_dino(
    rows: List[Dict[str, str]],
    *,
    anchor_rows: List[Dict[str, str]],
    model_name: str = "facebook/dinov2-base",
    device: str = "auto",
    eps: float = 1e-6,
    diag_var_floor: float = 1e-3,
    max_anchor_n: int = 2000,
    anchor_batch: int = 64,
    ood_threshold_quantile: float = 0.99,
    multicrop_n_random: int = 6,
    multicrop_crop_frac: float = 0.45,
    multicrop_seed_base: int = 20260214,
) -> Tuple[Dict[str, Dict[str, float]], DinoOodState]:
    from PIL import Image

    filt = DinoV2StructureOODFilter(
        model_name=model_name,
        device=device,
        eps=eps,
        diag_var_floor=diag_var_floor,
    )
    anchor_images = _load_images_from_rows(anchor_rows)
    ood_state = filt.fit_anchor(
        anchor_images,
        max_n=max_anchor_n,
        batch=anchor_batch,
        threshold_quantile=ood_threshold_quantile,
    )

    out: Dict[str, Dict[str, float]] = {}
    for row in rows:
        sid = str(row.get("sample_id", ""))
        p = Path(str(row.get("image_path", "")))
        if not p.exists():
            out[sid] = {
                "ood_md2": float(ood_state.threshold_md2 * 4.0 if ood_state.enabled else 0.0),
                "ood_score": 0.0 if ood_state.enabled else 1.0,
                "s_multicrop_consistency": 0.0,
            }
            continue
        with Image.open(p) as img:
            image = img.convert("RGB")
            consistency = filt.score_multicrop_consistency(
                image,
                n_random=multicrop_n_random,
                crop_frac=multicrop_crop_frac,
                seed=abs(hash((sid, multicrop_seed_base))) % (2**31),
            )
            if ood_state.enabled:
                md2 = filt.score_ood(image)
                ood_score = max(0.0, min(1.0, ood_state.threshold_md2 / max(md2, ood_state.threshold_md2)))
            else:
                md2 = 0.0
                ood_score = 1.0

        out[sid] = {
            "ood_md2": float(md2),
            "ood_score": float(ood_score),
            "s_multicrop_consistency": float(consistency),
        }
    return out, ood_state
