#!/usr/bin/env python
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minimal runnable milestone: filter -> train -> eval"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--python-bin",
        default="python",
        help="Python executable, e.g. `conda run -n open_data_engine python` is handled by shell wrapper",
    )
    args = parser.parse_args()

    py = args.python_bin
    run([py, "filter/run_filter.py", "--config", str(args.config)])
    run([py, "train/run_train.py", "--config", str(args.config)])
    run([py, "eval/run_eval.py", "--config", str(args.config)])
    print("minimal round done: filter -> train -> eval")


if __name__ == "__main__":
    main()
