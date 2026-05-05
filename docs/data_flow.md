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
  + splits/{accept,reject,uncertain}.jsonl
  ↓
Filter2 (YOLO pose/ROI) → filter2_scores.jsonl     DONE
  + splits/filter2_{accept,reject,uncertain}.jsonl
  ↓
Annotation (AI auto-label)                          TODO
  ↓
Training (YOLO11-seg, 3 conditions)                 TODO
  ↓
Eval figures                                        TODO
```

## Key Artifacts

| Stage | Output |
|---|---|
| DataLoader | `dataloader/real_manifest.jsonl` |
| Generation | `generate/synth_manifest.jsonl` |
| Filter1 | `filter/filter1_scores.jsonl`, `filter/splits/accept.jsonl` |
| Filter2 | `filter/filter2_scores.jsonl`, `filter/splits/filter2_accept.jsonl` |
| Annotation | `label/ai_annotations.jsonl` (TODO) |
| Training | `train_yolo/weights/best.pt` (TODO) |

## Next Steps

See [ROADMAP.md](../ROADMAP.md).

## Docs Index

- Run commands: [README.md](../README.md)
- Code style: [docs/architecture/style.md](architecture/style.md)
- Agent constraints: [AGENTS.md](../AGENTS.md)
