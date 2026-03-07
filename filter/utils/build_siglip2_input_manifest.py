#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.filter_input_builder import save_siglip2_filter_inputs_from_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and save SigLIP2 filter input manifest")
    parser.add_argument("--config", required=True, help="Path to filter config yaml/json")
    parser.add_argument("--out", default="", help="Optional output jsonl path")
    args = parser.parse_args()

    config_path = Path(args.config)
    out_path = Path(args.out).expanduser().resolve() if str(args.out).strip() else None
    saved = save_siglip2_filter_inputs_from_config(config_path, output_path=out_path)
    print(saved)


if __name__ == "__main__":
    main()
