#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, parse_bool


@dataclass
class PlanTask:
    stage_name: str
    task_name: str
    config_path: str


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text.strip())
    return s.strip("._-") or "task"


def _parse_tasks(stage_name: str, stage_obj: Dict[str, Any], stage_idx: int) -> List[PlanTask]:
    tasks_obj = stage_obj.get("tasks")
    if not isinstance(tasks_obj, list) or not tasks_obj:
        raise ValueError(f"serial_plan.stages[{stage_idx}].tasks must be a non-empty list")

    parsed: List[PlanTask] = []
    for task_idx, item in enumerate(tasks_obj):
        if isinstance(item, str):
            cfg = item.strip()
            if not cfg:
                raise ValueError(
                    f"serial_plan.stages[{stage_idx}].tasks[{task_idx}] cannot be empty"
                )
            parsed.append(
                PlanTask(
                    stage_name=stage_name,
                    task_name=f"{stage_name}_{task_idx + 1}",
                    config_path=cfg,
                )
            )
            continue

        if isinstance(item, dict):
            cfg = str(item.get("config", "")).strip()
            if not cfg:
                raise ValueError(
                    f"serial_plan.stages[{stage_idx}].tasks[{task_idx}].config is required"
                )
            task_name = str(item.get("name", f"{stage_name}_{task_idx + 1}")).strip()
            parsed.append(
                PlanTask(
                    stage_name=stage_name,
                    task_name=task_name or f"{stage_name}_{task_idx + 1}",
                    config_path=cfg,
                )
            )
            continue

        raise ValueError(
            f"serial_plan.stages[{stage_idx}].tasks[{task_idx}] must be string or mapping"
        )
    return parsed


def parse_plan(plan: Dict[str, Any]) -> tuple[List[PlanTask], bool]:
    serial_plan = plan.get("serial_plan")
    if not isinstance(serial_plan, dict):
        raise ValueError("plan root must contain mapping `serial_plan`")

    stages = serial_plan.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("serial_plan.stages must be a non-empty list")

    continue_on_error = parse_bool(serial_plan.get("continue_on_error"), False)
    queue: List[PlanTask] = []
    for idx, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise ValueError(f"serial_plan.stages[{idx}] must be a mapping")
        stage_name = str(stage.get("name", f"stage_{idx + 1}")).strip() or f"stage_{idx + 1}"
        queue.extend(_parse_tasks(stage_name=stage_name, stage_obj=stage, stage_idx=idx))
    return queue, continue_on_error


def run_task(
    python_bin: str,
    config_path: str,
    resume: bool,
    task_log: Path,
) -> int:
    cmd = [
        python_bin,
        "pipelines/run_managed_pipeline.py",
        "--config",
        config_path,
        "--resume",
        "true" if resume else "false",
    ]
    with task_log.open("a", encoding="utf-8") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=False)
        return int(proc.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serial multi-stage plan runner (v1: serial only)"
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--python-bin", default="python")
    parser.add_argument("--resume", default="true")
    parser.add_argument("--log-dir", type=Path, default=Path("artifacts/logs"))
    parser.add_argument("--log-file", type=Path, default=Path("artifacts/logs/managed_pipeline.log"))
    parser.add_argument("--continue-on-error", default=None)
    args = parser.parse_args()

    plan = load_config(args.plan)
    queue, continue_on_error_from_plan = parse_plan(plan)
    resume = parse_bool(args.resume, True)
    continue_on_error = parse_bool(args.continue_on_error, continue_on_error_from_plan)

    args.log_dir.mkdir(parents=True, exist_ok=True)
    args.log_file.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = args.log_dir / f"serial_plan_summary_{now}.json"

    results: List[Dict[str, Any]] = []
    fail_count = 0

    with args.log_file.open("a", encoding="utf-8") as main_log:
        main_log.write(
            f"[serial-plan] start plan={args.plan} jobs={len(queue)} "
            f"resume={resume} continue_on_error={continue_on_error}\n"
        )

        for idx, task in enumerate(queue):
            stage_slug = _slug(task.stage_name)
            task_slug = _slug(task.task_name)
            task_log = args.log_dir / f"{stage_slug}__{task_slug}_{now}.log"
            main_log.write(
                f"[serial-plan] start job={idx + 1}/{len(queue)} stage={task.stage_name} "
                f"task={task.task_name} config={task.config_path} log={task_log}\n"
            )
            main_log.flush()

            code = run_task(
                python_bin=args.python_bin,
                config_path=task.config_path,
                resume=resume,
                task_log=task_log,
            )
            ok = code == 0
            if not ok:
                fail_count += 1

            results.append(
                {
                    "index": idx + 1,
                    "stage": task.stage_name,
                    "task": task.task_name,
                    "config": task.config_path,
                    "log": str(task_log),
                    "return_code": code,
                    "status": "ok" if ok else "failed",
                }
            )

            if ok:
                main_log.write(
                    f"[serial-plan] done stage={task.stage_name} task={task.task_name}\n"
                )
            else:
                main_log.write(
                    f"[serial-plan] failed stage={task.stage_name} task={task.task_name} "
                    f"return_code={code}\n"
                )
                if not continue_on_error:
                    main_log.write("[serial-plan] exit on first failure\n")
                    break
            main_log.flush()

        final_status = "ok" if fail_count == 0 else "failed"
        main_log.write(
            f"[serial-plan] finished status={final_status} fail_count={fail_count}\n"
        )
        main_log.flush()

    summary = {
        "plan_path": str(args.plan),
        "resume": resume,
        "continue_on_error": continue_on_error,
        "job_count": len(queue),
        "fail_count": fail_count,
        "status": "ok" if fail_count == 0 else "failed",
        "results": results,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if fail_count > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
