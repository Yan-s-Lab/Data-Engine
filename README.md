# Data Engine — COCO Body Pose

Closed-loop data pipeline for synthetic-first training data generation and filtering.

**Pipeline:**
```
dataloader(norm) → control generation → filter1(SigLIP2) → filter2(YOLO pose/ROI) → annotation → training
```

See [ROADMAP.md](ROADMAP.md) for current progress and next steps.

---

## Setup

```bash
conda create -n dataengine python=3.10 -y
conda activate dataengine
pip install -r requirements.txt
```

Optional services (ComfyUI for generation, Label Studio for annotation):
```bash
./third_party/comfyui/comfyui_ctl.sh ensure
./third_party/label_studio/label_studio_ctl.sh ensure
```

---

## Run Commands (canonical order)

**1. DataLoader — normalize real images**
```bash
python ingest/run_dataloader.py \
  --config configs/examples/dataloader_norm_test_generation_yk002.yaml
```

**2. Control Generation — synthetic data via ComfyUI**
```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_only_managed.yaml
```

**3. Filter — build input manifest**
```bash
python filter/utils/build_siglip2_input_manifest.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_input_construction.yaml
```

**4. Filter1 — SigLIP2 semantic margin**
```bash
# Optional: evaluate threshold on labeled set first
python filter/utils/evaluate_siglip2_margin_threshold.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml

python filter/filter_stages/filter1/main.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml
```

**5. Filter2 — YOLO pose ROI gate**
```bash
python filter/filter_stages/filter2/main.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline_filter2.yaml
```

**6. Training — YOLO11-seg**
```bash
python train/run_yolo11_seg.py --config <your-train-config.yaml>
```

---

## Key Configs

| Config | Purpose |
|---|---|
| `configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_input_construction.yaml` | Build filter input manifest |
| `configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml` | Filter1 (SigLIP2) |
| `configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline_filter2.yaml` | Filter2 (YOLO pose/ROI) |

---

## Artifact Chain

```
dataloader/real_manifest.jsonl
  → generate/synth_manifest.jsonl
    → filter/filter1_scores.jsonl + splits/{accept,reject,uncertain}.jsonl
      → filter/splits/filter2_{accept,reject,uncertain}.jsonl
        → annotation labels
          → train/val dataset YAML → YOLO11-seg model
```

---

## Docker Pipeline (optional)

```bash
cp deploy/pipeline/.env.example deploy/pipeline/.env
# Edit .env: set PIPELINE_CONFIG or PIPELINE_SERIAL_PLAN
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml up --build
```

For filter-only runs, set `pipeline.steps: [filter]` in your config.

---

## Docs

- [ROADMAP.md](ROADMAP.md) — paper checklist and next steps
- [docs/data_flow.md](docs/data_flow.md) — pipeline state and artifact flow
- [docs/architecture/style.md](docs/architecture/style.md) — code style rules
- [AGENTS.md](AGENTS.md) — agent execution constraints
