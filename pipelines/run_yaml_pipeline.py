#!/usr/bin/env python
# 允许在 Python 3.10+ 中使用更直观的类型标注语法（例如 X | Y）
from __future__ import annotations

# 命令行参数解析
import argparse
# JSON 序列化与反序列化
import json
# 启动子进程执行各阶段脚本
import subprocess
# 路径处理
from pathlib import Path
# 动态修改模块搜索路径
import sys
# 类型标注
from typing import Any, Dict, List

# 项目根目录（当前文件在 pipelines/，向上两级回到仓库根）
ROOT = Path(__file__).resolve().parents[1]
# 把项目根目录加入 sys.path，保证可直接 import common/*
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 读取配置 + 统一计算本次 run 的输出目录
from common.config_io import load_config, resolve_run_dir

# 逻辑阶段名到可执行脚本路径的映射
STAGE_TO_SCRIPT = {
    "dataloader": "ingest/run_dataloader.py",
    "generate": "synth/run_generate.py",
    "filter": "filter/filter_stages/filter1/main.py",
    "train": "train/run_train.py",
    "eval": "eval/run_eval.py",
    "coco_to_yolo_pose": "label/build_coco_yolo_pose.py",
    "annotation": "label/run_ai_annotation.py",
    "build_mixed": "label/build_mixed_dataset.py",
    "train_yolo_pose": "train/run_yolo11_pose.py",
    "eval_yolo_pose": "eval/run_yolo11_pose_eval.py",
}


def run(cmd: List[str]) -> None:
    # 打印将要执行的命令，便于追踪流水线执行过程
    print("$", " ".join(cmd))
    # check=True: 任何阶段失败会立刻抛错并中断流水线
    subprocess.run(cmd, check=True)


def build_runtime_config(config: Dict[str, Any]) -> Dict[str, Any]:
    # 复制一份配置，避免直接修改调用方传入的对象
    cfg = dict(config)
    # 基于 run.run_id / artifacts_root 解析本轮统一输出目录
    run_dir = resolve_run_dir(cfg)

    # 读取 generate 子配置；若不存在则用空字典
    gen_cfg = dict(cfg.get("generate", {}))
    # 若用户未显式指定 generate.real_manifest，则自动接 dataloader 产物
    gen_cfg.setdefault("real_manifest", str(run_dir / "dataloader" / "real_manifest.jsonl"))
    # 把补全后的 generate 配置写回总配置
    cfg["generate"] = gen_cfg

    # 读取 filter 子配置；若不存在则用空字典
    filter_cfg = dict(cfg.get("filter", {}))
    # 若用户未显式指定 filter.input_manifests，则自动接 generate 产物
    if "input_manifests" not in filter_cfg:
        filter_cfg["input_manifests"] = [str(run_dir / "generate" / "synth_manifest.jsonl")]
    # 把补全后的 filter 配置写回总配置
    cfg["filter"] = filter_cfg
    # 返回“可直接执行”的运行时配置
    return cfg


def stage_output_ok(stage: str, run_dir: Path, config: Dict[str, Any] | None = None) -> bool:
    config = config or {}
    if stage == "build_mixed":
        mix_cfg = config.get("build_mixed", {})
        output_name = str(mix_cfg.get("output_name", "mixed_dataset")).strip() or "mixed_dataset"
        return (
            (run_dir / "label" / output_name / "report.json").exists()
            and (run_dir / "label" / output_name / "dataset.yaml").exists()
        )

    # 每个阶段必须产生的关键工件；用于最小正确性校验
    expected = {
        "dataloader": run_dir / "dataloader" / "real_manifest.jsonl",
        "generate": run_dir / "generate" / "synth_manifest.jsonl",
        "filter": run_dir / "filter" / "splits" / "accept.jsonl",
        "train": run_dir / "train" / "model_stub.json",
        "eval": run_dir / "eval" / "policy_feedback.json",
        "coco_to_yolo_pose": run_dir / "label" / "real_split_report.json",
        "annotation": run_dir / "label" / "ai_annotation_report.json",
        "train_yolo_pose": run_dir / "train_yolo_pose" / "report.json",
        "eval_yolo_pose": run_dir / "eval_yolo_pose" / "report.json",
    }[stage]
    # 只要关键工件存在，即认为该阶段输出通过
    return expected.exists()


def main() -> None:
    # 定义命令行接口
    parser = argparse.ArgumentParser(
        description="YAML-configurable single-node closed-loop pipeline"
    )
    # 必填：配置文件路径（yaml/json）
    parser.add_argument("--config", type=Path, required=True)
    # 可选：Python 可执行文件（默认 python）
    parser.add_argument("--python-bin", default="python")
    # 解析命令行参数
    args = parser.parse_args()

    # 读取用户原始配置
    raw_cfg = load_config(args.config)
    # 补全阶段间依赖路径，生成运行时配置
    runtime_cfg = build_runtime_config(raw_cfg)
    # 解析本轮 run 输出目录
    run_dir = resolve_run_dir(runtime_cfg)
    # pipeline 子目录专门存放流程级工件（运行时配置、summary）
    pipeline_dir = run_dir / "pipeline"
    # 创建目录（已存在则忽略）
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    # 记录实际执行时使用的配置快照，保证可复现
    runtime_cfg_path = pipeline_dir / "runtime_config.json"
    # 写入运行时配置 JSON（保留中文、可读缩进）
    runtime_cfg_path.write_text(json.dumps(runtime_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    # 读取执行步骤；未配置时走默认闭环顺序
    steps = runtime_cfg.get("pipeline", {}).get(
        "steps", ["dataloader", "generate", "filter", "train", "eval"]
    )
    # 基础合法性校验：steps 必须是非空列表
    if not isinstance(steps, list) or not steps:
        raise ValueError("pipeline.steps must be a non-empty list")

    # 逐阶段串行执行
    for stage in steps:
        # 防止配置里写入未知阶段名
        if stage not in STAGE_TO_SCRIPT:
            raise ValueError(f"unsupported stage in pipeline.steps: {stage}")
        # 根据阶段名拿到对应脚本路径
        script = STAGE_TO_SCRIPT[stage]
        # 调用阶段脚本，统一传入 runtime_config.json
        run([args.python_bin, script, "--config", str(runtime_cfg_path)])
        # 阶段执行后检查关键输出工件是否存在
        if not stage_output_ok(stage, run_dir, runtime_cfg):
            raise RuntimeError(f"stage `{stage}` completed but expected artifact is missing")

    # 所有阶段成功后的摘要信息
    summary = {
        "run_dir": str(run_dir),
        "runtime_config": str(runtime_cfg_path),
        "steps": steps,
        "status": "ok",
    }
    # 持久化 summary，便于后续自动化系统或人工检查
    (pipeline_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 同步打印到控制台
    print(json.dumps(summary, ensure_ascii=False, indent=2))


# 仅在脚本被直接执行时运行 main；被 import 时不会自动执行
if __name__ == "__main__":
    main()
