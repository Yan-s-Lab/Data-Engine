# Data Flow

## Pipeline

```
dataloader(norm) → control generation → filter1(SigLIP2) → filter2(YOLO pose/ROI) → annotation → training
```

The normal execution entry is a managed or serial pipeline config, not hand-running each stage. See [pipeline_operations.md](pipeline_operations.md) for local, Docker Compose, and systemd background modes.

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
Annotation (AI auto-label)                          READY
  + ai_dataset materialized from accepted synthetic images
  ↓
Training / evaluation                               READY
  + scripts are config-driven and write reports under run_dir
  ↓
Managed serial plan                                 READY
```

## Key Artifacts

| Stage | Output |
|---|---|
| DataLoader | `dataloader/real_manifest.jsonl` |
| Generation | `generate/synth_manifest.jsonl` |
| Filter1 | `filter/filter1_scores.jsonl`, `filter/splits/accept.jsonl` |
| Filter2 | `filter/filter2_scores.jsonl`, `filter/splits/filter2_accept.jsonl` |
| Annotation | `body_pose_coco_annotation/label/ai_annotations_manifest.jsonl`, `body_pose_coco_annotation/label/ai_dataset/` |
| Training | config-driven train reports under `<run_dir>/train_yolo_pose/` or `<run_dir>/train/` |
| Eval | config-driven eval reports under `<run_dir>/eval_yolo_pose/` or `<run_dir>/eval/` |

## Next Steps

See [ROADMAP.md](../ROADMAP.md).

## Docs Index

- Run commands: [README.md](../README.md)
- Pipeline operations: [docs/pipeline_operations.md](pipeline_operations.md)
- Architecture style: [docs/architecture/style.md](architecture/style.md)
