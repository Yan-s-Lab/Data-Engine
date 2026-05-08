#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
OUTPUT_COUNTER_RE = re.compile(r"^(?P<prefix>.+)_(?P<idx>\d{5})_$")


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_output_counter(filename: str) -> Tuple[str, int] | None:
    stem = Path(filename).stem
    m = OUTPUT_COUNTER_RE.match(stem)
    if not m:
        return None
    return m.group("prefix"), int(m.group("idx"))


def detect_generation_mode(ref: Dict[str, Any]) -> str:
    graph = str(ref.get("comfy_prompt_graph_source", "")).lower()
    if "canny" in graph:
        return "prompt_canny"
    if "flux_dev" in graph or str(ref.get("effective_filename_prefix", "")).startswith("prompt_only"):
        return "prompt_only"
    return "unknown"


def choose_run_group(prefix_refs_by_run: Dict[str, List[Dict[str, Any]]], run_order: Dict[str, int]) -> str:
    # Prefer run group with most references for the same prefix.
    # If tie, prefer the run appearing later in user-provided list.
    best_run = ""
    best_key = (-1, -1)
    for run_id, refs in prefix_refs_by_run.items():
        key = (len(refs), run_order.get(run_id, -1))
        if key > best_key:
            best_key = key
            best_run = run_id
    return best_run


