from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "YAML config requires PyYAML. Install dependency or use JSON config."
            ) from exc
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"unsupported config format: {path}")

    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {path}")
    return data


def resolve_run_dir(config: Dict[str, Any]) -> Path:
    run_cfg = config.get("run", {})
    run_id = str(run_cfg.get("run_id", "m1_local_run"))
    artifacts_root = Path(str(run_cfg.get("artifacts_root", "artifacts/runs")))
    run_dir = artifacts_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)
