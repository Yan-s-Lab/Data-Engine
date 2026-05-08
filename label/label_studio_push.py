#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.manifest_io import read_jsonl


def make_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Token {token}"}


def build_tasks(rows: List[Dict[str, Any]], image_key: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for row in rows:
        if image_key not in row:
            continue
        tasks.append({"data": {"image": row[image_key]}, "meta": row})
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Push manifest tasks to Label Studio")
    parser.add_argument("--base-url", required=True, help="Label Studio base URL, e.g. http://localhost:8080")
    parser.add_argument("--token", required=True, help="Label Studio API token")
    parser.add_argument("--project-id", type=int, required=True, help="Label Studio project id")
    parser.add_argument("--manifest", type=Path, required=True, help="JSONL manifest path")
    parser.add_argument("--image-key", default="image_url", help="Field name that stores image URL")
    args = parser.parse_args()

    rows = read_jsonl(args.manifest)
    tasks = build_tasks(rows, args.image_key)
    if not tasks:
        raise SystemExit(f"No valid tasks found by image key: {args.image_key}")

    resp = requests.post(
        f"{args.base_url.rstrip('/')}/api/projects/{args.project_id}/import",
        headers=make_headers(args.token),
        json=tasks,
        timeout=120,
    )
    resp.raise_for_status()
    print(resp.json())


if __name__ == "__main__":
    main()
