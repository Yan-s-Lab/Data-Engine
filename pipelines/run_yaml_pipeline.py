#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir

STAGE_TO_SCRIPT = {
    "dataloader": "ingest/run_dataloader.py",
    "generate": "synth/run_generate.py",
    "filter": "filter/run_filter.py",
    "train": "train/run_train.py",
    "eval": "eval/run_eval.py",
}


def run(cmd: List[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def build_runtime_config(config: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(config)
    run_dir = resolve_run_dir(cfg)

    gen_cfg = dict(cfg.get("generate", {}))
    gen_cfg.setdefault("real_manifest", str(run_dir / "dataloader" / "real_manifest.jsonl"))
    cfg["generate"] = gen_cfg

    filter_cfg = dict(cfg.get("filter", {}))
    filter_cfg.setdefault("input_manifest", str(run_dir / "generate" / "mixed_manifest.jsonl"))
    cfg["filter"] = filter_cfg
    return cfg


def stage_output_ok(stage: str, run_dir: Path) -> bool:
    expected = {
        "dataloader": run_dir / "dataloader" / "real_manifest.jsonl",
        "generate": run_dir / "generate" / "mixed_manifest.jsonl",
        "filter": run_dir / "filter" / "splits" / "accept.jsonl",
        "train": run_dir / "train" / "model_stub.json",
        "eval": run_dir / "eval" / "policy_feedback.json",
    }[stage]
    return expected.exists()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YAML-configurable single-node closed-loop pipeline"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--python-bin", default="python")
    args = parser.parse_args()

    raw_cfg = load_config(args.config)
    runtime_cfg = build_runtime_config(raw_cfg)
    run_dir = resolve_run_dir(runtime_cfg)
    pipeline_dir = run_dir / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    runtime_cfg_path = pipeline_dir / "runtime_config.json"
    runtime_cfg_path.write_text(json.dumps(runtime_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    steps = runtime_cfg.get("pipeline", {}).get(
        "steps", ["dataloader", "generate", "filter", "train", "eval"]
    )
    if not isinstance(steps, list) or not steps:
        raise ValueError("pipeline.steps must be a non-empty list")

    for stage in steps:
        if stage not in STAGE_TO_SCRIPT:
            raise ValueError(f"unsupported stage in pipeline.steps: {stage}")
        script = STAGE_TO_SCRIPT[stage]
        run([args.python_bin, script, "--config", str(runtime_cfg_path)])
        if not stage_output_ok(stage, run_dir):
            raise RuntimeError(f"stage `{stage}` completed but expected artifact is missing")

    summary = {
        "run_dir": str(run_dir),
        "runtime_config": str(runtime_cfg_path),
        "steps": steps,
        "status": "ok",
    }
    (pipeline_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
