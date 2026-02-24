#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plot AP vs IoU curves with uncertainty bands (std/CI envelopes) from WPD-style wide CSV.

Expected CSV format (like your files):
- Wide table with paired columns: [X, Y] per series.
- The first row contains literal 'X'/'Y' markers.
- Mean series columns look like: syn50_, syn100_, ... (ending with underscore, no 'sdt').
- Envelope columns look like: syn50_sdt_lower, syn50_sdt_higher (paired X/Y columns next to them).

Outputs:
- SVG figure
"""

import os
import argparse
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def extract_xy(raw: pd.DataFrame, xcol: str, ycol: str):
    """Extract numeric x,y from a (xcol,ycol) pair, skipping the first marker row."""
    x = pd.to_numeric(raw.loc[1:, xcol], errors="coerce")
    y = pd.to_numeric(raw.loc[1:, ycol], errors="coerce")
    m = x.notna() & y.notna()
    return x[m].astype(float).to_numpy(), y[m].astype(float).to_numpy()


def _parse_suffix_arg(raw: str):
    items = [x.strip() for x in raw.split(",")]
    return [x for x in items if x]


def _parse_alias_arg(raw: str):
    items = [x.strip() for x in raw.split(",")]
    aliases = {}
    for it in items:
        if not it:
            continue
        if "=" not in it:
            raise ValueError(f"Invalid alias '{it}', expected src=dst.")
        src, dst = it.split("=", 1)
        src, dst = src.strip(), dst.strip()
        if not src or not dst:
            raise ValueError(f"Invalid alias '{it}', expected src=dst.")
        aliases[src] = dst
    return aliases


def parse_wpd_wide_csv(
    csv_path: str,
    mean_suffixes=None,
    lower_suffixes=None,
    upper_suffixes=None,
    base_aliases=None,
    mean_regex: str | None = None,
):
    """Parse your WPD wide CSV into {series_name: {x,y,xl,yl,xu,yu}}."""
    if mean_suffixes is None:
        mean_suffixes = ["_", "_mid", "_mean"]
    if lower_suffixes is None:
        lower_suffixes = ["_sdt_lower", "_std_lower", "_lower"]
    if upper_suffixes is None:
        upper_suffixes = ["_sdt_higher", "_std_higher", "_higher", "_upper"]
    if base_aliases is None:
        base_aliases = {}

    raw = pd.read_csv(csv_path)
    cols = list(raw.columns)

    def _normalize_mean_base(name: str) -> str:
        # Configurable normalization so mean/envelope columns can be grouped.
        # e.g. real_mid + real_lower/real_higher -> base "real"
        for suffix in sorted(mean_suffixes, key=len, reverse=True):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return base_aliases.get(name, name)

    def _split_kind(col_name: str):
        for suffix in lower_suffixes:
            if col_name.endswith(suffix):
                return _normalize_mean_base(col_name[: -len(suffix)]), "lower"
        for suffix in upper_suffixes:
            if col_name.endswith(suffix):
                return _normalize_mean_base(col_name[: -len(suffix)]), "upper"
        return _normalize_mean_base(col_name), "mean"

    # Build X/Y pairs from the first marker row when available, then fallback to adjacent pairs.
    xy_pairs = []
    if not raw.empty:
        row0 = raw.iloc[0]
        for i in range(len(cols) - 1):
            x_mark = str(row0[cols[i]]).strip().upper()
            y_mark = str(row0[cols[i + 1]]).strip().upper()
            if x_mark == "X" and y_mark == "Y":
                xy_pairs.append((cols[i], cols[i + 1]))

    if not xy_pairs:
        for i in range(0, len(cols) - 1, 2):
            xy_pairs.append((cols[i], cols[i + 1]))

    mean_pairs = {}
    env_pairs = {}  # base -> {"lower":(xcol,ycol), "upper":(xcol,ycol)}
    mean_pattern = re.compile(mean_regex) if mean_regex else None
    for xcol, ycol in xy_pairs:
        base, kind = _split_kind(xcol)
        if kind == "mean":
            if mean_pattern and not mean_pattern.fullmatch(xcol):
                continue
            mean_pairs[base] = (xcol, ycol)
        else:
            env_pairs.setdefault(base, {})[kind] = (xcol, ycol)

    data = {}
    for name, (xcol, ycol) in mean_pairs.items():
        x, y = extract_xy(raw, xcol, ycol)

        # sort by x
        idx = np.argsort(x)
        x, y = x[idx], y[idx]

        data[name] = {"x": x, "y": y}

        if name in env_pairs and "lower" in env_pairs[name] and "upper" in env_pairs[name]:
            xl, yl = extract_xy(raw, *env_pairs[name]["lower"])
            xu, yu = extract_xy(raw, *env_pairs[name]["upper"])

            # sort envelopes
            s = np.argsort(xl); xl, yl = xl[s], yl[s]
            s = np.argsort(xu); xu, yu = xu[s], yu[s]

            data[name].update({"xl": xl, "yl": yl, "xu": xu, "yu": yu})

    if not data:
        raise ValueError("No series parsed. Check your CSV column names / format.")

    return data


def sort_series_by_size(series_names):
    """
    Sort names like syn50, syn100, syn345 by numeric suffix if present.
    Falls back to lexical if parsing fails.
    """
    def key_fn(n):
        # n like "syn50"
        digits = "".join([c for c in n if c.isdigit()])
        return int(digits) if digits else 10**9
    try:
        return sorted(series_names, key=key_fn)
    except Exception:
        return sorted(series_names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to WPD wide CSV (your format).")
    ap.add_argument("--out", default="ap_vs_iou.svg", help="Output SVG filename.")
    ap.add_argument("--title", default="AP vs IoU (shaded + errorbars) — domain=real")
    ap.add_argument("--xlabel", default="IoU threshold")
    ap.add_argument("--ylabel", default="AP")
    ap.add_argument("--ymin", type=float, default=-0.05, help="Bottom y-limit to create padding (so y=0 not on frame).")
    ap.add_argument("--ymax", type=float, default=1.02)
    ap.add_argument("--xmin", type=float, default=None, help="Optional explicit left x-limit.")
    ap.add_argument("--xmax", type=float, default=None, help="Optional explicit right x-limit.")
    ap.add_argument("--xpad", type=float, default=1.0, help="Left/right padding when xmin/xmax are not provided.")
    ap.add_argument("--band_alpha", type=float, default=0.15)
    ap.add_argument("--highlight-xmin", type=float, default=0.5, help="Left x bound for emphasized rectangle. Set to none via --disable-highlight.")
    ap.add_argument("--highlight-xmax", type=float, default=0.7, help="Right x bound for emphasized rectangle.")
    ap.add_argument("--highlight-alpha", type=float, default=0.20, help="Alpha for emphasized rectangle.")
    ap.add_argument("--highlight-color", default="#ffd166", help="Color for emphasized rectangle.")
    ap.add_argument("--disable-highlight", action="store_true", help="Disable x-range emphasized rectangle.")
    ap.add_argument("--linewidth", type=float, default=2.0)
    ap.add_argument("--markersize", type=float, default=5.0)
    ap.add_argument("--cmap", default="viridis", help="Sequential colormap name (viridis/cividis/plasma).")
    ap.add_argument(
        "--mean-suffixes",
        default="_,_mid,_mean",
        help="Comma-separated mean suffixes stripped from X column title for series grouping.",
    )
    ap.add_argument(
        "--lower-suffixes",
        default="_sdt_lower,_std_lower,_lower",
        help="Comma-separated lower-band suffixes used to classify envelope columns.",
    )
    ap.add_argument(
        "--upper-suffixes",
        default="_sdt_higher,_std_higher,_higher,_upper",
        help="Comma-separated upper-band suffixes used to classify envelope columns.",
    )
    ap.add_argument(
        "--base-aliases",
        default="",
        help="Optional comma-separated base aliases in src=dst form (e.g. real_mid=real,syn_avg=syn).",
    )
    ap.add_argument(
        "--mean-regex",
        default=None,
        help="Optional regex to restrict mean-series X column names (full match).",
    )
    args = ap.parse_args()

    data = parse_wpd_wide_csv(
        args.csv,
        mean_suffixes=_parse_suffix_arg(args.mean_suffixes),
        lower_suffixes=_parse_suffix_arg(args.lower_suffixes),
        upper_suffixes=_parse_suffix_arg(args.upper_suffixes),
        base_aliases=_parse_alias_arg(args.base_aliases),
        mean_regex=args.mean_regex,
    )

    # stable / semantic ordering: syn50 < syn100 < ...
    names = sort_series_by_size(list(data.keys()))

    # choose ordered, colorblind-safe colors
    cmap = plt.get_cmap(args.cmap)
    colors = cmap(np.linspace(0.15, 0.90, len(names)))

    # figure size: similar compact paper style
    plt.figure(figsize=(6.2, 4.8))

    for name, color in zip(names, colors):
        d = data[name]
        x, y = d["x"], d["y"]

        # draw band if present
        if "yl" in d and "yu" in d:
            xl, yl = d["xl"], d["yl"]
            xu, yu = d["xu"], d["yu"]

            # Align envelopes to mean x grid (important if envelope x is slightly off-grid)
            y_lower = np.interp(x, xl, yl)
            y_upper = np.interp(x, xu, yu)

            # Enforce ordering to avoid digitization artifacts
            y_lower = np.minimum(y_lower, y)
            y_upper = np.maximum(y_upper, y)

            plt.fill_between(
                x, y_lower, y_upper,
                color=color, alpha=args.band_alpha, linewidth=0
            )

        # mean line
        plt.plot(
            x, y,
            marker="o",
            markersize=args.markersize,
            linewidth=args.linewidth,
            color=color,
            label=name + "_"  # keep legend style similar to original if you want
        )

    # axes labels/title
    plt.title(args.title)
    plt.xlabel(args.xlabel)
    plt.ylabel(args.ylabel)

    # padding like your original figure (y=0 not on bottom frame)
    all_x = np.concatenate([data[n]["x"] for n in names])
    xmin, xmax = float(np.min(all_x)), float(np.max(all_x))
    xleft = args.xmin if args.xmin is not None else xmin - args.xpad
    xright = args.xmax if args.xmax is not None else xmax + args.xpad
    if xleft >= xright:
        raise ValueError(f"Invalid x limits: xmin={xleft} must be < xmax={xright}.")
    plt.xlim(xleft, xright)
    plt.ylim(args.ymin, args.ymax)

    if not args.disable_highlight:
        hx0, hx1 = args.highlight_xmin, args.highlight_xmax
        if hx0 >= hx1:
            raise ValueError(f"Invalid highlight x-range: {hx0} must be < {hx1}.")
        plt.axvspan(
            hx0, hx1,
            color=args.highlight_color,
            alpha=args.highlight_alpha,
            zorder=0
        )

    # small extra margins
    plt.margins(x=0.01, y=0.02)

    plt.legend(loc="upper right")
    plt.tight_layout()

    out_path = args.out
    plt.savefig(out_path, format="svg")
    print(f"Saved SVG: {out_path}")


if __name__ == "__main__":
    main()
