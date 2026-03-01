# Kernel Design: DataRegistry

## 1. Scope

DataRegistry owns global sample identity, dedup decisions, and provenance event records.

MVP profile (single-node first):
- keep registration lightweight and append-only
- default dedup can be conservative (`new_sample` unless explicit conflict signal)
- preserve fields needed for future multi-node upgrade without enforcing full distributed logic now

## 2. Responsibilities

- assign and resolve stable `sample_id`
- decide duplicate/same-task relationships across batches and nodes
- persist append-only manifest/event logs
- expose identity/provenance lookup for downstream modules

## 3. Non-scope

- file normalization and schema repair (owned by DataLoader)
- distributed task dispatch and retry policy (owned by TaskOrchestrator)
- artifact transfer and integrity transport mechanics (owned by ArtifactSync)

## 4. Identity model

DataRegistry uses a two-level identity to support multi-node idempotency:

- `producer_asset_key`: external idempotency key from producer side
- `sample_id`: global canonical identity used by all downstream modules

Minimum `producer_asset_key` tuple:
- `producer_name`
- `producer_run_id`
- `producer_asset_id` (or producer-side absolute path + file digest)

`sample_id` requirements:
- globally unique
- stable under repeated registration of same asset
- independent from filename conventions

## 5. Dedup decision model

Every registration attempt must end in one of these outcomes:
- `new_sample`: new canonical sample entry
- `known_sample`: same sample already registered (idempotent replay)
- `duplicate_of_existing`: new producer asset mapped to existing `sample_id`
- `conflict_pending_review`: insufficient confidence for auto merge

Dedup evidence can combine:
- content digest match
- metadata fingerprint similarity
- task-level linkage (`task_id`, `prompt_signature`, upstream lineage)

## 6. Event and manifest model

DataRegistry is append-only at event level.

Minimum event fields:
- `event_id`
- `event_type`
- `event_time`
- `sample_id` (or provisional reference before assignment)
- `producer_name`
- `producer_run_id`
- `task_id` (if available)
- `decision` (`new_sample/known_sample/duplicate_of_existing/conflict_pending_review`)
- `evidence_ref` (hash/report pointer)

Recommended event types:
- `sample.registered`
- `sample.replayed`
- `sample.dedup_linked`
- `sample.conflict_flagged`
- `sample.provenance_updated`

## 7. Contracts

Inputs (from DataLoader / NodeAgent / ArtifactSync handoff):
- normalized sample descriptor
- producer identity block
- optional digest/fingerprint block
- optional task/upstream lineage block

Outputs:
- canonical registration result (`sample_id` + dedup decision)
- updated manifest/event entries
- lookup-ready identity/provenance record for downstream modules

## 8. Invariants

- filename is not identity; `sample_id` is identity
- registration is idempotent under repeated node delivery
- identity/provenance history is append-only
- same input key replay must not create new `sample_id`
- downstream modules consume registry IDs, not producer-local file names

## 9. Cross-kernel boundaries

- DataLoader must complete normalization before DataRegistry registration.
- TaskOrchestrator uses registry state for stop conditions (for example target count).
- ArtifactSync transfer completion does not imply registration completion; DataRegistry is the source of truth for accepted samples.

## 10. Open Questions

- canonical `sample_id` composition and collision policy
- auto-merge threshold for `duplicate_of_existing` vs manual review trigger
- retention strategy for conflict cases after HITL resolution
