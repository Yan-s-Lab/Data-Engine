# Current Implementation State (Facts)

> **Scope**
> This file records what is **actually implemented** in the repository at the time of writing.
> It is *not* an aspirational plan. Plans belong in `docs/design/project_vision.md`.

## Snapshot (as of 2026-02-10)

Current repository state implements an **ingestion-focused MVP**:
- A FastAPI-based `collection-gateway` creates collection runs and ingests image samples.
- Uploaded samples are stored in **MinIO** (objects) and indexed in **Postgres** (metadata).
- Working collectors exist for:
  - manual directory upload
  - simple web-image spidering
- Synthetic generation code exists as scaffolding, but is **not end-to-end functional**.

This repo may be rewritten into a **CLI-first** research pipeline. This file is still useful as a factual record of what exists now and what can be reused.

## Implemented (Verified)

- Collection run creation API (DB persistence)
- Single image upload pipeline (sanitize → MinIO write → DB row)
- ZIP archive batch upload pipeline
- SQLAlchemy schema for `collection_runs` / `raw_samples`
- Local docker-compose infra for Postgres + MinIO + collection-gateway
- CLI collectors:
  - manual uploader (zip dir → create run → upload archive)
  - spider collector (download urls → zip → upload)

## Partial / Experimental

- Synthetic generation scaffold (Comfy/Diffusers):
  - backend abstraction exists
  - end-to-end “generate → upload” is incomplete
  - backend/config mismatches observed previously

## Not implemented (despite being mentioned in docs/ideas)

- CLIP-based filtering (ASF/PCS) and filter orchestration layer
- HITL workflow integration (Label Studio or otherwise)
- Dataset packaging/versioning/export
- Training/evaluation pipelines and feedback-driven policy updates
- Automated tests / CI

## Known risks / tech debt (current repo)

- Object storage writes are not transactionally coupled with DB commits (possible orphan objects).
- ZIP ingestion flattens filenames (risk of collisions/overwrite).
- Hardcoded default credentials exist for local dev setups.
- Minimal observability and no automated tests.

## Reuse candidates (if rewriting CLI-first)

- Ingestion-time file safety checks / sanitization logic
- Collector patterns (manifesting → batching → upload)
- Storage conventions (raw sample registry + object storage pointers)
- Any MinIO-backed “image URL” pattern can be reused for HITL tools (e.g., Label Studio).

