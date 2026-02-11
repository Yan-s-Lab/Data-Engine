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

from common.manifest_io import write_jsonl


def make_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Token {token}"}


def fetch_tasks(base_url: str, token: str, project_id: int, page_size: int = 100) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    page = 1

    while True:
        resp = requests.get(
            f"{base_url.rstrip('/')}/api/tasks",
            headers=make_headers(token),
            params={"project": project_id, "page": page, "page_size": page_size},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            break

        tasks.extend(results)
        if not data.get("next"):
            break
        page += 1

    return tasks


def flatten_annotations(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for task in tasks:
        task_id = task.get("id")
        data = task.get("data", {})
        anns = task.get("annotations", [])
        if not anns:
            rows.append({"task_id": task_id, "data": data, "has_annotation": False})
            continue

        for ann in anns:
            rows.append(
                {
                    "task_id": task_id,
                    "annotation_id": ann.get("id"),
                    "created_at": ann.get("created_at"),
                    "updated_at": ann.get("updated_at"),
                    "completed_by": ann.get("completed_by"),
                    "result": ann.get("result", []),
                    "data": data,
                    "has_annotation": True,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull labels from Label Studio tasks API")
    parser.add_argument("--base-url", required=True, help="Label Studio base URL")
    parser.add_argument("--token", required=True, help="Label Studio API token")
    parser.add_argument("--project-id", type=int, required=True, help="Label Studio project id")
    parser.add_argument("--out", type=Path, required=True, help="Output JSONL file")
    args = parser.parse_args()

    tasks = fetch_tasks(args.base_url, args.token, args.project_id)
    rows = flatten_annotations(tasks)
    write_jsonl(args.out, rows)
    print({"tasks": len(tasks), "rows": len(rows), "out": str(args.out)})


if __name__ == "__main__":
    main()
