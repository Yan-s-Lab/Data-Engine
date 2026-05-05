# Data Flow — Current State

## Pipeline

```
dataloader(norm) → control generation → filter1(SigLIP2) → filter2(YOLO pose/ROI) → annotation → training
```

## Stage Status

```
DataLoader → real_manifest.jsonl                   DONE
  ↓
Control Generation → synth_manifest.jsonl           DONE
  ↓
Filter1 (SigLIP2 margin) → filter1_scores.jsonl    DONE
  + splits/{accept,reject}.jsonl
  ↓
Filter2 (YOLO pose/ROI) → filter2_scores.jsonl     DONE
  + splits/filter2_{accept,reject,uncertain}.jsonl
  ↓
Annotation (AI auto-label)                          PARTIAL
  + filtered-synth ai_dataset done; raw-synth branch not materialized
  ↓
Training (YOLO11-pose, fair 5 ablations)            READY TO RUN
  + legacy real-only / filtered-synth-only reports exist, but are not final fair results
  ↓
Shared-holdout eval + paper figures                 TODO
```

## Key Artifacts

| Stage | Output |
|---|---|
| DataLoader | `dataloader/real_manifest.jsonl` |
| Generation | `generate/synth_manifest.jsonl` |
| Filter1 | `filter/filter1_scores.jsonl`, `filter/splits/accept.jsonl` |
| Filter2 | `filter/filter2_scores.jsonl`, `filter/splits/filter2_accept.jsonl` |
| Annotation | `body_pose_coco_annotation/label/ai_annotations_manifest.jsonl`, `body_pose_coco_annotation/label/ai_dataset/` |
| Training | fair configs under `configs/coco_pose_2017__expansion/train/`; final five-group reports pending |
| Eval | shared-holdout configs under `configs/coco_pose_2017__expansion/eval/`; reports pending |

## Next Steps

See [ROADMAP.md](../ROADMAP.md).

## Docs Index

- Run commands: [README.md](../README.md)
- Code style: [docs/architecture/style.md](architecture/style.md)
- Agent constraints: [AGENTS.md](../AGENTS.md)
