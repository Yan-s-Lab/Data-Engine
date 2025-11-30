# collectors/manual-uploader/upload_from_dir.py
import argparse
import sys
from pathlib import Path
from typing import List

import zipfile
import time
import os

# 把仓库根目录加到 sys.path，方便导入 collectors.common
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collectors.common.client import (  # type: ignore
    create_collection_run,
    upload_archive_to_collection,
)


def collect_files(src_dir: Path, recursive: bool) -> List[Path]:
    """收集目录下的所有文件路径。"""
    src_dir = src_dir.resolve()
    files: List[Path] = []
    if recursive:
        for p in src_dir.rglob("*"):
            if p.is_file():
                files.append(p)
    else:
        for p in src_dir.iterdir():
            if p.is_file():
                files.append(p)
    return files


def make_flat_zip(file_paths: List[Path], zip_path: Path):
    """
    把一堆文件打成 zip，所有文件都放在 zip 的根目录（不保留原目录结构）。
    arcname 使用原文件名，避免路径过深。
    """
    zip_path = zip_path.resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in file_paths:
            zf.write(p, arcname=p.name)
    return zip_path


def main():
    parser = argparse.ArgumentParser(
        description="Upload a local directory as an archive to collection-gateway."
    )
    parser.add_argument(
        "--src-dir",
        type=str,
        required=True,
        help="要上传的本地目录路径。",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default=None,
        help="collection_run 名称（默认: manual_{目录名}_{timestamp}）。",
    )
    parser.add_argument(
        "--description",
        type=str,
        default=None,
        help="collection_run 描述，可选。",
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default="./tmp_manual_runs",
        help="临时工作目录，用于存放 zip 文件。",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="只扫描 src-dir 这一层，不递归子目录。",
    )
    args = parser.parse_args()

    src_dir = Path(args.src_dir).expanduser().resolve()
    if not src_dir.exists() or not src_dir.is_dir():
        raise SystemExit(f"src-dir 不存在或不是目录: {src_dir}")

    recursive = not args.no_recursive
    files = collect_files(src_dir, recursive=recursive)
    if not files:
        raise SystemExit("没有找到任何文件，终止。")

    print(f"发现 {len(files)} 个文件，准备打包上传。")

    # 准备工作目录和 zip 路径
    work_root = Path(args.work_dir).resolve()
    run_id = int(time.time())
    run_dir = work_root / f"manual_run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    zip_path = run_dir / "archive.zip"

    make_flat_zip(files, zip_path)
    print(f"已生成 zip: {zip_path}")

    # 创建 collection_run
    collection_name = (
        args.collection_name
        or f"manual_{src_dir.name}_{run_id}"
    )
    description = args.description or f"Manual upload from {src_dir} (recursive={recursive})"

    run_meta = {
        "collector": "manual-uploader",
        "src_dir": str(src_dir),
        "recursive": recursive,
        "file_count": len(files),
        "hostname": os.uname().nodename if hasattr(os, "uname") else None,
    }

    print("创建 collection_run ...")
    run_data = create_collection_run(
        name=collection_name,
        source_type="manual",
        description=description,
        meta=run_meta,
    )
    collection_run_id = run_data["id"]
    print(f"collection_run 创建完成: id={collection_run_id}")

    # 上传 zip
    print("上传 zip 到 /samples/from_archive ...")
    resp = upload_archive_to_collection(
        collection_run_id=collection_run_id,
        archive_path=zip_path,
        source_type="manual",
        extra_meta={
            "collector": "manual-uploader",
            "file_count": len(files),
        },
    )
    print("上传完成，服务端返回：")
    print(resp)


if __name__ == "__main__":
    main()
