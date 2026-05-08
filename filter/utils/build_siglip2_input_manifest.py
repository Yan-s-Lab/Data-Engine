#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config
from common.filter_input_builder import (
    build_siglip2_filter_inputs,
    save_siglip2_filter_inputs_from_config,
)
from common.manifest_io import write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and save SigLIP2 filter input manifest")
    parser.add_argument("--config", required=True, help="Path to filter config yaml/json")
    parser.add_argument("--out", default="", help="Optional output jsonl path")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    out_path = Path(args.out).expanduser().resolve() if str(args.out).strip() else None
    config = load_config(config_path)

    filter_cfg = config.get("filter")
    if isinstance(filter_cfg, dict):
        saved = save_siglip2_filter_inputs_from_config(config_path, output_path=out_path)
        print(saved)
        return

    input_cfg = config.get("filter_input_configs")
    if not isinstance(input_cfg, dict):
        raise ValueError("config must contain `filter` or `filter_input_configs` mapping")

    rows = build_siglip2_filter_inputs(filter_cfg=input_cfg, config_path=config_path)
    if out_path is not None:
        saved = out_path
    else:
        output_raw = str(config.get("output", "")).strip()
        if not output_raw:
            raise ValueError("`output` is required when using `filter_input_configs`")
        saved = Path(output_raw)
        if not saved.is_absolute():
            saved = (config_path.parent / saved).resolve()
    write_jsonl(saved, rows)
    print(saved)


if __name__ == "__main__":
    main()
