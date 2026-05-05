# ROADMAP — Data Engine Paper (Body Pose)

**Goal:** deliver minimal experiment proving the data engine pipeline. Real-only vs synth-only vs real+synth(data engine). No novel architecture needed.

---

## Pipeline Status

| Stage | Status | Entry |
|---|---|---|
| DataLoader (norm) | DONE | `ingest/run_dataloader.py` |
| Control Generation (ComfyUI) | DONE | `synth/run_generate.py` |
| Filter1 — SigLIP2 semantic margin | DONE | `filter/filter_stages/filter1/main.py` |
| Filter2 — YOLO pose/ROI gate | DONE | `filter/filter_stages/filter2/main.py` |
| Annotation — AI auto-label (YOLO pose) | **READY** | `label/run_ai_annotation.py` |
| Real data prep — COCO val2017 → YOLO-pose | **TODO** | `label/build_coco_yolo_pose.py` |
| Mixed dataset — merge real + synth | **TODO** | `label/build_mixed_dataset.py` |
| Training — YOLO11-pose (3 conditions) | **TODO** | `train/run_yolo11_pose.py` |
| Eval figures — mAP / OKS / visual | **TODO** | `eval/run_yolo11_pose_eval.py` |

---

## Next Steps (ordered, minimal)

### Step 1: AI Annotation on filter2_accept
Run YOLO pose on `filter2_accept.jsonl` images to auto-generate keypoint/body labels.
- Input: `<run_dir>/filter/splits/filter2_accept.jsonl`
- Tool: YOLO pose model (`third_party/yolo26x-pose.pt`) or ViTPose
- Output: COCO-format annotation JSON or YOLO-format label files
- Script to add: `label/run_ai_annotation.py`

Optionally push uncertain samples to Label Studio for minimal human review:
```bash
python label/label_studio_push.py --config <config>
python label/label_studio_pull.py --config <config>
python label/label_studio_to_yolo_seg.py --config <config>
```

### Step 2: Build dataset YAML (train/val split)
Three conditions for ablation:
- **A**: real-only (COCO pose val split, small anchor set)
- **B**: synth-only (filter2_accept, no real)
- **C**: real + synth (data engine full output) ← main claim

Create `configs/coco_pose_2017__expansion/train/dataset_real_only.yaml`, `dataset_synth_only.yaml`, `dataset_mixed.yaml`.

### Step 3: Run training (3 conditions)
```bash
python train/run_yolo11_seg.py --config configs/.../train/dataset_mixed.yaml
```
Use `train_yolo.model: yolo11n-seg.pt` (or `yolo11s-seg.pt` for better accuracy).

### Step 4: Eval + paper figures
- mAP@50 / mAP@50-95 per condition
- PCKh or OKS for body pose quality
- Visual: side-by-side real vs synth vs filtered samples
- Visual: training curve real-only vs mixed

---

## Paper Narrative (key claims to demonstrate)

1. Synthetic-first + filtering matches or improves over real-only baseline with less human labeling effort
2. Filter cascade (SigLIP2 → YOLO pose ROI) removes bad generations effectively — show accept/reject rate and qualitative examples
3. AI annotation (YOLO pose) replaces most human annotation — show label quality comparison
4. Mixed training (real+synth) beats synth-only — validates data engine value

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
    ai_annotations.jsonl   ← TODO
  train_yolo/
    weights/best.pt        ← TODO
```
