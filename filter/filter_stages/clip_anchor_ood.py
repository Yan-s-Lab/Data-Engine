from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


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


def _collect_anchor_rows(rows: List[Dict[str, Any]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    use_source_real = bool(cfg.get("anchor_from_source_real", True))
    if use_source_real:
        out.extend([r for r in rows if str(r.get("source", "")) == "real"])

    anchor_manifest = cfg.get("anchor_manifest")
    if anchor_manifest:
        from common.manifest_io import read_jsonl

        out.extend(read_jsonl(Path(str(anchor_manifest))))

    anchor_image_dir = cfg.get("anchor_image_dir")
    if anchor_image_dir:
        img_dir = Path(str(anchor_image_dir))
        patterns = cfg.get("anchor_patterns", ["*.png", "*.jpg", "*.jpeg"])
        for p in patterns:
            for image_path in sorted(img_dir.glob(str(p))):
                out.append(
                    {
                        "sample_id": f"anchor_{image_path.stem}",
                        "source": "real",
                        "image_path": str(image_path),
                    }
                )
    return out


def fit_anchor_ood_stats(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    eps = float(cfg.get("eps", 1e-6))
    diag_var_floor = float(cfg.get("diag_var_floor", 1e-3))
    max_anchor_samples = int(cfg.get("max_anchor_samples", 2000))
    threshold_quantile = float(cfg.get("threshold_quantile", 0.99))

    anchor_rows = _collect_anchor_rows(rows=rows, cfg=cfg)
    anchor_embs: List[Any] = []
    anchor_sids: List[str] = []
    for row in anchor_rows:
        sid = str(row.get("sample_id", ""))
        emb = image_embeddings.get(sid)
        if emb is None:
            continue
        anchor_sids.append(sid)
        anchor_embs.append(emb.detach().cpu())

    if len(anchor_embs) > max_anchor_samples:
        anchor_embs = anchor_embs[:max_anchor_samples]
        anchor_sids = anchor_sids[:max_anchor_samples]

    if len(anchor_embs) < 4:
        return {
            "enabled": False,
            "reason": "insufficient_anchor_embeddings",
            "anchor_count": len(anchor_embs),
        }

    import torch  # type: ignore

    X = torch.stack(anchor_embs, dim=0)
    mu = X.mean(dim=0, keepdim=True)
    Xc = X - mu
    n = int(X.shape[0])
    d = int(X.shape[1])
    if n < d:
        # Small-sample regime: use diagonal covariance for stability.
        var = Xc.pow(2).mean(dim=0).clamp(min=max(eps, diag_var_floor))
        inv_cov = torch.diag(1.0 / var)
        covariance_type = "diag"
    else:
        cov = (Xc.T @ Xc) / max(1, Xc.shape[0] - 1)
        cov = cov + eps * torch.eye(cov.shape[0], dtype=cov.dtype)
        inv_cov = torch.linalg.pinv(cov)
        covariance_type = "full_pinv"

    md2_anchor: List[float] = []
    for i in range(X.shape[0]):
        d = X[i] - mu.squeeze(0)
        md2 = float((d.unsqueeze(0) @ inv_cov @ d.unsqueeze(1)).item())
        md2_anchor.append(md2)

    threshold = cfg.get("threshold")
    threshold_md2 = float(threshold) if threshold is not None else _quantile(md2_anchor, threshold_quantile)

    return {
        "enabled": True,
        "mu": mu.squeeze(0),
        "inv_cov": inv_cov,
        "threshold_md2": threshold_md2,
        "threshold_quantile": threshold_quantile,
        "anchor_count": int(X.shape[0]),
        "covariance_type": covariance_type,
        "diag_var_floor": diag_var_floor,
        "anchor_md2_p50": _quantile(md2_anchor, 0.50),
        "anchor_md2_p95": _quantile(md2_anchor, 0.95),
        "anchor_md2_p99": _quantile(md2_anchor, 0.99),
    }


def compute_anchor_ood_scores(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    ood_state: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    if not bool(ood_state.get("enabled", False)):
        for row in rows:
            sid = str(row.get("sample_id", ""))
            out[sid] = {
                "ood_md2": 0.0,
                "ood_score": 1.0,
            }
        return out

    mu = ood_state["mu"].detach().cpu()
    inv_cov = ood_state["inv_cov"].detach().cpu()
    threshold_md2 = float(ood_state["threshold_md2"])

    for row in rows:
        sid = str(row.get("sample_id", ""))
        emb = image_embeddings.get(sid)
        if emb is None:
            out[sid] = {
                "ood_md2": threshold_md2 * 4.0,
                "ood_score": 0.0,
            }
            continue

        x = emb.detach().cpu()
        d = x - mu
        md2 = float((d.unsqueeze(0) @ inv_cov @ d.unsqueeze(1)).item())
        # Monotonic bounded score for report weighting/debug, higher is better.
        ood_score = max(0.0, min(1.0, threshold_md2 / max(md2, threshold_md2)))
        out[sid] = {
            "ood_md2": md2,
            "ood_score": ood_score,
        }
    return out
