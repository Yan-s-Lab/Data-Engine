#!/usr/bin/env python
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval stage placeholder")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    print({"stage": "eval", "config": args.config, "status": "todo"})


if __name__ == "__main__":
    main()
