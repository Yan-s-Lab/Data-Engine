# Current Implementation State (Facts)

> **Scope**
> This file records what is **actually implemented** in this repository at scan time.
> It is not an architecture target; targets belong in `docs/design/*.md`.

## Snapshot (as of 2026-02-11)

The repository is currently a **CLI-first rewrite scaffold** with a few working adapters.

What is real today:
- Stage folders exist: `ingest/`, `embed/`, `filter/`, `label/`, `train/`, `eval/`, `synth/`, `pipelines/`, `common/`.
- `synth -> ingest` can run through external services:
  - generate images from ComfyUI HTTP API
  - zip generated outputs
  - create collection run and upload archive to `collection-gateway`
- Label Studio integration exists as independent CLIs:
  - push tasks from manifest JSONL
  - pull tasks/annotations and flatten to JSONL

What is not in this repository now:
- No local `collection-gateway` service implementation.
- No local model training/evaluation/filter algorithms yet.
- No end-to-end closed-loop policy update implementation.

## Directory Structure Assessment

Structure is **reasonable for CLI-first research iteration**:
- Pros:
  - clear stage separation by folder
  - each stage has a dedicated CLI entry script
  - pipeline orchestration kept in `pipelines/`
  - shared helpers isolated in `common/`
- Gaps:
  - most stage scripts are placeholders (`embed/filter/train/eval`)
  - currently depends heavily on external services, with thin local state tracking
  - no tests and no experiment/state artifacts schema under versioned docs/config

## Implemented (Verified by code scan)

- `synth/comfyui_generate.py`
  - submits workflow to ComfyUI `/prompt`
  - polls `/history/{prompt_id}`
  - downloads images from `/view`
  - writes local files + `manifest.jsonl`
- `synth/comfyui_to_collection.py`
  - creates collection run via `common.gateway_client.create_collection_run`
  - zips flat image directory via `common.archive.zip_flat_dir`
  - uploads archive via `/samples/from_archive`
- `ingest/register_archive.py`
  - generic archive registration path to `collection-gateway`
- `label/label_studio_push.py`
  - converts manifest rows to Label Studio import task payloads
- `label/label_studio_pull.py`
  - pages through Label Studio tasks API
  - flattens annotations to JSONL for downstream use
- `pipelines/closed_loop_round.py`
  - orchestrates one minimal round: `comfyui_generate -> comfyui_to_collection`
- `common/manifest_io.py`, `common/gateway_client.py`, `common/archive.py`
  - JSON/JSONL IO, gateway HTTP calls, archive packaging

## Partial / Placeholder

- `embed/run_embed.py`: CLI placeholder only
- `filter/run_filter.py`: CLI placeholder only
- `train/run_train.py`: CLI placeholder only
- `eval/run_eval.py`: CLI placeholder only
- `pipelines/closed_loop_round.py`: not a full closed loop yet (no filter/train/eval/feedback stage)

## Progress vs Target Closed Loop

Target loop:
`Real/Synth ingest -> Filter/Label -> Train -> Eval -> Failure analysis -> Policy update -> next round`

Current progress level by subsystem:
- Ingest: **L2** (basic external gateway integration)
- Synth generation: **L2** (ComfyUI job + output manifest)
- Label/HITL bridge: **L2** (push/pull APIs available)
- Embed: **L0** (not implemented)
- Filter (ASF/PCS/policy): **L0** (not implemented)
- Train (real + synthetic mixing): **L0** (not implemented)
- Eval + slice failure analysis: **L0** (not implemented)
- Feedback-driven policy refinement: **L0** (not implemented)

Legend:
- `L0`: absent
- `L1`: interface/placeholder
- `L2`: single-step runnable
- `L3`: connected multi-step pipeline
- `L4`: iterative closed loop with policy updates

## External Dependencies (Runtime Contracts)

Current CLIs assume these external services are available:
- ComfyUI HTTP API (default `http://127.0.0.1:8188`)
- collection-gateway (via `COLLECTION_GATEWAY_URL`, default `http://localhost:8001`)
- Label Studio API (`/api/projects/{id}/import`, `/api/tasks`)

## Known Risks / Tech Debt

- `common.archive.zip_flat_dir` writes flattened filenames only; same-name files can collide.
- Label Studio bridge does not yet track correction provenance back into training sets.
- No filtering policy state store (threshold/version/history).
- No automated tests or CI checks.
- `requirements.txt` includes many service dependencies not exercised by current CLI subset.
