# ROADMAP — Data Engine Paper (Body Pose)

**Goal:** deliver a fair fixed-real-budget experiment for the body-pose data engine. No novel model architecture needed.

---

## Pipeline Status

| Stage | Status | Entry |
|---|---|---|
| DataLoader (norm) | DONE | `ingest/run_dataloader.py` |
| Control Generation (ComfyUI) | DONE | `synth/run_generate.py` |
| Filter1 — SigLIP2 semantic margin | DONE | `filter/filter_stages/filter1/main.py` |
| Filter2 — YOLO pose/ROI gate | DONE | `filter/filter_stages/filter2/main.py` |
| Annotation — AI auto-label (YOLO pose) | **READY** | `label/run_ai_annotation.py` |
| Real data prep — fair anchor + holdout split | **READY** | `label/build_coco_yolo_pose.py` |
| Mixed dataset — fair shared-holdout merge | **READY** | `label/build_mixed_dataset.py` |
| Training — YOLO11-pose (5 ablations) | **READY TO RUN** | `train/run_yolo11_pose.py` |
| Eval figures — shared real holdout + summary | **READY TO RUN** | `eval/run_yolo11_pose_eval.py`, `eval/aggregate_pose_ablation_results.py` |

---

## Next Steps (ordered, minimal)

### Step 1: Materialize datasets
- Run fair real split:
  - `python label/build_coco_yolo_pose.py --config configs/coco_pose_2017__expansion/train/body_pose_real_only_prep.yaml`
- Run filtered synthetic annotation:
  - `python label/run_ai_annotation.py --config configs/coco_pose_2017__expansion/annotation/body_pose_ai_annotation.yaml`
- Run raw synthetic annotation:
  - `python label/run_ai_annotation.py --config configs/coco_pose_2017__expansion/annotation/body_pose_ai_annotation_raw.yaml`
- Build mixed datasets:
  - `python label/build_mixed_dataset.py --config configs/coco_pose_2017__expansion/train/body_pose_mixed_prep.yaml`
  - `python label/build_mixed_dataset.py --config configs/coco_pose_2017__expansion/train/body_pose_mixed_raw_prep.yaml`

### Step 2: Train five groups
- `A_real_only`
- `B_raw_synth_only`
- `C_filtered_synth_only`
- `D_real_plus_raw_synth`
- `E_real_plus_filtered_synth`

All train configs live under `configs/coco_pose_2017__expansion/train/`.

### Step 3: Evaluate on one shared real holdout
- Run `eval/run_yolo11_pose_eval.py` for all five groups using configs under `configs/coco_pose_2017__expansion/eval/`.
- Every reported metric must come from `real_test_holdout`.

### Step 4: Aggregate and write paper figures
- Run:
  - `python eval/aggregate_pose_ablation_results.py --config configs/coco_pose_2017__expansion/eval/body_pose_ablation_summary.yaml`
- Produce:
  - pose `mAP50`
  - pose `mAP50-95`
  - box `mAP50`
  - training composition counts

---

## Paper Narrative (key claims to demonstrate)

1. `real + filtered synth` improves over `real-only` under the same real-data budget
2. `filtered synth` beats `raw synth`, showing the filter cascade adds training value
3. `real + filtered synth` beats `real + raw synth`, showing filtered augmentation is better than unfiltered augmentation
4. AI annotation is reusable across raw and filtered synth branches without changing the protocol

---

## Artifact Reference

```
data/
  coco_pose_2017/          ← real anchor images
<run_dir>/
  dataloader/real_manifest.jsonl
  generate/synth_manifest.jsonl
  filter/
    filter1_scores.jsonl
    splits/{accept,reject,uncertain}.jsonl
    splits/filter2_{accept,reject,uncertain}.jsonl
  label/
    real_train_anchor/
    real_test_holdout/
    ai_dataset/
    real_plus_filtered_synth_dataset/
    real_plus_raw_synth_dataset/
```
