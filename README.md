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

**6. AI Annotation — build filtered and raw synthetic pose datasets**
```bash
# Filtered synth branch (main paper branch)
python label/run_ai_annotation.py \
  --config configs/coco_pose_2017__expansion/annotation/body_pose_ai_annotation.yaml

# Raw synth branch (pre-filter ablation)
python label/run_ai_annotation.py \
  --config configs/coco_pose_2017__expansion/annotation/body_pose_ai_annotation_raw.yaml
```

**7. Real data — freeze fair train anchor + shared real holdout**
```bash
# Download first: val2017.zip + annotations_trainval2017.zip → artifacts/datasets/coco_val2017/
python label/build_coco_yolo_pose.py \
  --config configs/coco_pose_2017__expansion/train/body_pose_real_only_prep.yaml
```

**8. Mixed datasets — merge train splits, reuse shared real holdout**
```bash
# Real + filtered synth
python label/build_mixed_dataset.py \
  --config configs/coco_pose_2017__expansion/train/body_pose_mixed_prep.yaml

# Real + raw synth
python label/build_mixed_dataset.py \
  --config configs/coco_pose_2017__expansion/train/body_pose_mixed_raw_prep.yaml
```

**9. Training — YOLO11-pose fair ablations**
```bash
# A: real-only
python train/run_yolo11_pose.py --config configs/coco_pose_2017__expansion/train/body_pose_A_real_only.yaml
# B: raw synth-only
python train/run_yolo11_pose.py --config configs/coco_pose_2017__expansion/train/body_pose_B_raw_synth_only.yaml
# C: filtered synth-only
python train/run_yolo11_pose.py --config configs/coco_pose_2017__expansion/train/body_pose_C_filtered_synth_only.yaml
# D: real + raw synth
python train/run_yolo11_pose.py --config configs/coco_pose_2017__expansion/train/body_pose_D_real_plus_raw_synth.yaml
# E: real + filtered synth
python train/run_yolo11_pose.py --config configs/coco_pose_2017__expansion/train/body_pose_E_real_plus_filtered_synth.yaml
```

**10. Eval — one shared real holdout for every group**
```bash
python eval/run_yolo11_pose_eval.py --config configs/coco_pose_2017__expansion/eval/body_pose_A_real_only_eval.yaml
python eval/run_yolo11_pose_eval.py --config configs/coco_pose_2017__expansion/eval/body_pose_B_raw_synth_only_eval.yaml
python eval/run_yolo11_pose_eval.py --config configs/coco_pose_2017__expansion/eval/body_pose_C_filtered_synth_only_eval.yaml
python eval/run_yolo11_pose_eval.py --config configs/coco_pose_2017__expansion/eval/body_pose_D_real_plus_raw_synth_eval.yaml
python eval/run_yolo11_pose_eval.py --config configs/coco_pose_2017__expansion/eval/body_pose_E_real_plus_filtered_synth_eval.yaml

python eval/aggregate_pose_ablation_results.py \
  --config configs/coco_pose_2017__expansion/eval/body_pose_ablation_summary.yaml
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
          → fair train datasets + shared real holdout → YOLO11-pose model
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
- [docs/body_pose_fair_experiment.md](docs/body_pose_fair_experiment.md) — fair experiment protocol
- [docs/data_flow.md](docs/data_flow.md) — pipeline state and artifact flow
- [docs/architecture/style.md](docs/architecture/style.md) — code style rules
- [AGENTS.md](AGENTS.md) — agent execution constraints
