# Project Vision — Real-Anchored Synthetic Data Engine (CLI-First)

## 1. One-sentence definition

A Real-Anchored Synthetic Data Engine is a CLI-first closed-loop system that iteratively builds training data and policies through:

- real data ingestion
- guided synthetic generation
- filtering and labeling
- train (real + synthetic)
- evaluation and failure analysis
- feedback-driven policy updates
- HITL correction

## 2. Why this architecture

This project is optimized for fast research iteration with a single-node-first workflow, while keeping a clear path to multi-machine extension.

Design assumptions (MVP phase):
- data is exchanged by disk artifacts and third-party tools
- most runs execute on one host
- services like ComfyUI and Label Studio can run on different hosts

Therefore the system must be:
- CLI-first: every stage is runnable as a single CLI module
- pipeline-first: composition happens through artifact contracts
- artifact-first: manifests and reports are the source of truth
- kernel-first: stable core interfaces before algorithm expansion
- MVP-first: run end-to-end on one machine before strong consistency/distributed orchestration

## 3. Kernel vs Business Functions

Kernel is the core CLI architecture that keeps the system coherent under iteration.
Business Functions are pluggable algorithms built on top of Kernel contracts.

Kernel scope (MVP now):
- DataLoader
- DataRegistry
- DataSpider
- DataFilter bridge
- ModelLoader
- ThirdPartRunner
- ConfigurablePipeliner

Kernel scope (post-MVP extension):
- TaskOrchestrator
- ArtifactSync

Business Function scope:
- PCS 
- ASF
- ...

Rule:
- Business functions must not bypass kernel contracts.

Design split policy:
- `project_vision.md` keeps principle-level architecture only.
- Every Kernel component has its own design doc under `docs/design/kernel/`.
- Every Business function has its own design doc under `docs/design/business/`.

Current design doc index:

Kernel docs:
- `docs/design/kernel/dataloader.md`
- `docs/design/kernel/data_registry.md`
- `docs/design/kernel/dataspider.md`
- `docs/design/kernel/datafilter_bridge.md`
- `docs/design/kernel/modelloader.md`
- `docs/design/kernel/thirdpartrunner.md`
- `docs/design/kernel/task_orchestrator.md`
- `docs/design/kernel/artifact_sync.md`
- `docs/design/kernel/configurable_pipeliner.md`

Business docs:
- `docs/design/business/pcs.md`
- `docs/design/business/asf.md`

## 4. Canonical modules

Conceptual decomposition:
- `ingest/`: normalize and register incoming data
- `embed/`: compute embeddings for filtering
- `filter/`: apply policies and output decisions
- `label/`: integrate pseudo-labeling and HITL labels
- `train/`: train with mixed real and synthetic data
- `eval/`: metrics, slices, failure analysis, policy feedback
- `pipelines/`: orchestrate CLI chains
- `common/`: shared IO/config/contracts

## 5. Closed-loop policy requirement

Feedback must explicitly update next-round policies:
- filter thresholds and acceptance logic
- synthetic generation guidance
- pseudo-label acceptance gates
- sample mix strategy

Policy updates must be serialized as artifacts, not implicit runtime state.

## 6. Future multi-machine consistency constraints (post-MVP)

Root-host + multi-node execution must satisfy:
- global sample identity is managed by DataRegistry, not by DataLoader
- filename is not identity; `sample_id` is identity
- node execution uses at-least-once delivery with idempotent registration
- all task/sample state transitions are append-only events
- root host can stop distributed generation based on target count policy
- filter stages output subset manifests; they do not delete raw artifacts

## 7. Filter focus (PCS + ASF)

PCS concept:
- test embedding stability under controlled perturbations
- hypothesis: low-quality samples are less sensitive to perturbation structure

ASF concept:
- compare annotation distribution and semantic similarity consistency
- detect suspicious label-density/class-count mismatch

Both are policy modules and are versioned independently from pipeline code.

## 8. HITL integration principle

HITL is mandatory but can be minimally integrated:
- push uncertain split to annotation platform
- pull corrected labels
- preserve correction provenance
- re-inject corrected labels into future rounds

## 9. Non-goals

- production microservice reliability design
- full automation before artifact contracts are stable
- coupling core architecture to a single vendor tool
