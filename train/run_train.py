#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import read_jsonl, write_json, write_jsonl


def ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train stage stub with artifact outputs")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    run_dir = resolve_run_dir(config)
    train_cfg = config.get("train", {})

    accept_manifest = Path(
        str(train_cfg.get("accept_manifest", run_dir / "filter" / "splits" / "accept.jsonl"))
    )
    if not accept_manifest.exists():
        raise FileNotFoundError(f"missing filter accept artifact: {accept_manifest}")

    accepted_rows = read_jsonl(accept_manifest)
    train_manifest = accepted_rows[: int(train_cfg.get("max_train_samples", len(accepted_rows)))]

    train_dir = run_dir / "train"
    model_dir = train_dir / "models"
    train_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    real_count = sum(1 for row in train_manifest if row.get("source") == "real")
    synth_count = sum(1 for row in train_manifest if row.get("source") == "synthetic")
    total = len(train_manifest)

    mix_report = {
        "total_train_samples": total,
        "real_count": real_count,
        "synthetic_count": synth_count,
        "real_ratio": ratio(real_count, total),
        "synthetic_ratio": ratio(synth_count, total),
    }

    # Deterministic pseudo metric that improves with more balanced mix and sample count.
    balance_penalty = abs(mix_report["real_ratio"] - 0.5)
    quality = 0.5 + min(total / 100.0, 0.35) - balance_penalty * 0.15
    train_metric = max(0.0, min(0.99, round(quality, 4)))

    model_stub = {
        "model_name": str(train_cfg.get("model_name", "stub_detector_v0")),
        "checkpoint_path": str(model_dir / "model_stub.bin"),
        "train_metric": train_metric,
        "source_run_dir": str(run_dir),
    }

    (model_dir / "model_stub.bin").write_text("stub model bytes\n", encoding="utf-8")
    write_jsonl(train_dir / "train_manifest.jsonl", train_manifest)
    write_json(train_dir / "mix_report.json", mix_report)
    write_json(train_dir / "model_stub.json", model_stub)

    out = {
        "stage": "train",
        "run_dir": str(run_dir),
        "model_stub": str(train_dir / "model_stub.json"),
        "train_metric": train_metric,
        "train_samples": total,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
