# Project Vision — Synthetic-First Data Engine (CLI-First)

## 1. One-sentence definition

A **synthetic-first Data Engine** is a **closed-loop dataset construction system** that continuously improves data quality and model performance through:

- ingestion (real + synthetic)
- multi-stage filtering and labeling
- supervised / semi-supervised training
- evaluation + failure analysis
- feedback-driven updates to filters, sampling, and pseudo-labeling
- HITL review and correction (optionally via third-party tools like Label Studio)

## 2. Design intent

This project optimizes for **research iteration speed** and **clarity**.

- **CLI-first**: every capability must be runnable from the command line.
- **Pipeline-first**: end-to-end workflows are composed of small CLIs.
- **Filter-centric**: data decisions are explicit, scored, explainable, and revisable.
- **Artifacts-first**: the system outputs manifests/reports on disk that make every run reproducible.

> Services/UI are optional wrappers. The “engine” must stand alone as scripts.

## 3. Canonical architecture (modules)

This is the conceptual decomposition (not an implementation claim):

### A) ingest/
Normalize and register incoming samples.

- Inputs: directories, zips, URL lists, synthetic output dirs
- Outputs: canonical **sample manifest** + normalized file layout

### B) embed/
Compute reusable embeddings to support filters.

- Inputs: sample manifest
- Outputs: embedding cache (parquet/npz/sqlite)

### C) filter/
Combine multiple filters to produce data decisions.

- Inputs: sample manifest + embeddings + filter policy config
- Outputs:
  - accept/reject/uncertain splits
  - filter scores per sample
  - summary report (counts, distributions, slices)

### D) label/
Generate or refine labels via pseudo-labeling and HITL.

- Inputs: uncertain split, model predictions, weak labels
- Outputs:
  - labels in a canonical format
  - provenance logs (who/what/when/how)

### E) train/
Train models as part of the engine.

- Inputs: training manifest (real+synthetic mix), labels
- Outputs: model artifacts, training logs, failure buckets

### F) eval/
Evaluate models and produce feedback signals.

- Inputs: model + eval manifest
- Outputs: metrics, error cases, slice reports, feedback signals

## 4. Closed-loop feedback (core requirement)

Training/Eval/HITL produce signals that **must** feed back to update:

- filter thresholds and rules
- pseudo-label acceptance criteria
- sampling strategy for next data collection/generation round
- prompt/generation policy for synthetic engine

The engine should make these updates **explicit** as versioned “policies”.

## 5. Filters (focus area)

### 5.1 ASF — Annotation Similarity Filter (concept)
Goal: detect samples with suspicious label distributions or semantic mismatch.

Typical inputs:
- annotation class counts / geometry stats
- CLIP embedding similarity to class prototypes / exemplars

Outputs:
- ASF score
- reason codes (e.g., “class imbalance anomaly”, “semantic mismatch”)

### 5.2 PCS — Perturbation CLIP Similarity (concept)
Goal: check semantic stability under controlled perturbations (prompt/pose/style).

Typical approach:
- generate perturbations (synthetic or augmented views)
- measure embedding consistency / similarity across perturbations

Outputs:
- PCS stability score
- reason codes (e.g., “unstable semantics under perturbation”)

> ASF/PCS are policies. They evolve as your model and data evolve.

## 6. HITL via third-party platforms (minimal integration)

The engine may integrate external labeling tools (e.g., Label Studio) in a **minimal** way:

- **push unlabeled** tasks from a manifest to an existing project
- **pull labeled** exports back and convert to the engine’s label format

Manual operations in the UI are acceptable. The engine avoids “always-on” coupling.

## 7. Non-goals

- production microservices, HA, multi-tenant auth, polished UI
- fully automated orchestration unless required by a specific experiment
- making every component perfect before an end-to-end loop exists

## 8. Expected artifacts (recommended conventions)

- `artifacts/runs/<run_id>/manifest_in.jsonl`
- `artifacts/runs/<run_id>/filter/report.json`
- `artifacts/runs/<run_id>/splits/accept.jsonl`, `reject.jsonl`, `uncertain.jsonl`
- `artifacts/runs/<run_id>/labels/` + `provenance.jsonl`
- `artifacts/runs/<run_id>/models/` + `metrics/` + `error_buckets/`

