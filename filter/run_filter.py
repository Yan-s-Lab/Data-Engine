#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import write_json, write_jsonl
from filter.pipeline_engine import (
    apply_dual_signal_selection as _apply_dual_signal_selection_impl,
    inject_anchor_real_rows as _inject_anchor_real_rows,
    load_input_rows,
    resolve_filter_input_manifest as _resolve_filter_input_manifest,
    resolve_filter_input_manifests as _resolve_filter_input_manifests,
    resolve_filter_prompt_text as _resolve_filter_prompt_text,
    run_filter_pipeline,
)


def _apply_dual_signal_selection(
    score_rows: List[Dict[str, Any]],
    filter_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    return _apply_dual_signal_selection_impl(
        score_rows=score_rows,
        phase_cfg=dict(filter_cfg.get("phase1_dual_signal", {})),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter pipeline entrypoint")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)
    run_dir = resolve_run_dir(config)
    filter_cfg = config.get("filter", {})

    if not isinstance(filter_cfg, dict):
        raise ValueError("filter config must be a dict")

    mode = str(filter_cfg.get("mode", "compose")).strip().lower()
    if mode != "compose":
        raise ValueError(f"unsupported filter.mode: {mode}. Only compose is supported.")

    policy_cfg = dict(filter_cfg.get("policy", {}))
    decision_policy = str(policy_cfg.get("decision", "phase1_dual_signal")).strip().lower()
    if decision_policy != "phase1_dual_signal":
        raise ValueError("Only policy.decision=phase1_dual_signal is supported")

    prompt_source = _resolve_filter_prompt_text(filter_cfg=filter_cfg, config_path=config_path)
    clip_cfg = filter_cfg.get("clip")
    if prompt_source and isinstance(clip_cfg, dict):
        clip_cfg["prompt_text_source"] = prompt_source

    rows, input_state = load_input_rows(
        filter_cfg=filter_cfg,
        run_dir=run_dir,
        config_path=config_path,
    )

    filter_dir = run_dir / "filter"
    splits_dir = filter_dir / "splits"
    filter_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    score_rows, pipeline_report = run_filter_pipeline(
        rows=rows,
        filter_dir=filter_dir,
        filter_cfg=filter_cfg,
    )

    accept_set = {r["sample_id"] for r in score_rows if r.get("decision") == "accept"}
    reject_set = {r["sample_id"] for r in score_rows if r.get("decision") == "reject"}
    uncertain_set = {r["sample_id"] for r in score_rows if r.get("decision") == "uncertain"}

    accept_rows = [row for row in rows if str(row.get("sample_id", "")) in accept_set]
    reject_rows = [row for row in rows if str(row.get("sample_id", "")) in reject_set]
    uncertain_rows = [row for row in rows if str(row.get("sample_id", "")) in uncertain_set]

    write_jsonl(filter_dir / "manifest_in.jsonl", rows)
    write_jsonl(filter_dir / "filter_scores.jsonl", score_rows)
    write_jsonl(splits_dir / "accept.jsonl", accept_rows)
    write_jsonl(splits_dir / "reject.jsonl", reject_rows)
    write_jsonl(splits_dir / "uncertain.jsonl", uncertain_rows)

    report: Dict[str, Any] = {
        "stage": "filter",
        "mode": mode,
        "run_dir": str(run_dir),
        **input_state,
        "total": len(rows),
        "accept": len(accept_rows),
        "reject": len(reject_rows),
        "uncertain": len(uncertain_rows),
        "accept_ratio": round(len(accept_rows) / len(rows), 4) if rows else 0.0,
        **pipeline_report,
    }
    write_json(filter_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
