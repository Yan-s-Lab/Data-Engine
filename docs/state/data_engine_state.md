# Implementation State (2026-05-05)

## Done
- DataLoader normalization: `ingest/run_dataloader.py`
- Control generation (ComfyUI): `synth/run_generate.py`
- Filter1 (SigLIP2 semantic margin): `filter/filter_stages/filter1/main.py`
- Filter2 (YOLO pose/ROI gate): `filter/filter_stages/filter2/main.py`
- Label Studio push/pull: `label/label_studio_{push,pull}.py`
- Label→YOLO-seg converter: `label/label_studio_to_yolo_seg.py`
- YOLO11-seg trainer: `train/run_yolo11_seg.py`

## Not Yet Run / TODO
- AI annotation on filter2_accept (script: `label/run_ai_annotation.py` — not yet written)
- Dataset YAML construction (train/val split for 3 conditions)
- Training runs (real-only / synth-only / mixed)
- Eval figures for paper

## See Also
- [ROADMAP.md](../../ROADMAP.md) — ordered next steps
- [docs/data_flow.md](../data_flow.md) — artifact chain
