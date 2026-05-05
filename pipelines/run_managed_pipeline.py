#!/usr/bin/env python
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, parse_bool, resolve_run_dir
from pipelines.run_yaml_pipeline import STAGE_TO_SCRIPT, build_runtime_config, stage_output_ok


class SingleInstanceLock:
    def __init__(self, lock_path: Path, pid_path: Path) -> None:
        self.lock_path = lock_path
        self.pid_path = pid_path
        self._fh: Optional[object] = None

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.lock_path.open("a+")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"pipeline already running; lock file busy: {self.lock_path}") from exc

        self.pid_path.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "started_at": int(time.time()),
                    "lock_file": str(self.lock_path),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if self.pid_path.exists():
                self.pid_path.unlink()
        finally:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None


class ManagedPipeline:
    def __init__(self) -> None:
        self._stop_requested = False
        self._child: Optional[subprocess.Popen[Any]] = None
        self._stop_requested_at: Optional[float] = None

    def _on_sigterm(self, signum: int, frame: object) -> None:
        _ = frame
        print(f"[managed-pipeline] received signal={signum}, stopping...")
        self._stop_requested = True
        self._stop_requested_at = time.time()
        if self._child is not None and self._child.poll() is None:
            self._child.terminate()

    def _run_stage(self, cmd: List[str]) -> None:
        print("$", " ".join(cmd))
        self._child = subprocess.Popen(cmd)
        try:
            while True:
                try:
                    ret = self._child.wait(timeout=1)
                    if ret != 0:
                        raise subprocess.CalledProcessError(ret, cmd)
                    return
                except subprocess.TimeoutExpired:
                    if self._stop_requested and self._child.poll() is None:
                        if self._stop_requested_at is not None and time.time() - self._stop_requested_at > 120:
                            print("[managed-pipeline] child did not exit in 120s after SIGTERM; killing...")
                            self._child.kill()
                        continue
        finally:
            self._child = None

    def execute(
        self,
        runtime_cfg: Dict[str, Any],
        runtime_cfg_path: Path,
        run_dir: Path,
        python_bin: str,
        resume: bool,
    ) -> Dict[str, Any]:
        steps = runtime_cfg.get("pipeline", {}).get(
            "steps", ["dataloader", "generate", "filter", "train", "eval"]
        )
        if not isinstance(steps, list) or not steps:
            raise ValueError("pipeline.steps must be a non-empty list")

        # 仅响应主动终止；忽略终端断开
        signal.signal(signal.SIGTERM, self._on_sigterm)
        signal.signal(signal.SIGINT, self._on_sigterm)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, signal.SIG_IGN)

        completed_steps: List[str] = []
        skipped_steps: List[str] = []

        for stage in steps:
            if self._stop_requested:
                raise KeyboardInterrupt("stop requested")
            if stage not in STAGE_TO_SCRIPT:
                raise ValueError(f"unsupported stage in pipeline.steps: {stage}")

            if resume and stage_output_ok(stage, run_dir, runtime_cfg):
                print(f"[managed-pipeline] skip completed stage: {stage}")
                skipped_steps.append(stage)
                continue

            script = STAGE_TO_SCRIPT[stage]
            self._run_stage([python_bin, script, "--config", str(runtime_cfg_path)])
            if not stage_output_ok(stage, run_dir, runtime_cfg):
                raise RuntimeError(f"stage `{stage}` completed but expected artifact is missing")
            completed_steps.append(stage)

        return {
            "run_dir": str(run_dir),
            "runtime_config": str(runtime_cfg_path),
            "steps": steps,
            "completed_steps": completed_steps,
            "skipped_steps": skipped_steps,
            "resume_enabled": resume,
            "status": "ok",
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Managed pipeline runner with lock/pid/sigterm/resume support"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--python-bin", default="python")
    parser.add_argument("--resume", default=None)
    args = parser.parse_args()

    raw_cfg = load_config(args.config)
    runtime_cfg = build_runtime_config(raw_cfg)
    run_dir = resolve_run_dir(runtime_cfg)

    pipeline_cfg = runtime_cfg.get("pipeline", {}) if isinstance(runtime_cfg.get("pipeline", {}), dict) else {}
    default_resume = parse_bool(pipeline_cfg.get("resume_from_artifacts"), True)
    resume = parse_bool(args.resume, default_resume)

    pipeline_dir = run_dir / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    runtime_cfg_path = pipeline_dir / "runtime_config.json"
    runtime_cfg_path.write_text(json.dumps(runtime_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    lock = SingleInstanceLock(
        lock_path=Path(str(pipeline_cfg.get("lock_file", pipeline_dir / "managed.lock"))),
        pid_path=Path(str(pipeline_cfg.get("pid_file", pipeline_dir / "managed.pid"))),
    )

    runner = ManagedPipeline()
    try:
        lock.acquire()
        summary = runner.execute(
            runtime_cfg=runtime_cfg,
            runtime_cfg_path=runtime_cfg_path,
            run_dir=run_dir,
            python_bin=args.python_bin,
            resume=resume,
        )
    except KeyboardInterrupt:
        summary = {
            "run_dir": str(run_dir),
            "runtime_config": str(runtime_cfg_path),
            "resume_enabled": resume,
            "status": "interrupted",
        }
        (pipeline_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(143)
    except Exception as exc:
        summary = {
            "run_dir": str(run_dir),
            "runtime_config": str(runtime_cfg_path),
            "resume_enabled": resume,
            "status": "failed",
            "error": str(exc),
        }
        (pipeline_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise
    finally:
        lock.release()

    (pipeline_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
