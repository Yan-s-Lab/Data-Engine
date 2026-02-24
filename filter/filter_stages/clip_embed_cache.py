from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _fingerprint(image_path: Path, model_id: str) -> str:
    st = image_path.stat()
    raw = f"{image_path.resolve()}|{st.st_size}|{st.st_mtime_ns}|{model_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ClipRuntime:
    torch_mod: Any
    model: Any
    processor: Any
    device: str
    model_id: str
    model_family: str


def load_clip_runtime(model_id: str, device_cfg: str) -> ClipRuntime:
    try:
        import torch  # type: ignore
        from transformers import AutoModel, AutoProcessor  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "clip stages require `torch` and `transformers`. "
            "Install them first, e.g. `pip install torch transformers`."
        ) from exc

    if device_cfg == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = device_cfg

    model = AutoModel.from_pretrained(model_id)
    processor = AutoProcessor.from_pretrained(model_id)
    model.to(device)
    model.eval()
    if not hasattr(model, "get_image_features") or not hasattr(model, "get_text_features"):
        raise RuntimeError(
            f"model `{model_id}` does not expose get_image_features/get_text_features; "
            "choose a CLIP/SigLIP-compatible vision-language model."
        )
    model_family = str(getattr(getattr(model, "config", None), "model_type", "unknown"))
    return ClipRuntime(
        torch_mod=torch,
        model=model,
        processor=processor,
        device=device,
        model_id=model_id,
        model_family=model_family,
    )


def image_embedding(image_path: Path, runtime: ClipRuntime) -> Any:
    from PIL import Image

    with Image.open(image_path) as img:
        image = img.convert("RGB")
        inputs = runtime.processor(images=image, return_tensors="pt")
    inputs = {k: v.to(runtime.device) for k, v in inputs.items()}
    with runtime.torch_mod.no_grad():
        feat = _extract_feature_tensor(runtime.model.get_image_features(**inputs))
        feat = _l2_normalize(feat, runtime=runtime)
    return feat[0]


def text_embedding(text: str, runtime: ClipRuntime) -> Any:
    inputs = runtime.processor(text=[text], return_tensors="pt", padding=True)
    inputs = {k: v.to(runtime.device) for k, v in inputs.items()}
    with runtime.torch_mod.no_grad():
        feat = _extract_feature_tensor(runtime.model.get_text_features(**inputs))
        feat = _l2_normalize(feat, runtime=runtime)
    return feat[0]


def cosine_similarity(vec_a: Any, vec_b: Any) -> float:
    return float((vec_a * vec_b).sum().item())


def image_text_logits(images: Any, texts: List[str], runtime: ClipRuntime) -> Any:
    inputs = runtime.processor(text=texts, images=images, return_tensors="pt", padding=True)
    inputs = {k: v.to(runtime.device) for k, v in inputs.items()}
    with runtime.torch_mod.no_grad():
        outputs = runtime.model(**inputs)
    logits = getattr(outputs, "logits_per_image", None)
    if logits is None:
        raise RuntimeError(
            f"model `{runtime.model_id}` does not return `logits_per_image`; "
            "siglip_sigmoid prompt mode is unavailable for this model."
        )
    return logits


def _extract_feature_tensor(feat: Any) -> Any:
    # Some model families return structured outputs instead of plain tensors.
    if hasattr(feat, "shape"):
        return feat
    for key in ("image_embeds", "text_embeds", "pooler_output"):
        val = getattr(feat, key, None)
        if val is not None and hasattr(val, "shape"):
            return val
    raise RuntimeError(
        "unable to extract feature tensor from model output; "
        "expected tensor-like output or one of image_embeds/text_embeds/pooler_output."
    )


def _l2_normalize(feat: Any, runtime: ClipRuntime) -> Any:
    # Ensure [batch, dim]
    if len(getattr(feat, "shape", [])) == 1:
        feat = feat.unsqueeze(0)
    return feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-12)


def _load_cache(cache_path: Path) -> Dict[str, List[float]]:
    if not cache_path.exists():
        return {}
    data = cache_path.read_text(encoding="utf-8")
    if not data.strip():
        return {}
    import json

    obj = json.loads(data)
    if not isinstance(obj, dict):
        return {}
    out: Dict[str, List[float]] = {}
    for k, v in obj.items():
        if isinstance(k, str) and isinstance(v, list):
            out[k] = [float(x) for x in v]
    return out


def _save_cache(cache_path: Path, cache: Dict[str, List[float]]) -> None:
    import json

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def build_image_embeddings(
    rows: List[Dict[str, Any]],
    model_id: str,
    device_cfg: str,
    cache_path: Path,
) -> Tuple[Dict[str, Any], ClipRuntime, Dict[str, Any]]:
    runtime = load_clip_runtime(model_id=model_id, device_cfg=device_cfg)
    cache = _load_cache(cache_path)

    result: Dict[str, Any] = {}
    miss_count = 0
    hit_count = 0

    for row in rows:
        sample_id = str(row.get("sample_id", ""))
        image_path = Path(str(row.get("image_path", "")))
        if not sample_id or not image_path.exists():
            continue

        key = _fingerprint(image_path=image_path, model_id=model_id)
        cached = cache.get(key)
        if cached is not None:
            emb = runtime.torch_mod.tensor(cached, dtype=runtime.torch_mod.float32, device=runtime.device)
            emb = emb / emb.norm(dim=-1, keepdim=False).clamp(min=1e-12)
            hit_count += 1
        else:
            emb = image_embedding(image_path=image_path, runtime=runtime)
            cache[key] = emb.detach().cpu().tolist()
            miss_count += 1

        result[sample_id] = emb

    _save_cache(cache_path=cache_path, cache=cache)
    stats = {
        "embed_cache_path": str(cache_path),
        "embed_cache_hit": hit_count,
        "embed_cache_miss": miss_count,
        "embed_cache_total": hit_count + miss_count,
    }
    return result, runtime, stats
