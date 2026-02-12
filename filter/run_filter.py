#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import read_jsonl, write_json, write_jsonl


def stable_score(sample_id: str) -> float:
    digest = hashlib.sha256(sample_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def build_stub_manifest(total_count: int, real_ratio: float) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    real_count = int(total_count * real_ratio)
    synth_count = total_count - real_count
    for i in range(real_count):
        sample_id = f"real_{i:04d}"
        rows.append(
            {
                "sample_id": sample_id,
                "source": "real",
                "image_path": f"data/real/{sample_id}.jpg",
            }
        )
    for i in range(synth_count):
        sample_id = f"synth_{i:04d}"
        rows.append(
            {
                "sample_id": sample_id,
                "source": "synthetic",
                "image_path": f"data/synth/{sample_id}.jpg",
            }
        )
    return rows

def main() -> None:
    parser = argparse.ArgumentParser(description="Filter stage stub with artifact outputs")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    filter_cfg = config.get("filter", {})

    input_manifest = filter_cfg.get("input_manifest")
    if input_manifest:
        rows = read_jsonl(Path(str(input_manifest)))
    else:
        rows = build_stub_manifest(
            total_count=int(filter_cfg.get("stub_total_count", 24)),
            real_ratio=float(filter_cfg.get("stub_real_ratio", 0.5)),
        )

    min_score = float(filter_cfg.get("accept_threshold", 0.6))
    uncertain_low = float(filter_cfg.get("uncertain_low", 0.45))
    uncertain_high = float(filter_cfg.get("uncertain_high", 0.6))

    filter_dir = run_dir / "filter"
    splits_dir = filter_dir / "splits"
    filter_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    score_rows: List[Dict[str, Any]] = []
    accept_rows: List[Dict[str, Any]] = []
    reject_rows: List[Dict[str, Any]] = []
    uncertain_rows: List[Dict[str, Any]] = []

    for row in rows:
        sample_id = str(row.get("sample_id", "unknown"))
        score = stable_score(sample_id)
        decision = "reject"
        if score >= min_score:
            decision = "accept"
            accept_rows.append(row)
        elif uncertain_low <= score < uncertain_high:
            decision = "uncertain"
            uncertain_rows.append(row)
        else:
            reject_rows.append(row)

        score_rows.append(
            {
                "sample_id": sample_id,
                "source": row.get("source"),
                "score_asf": round(score, 6),
                "score_pcs": round(1.0 - abs(score - 0.5) * 2.0, 6),
                "decision": decision,
            }
        )

    write_jsonl(filter_dir / "manifest_in.jsonl", rows)
    write_jsonl(filter_dir / "filter_scores.jsonl", score_rows)
    write_jsonl(splits_dir / "accept.jsonl", accept_rows)
    write_jsonl(splits_dir / "reject.jsonl", reject_rows)
    write_jsonl(splits_dir / "uncertain.jsonl", uncertain_rows)

    report = {
        "stage": "filter",
        "run_dir": str(run_dir),
        "total": len(rows),
        "accept": len(accept_rows),
        "reject": len(reject_rows),
        "uncertain": len(uncertain_rows),
        "accept_ratio": round(len(accept_rows) / len(rows), 4) if rows else 0.0,
        "thresholds": {
            "accept_threshold": min_score,
            "uncertain_low": uncertain_low,
            "uncertain_high": uncertain_high,
        },
    }
    write_json(filter_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
