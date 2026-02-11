#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collectors.common.client import create_collection_run, upload_archive_to_collection


def main() -> None:
    parser = argparse.ArgumentParser(description="Register archive to collection-gateway")
    parser.add_argument("--archive", type=Path, required=True, help="Path to zip archive")
    parser.add_argument("--name", required=True, help="Collection run name")
    parser.add_argument("--source-type", default="manual", help="manual/spider/robot/video")
    parser.add_argument("--description", default="", help="Run description")
    args = parser.parse_args()

    run = create_collection_run(
        name=args.name,
        source_type=args.source_type,
        description=args.description,
        meta={"entrypoint": "ingest/register_archive.py"},
    )
    run_id = run["id"]

    result = upload_archive_to_collection(
        collection_run_id=run_id,
        archive_path=args.archive,
        source_type=args.source_type,
        extra_meta={"ingested_by": "cli_rewrite"},
    )
    print({"collection_run_id": run_id, "ingest_result": result})


if __name__ == "__main__":
    main()
