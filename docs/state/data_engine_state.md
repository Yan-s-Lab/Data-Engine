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
- Minimal local runnable closed-loop stub exists for:
  - `filter -> train -> eval` artifact-connected pipeline
  - policy feedback artifact output for next-round threshold update

What is not in this repository now:
- No local `collection-gateway` service implementation.
- No real model training/evaluation/filter algorithms yet (current implementation is stub logic).
- No end-to-end closed-loop policy update implementation.
- No canonical DataLoader contract for cross-machine identity/provenance management.

## Directory Structure Assessment

Structure is **reasonable for CLI-first research iteration**:
- Pros:
  - clear stage separation by folder
  - each stage has a dedicated CLI entry script
  - pipeline orchestration kept in `pipelines/`
  - shared helpers isolated in `common/`
- Gaps:
  - `embed` remains placeholder; `filter/train/eval` are currently runnable stubs, not real algorithms
  - currently depends heavily on external services, with thin local state tracking
  - no machine-aware producer identity schema (`producer_name`, `producer_type`) enforced in manifests
  - no canonical sample-id assignment entrypoint for all data sources
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
- `filter/run_filter.py`
  - reads config, builds/loads manifest, writes split artifacts (`accept/reject/uncertain`)
  - writes filter scores + stage report
- `train/run_train.py`
  - consumes filter `accept` split
  - writes train manifest, mix report, and model stub artifact
- `eval/run_eval.py`
  - consumes train model stub + filter scores
  - writes metrics/slice/failure artifacts and policy feedback suggestion
- `pipelines/closed_loop_round.py`
  - orchestrates one minimal round: `comfyui_generate -> comfyui_to_collection`
- `pipelines/filter_train_eval_round.py`
  - orchestrates one minimal local round: `filter -> train -> eval`
- `common/manifest_io.py`, `common/gateway_client.py`, `common/archive.py`
  - JSON/JSONL IO, gateway HTTP calls, archive packaging
- `common/config_io.py`
  - shared config loader (YAML/JSON) and run-dir resolver

## Partial / Placeholder

- `embed/run_embed.py`: CLI placeholder only
- `pipelines/closed_loop_round.py`: not a full closed loop yet (no filter/train/eval/feedback stage)
- DataLoader kernel: not implemented as a dedicated CLI contract yet
- DataFilter plugin bridge: not implemented (current filter stage is monolithic stub)
- ConfigurablePipeliner: not implemented (current pipelines are hard-coded chains)

## Progress vs Target Closed Loop

Target loop:
`Real/Synth ingest -> Filter/Label -> Train -> Eval -> Failure analysis -> Policy update -> next round`

Current progress level by subsystem:
- Ingest: **L2** (basic external gateway integration, but no canonical DataLoader)
- Synth generation: **L2** (ComfyUI job + output manifest)
- Label/HITL bridge: **L2** (push/pull APIs available)
- Embed: **L0** (not implemented)
- Filter (ASF/PCS/policy): **L2** (stub filter decisions + split artifacts, no plugin kernel)
- Train (real + synthetic mixing): **L2** (stub train mix + model artifact)
- Eval + slice failure analysis: **L2** (stub metrics + failure report)
- Feedback-driven policy refinement: **L1** (policy suggestion artifact only)
- Multi-machine producer identity and provenance loop: **L0** (not implemented)

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
- No append-only event ledger for data lifecycle transitions.
- No claim/lock mechanism for concurrent multi-machine processing.
- No dataset-level single-format enforcement (for example, all png within one dataset).
- No standard producer identity field to disambiguate outputs from A/B/C machines.
- No automated tests or CI checks.
- `requirements.txt` includes many service dependencies not exercised by current CLI subset.

## Confirmed Direction (Design Alignment for M2)

The following direction is confirmed in `docs/design/*` and not fully implemented yet:

- Kernel-first abstraction:
  - DataLoader (entrypoint)
  - DataSpider
  - DataFilter bridge
  - ModelLoader
  - ThirdPartRunner
  - ConfigurablePipeliner
- Business functions (PCS/ASF) are extensions that must consume kernel contracts.
- Machine identity is first-class provenance:
  - `producer_name` can be machine identity (e.g. `node-a`, `node-b`, `node-c`)
  - third-party outputs must keep upstream task references

This section is a direction checkpoint, not an implementation claim.
