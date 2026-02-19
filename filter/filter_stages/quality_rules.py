from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _blur_score_laplacian_var(image_path: Path) -> float:
    from PIL import Image
    import numpy as np

    with Image.open(image_path) as img:
        arr = np.array(img.convert("L"), dtype=np.float32)

    # 3x3 Laplacian kernel (manual conv, no scipy dependency)
    pad = np.pad(arr, ((1, 1), (1, 1)), mode="edge")
    lap = (
        -4.0 * pad[1:-1, 1:-1]
        + pad[0:-2, 1:-1]
        + pad[2:, 1:-1]
        + pad[1:-1, 0:-2]
        + pad[1:-1, 2:]
    )
    return float(lap.var())


def _exposure_score(image_path: Path) -> float:
    from PIL import Image
    import numpy as np

    with Image.open(image_path) as img:
        arr = np.array(img.convert("L"), dtype=np.float32) / 255.0

    # Reward mid-tone occupancy, penalize clipping on both ends.
    low_clip = float((arr < 0.03).mean())
    high_clip = float((arr > 0.97).mean())
    mid_band = float(((arr >= 0.2) & (arr <= 0.85)).mean())
    score = mid_band - 0.5 * (low_clip + high_clip)
    return max(0.0, min(1.0, score))


def compute_quality_scores(rows: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    blur_good_threshold = float(cfg.get("blur_good_threshold", 80.0))

    out: Dict[str, Dict[str, float]] = {}
    for row in rows:
        sid = str(row.get("sample_id", ""))
        image_path = Path(str(row.get("image_path", "")))
        if not image_path.exists():
            out[sid] = {
                "blur_score": 0.0,
                "blur_norm": 0.0,
                "exposure_score": 0.0,
            }
            continue

        blur = _blur_score_laplacian_var(image_path)
        blur_norm = max(0.0, min(1.0, blur / max(1e-6, blur_good_threshold)))
        exposure = _exposure_score(image_path)

        out[sid] = {
            "blur_score": blur,
            "blur_norm": blur_norm,
            "exposure_score": exposure,
        }
    return out
