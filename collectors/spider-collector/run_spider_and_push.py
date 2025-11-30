# collectors/spider-collector/run_spider_and_push.py
import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import os

import requests
import zipfile

# 把仓库根目录加到 sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collectors.common.client import (  # type: ignore
    create_collection_run,
    upload_archive_to_collection,
)


def download_image(url: str, out_dir: Path, timeout: int = 20) -> Optional[Path]:
    """
    下载单张图片到 out_dir，返回文件路径。
    文件名使用 uuid，保留 URL 中的扩展名（如果有）。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 尝试从 URL 提取扩展名
    ext = ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        name = os.path.basename(parsed.path)
        if "." in name:
            ext_candidate = name.rsplit(".", 1)[-1]
            if 0 < len(ext_candidate) <= 5:
                ext = "." + ext_candidate
    except Exception:
        pass

    if not ext:
        ext = ".bin"

    fname = f"{uuid.uuid4().hex}{ext}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    out_path = out_dir / fname
    out_path.write_bytes(resp.content)
    return out_path


def simple_spider(
    url_list: List[str],
    out_dir: Path,
    tag: str,
    max_num: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    极简版爬虫：从 url_list 下载图片。
    返回每个成功下载文件的 meta（目前主要用于统计）。
    """
    metas: List[Dict[str, Any]] = []
    total = len(url_list)
    if max_num is not None:
        url_list = url_list[:max_num]

    for idx, url in enumerate(url_list, start=1):
        url = url.strip()
        if not url:
            continue

        print(f"[{idx}/{total}] downloading {url} ...")
        try:
            out_path = download_image(url, out_dir)
            if out_path is None:
                continue
        except Exception as e:
            print(f"  -> failed: {e}")
            continue

        metas.append(
            {
                "filename": out_path.name,
                "source_url": url,
                "tag": tag,
                "timestamp": time.time(),
            }
        )

    return metas


def make_flat_zip_from_dir(src_dir: Path, zip_path: Path):
    """
    把 src_dir 下的所有文件打进一个 zip，放在 zip 根目录。
    """
    src_dir = src_dir.resolve()
    zip_path = zip_path.resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    files = [p for p in src_dir.iterdir() if p.is_file()]

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, arcname=p.name)

    return zip_path


def main():
    parser = argparse.ArgumentParser(
        description="Run a simple spider, pack results, and push to collection-gateway."
    )
    parser.add_argument(
        "--url-file",
        type=str,
        required=True,
        help="文本文件，每行一个图片 URL。",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default=None,
        help="collection_run 名称（默认：spider_{文件名}_{timestamp}）。",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default="spider",
        help="给这一批样本打一个 tag（写在 run meta 里）。",
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default="./tmp_spider_runs",
        help="本地工作目录。",
    )
    parser.add_argument(
        "--max-num",
        type=int,
        default=None,
        help="最多下载多少条 URL（调试用，可选）。",
    )
    args = parser.parse_args()

    url_file = Path(args.url_file).expanduser().resolve()
    if not url_file.exists():
        raise SystemExit(f"url-file 不存在: {url_file}")

    urls = [
        line.strip()
        for line in url_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not urls:
        raise SystemExit("url-file 为空，终止。")

    work_root = Path(args.work_dir).resolve()
    run_id = int(time.time())
    run_dir = work_root / f"spider_run_{run_id}"
    files_dir = run_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    print(f"工作目录: {run_dir}")
    print(f"总 URL 数: {len(urls)}")

    metas = simple_spider(
        url_list=urls,
        out_dir=files_dir,
        tag=args.tag,
        max_num=args.max_num,
    )
    if not metas:
        raise SystemExit("没有成功下载任何文件，终止。")

    print(f"成功下载 {len(metas)} 个文件。")

    # 打 zip
    zip_path = run_dir / "archive.zip"
    make_flat_zip_from_dir(files_dir, zip_path)
    print(f"已生成 zip: {zip_path}")

    # 创建 collection_run
    base_name = url_file.stem
    collection_name = (
        args.collection_name
        or f"spider_{base_name}_{run_id}"
    )

    run_meta = {
        "collector": "spider",
        "url_file": str(url_file),
        "start_urls_preview": urls[:5],  # 只存前几条预览
        "total_urls": len(urls),
        "downloaded": len(metas),
        "tag": args.tag,
        "max_num": args.max_num,
        "hostname": os.uname().nodename if hasattr(os, "uname") else None,
    }

    print("创建 collection_run ...")
    run_data = create_collection_run(
        name=collection_name,
        source_type="spider",
        description=f"Spider run from {url_file}",
        meta=run_meta,
    )
    collection_run_id = run_data["id"]
    print(f"collection_run 创建完成: id={collection_run_id}")

    # 上传 zip
    print("上传 zip 到 /samples/from_archive ...")
    resp = upload_archive_to_collection(
        collection_run_id=collection_run_id,
        archive_path=zip_path,
        source_type="spider",
        extra_meta={
            "collector": "spider",
            "downloaded": len(metas),
        },
    )
    print("上传完成，服务端返回：")
    print(resp)


if __name__ == "__main__":
    main()
