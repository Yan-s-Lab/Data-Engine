# CLI Rewrite Plan (Branch: rewrite/cli-data-engine)

## Why split branch
- Keep current `master` as SaaS-style baseline for regression and reuse.
- Build a CLI-first closed-loop engine in isolation to avoid architecture drift.

## Keep and reuse
- `AGENTS.md` and `docs/` as conceptual + state truth.
- Reusable ingestion functions from:
  - `collectors/common/client.py`
  - `libs/ingestion/*`
  - `libs/core_storage/*`

## New CLI-first skeleton
- `ingest/`
- `embed/`
- `filter/`
- `label/`
- `train/`
- `eval/`
- `synth/`
- `pipelines/`
- `common/`

## Phase-1 deliverables
1. `synth/comfyui_generate.py`: ComfyUI API generation + local manifest
2. `synth/comfyui_to_collection.py`: zip and ingest to collection-gateway
3. `label/label_studio_push.py`: push uncertain samples to Label Studio
4. `label/label_studio_pull.py`: pull annotations to JSONL
5. `pipelines/closed_loop_round.py`: minimal `synth -> ingest` round

## Notes
- This branch is rewrite-first, not service-compatibility-first.
- Service endpoints are reused only as temporary adapters.
