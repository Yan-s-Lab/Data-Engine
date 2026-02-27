from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List

from common.manifest_io import write_jsonl


def _image_paths(image_dir: Path, patterns: List[str]) -> List[Path]:
    paths: List[Path] = []
    for pattern in patterns:
        paths.extend(sorted(image_dir.glob(pattern)))
    # De-duplicate while preserving order.
    seen: set[str] = set()
    out: List[Path] = []
    for p in paths:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _ctx(image_path: Path) -> Dict[str, str]:
    return {
        "stem": image_path.stem,
        "name": image_path.name,
        "suffix": image_path.suffix,
        "path": str(image_path),
        "parent": image_path.parent.name,
    }


def _render(template: str, context: Dict[str, str]) -> str:
    try:
        return template.format(**context)
    except Exception:
        return ""


def _build_real_rows(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    real_cfg = dict(cfg.get("real", {}))
    image_dir = Path(str(real_cfg.get("image_dir", "")).strip())
    if not image_dir.exists():
        raise FileNotFoundError(f"manifest_builder.real.image_dir not found: {image_dir}")
    patterns = [str(x) for x in real_cfg.get("patterns", ["*.png", "*.jpg", "*.jpeg"])]
    source = str(real_cfg.get("source", "real")).strip() or "real"
    sid_tpl = str(real_cfg.get("sample_id_template", "{stem}_real"))

    rows: List[Dict[str, Any]] = []
    for image_path in _image_paths(image_dir, patterns):
        c = _ctx(image_path)
        sid = _render(sid_tpl, c) or c["stem"]
        rows.append(
            {
                "sample_id": sid,
                "source": source,
                "image_path": str(image_path),
            }
        )
    return rows


def _anchor_from_regex(stem: str, anchor_cfg: Dict[str, Any]) -> str:
    pattern = str(anchor_cfg.get("pattern", "")).strip()
    if not pattern:
        return ""
    m = re.match(pattern, stem)
    if not m:
        return ""
    ctx = dict(m.groupdict())
    if not ctx:
        return ""
    template = str(anchor_cfg.get("template", "{anchor}_real"))
    return _render(template, {k: str(v) for k, v in ctx.items()})


def _build_synth_rows(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    synth_cfg = dict(cfg.get("synthetic", {}))
    groups = synth_cfg.get("groups", [])
    if not isinstance(groups, list):
        raise ValueError("manifest_builder.synthetic.groups must be a list")

    rows: List[Dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        image_dir = Path(str(group.get("image_dir", "")).strip())
        if not image_dir.exists():
            raise FileNotFoundError(f"manifest_builder.synthetic.groups.image_dir not found: {image_dir}")
        patterns = [str(x) for x in group.get("patterns", ["*.png", "*.jpg", "*.jpeg"])]
        source = str(group.get("source", "synthetic")).strip() or "synthetic"
        sid_tpl = str(group.get("sample_id_template", "{stem}"))
        anchor_cfg = dict(group.get("anchor", {}))
        anchor_field = str(anchor_cfg.get("field", "guide_image_id")).strip() or "guide_image_id"
        strict_anchor = bool(anchor_cfg.get("strict", False))

        for image_path in _image_paths(image_dir, patterns):
            c = _ctx(image_path)
            sid = _render(sid_tpl, c) or c["stem"]
            row: Dict[str, Any] = {
                "sample_id": sid,
                "source": source,
                "image_path": str(image_path),
            }

            if str(anchor_cfg.get("mode", "")).strip().lower() == "regex":
                anchor_sid = _anchor_from_regex(c["stem"], anchor_cfg)
                if anchor_sid:
                    row[anchor_field] = anchor_sid
                elif strict_anchor:
                    raise ValueError(
                        f"cannot resolve anchor for synthetic sample `{c['stem']}` with pattern `{anchor_cfg.get('pattern', '')}`"
                    )
            rows.append(row)
    return rows


def _scan_paths(roots: List[str], patterns: List[str]) -> List[Path]:
    all_paths: List[Path] = []
    for root in roots:
        base = Path(str(root).strip())
        if not base.exists():
            continue
        for pattern in patterns:
            all_paths.extend(sorted(base.glob(pattern)))
    seen: set[str] = set()
    out: List[Path] = []
    for p in all_paths:
        if not p.is_file():
            continue
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _build_filename_driven_rows(builder_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    fd_cfg = dict(builder_cfg.get("filename_driven", {}))
    if not bool(fd_cfg.get("enabled", False)):
        return []

    roots = [str(x) for x in fd_cfg.get("roots", []) if str(x).strip()]
    if not roots:
        raise ValueError("manifest_builder.filename_driven.roots must be non-empty when enabled")
    patterns = [str(x) for x in fd_cfg.get("patterns", ["**/*.png", "**/*.jpg", "**/*.jpeg"])]
    exclude_contains = [str(x) for x in fd_cfg.get("exclude_path_contains", [])]

    real_cfg = dict(fd_cfg.get("real", {}))
    real_source = str(real_cfg.get("source", "real")).strip() or "real"
    real_sid_tpl = str(real_cfg.get("sample_id_template", "{stem}_real"))

    synth_cfg = dict(fd_cfg.get("synthetic", {}))
    synth_source = str(synth_cfg.get("source", "synthetic")).strip() or "synthetic"
    synth_sid_tpl = str(synth_cfg.get("sample_id_template", "{stem}"))
    synth_pattern = str(synth_cfg.get("stem_pattern", "^(?P<anchor>.+)_[^_]+_[0-9]+$")).strip()
    synth_anchor_tpl = str(synth_cfg.get("anchor_template", "{anchor}_real"))
    synth_anchor_field = str(synth_cfg.get("anchor_field", "guide_image_id")).strip() or "guide_image_id"
    synth_anchor_strict = bool(synth_cfg.get("strict_anchor", True))
    synth_re = re.compile(synth_pattern)

    rows: List[Dict[str, Any]] = []
    for image_path in _scan_paths(roots=roots, patterns=patterns):
        path_text = str(image_path)
        if any(token and token in path_text for token in exclude_contains):
            continue

        c = _ctx(image_path)
        m = synth_re.match(c["stem"])
        if m:
            sid = _render(synth_sid_tpl, c) or c["stem"]
            row: Dict[str, Any] = {
                "sample_id": sid,
                "source": synth_source,
                "image_path": str(image_path),
            }
            gctx = {k: str(v) for k, v in m.groupdict().items()}
            anchor_sid = _render(synth_anchor_tpl, gctx)
            if anchor_sid:
                row[synth_anchor_field] = anchor_sid
            elif synth_anchor_strict:
                raise ValueError(
                    f"cannot resolve anchor from stem `{c['stem']}` with template `{synth_anchor_tpl}`"
                )
            rows.append(row)
            continue

        sid = _render(real_sid_tpl, c) or c["stem"]
        rows.append(
            {
                "sample_id": sid,
                "source": real_source,
                "image_path": str(image_path),
            }
        )
    return rows


def build_input_manifest_from_config(
    filter_cfg: Dict[str, Any],
    input_manifest_path: Path | None = None,
) -> List[Dict[str, Any]]:
    builder_cfg = dict(filter_cfg.get("manifest_builder", {}))
    if not bool(builder_cfg.get("enabled", False)):
        return []

    rows = _build_filename_driven_rows(builder_cfg)
    if not rows:
        real_rows = _build_real_rows(builder_cfg)
        synth_rows = _build_synth_rows(builder_cfg)
        rows = [*real_rows, *synth_rows]
    if not rows:
        raise RuntimeError("manifest_builder produced empty rows")

    output_path_cfg = str(builder_cfg.get("output_path", "")).strip()
    output_path = Path(output_path_cfg) if output_path_cfg else input_manifest_path
    if output_path is not None and bool(builder_cfg.get("write_output", True)):
        write_jsonl(output_path, rows)
    return rows
