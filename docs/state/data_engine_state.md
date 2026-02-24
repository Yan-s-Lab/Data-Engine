# Current Implementation State (Facts)

> **Scope**
> This file records what is **actually implemented** in this repository at scan time.
> It is not an architecture target; targets belong in `docs/design/*.md`.

## Snapshot (as of 2026-02-24)

The repository is currently a **CLI-first rewrite scaffold** with a few working adapters.

What is real today:
- Stage folders exist: `ingest/`, `embed/`, `filter/`, `label/`, `train/`, `eval/`, `synth/`, `pipelines/`, `common/`.
- Single-node YAML pipeline is runnable:
  - `dataloader -> generate -> filter -> train -> eval`
  - entrypoint: `pipelines/run_yaml_pipeline.py`
- DataLoader CLI is implemented (`ingest/run_dataloader.py`) for:
  - image collection from configured raw paths
  - optional label pairing by stem
  - filename canonicalization with template variables (including `services_id`)
  - optional image extension normalization (e.g., jpg/jpeg -> png)
  - normalized dataset output (`images/`, `labels/`) + manifest/report artifacts
- `synth -> ingest` can run through external services:
  - generate images from ComfyUI HTTP API
  - zip generated outputs
  - create collection run and upload archive to `collection-gateway`
- `generate` stage supports configurable backend:
  - `local_stub` (local image augmentation)
  - `comfyui` (real generation via ComfyUI `/prompt`)
  - ComfyUI mode supports `client_id`, `extra_data`, optional websocket completion wait, and `/history` fallback
  - ComfyUI mode now supports API-graph-native prompt injection and real-anchor image input injection by config
- Label Studio integration exists as independent CLIs:
  - push tasks from manifest JSONL
  - pull tasks/annotations and flatten to JSONL
- Minimal local runnable closed-loop stub exists for:
  - `filter -> train -> eval` artifact-connected pipeline
  - policy feedback artifact output for next-round threshold update

What is not in this repository now:
- No local `collection-gateway` service implementation.
- No real model training/evaluation algorithms yet (training/eval are currently stub logic).
- No end-to-end closed-loop policy update implementation.
- No full DataLoader kernel contract for global cross-machine identity/provenance management yet.

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
- `synth/run_generate.py`
  - supports `generate.backend` dispatch (`local_stub` / `comfyui`)
  - in `comfyui` mode:
    - accepts ComfyUI API prompt graph via `generate.comfyui.workflow` or inline `generate.comfyui.prompt_graph`
    - validates and rejects UI workflow JSON shape early with explicit error
    - submits `/prompt` with optional `client_id` and `extra_data`
    - optional text prompt injection to configured node/input (`generate.comfyui.prompt.*`)
    - optional per-anchor image upload via `/upload/image` and node/input injection (`generate.comfyui.anchor_image.*`)
    - optional multi-anchor image injection for multi-control workflows (`generate.comfyui.anchor_images[]`)
    - optional non-blocking batch submit/poll mode (`generate.comfyui.non_blocking`, `generate.comfyui.max_inflight`)
    - optional websocket wait (`executing` completion signal), then fetches final outputs from `/history`
    - downloads generated images via `/view`
    - writes `generate/{synth_manifest.jsonl,mixed_manifest.jsonl,report.json}`
- `third_party/comfyui/docker-compose.comfyui.yml`
  - ComfyUI third-party subsystem compose entry (GPU container + mounted models/output/custom_nodes/workflows)
- `third_party/comfyui/comfyui_ctl.sh`
  - check-first startup controller for ComfyUI (`ensure/check/status/start/stop/logs`)
  - `ensure` probes `/system_stats` first, then starts via docker compose when unavailable
- `third_party/comfyui/run_comfyui.sh`
  - compatibility launcher with GPU pre-check, then delegates to `comfyui_ctl.sh ensure`
  - optional model bootstrap (`DOWNLOAD_MODELS=1` by default)
- `third_party/comfyui/Dockerfile`
  - image definition for ComfyUI runtime container used by compose entry
- `third_party/comfyui/models.yaml`
  - declarative model/weights manifest reused from historical infra workflow
- `third_party/comfyui/download_models.sh`
  - model downloader for HuggingFace/Civitai targets into `data/comfyui/models`
