#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.gateway_client import create_collection_run, upload_archive_to_collection
from common.archive import zip_flat_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack generated images and ingest to collection-gateway")
    parser.add_argument("--images-dir", type=Path, required=True, help="Directory with generated images")
    parser.add_argument("--collection-name", required=True, help="Collection run name")
    parser.add_argument("--description", default="ComfyUI synthetic run", help="Run description")
    parser.add_argument("--source-type", default="manual", help="Source type for collection run")
    parser.add_argument("--archive-out", type=Path, default=Path("./artifacts/synth_archive.zip"))
    args = parser.parse_args()

    run = create_collection_run(
        name=args.collection_name,
        source_type=args.source_type,
        description=args.description,
        meta={
            "entrypoint": "synth/comfyui_to_collection.py",
            "images_dir": str(args.images_dir),
            "ts": int(time.time()),
        },
    )
    run_id = run["id"]

    archive_path = zip_flat_dir(args.images_dir, args.archive_out)
    result = upload_archive_to_collection(
        collection_run_id=run_id,
        archive_path=archive_path,
        source_type=args.source_type,
        extra_meta={"collector": "comfyui", "archive": str(archive_path)},
    )

    print({"collection_run_id": run_id, "archive": str(archive_path), "result": result})


if __name__ == "__main__":
    main()
