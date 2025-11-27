# 人工上传数据
import argparse
import os
from pathlib import Path
from typing import Iterable

import requests


def iter_images(root: Path) -> Iterable[Path]:
    exts = {".jpg", ".jpeg", ".png"}
    for p in root.rglob("*"):
        if p.suffix.lower() in exts:
            yield p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=str, help="Local directory of images")
    parser.add_argument(
        "--gateway",
        type=str,
        default="http://localhost:8001",  # collection-gateway 的端口
    )
    parser.add_argument(
        "--name", type=str, default="injection-cold-start"
    )
    args = parser.parse_args()

    # 1. 创建 collection_run
    resp = requests.post(
        f"{args.gateway}/collections/",
        json={
            "name": args.name,
            "description": "Initial injection dataset",
            "source_type": "manual",
        },
    )
    resp.raise_for_status()
    collection = resp.json()
    collection_id = collection["id"]
    print("Created collection:", collection)

    # 2. 上传所有图片
    data_dir = Path(args.data_dir)
    for img_path in iter_images(data_dir):
        files = {"file": (img_path.name, open(img_path, "rb"), "image/jpeg")}
        data = {
            "collection_run_id": str(collection_id),
            "source_type": "manual",
        }
        r = requests.post(f"{args.gateway}/samples/", data=data, files=files)
        r.raise_for_status()
        print("Uploaded", img_path, "→", r.json()["id"])


if __name__ == "__main__":
    main()
