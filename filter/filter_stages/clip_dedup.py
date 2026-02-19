from __future__ import annotations

from typing import Any, Dict, List


def compute_duplicate_similarity(
    rows: List[Dict[str, Any]],
    image_embeddings: Dict[str, Any],
    synthetic_only: bool = False,
) -> Dict[str, float]:
    # Brute-force cosine max similarity for small/medium research runs.
    candidates = rows
    if synthetic_only:
        candidates = [r for r in rows if str(r.get("source", "")) == "synthetic"]

    ids: List[str] = []
    embs: List[Any] = []
    for row in candidates:
        sid = str(row.get("sample_id", ""))
        emb = image_embeddings.get(sid)
        if not sid or emb is None:
            continue
        ids.append(sid)
        embs.append(emb)

    out: Dict[str, float] = {str(r.get("sample_id", "")): 0.0 for r in rows}
    if len(ids) <= 1:
        return out

    torch_mod = embs[0].__class__.__module__.split(".")[0]
    if torch_mod != "torch":
        return out

    import torch  # type: ignore

    mat = torch.stack(embs, dim=0)
    sim = mat @ mat.T
    n = sim.shape[0]
    eye = torch.eye(n, dtype=sim.dtype, device=sim.device)
    sim = sim - eye * 2.0

    max_sim, _ = sim.max(dim=1)
    for sid, v in zip(ids, max_sim.tolist()):
        out[sid] = float(v)
    return out
