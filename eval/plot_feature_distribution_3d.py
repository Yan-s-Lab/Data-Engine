#!/usr/bin/env python3
"""
3D feature-space distribution plot: real / raw synth / filtered synth.

Uses ResNet50 (pretrained) to extract image embeddings, reduces to 3D via UMAP,
then renders a matplotlib 3D scatter plot suitable for paper figures.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.models import resnet50, ResNet50_Weights

ROOT = Path(__file__).resolve().parents[1]

TRANSFORM = T.Compose([
    T.Resize(256),
    T.CenterCrop(224),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def load_image_paths(source: str, cfg: dict) -> list[Path]:
    if source == "real":
        img_dir = Path(cfg["real_images_dir"])
        return sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.png"))
    elif source == "raw_synth":
        img_dir = Path(cfg["raw_synth_dir"])
        return sorted(img_dir.glob("*.png")) + sorted(img_dir.glob("*.jpg"))
    elif source == "filtered_synth":
        manifest = Path(cfg["filter2_accept_manifest"])
        rows = [json.loads(l) for l in manifest.read_text().splitlines() if l.strip()]
        paths = []
        for row in rows:
            for key in ("image_path", "synthetic_image_path", "path"):
                raw = str(row.get(key, "")).strip()
                if raw:
                    p = Path(raw)
                    paths.append(p if p.is_absolute() else ROOT / p)
                    break
        return paths
    raise ValueError(f"unknown source: {source}")


def extract_features(paths: list[Path], device: torch.device, batch_size: int = 32,
                     backbone: str = "resnet50") -> np.ndarray:
    if backbone == "siglip2":
        return _extract_siglip2(paths, device, batch_size)
    return _extract_resnet50(paths, device, batch_size)


def _extract_resnet50(paths: list[Path], device: torch.device, batch_size: int) -> np.ndarray:
    model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
    model.fc = torch.nn.Identity()
    model = model.to(device).eval()

    feats = []
    for i in range(0, len(paths), batch_size):
        batch_paths = paths[i : i + batch_size]
        imgs = []
        for p in batch_paths:
            try:
                img = Image.open(p).convert("RGB")
                imgs.append(TRANSFORM(img))
            except Exception:
                imgs.append(torch.zeros(3, 224, 224))
        batch = torch.stack(imgs).to(device)
        with torch.no_grad():
            out = model(batch)
        feats.append(out.cpu().numpy())
        if (i // batch_size) % 5 == 0:
            print(f"  {i + len(batch_paths)}/{len(paths)}")
    return np.concatenate(feats, axis=0)


def _extract_siglip2(paths: list[Path], device: torch.device, batch_size: int) -> np.ndarray:
    from transformers import AutoProcessor, AutoModel
    model_id = "google/siglip2-so400m-patch16-naflex"
    print(f"  Loading {model_id} ...")
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id).to(device).eval()

    feats = []
    for i in range(0, len(paths), batch_size):
        batch_paths = paths[i : i + batch_size]
        imgs = []
        for p in batch_paths:
            try:
                imgs.append(Image.open(p).convert("RGB"))
            except Exception:
                imgs.append(Image.new("RGB", (224, 224)))
        inputs = processor(images=imgs, return_tensors="pt", padding=True).to(device)
        with torch.no_grad():
            out = model.get_image_features(**inputs)
        feats.append(out.cpu().float().numpy())
        if (i // batch_size) % 5 == 0:
            print(f"  {i + len(batch_paths)}/{len(paths)}")
    return np.concatenate(feats, axis=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real_images_dir", default="artifacts/runs/yk003/body_pose_coco/body_pose_coco_real/label/real_train_anchor/images/train")
    parser.add_argument("--raw_synth_dir", default="data/comfyui/output")
    parser.add_argument("--filter2_accept_manifest", default="artifacts/runs/yk003/body_pose_coco/body_pose_coco_filter_2/filter/splits/filter2_accept.jsonl")
    parser.add_argument("--n_samples", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="artifacts/figures/feature_distribution_3d.png")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--backbone", default="resnet50", choices=["resnet50", "siglip2"])
    args = parser.parse_args()

    cfg = vars(args)
    rng = random.Random(args.seed)
    device = torch.device(args.device)

    groups = {
        "Real (COCO)": ("real", "#2196F3"),
        "Synthetic": ("raw_synth", "#FF5722"),
    }

    all_feats = []
    all_labels = []
    all_colors = []

    for label, (source, color) in groups.items():
        print(f"Loading {label} ...")
        paths = load_image_paths(source, cfg)
        paths = [p for p in paths if p.exists()]
        if len(paths) > args.n_samples:
            paths = rng.sample(paths, args.n_samples)
        print(f"  {len(paths)} images, extracting features ({args.backbone}) ...")
        feats = extract_features(paths, device, backbone=args.backbone)
        all_feats.append(feats)
        all_labels.extend([label] * len(feats))
        all_colors.extend([color] * len(feats))

    X = np.concatenate(all_feats, axis=0)
    print(f"Total features: {X.shape}, running UMAP ...")

    import umap
    reducer = umap.UMAP(n_components=3, n_neighbors=30, min_dist=0.1, random_state=args.seed)
    X3 = reducer.fit_transform(X)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    out_path = ROOT / args.out
    if args.backbone != "resnet50":
        out_path = out_path.with_name(out_path.stem + f"_{args.backbone}" + out_path.suffix)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    unique_labels = list(groups.keys())
    unique_colors = [groups[l][1] for l in unique_labels]
    masks = {l: np.array([x == l for x in all_labels]) for l in unique_labels}

    # --- 3D figure ---
    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection="3d")

    for label, color in zip(unique_labels, unique_colors):
        ax.scatter(
            X3[masks[label], 0], X3[masks[label], 1], X3[masks[label], 2],
            c=color, label=label, s=18, alpha=0.55, edgecolors="none", rasterized=True,
        )

    ax.view_init(elev=25, azim=45)
    ax.set_xlabel("UMAP-1", fontsize=11, labelpad=8)
    ax.set_ylabel("UMAP-2", fontsize=11, labelpad=8)
    ax.set_zlabel("UMAP-3", fontsize=11, labelpad=8)
    ax.set_title("Image Feature Distribution\n(ResNet50 + UMAP 3D)", fontsize=13, pad=12)
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_zticklabels([])
    ax.legend(fontsize=11, markerscale=2.5, loc="upper left", bbox_to_anchor=(0.0, 0.95))

    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    print(f"Saved 3D: {out_path}")
    plt.close()

    # --- 2D UMAP figure ---
    print("Running UMAP 2D ...")
    reducer2d = umap.UMAP(n_components=2, n_neighbors=30, min_dist=0.1, random_state=args.seed)
    X2 = reducer2d.fit_transform(X)

    fig2, ax2 = plt.subplots(figsize=(9, 7))
    for label, color in zip(unique_labels, unique_colors):
        ax2.scatter(
            X2[masks[label], 0], X2[masks[label], 1],
            c=color, label=label, s=18, alpha=0.55, edgecolors="none", rasterized=True,
        )
    ax2.set_xlabel("UMAP-1", fontsize=12)
    ax2.set_ylabel("UMAP-2", fontsize=12)
    ax2.set_title("Image Feature Distribution (ResNet50 + UMAP 2D)", fontsize=13)
    ax2.set_xticks([])
    ax2.set_yticks([])
    ax2.legend(fontsize=11, markerscale=2.5)
    fig2.tight_layout()
    out2d = out_path.parent / out_path.name.replace("3d", "2d")
    fig2.savefig(out2d, dpi=180, bbox_inches="tight")
    print(f"Saved 2D UMAP: {out2d}")
    plt.close()

    # --- t-SNE figure ---
    print("Running t-SNE ...")
    from sklearn.manifold import TSNE
    from sklearn.decomposition import PCA
    # PCA to 50 dims first (speeds up t-SNE significantly)
    X_pca = PCA(n_components=50, random_state=args.seed).fit_transform(X)
    X_tsne = TSNE(n_components=2, perplexity=40, max_iter=1000, random_state=args.seed, n_jobs=-1).fit_transform(X_pca)

    fig3, ax3 = plt.subplots(figsize=(9, 7))
    for label, color in zip(unique_labels, unique_colors):
        ax3.scatter(
            X_tsne[masks[label], 0], X_tsne[masks[label], 1],
            c=color, label=label, s=18, alpha=0.6, edgecolors="none", rasterized=True,
        )
    ax3.set_xlabel("t-SNE 1", fontsize=12)
    ax3.set_ylabel("t-SNE 2", fontsize=12)
    ax3.set_title(f"Image Feature Distribution ({args.backbone} + t-SNE)", fontsize=13)
    ax3.set_xticks([])
    ax3.set_yticks([])
    ax3.legend(fontsize=11, markerscale=2.5)
    fig3.tight_layout()
    out_tsne = out_path.parent / out_path.name.replace("3d", "tsne")
    fig3.savefig(out_tsne, dpi=180, bbox_inches="tight")
    print(f"Saved t-SNE: {out_tsne}")
    out_tsne_svg = out_tsne.with_suffix(".svg")
    fig3.savefig(out_tsne_svg, bbox_inches="tight")
    print(f"Saved t-SNE SVG: {out_tsne_svg}")
    plt.close()


if __name__ == "__main__":
    main()
