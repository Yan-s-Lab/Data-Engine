from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _normalize_group_values(raw_values: Any) -> List[str]:
    if not isinstance(raw_values, list):
        return []
    values: List[str] = []
    for item in raw_values:
        text = str(item).strip()
        if text:
            values.append(text)
    return values


def resolve_prompt_groups(clip_cfg: Dict[str, Any]) -> Tuple[Dict[str, List[str]], str]:
    """
    Resolve positive/negative prompt groups from the supported config keys.

    Precedence:
      1) compare-texts
      2) compare_texts
      3) compared_prompt
    """
    for key in ("compare-texts", "compare_texts", "compared_prompt"):
        raw = clip_cfg.get(key, {})
        if not isinstance(raw, dict):
            continue
        groups = {
            "positive": _normalize_group_values(raw.get("positive", [])),
            "negative": _normalize_group_values(raw.get("negative", [])),
        }
        if groups["positive"] and groups["negative"]:
            return groups, f"clip.{key}"

    return {"positive": [], "negative": []}, ""
