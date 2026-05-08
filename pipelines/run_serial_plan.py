#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest
import sys
from typing import Any, Dict, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, parse_bool


@dataclass
class PlanTask:
    stage_name: str
    task_name: str
    config_path: str
    post_actions: List[Dict[str, Any]]


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text.strip())
    return s.strip("._-") or "task"


def _parse_post_actions(raw: Any, context: str) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{context} must be a list")

    parsed: List[Dict[str, Any]] = []
    for action_idx, item in enumerate(raw):
        if isinstance(item, str):
            type_name = item.strip()
            action_obj: Dict[str, Any] = {"type": type_name}
        elif isinstance(item, Mapping):
            action_obj = dict(item)
            type_name = str(action_obj.get("type", "")).strip()
        else:
            raise ValueError(f"{context}[{action_idx}] must be a string or mapping")

        if not type_name:
            raise ValueError(f"{context}[{action_idx}].type is required")

        on = str(action_obj.get("on", "always")).strip().lower()
        if on not in {"always", "success", "failure"}:
            raise ValueError(f"{context}[{action_idx}].on must be one of: always, success, failure")

        timeout_sec = int(action_obj.get("timeout_sec", 10))
        if timeout_sec <= 0:
            raise ValueError(f"{context}[{action_idx}].timeout_sec must be > 0")

        params_raw = action_obj.get("params", {})
        if not isinstance(params_raw, Mapping):
            raise ValueError(f"{context}[{action_idx}].params must be a mapping")

        parsed.append(
            {
                "type": type_name,
                "enabled": parse_bool(action_obj.get("enabled"), True),
                "on": on,
                "continue_on_error": parse_bool(action_obj.get("continue_on_error"), False),
                "timeout_sec": timeout_sec,
                "params": dict(params_raw),
            }
        )
    return parsed


def _parse_tasks(
    stage_name: str,
    stage_obj: Dict[str, Any],
    stage_idx: int,
    inherited_post_actions: List[Dict[str, Any]],
) -> List[PlanTask]:
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
                    post_actions=list(inherited_post_actions),
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
            task_post_actions = _parse_post_actions(
                item.get("post_actions"),
                f"serial_plan.stages[{stage_idx}].tasks[{task_idx}].post_actions",
            )
            parsed.append(
                PlanTask(
                    stage_name=stage_name,
                    task_name=task_name or f"{stage_name}_{task_idx + 1}",
                    config_path=cfg,
                    post_actions=[*inherited_post_actions, *task_post_actions],
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
    global_post_actions = _parse_post_actions(serial_plan.get("post_actions"), "serial_plan.post_actions")
    queue: List[PlanTask] = []
    for idx, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise ValueError(f"serial_plan.stages[{idx}] must be a mapping")
        stage_name = str(stage.get("name", f"stage_{idx + 1}")).strip() or f"stage_{idx + 1}"
        stage_post_actions = _parse_post_actions(
            stage.get("post_actions"),
            f"serial_plan.stages[{idx}].post_actions",
        )
        queue.extend(
            _parse_tasks(
                stage_name=stage_name,
                stage_obj=stage,
                stage_idx=idx,
                inherited_post_actions=[*global_post_actions, *stage_post_actions],
            )
        )
    return queue, continue_on_error


def _should_run_post_action(action: Dict[str, Any], task_ok: bool) -> bool:
    if not bool(action.get("enabled", True)):
        return False
    on = str(action.get("on", "always"))
    if on == "always":
        return True
    if on == "success":
        return task_ok
    if on == "failure":
        return not task_ok
    return False


def _http_request_json(
    *,
    method: str,
    url: str,
    timeout_sec: int,
    payload: Dict[str, Any] | None = None,
) -> Any:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=body, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read()
    except urlerror.URLError as exc:
        raise RuntimeError(f"http request failed: {method} {url}: {exc}") from exc
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _run_post_action(action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = str(action.get("type", "")).strip()
    timeout_sec = int(action.get("timeout_sec", 10))
    params = action.get("params", {})
    if not isinstance(params, dict):
        params = {}

    base_url = str(params.get("base_url", "http://127.0.0.1:8188")).rstrip("/")
    if not base_url:
        raise ValueError(f"post_action `{action_type}` requires non-empty base_url")

    if action_type == "comfyui.queue_empty_check":
        queue = _http_request_json(
            method="GET",
            url=f"{base_url}/queue",
            timeout_sec=timeout_sec,
        )
        if not isinstance(queue, dict):
            raise RuntimeError("comfyui.queue_empty_check expected mapping response from /queue")
        running = queue.get("queue_running", [])
        pending = queue.get("queue_pending", [])
        running_count = len(running) if isinstance(running, list) else 0
        pending_count = len(pending) if isinstance(pending, list) else 0
        if running_count > 0 or pending_count > 0:
            raise RuntimeError(
                f"comfyui queue not empty: running={running_count} pending={pending_count}"
            )
        return {"running_count": running_count, "pending_count": pending_count}

    if action_type == "comfyui.free_memory":
        payload = {
            "unload_models": parse_bool(params.get("unload_models"), True),
            "free_memory": parse_bool(params.get("free_memory"), True),
        }
        _http_request_json(
            method="POST",
            url=f"{base_url}/free",
            timeout_sec=timeout_sec,
            payload=payload,
        )
        return payload

    raise ValueError(f"unsupported serial plan post_action.type: {action_type}")


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
            post_action_reports: List[Dict[str, Any]] = []
            for action_idx, action in enumerate(task.post_actions):
                if not _should_run_post_action(action, task_ok=ok):
                    continue
                action_type = str(action.get("type", "")).strip()
                try:
                    details = _run_post_action(action)
                    post_action_reports.append(
                        {
                            "index": action_idx + 1,
                            "type": action_type,
                            "status": "ok",
                            "on": action.get("on", "always"),
                            "details": details,
                        }
                    )
                    main_log.write(
                        f"[serial-plan] post-action ok stage={task.stage_name} task={task.task_name} "
                        f"type={action_type}\n"
                    )
                except Exception as exc:
                    post_action_reports.append(
                        {
                            "index": action_idx + 1,
                            "type": action_type,
                            "status": "failed",
                            "on": action.get("on", "always"),
                            "error": str(exc),
                        }
                    )
                    main_log.write(
                        f"[serial-plan] post-action failed stage={task.stage_name} task={task.task_name} "
                        f"type={action_type} error={exc}\n"
                    )
                    if not parse_bool(action.get("continue_on_error"), False):
                        if ok:
                            code = 90
                            ok = False
                        break
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
                    "post_actions": post_action_reports,
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
