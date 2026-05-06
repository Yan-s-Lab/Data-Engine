#!/usr/bin/env python3
"""Radar (spider) chart for pose ablation: 5 conditions × 5 metrics.

Style matches train/val_datasets/plot.py: viridis colormap, compact paper size, SVG output.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

EVAL_REPORTS = {
    "A": ROOT / "artifacts/runs/yk003/body_pose_coco/body_pose_coco_A_real_only_eval/eval_yolo_pose/report.json",
    "B": ROOT / "artifacts/runs/yk003/body_pose_coco/body_pose_coco_B_raw_synth_only_eval/eval_yolo_pose/report.json",
    "C": ROOT / "artifacts/runs/yk003/body_pose_coco/body_pose_coco_C_filtered_synth_only_eval/eval_yolo_pose/report.json",
    "D": ROOT / "artifacts/runs/yk003/body_pose_coco/body_pose_coco_D_real_plus_raw_synth_eval/eval_yolo_pose/report.json",
    "E": ROOT / "artifacts/runs/yk003/body_pose_coco/body_pose_coco_E_real_plus_filtered_synth_eval/eval_yolo_pose/report.json",
}

CONDITION_LABELS = {
    "A": "A: Real only",
    "B": "B: Raw synth only",
    "C": "C: Filtered synth only",
    "D": "D: Real + Raw synth",
    "E": "E: Real + Filtered synth",
}

METRICS = [
    ("metrics/mAP50(P)",    "Pose\nmAP50"),
    ("metrics/mAP50-95(P)", "Pose\nmAP50-95"),
    ("metrics/precision(P)","Pose\nPrecision"),
    ("metrics/recall(P)",   "Pose\nRecall"),
    ("metrics/mAP50(B)",    "Box\nmAP50"),
]

OUT_DIR = ROOT / "artifacts/figures"


def load_metrics() -> dict[str, dict]:
    data = {}
    for cid, path in EVAL_REPORTS.items():
        m = json.loads(path.read_text())["metrics"]
        data[cid] = {k: v for k, v in m.items()}
    return data


def radar_chart(data: dict[str, dict]) -> None:
    cmap = plt.get_cmap("viridis")
    colors = cmap(np.linspace(0.15, 0.90, len(EVAL_REPORTS)))

    metric_keys = [m[0] for m in METRICS]
    metric_names = [m[1] for m in METRICS]
    N = len(METRICS)

    # Angles for each axis (close the polygon)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6.4, 6.0), subplot_kw={"polar": True})

    for idx, (cid, color) in enumerate(zip(EVAL_REPORTS.keys(), colors)):
        values = [data[cid][k] for k in metric_keys]
        values += values[:1]  # close polygon
        ax.plot(angles, values, color=color, linewidth=1.8, linestyle="-", zorder=3)
        ax.fill(angles, values, color=color, alpha=0.15)
        # Label the last point with condition ID for clarity
        ax.scatter(angles[:-1], [data[cid][k] for k in metric_keys],
                   color=color, s=28, zorder=4)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metric_names, fontsize=9.5)
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=7.5, color="grey")
    ax.grid(color="grey", linestyle="--", linewidth=0.5, alpha=0.6)

    # Annotate each polygon with its condition letter at the Pose mAP50 axis (top)
    for idx, (cid, color) in enumerate(zip(EVAL_REPORTS.keys(), colors)):
        val = data[cid]["metrics/mAP50(P)"]
        offset = 0.06 * idx - 0.12  # slight radial offset so labels don't stack
        ax.annotate(
            cid,
            xy=(angles[0], val + offset),
            fontsize=8,
            color=color,
            fontweight="bold",
            ha="center",
            va="center",
        )

    legend_handles = [
        plt.Line2D([0], [0], color=c, linewidth=2, label=CONDITION_LABELS[cid])
        for cid, c in zip(EVAL_REPORTS.keys(), colors)
    ]
    ax.set_title("Pose Ablation — Shared Real Holdout\n(5-metric radar)", fontsize=11, pad=18)
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=2,
        fontsize=8.5,
        framealpha=0.90,
        edgecolor="#cccccc",
    )

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.22)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"):
        out = OUT_DIR / f"ablation_radar.{ext}"
        fig.savefig(out, dpi=180, bbox_inches="tight")
        print(f"Saved: {out}")
    plt.close()


def bar_chart_viridis(data: dict[str, dict]) -> None:
    """Clean mAP50 bar chart with viridis palette (matches seg plot style)."""
    cmap = plt.get_cmap("viridis")
    colors = list(cmap(np.linspace(0.15, 0.90, len(EVAL_REPORTS))))

    ids = list(EVAL_REPORTS.keys())
    map50 = [data[cid]["metrics/mAP50(P)"] for cid in ids]
    x = np.arange(len(ids))

    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    bars = ax.bar(x, map50, 0.55, color=colors, edgecolor="white", linewidth=0.8)
    ax.axhline(map50[0], color=colors[0], linestyle="--", linewidth=1.5, alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([i for i in ids], fontsize=12)
    ax.set_ylabel("Pose mAP@0.5 (OKS)", fontsize=11)
    ax.set_title("Data Engine Ablation — Pose mAP50\n(shared real holdout)", fontsize=11)
    ax.set_ylim(0, 0.92)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    for bar, val in zip(bars, map50):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.012, f"{val:.3f}",
                ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    legend_handles = [
        plt.Line2D([0], [0], color=c, linewidth=0, marker="s", markersize=9,
                   label=CONDITION_LABELS[cid])
        for cid, c in zip(ids, colors)
    ]
    fig.legend(handles=legend_handles, loc="lower center", bbox_to_anchor=(0.5, -0.08),
               ncol=2, fontsize=8.5, framealpha=0.90, edgecolor="#cccccc")
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.22)
    for ext, kw in [("svg", {}), ("png", {"dpi": 180})]:
        out = OUT_DIR / f"ablation_map50_viridis.{ext}"
        fig.savefig(out, bbox_inches="tight", **kw)
        print(f"Saved: {out}")
    plt.close()


def dual_metric_viridis(data: dict[str, dict]) -> None:
    """mAP50 + mAP50-95 side-by-side, viridis palette."""
    cmap = plt.get_cmap("viridis")
    colors = list(cmap(np.linspace(0.15, 0.90, len(EVAL_REPORTS))))
    ids = list(EVAL_REPORTS.keys())
    map50   = [data[cid]["metrics/mAP50(P)"]    for cid in ids]
    map5095 = [data[cid]["metrics/mAP50-95(P)"] for cid in ids]
    x = np.arange(len(ids))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8), sharey=False)
    for ax, vals, title, ylabel in [
        (axes[0], map50,   "Pose mAP50",    "Pose mAP@0.5 (OKS)"),
        (axes[1], map5095, "Pose mAP50-95", "Pose mAP@0.5:0.95 (OKS)"),
    ]:
        bars = ax.bar(x, vals, 0.55, color=colors, edgecolor="white", linewidth=0.8)
        ax.axhline(vals[0], color=colors[0], linestyle="--", linewidth=1.2, alpha=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels(ids, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=11)
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, val + 0.008, f"{val:.3f}",
                    ha="center", va="bottom", fontsize=9, fontweight="bold")

    fig.suptitle("Data Engine Ablation — Real Holdout Evaluation", fontsize=12)
    legend_handles = [
        plt.Line2D([0], [0], color=c, linewidth=0, marker="s", markersize=9,
                   label=CONDITION_LABELS[cid])
        for cid, c in zip(ids, colors)
    ]
    fig.legend(handles=legend_handles, loc="lower center", bbox_to_anchor=(0.5, -0.05),
               ncol=3, fontsize=8.5, framealpha=0.90, edgecolor="#cccccc")
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.18)
    for ext, kw in [("svg", {}), ("png", {"dpi": 180})]:
        out = OUT_DIR / f"ablation_dual_viridis.{ext}"
        fig.savefig(out, bbox_inches="tight", **kw)
        print(f"Saved: {out}")
    plt.close()


def main() -> None:
    data = load_metrics()
    radar_chart(data)
    bar_chart_viridis(data)
    dual_metric_viridis(data)


if __name__ == "__main__":
    main()