def build_manifest(
    output_dir: Path,
    synth_manifests: List[Path],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    output_files = sorted(
        p.name for p in output_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )

    run_order: Dict[str, int] = {}
    refs: List[Dict[str, Any]] = []
    for idx, manifest in enumerate(synth_manifests):
        run_id = manifest.parents[1].name
        run_order[run_id] = idx
        for row in read_jsonl(manifest):
            ref = dict(row)
            ref["_run_id"] = run_id
            ref["_manifest_path"] = str(manifest)
            refs.append(ref)

    by_comfy_filename: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_prefix_run: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for ref in refs:
        comfy_filename = str(ref.get("comfy_filename", "")).strip()
        if comfy_filename:
            by_comfy_filename[comfy_filename].append(ref)
        prefix = str(ref.get("effective_filename_prefix", "")).strip()
        comfy_filename = str(ref.get("comfy_filename", ""))
        comfy_type = str(ref.get("comfy_type", "")).lower()
        # Prefix fallback is only for temp-style names where exact filename cannot be reused.
        is_temp_style = comfy_type == "temp" or comfy_filename.startswith("ComfyUI_temp_")
        if prefix and is_temp_style:
            by_prefix_run[prefix][str(ref["_run_id"])].append(ref)

    rows: List[Dict[str, Any]] = []
    used_ref_ids: set[str] = set()

    exact_match_count = 0
    prefix_match_count = 0
    no_ref_count = 0
    ambiguous_exact_count = 0
    ambiguous_prefix_count = 0

    # Pass 1: exact comfy_filename match
    unmatched_output_files: List[str] = []
    for filename in output_files:
        candidates = by_comfy_filename.get(filename, [])
        if not candidates:
            unmatched_output_files.append(filename)
            continue
        chosen = candidates[0]
        if len(candidates) > 1:
            ambiguous_exact_count += 1
        used_ref_ids.add(f"{chosen['_manifest_path']}::{chosen.get('sample_id')}")
        exact_match_count += 1
        rows.append(
            {
                "sample_id": Path(filename).stem,
                "source": "synthetic",
                "image_path": str(output_dir / filename),
                "map_status": "matched",
                "map_method": "exact_comfy_filename",
                "map_ambiguous_candidates": len(candidates),
                "output_filename": filename,
                "reference_run_id": chosen.get("_run_id"),
                "reference_sample_id": chosen.get("sample_id"),
                "reference_manifest_path": chosen.get("_manifest_path"),
                "generation_mode": detect_generation_mode(chosen),
                "guide_image_id": chosen.get("guide_image_id", chosen.get("anchor_real_sample_id", "")),
                "anchor_real_image_path": chosen.get("anchor_real_image_path"),
                "guided_by_real": bool(
                    str(chosen.get("guide_image_id", chosen.get("anchor_real_sample_id", ""))).strip()
                ),
                "effective_filename_prefix": chosen.get("effective_filename_prefix"),
                "comfy_filename_ref": chosen.get("comfy_filename"),
            }
        )

    # Pass 2: prefix fallback
    grouped_unmatched: Dict[str, List[str]] = defaultdict(list)
    still_unmatched: List[str] = []
    for filename in unmatched_output_files:
        parsed = parse_output_counter(filename)
        if not parsed:
            still_unmatched.append(filename)
            continue
        prefix, _ = parsed
        grouped_unmatched[prefix].append(filename)

    for prefix, files in sorted(grouped_unmatched.items()):
        refs_by_run = by_prefix_run.get(prefix, {})
        if not refs_by_run:
            still_unmatched.extend(files)
            continue
        if len(refs_by_run) > 1:
            ambiguous_prefix_count += 1
        chosen_run = choose_run_group(refs_by_run, run_order)
        chosen_refs = refs_by_run[chosen_run]

        chosen_refs_sorted = sorted(chosen_refs, key=lambda r: str(r.get("sample_id", "")))
        files_sorted = sorted(files, key=lambda fn: parse_output_counter(fn)[1] if parse_output_counter(fn) else 0)
        pair_count = min(len(chosen_refs_sorted), len(files_sorted))

        for i in range(pair_count):
            ref = chosen_refs_sorted[i]
            filename = files_sorted[i]
            used_ref_ids.add(f"{ref['_manifest_path']}::{ref.get('sample_id')}")
            prefix_match_count += 1
            rows.append(
                {
                    "sample_id": Path(filename).stem,
                    "source": "synthetic",
                    "image_path": str(output_dir / filename),
                    "map_status": "matched",
                    "map_method": "prefix_fallback",
                    "map_ambiguous_candidates": len(refs_by_run),
                    "output_filename": filename,
                    "reference_run_id": ref.get("_run_id"),
                    "reference_sample_id": ref.get("sample_id"),
                    "reference_manifest_path": ref.get("_manifest_path"),
                    "generation_mode": detect_generation_mode(ref),
                    "guide_image_id": ref.get("guide_image_id", ref.get("anchor_real_sample_id", "")),
                    "anchor_real_image_path": ref.get("anchor_real_image_path"),
                    "guided_by_real": bool(
                        str(ref.get("guide_image_id", ref.get("anchor_real_sample_id", ""))).strip()
                    ),
                    "effective_filename_prefix": ref.get("effective_filename_prefix"),
                    "comfy_filename_ref": ref.get("comfy_filename"),
                }
            )

        for filename in files_sorted[pair_count:]:
            still_unmatched.append(filename)

    for filename in sorted(still_unmatched):
        no_ref_count += 1
        rows.append(
            {
                "sample_id": Path(filename).stem,
                "source": "synthetic",
                "image_path": str(output_dir / filename),
                "map_status": "no_reference",
                "map_method": "",
                "map_ambiguous_candidates": 0,
                "output_filename": filename,
                "reference_run_id": "",
                "reference_sample_id": "",
                "reference_manifest_path": "",
                "generation_mode": "unknown",
                "guide_image_id": "",
                "anchor_real_image_path": "",
                "guided_by_real": False,
                "effective_filename_prefix": "",
                "comfy_filename_ref": "",
            }
        )

    rows.sort(key=lambda r: str(r["output_filename"]))

    summary = {
        "output_dir": str(output_dir),
        "output_image_count": len(output_files),
        "reference_manifest_count": len(synth_manifests),
        "reference_row_count": len(refs),
        "matched_exact_count": exact_match_count,
        "matched_prefix_count": prefix_match_count,
        "no_reference_count": no_ref_count,
        "ambiguous_exact_filename_count": ambiguous_exact_count,
        "ambiguous_prefix_count": ambiguous_prefix_count,
        "matched_total_count": exact_match_count + prefix_match_count,
    }
    return rows, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build clean synthetic manifest from data/comfyui/output using synth_manifest references."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/comfyui/output"))
    parser.add_argument(
        "--synth-manifest",
        type=Path,
        action="append",
        required=True,
        help="Path to a synth_manifest.jsonl; can be specified multiple times.",
    )
    parser.add_argument("--out-jsonl", type=Path, required=True)
    parser.add_argument("--out-summary", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, summary = build_manifest(
        output_dir=args.output_dir,
        synth_manifests=args.synth_manifest,
    )
    write_jsonl(args.out_jsonl, rows)
    write_json(args.out_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
