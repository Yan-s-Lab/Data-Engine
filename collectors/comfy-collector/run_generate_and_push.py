#!/usr/bin/env python
# collectors/comfy-collector/run_generate_and_push.py
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import yaml

from backends import get_backend, GenerationRequest  # 相对路径取决于你怎么运行


def load_generators_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def pick_generator(cfg: Dict[str, Any], generator_id: str) -> Dict[str, Any]:
    gens = cfg.get("generators", [])
    for g in gens:
        if g.get("id") == generator_id:
            return g
    raise ValueError(f"Generator id {generator_id!r} not found in config")


def render_prompt(gen_cfg: Dict[str, Any], idx: int) -> str:
    """
    这里可以用你原来的模板系统；先给一个最简单的占位版本.
    """
    base_prompt: str = gen_cfg["prompt"]
    # 如果有变量，可以在这里根据 idx 或变量表渲染
    return base_prompt


def make_zip(src_dir: Path, out_dir: Path, zip_name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_base = out_dir / zip_name
    # shutil.make_archive 会自动加 .zip
    archive_path = shutil.make_archive(str(zip_base), "zip", root_dir=src_dir)
    return Path(archive_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate images and push to Data Engine")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("generators.yml"),
        help="Path to generators.yml",
    )
    parser.add_argument(
        "--generator-id",
        required=True,
        help="Generator id defined in generators.yml",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("./tmp_outputs"),
        help="Root directory for generated images before zipping",
    )
    args = parser.parse_args()

    config_all = load_generators_config(args.config)
    gen_cfg = pick_generator(config_all, args.generator_id)

    backend_name: str = gen_cfg["backend"]  # e.g. "comfyui" / "diffusers_local"
    num_images: int = int(gen_cfg.get("num_images", 1))

    # 后端专用配置
    backend_config: Dict[str, Any] = gen_cfg.get("backend_config", {})
    backend_config["generator_id"] = gen_cfg["id"]

    backend = get_backend(backend_name, backend_config)

    # 输出目录：可以用 generator_id 做子目录，便于区分
    work_dir = args.out_root / gen_cfg["id"]
    work_dir.mkdir(parents=True, exist_ok=True)

    metas: List[Dict[str, Any]] = []

    seed_base = gen_cfg.get("seed_base")
    width = gen_cfg.get("width")
    height = gen_cfg.get("height")

    for idx in range(num_images):
        prompt = render_prompt(gen_cfg, idx)
        negative_prompt = gen_cfg.get("negative_prompt")

        req = GenerationRequest(
            idx=idx,
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=(seed_base + idx) if seed_base is not None else None,
            width=width,
            height=height,
            extra=gen_cfg.get("extra_params", {}),
        )

        meta = backend.generate_one(req, work_dir)
        metas.append(meta.to_dict())
        print(f"[{idx+1}/{num_images}] saved {meta.filename}")

    # 打包成 zip（名字里带上 generator_id 和一个简单的时间戳）
    archive_dir = args.out_root / "archives"
    archive_name = f"{gen_cfg['id']}"
    archive_path = make_zip(work_dir, archive_dir, archive_name)

    metas_path = archive_dir / f"{archive_name}_metas.json"
    with metas_path.open("w", encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Generated {num_images} images.")
    print(f"   Images dir : {work_dir}")
    print(f"   Archive    : {archive_path}")
    print(f"   Metas      : {metas_path}")

    # TODO: 在这里调用你现有的 collection-gateway 客户端，把 archive_path + metas 上传
    # 比如参考 spider-collector 的 run_spider_and_push.py：
    #
    # from common.collection_gateway_client import upload_archive
    # upload_archive(
    #     archive_path=archive_path,
    #     metas=metas,
    #     collection_name=gen_cfg["collection_name"],
    #     source_type="synthetic",
    # )
    #
    # 这样 comfy-collector 和 spider-collector 的上传流程就是统一的。
    #


if __name__ == "__main__":
    main()
