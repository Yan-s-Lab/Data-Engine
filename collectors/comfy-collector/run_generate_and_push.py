import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml  # pip install pyyaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collectors.common.client import (
    create_collection_run,
    upload_archive_to_collection,
)

from .backends.base import GenerationBackend
from .backends.comfyui import ComfyUIBackend
from .backends.diffusers_local import DiffusersBackend


BACKEND_REGISTRY = {
    "comfyui": ComfyUIBackend,
    "diffusers": DiffusersBackend,
}


def make_zip(src_dir: Path, zip_path: Path):
    import zipfile

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
        description="Run multiple image generators (ComfyUI / pipelines), pack results, and push to collection-gateway."
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="YAML config path (generators.yaml)",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config).expanduser().resolve()
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

    run_name = cfg.get("run_name") or f"gen_run"
    out_root = Path(cfg.get("out_dir", "./tmp_generation_runs")).resolve()

    run_id = int(time.time())
    run_dir = out_root / f"gen_run_{run_id}"
    images_dir = run_dir / "images"
    meta_path = run_dir / "meta.jsonl"
    images_dir.mkdir(parents=True, exist_ok=True)

    print(f"[gen] 工作目录: {run_dir}")

    backends_cfg: List[Dict[str, Any]] = cfg.get("backends", [])
    if not backends_cfg:
        raise SystemExit("no backends in config.")

    # 1. 初始化 backends
    backends: List[GenerationBackend] = []
    for bc in backends_cfg:
        btype = bc["type"]
        name = bc["name"]
        cls = BACKEND_REGISTRY.get(btype)
        if cls is None:
            raise SystemExit(f"Unknown backend type: {btype}")
        backends.append(cls(name=name, config=bc))

    # 2. 并发调度任务（简单用线程池）
    metas: List[Dict[str, Any]] = []
    futures = []
    max_workers = sum(b.config.get("concurrency", 1) for b in backends)
    if max_workers <= 0:
        max_workers = 1

    print(f"[gen] Using ThreadPoolExecutor(max_workers={max_workers})")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for backend in backends:
            n = int(backend.config.get("num_images", 0))
            if n <= 0:
                continue
            for i in range(n):
                idx = i
                futures.append(
                    executor.submit(
                        backend.generate_one, idx, images_dir / backend.name
                    )
                )

        for fu in as_completed(futures):
            try:
                meta = fu.result()
                metas.append(meta)
                print(
                    f"[gen] done: backend={meta['backend']} file={meta['filename']}"
                )
            except Exception as e:
                print(f"[gen] error in generation task: {e}")

    if not metas:
        raise SystemExit("No images generated, abort.")

    # 3. 写 meta.jsonl
    with meta_path.open("w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    # 4. 打 zip
    zip_path = run_dir / "archive.zip"
    make_zip(images_dir, zip_path)
    print(f"[gen] 已生成 zip: {zip_path}")

    # 5. 创建 collection_run
    run_meta = {
        "collector": "generator",
        "backends": [b.name for b in backends],
        "config_file": str(cfg_path),
        "total_images": len(metas),
        "hostname": os.uname().nodename if hasattr(os, "uname") else None,
    }

    collection_name = f"{run_name}_{run_id}"

    print("[gen] 创建 collection_run ...")
    run_data = create_collection_run(
        name=collection_name,
        source_type="generator",
        description=f"Image generation run from config {cfg_path.name}",
        meta=run_meta,
    )
    collection_run_id = run_data["id"]
    print(f"[gen] collection_run 创建完成: id={collection_run_id}")

    # 6. 上传 zip
    print("[gen] 上传 zip 到 /samples/from_archive ...")
    resp = upload_archive_to_collection(
        collection_run_id=collection_run_id,
        archive_path=zip_path,
        source_type="generator",
        extra_meta={
            "collector": "generator",
            "total_images": len(metas),
        },
    )
    print("[gen] 上传完成，服务端返回：")
    print(resp)


if __name__ == "__main__":
    main()