- `synth/comfyui_to_collection.py`
  - creates collection run via `common.gateway_client.create_collection_run`
  - zips flat image directory via `common.archive.zip_flat_dir`
  - uploads archive via `/samples/from_archive`
- `ingest/register_archive.py`
  - generic archive registration path to `collection-gateway`
- `ingest/run_dataloader.py`
  - normalizes raw dataset layout by config
  - enforces image/label stem consistency during rename
  - supports template-based output naming and output-root templating
  - writes `dataloader/{real_manifest.jsonl,anchor_stats.json,report.json}`
- `label/label_studio_push.py`
  - converts manifest rows to Label Studio import task payloads
- `label/label_studio_pull.py`
  - pages through Label Studio tasks API
  - flattens annotations to JSONL for downstream use
- `filter/run_filter.py`
  - reads config, builds/loads manifest, writes split artifacts (`accept/reject/uncertain`)
  - supports `filter.mode: stub|pcs_clip|staged_clip|compose`
  - `pcs_clip` mode performs block-shuffle perturbation and CLIP image similarity scoring
  - `staged_clip` mode runs modular filter stages and produces weighted final scores
  - `compose` mode runs configurable stage switches + policy gates/weighted fusion
  - supports phase1 semantic routing (`filter.phase1_semantic`) for guided/prompt-only/fallback score selection
  - writes filter scores + stage report
- `filter/filter_stages/`
  - `clip_embed_cache.py`: CLIP/SigLIP runtime + embedding cache
  - `clip_prompt_score.py`: prompt alignment score + positive-negative prompt margin score (supports `siglip_sigmoid` mode via `logits_per_image -> sigmoid`)
  - `clip_semantic_anchor.py`: anchor-calibrated semantic consistency score (`median` over real anchors) + paired real-guided semantic score (`Sim(E(x), E(anchor(x)))`)
  - `clip_consistency.py`: perturb consistency score + multi-crop consistency score
  - `clip_anchor_ood.py`: anchor-manifold Mahalanobis OOD scoring
  - `clip_dedup.py`: duplicate similarity score
  - `quality_rules.py`: blur/exposure quality scores
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
- `pipelines/run_yaml_pipeline.py`
  - orchestrates single-node closed loop by config:
    - `dataloader -> generate -> filter -> train -> eval`
  - verifies each stage expected artifact exists
- `configs/examples/min_single_node_closed_loop_comfyui.yaml`
  - example config for real ComfyUI-backed generate stage
- `configs/examples/min_single_node_closed_loop_comfyui_api.yaml`
  - example single-node closed-loop config using ComfyUI API graph workflow
- `configs/examples/comfyui/flux_dev_api_img2img.json`
  - ComfyUI API graph example for image-to-image anchor generation
- `configs/examples/min_single_node_closed_loop_phase1_semantic_clip.yaml`
  - compose mode example for phase1 semantic routing with SigLIP2 scoring
- `common/manifest_io.py`, `common/gateway_client.py`, `common/archive.py`
  - JSON/JSONL IO, gateway HTTP calls, archive packaging
- `common/config_io.py`
  - shared config loader (YAML/JSON) and run-dir resolver

## Partial / Placeholder

- `embed/run_embed.py`: CLI placeholder only
- `pipelines/closed_loop_round.py`: not a full closed loop yet (no filter/train/eval/feedback stage)
- DataLoader kernel: partially implemented as a dedicated CLI, but not a complete kernel contract yet
- DataFilter plugin bridge: not implemented (current filter stage is monolithic stub)
- ConfigurablePipeliner: not implemented (current pipelines are hard-coded chains)

## Progress vs Target Closed Loop

Target loop:
`Real/Synth ingest -> Filter/Label -> Train -> Eval -> Failure analysis -> Policy update -> next round`

Current progress level by subsystem:
- Ingest: **L3** (DataLoader normalization CLI + external gateway integration; no full global identity kernel yet)
- Synth generation: **L3** (single-node pipeline-connected; configurable local/comfyui backend)
- Label/HITL bridge: **L2** (push/pull APIs available)
- Embed: **L0** (not implemented)
- Filter (ASF/PCS/policy): **L2** (stub + PCS-CLIP runnable decisions + split artifacts, no plugin kernel)
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

ComfyUI startup can be managed from this repo:
- `./third_party/comfyui/comfyui_ctl.sh ensure`

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
