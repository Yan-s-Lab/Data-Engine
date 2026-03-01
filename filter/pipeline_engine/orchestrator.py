from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .phase1_dual_signal import PHASE_ID as PHASE1_DUAL_SIGNAL_ID
from .phase1_dual_signal import run_phase as run_phase1_dual_signal


PhaseRunner = Any


def _resolve_phase_plan(filter_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    pipeline_cfg = filter_cfg.get("pipeline")
    if isinstance(pipeline_cfg, dict):
        phases = pipeline_cfg.get("phases")
        if isinstance(phases, list) and phases:
            out: List[Dict[str, Any]] = []
            for p in phases:
                if isinstance(p, str):
                    out.append({"id": p, "enabled": True})
                elif isinstance(p, dict):
                    out.append(dict(p))
            if out:
                return out

    phase1_cfg = dict(filter_cfg.get("phase1_dual_signal", {}))
    return [{"id": PHASE1_DUAL_SIGNAL_ID, **phase1_cfg, "enabled": bool(phase1_cfg.get("enabled", True))}]


def _phase_registry() -> Dict[str, PhaseRunner]:
    return {
        PHASE1_DUAL_SIGNAL_ID: run_phase1_dual_signal,
    }


def run_filter_pipeline(
    rows: List[Dict[str, Any]],
    *,
    filter_dir: Path,
    filter_cfg: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    registry = _phase_registry()
    phase_plan = _resolve_phase_plan(filter_cfg)

    score_rows: List[Dict[str, Any]] = []
    pipeline_report: Dict[str, Any] = {
        "pipeline": {
            "phase_count": len(phase_plan),
            "phases": [],
        }
    }

    current_rows = rows
    for idx, phase_cfg in enumerate(phase_plan, start=1):
        phase_id = str(phase_cfg.get("id", "")).strip()
        enabled = bool(phase_cfg.get("enabled", True))
        if not enabled:
            pipeline_report["pipeline"]["phases"].append(
                {"index": idx, "id": phase_id, "enabled": False, "skipped": True}
            )
            continue

        runner = registry.get(phase_id)
        if runner is None:
            raise ValueError(f"unsupported filter pipeline phase id: {phase_id}")

        score_rows, phase_report = runner(
            current_rows,
            filter_dir=filter_dir,
            filter_cfg=filter_cfg,
            phase_cfg=phase_cfg,
        )

        reject_ids = {
            str(r.get("sample_id", ""))
            for r in score_rows
            if str(r.get("decision", "")) == "reject"
        }
        if reject_ids:
            current_rows = [row for row in current_rows if str(row.get("sample_id", "")) not in reject_ids]

        pipeline_report["pipeline"]["phases"].append(
            {
                "index": idx,
                "id": phase_id,
                "enabled": True,
                "input_rows": len(current_rows) + len(reject_ids),
                "rejected_rows": len(reject_ids),
                "output_rows": len(current_rows),
            }
        )
        pipeline_report.update(phase_report)

    return score_rows, pipeline_report
