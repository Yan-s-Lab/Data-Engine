#!/usr/bin/env python3
"""Plot ablation experiment bar charts from the aggregate summary JSON."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

SUMMARY_JSON = ROOT / "artifacts/runs/yk003/body_pose_coco/body_pose_coco_ablation_summary/pose_ablation_summary/summary.json"
OUT_DIR = ROOT / "artifacts/figures"

LABELS = {
    "A": "A: Real only\n(1589 imgs)",
    "B": "B: Raw synth only\n(479 imgs)",
    "C": "C: Filtered synth only\n(518 imgs)",
    "D": "D: Real + Raw synth\n(2068 imgs)",
    "E": "E: Real + Filtered synth\n(2107 imgs)",
}

COLORS = {
    "A": "#2196F3",   # blue — real baseline
    "B": "#FF9800",   # orange — raw synth
    "C": "#4CAF50",   # green — filtered synth
    "D": "#FF5722",   # deep orange — real + raw
    "E": "#9C27B0",   # purple — real + filtered (data engine full)
}

GROUP_COLORS = ["#2196F3", "#FF9800", "#4CAF50", "#FF5722", "#9C27B0"]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = json.loads(SUMMARY_JSON.read_text())["rows"]
    ids = [r["group_id"] for r in rows]
    map50 = [r["pose_mAP50"] for r in rows]
    map50_95 = [r["pose_mAP50_95"] for r in rows]
    box_map50 = [r["box_mAP50"] for r in rows]
    xlabels = [LABELS[i] for i in ids]
    colors = [COLORS[i] for i in ids]

    x = np.arange(len(ids))
    width = 0.26

    # --- Figure 1: grouped bar (mAP50-P + mAP50-95-P + box mAP50) ---
    fig, ax = plt.subplots(figsize=(13, 6))
    bars1 = ax.bar(x - width, map50,     width, label="Pose mAP50",    color=[c + "cc" for c in colors])
    bars2 = ax.bar(x,         map50_95,  width, label="Pose mAP50-95", color=[c + "88" for c in colors])
    bars3 = ax.bar(x + width, box_map50, width, label="Box mAP50",     color=[c + "44" for c in colors], edgecolor=colors, linewidth=1.2)

    ax.set_xticks(x)
    ax.set_xticklabels(xlabels, fontsize=9.5)
    ax.set_ylabel("mAP", fontsize=12)
    ax.set_title("Pose Estimation Ablation — Shared Real Holdout Evaluation", fontsize=13)
    ax.set_ylim(0, 1.0)
    ax.axhline(map50[0], color=COLORS["A"], linestyle="--", linewidth=1.2, alpha=0.6, label="Real-only baseline (mAP50)")
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.008, f"{h:.3f}",
                    ha="center", va="bottom", fontsize=7.5, rotation=90)
    fig.tight_layout()
    out1 = OUT_DIR / "ablation_grouped_bar.png"
    fig.savefig(out1, dpi=180, bbox_inches="tight")
    print(f"Saved: {out1}")
    plt.close()

    # --- Figure 2: clean pose mAP50 bar only (paper-ready) ---
    fig2, ax2 = plt.subplots(figsize=(9, 5))
    bars = ax2.bar(x, map50, 0.55, color=colors, edgecolor="white", linewidth=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(xlabels, fontsize=10)
    ax2.set_ylabel("Pose mAP@0.5 (OKS)", fontsize=12)
    ax2.set_title("Data Engine Ablation — Pose mAP50 on Real Holdout", fontsize=13)
    ax2.set_ylim(0, 0.92)
    ax2.axhline(map50[0], color=COLORS["A"], linestyle="--", linewidth=1.5, alpha=0.7, label=f"Real-only baseline ({map50[0]:.3f})")
    ax2.legend(fontsize=10)
    ax2.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, map50):
        ax2.text(bar.get_x() + bar.get_width() / 2, val + 0.012, f"{val:.3f}",
                 ha="center", va="bottom", fontsize=10, fontweight="bold")
    fig2.tight_layout()
    out2 = OUT_DIR / "ablation_map50_bar.png"
    fig2.savefig(out2, dpi=180, bbox_inches="tight")
    print(f"Saved: {out2}")
    plt.close()

    # --- Figure 3: dual metric (mAP50 + mAP50-95) side by side ---
    fig3, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=False)
    for ax, metric, title, vals in [
        (axes[0], "Pose mAP@0.5",      "Pose mAP50",    map50),
        (axes[1], "Pose mAP@0.5:0.95", "Pose mAP50-95", map50_95),
    ]:
        bars = ax.bar(x, vals, 0.55, color=colors, edgecolor="white", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([LABELS[i].split("\n")[0] for i in ids], fontsize=9, rotation=15, ha="right")
        ax.set_ylabel(metric, fontsize=11)
        ax.set_title(title, fontsize=12)
        ax.axhline(vals[0], color=COLORS["A"], linestyle="--", linewidth=1.2, alpha=0.6)
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, val + 0.008, f"{val:.3f}",
                    ha="center", va="bottom", fontsize=9.5, fontweight="bold")
    fig3.suptitle("Data Engine Ablation — Real Holdout Evaluation", fontsize=13)
    fig3.tight_layout()
    out3 = OUT_DIR / "ablation_dual_metric.png"
    fig3.savefig(out3, dpi=180, bbox_inches="tight")
    print(f"Saved: {out3}")
    plt.close()


if __name__ == "__main__":
    main()
