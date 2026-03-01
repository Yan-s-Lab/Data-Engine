# CLI Rewrite Plan (Kernel-First)

## 1. Rewrite objective

Build a CLI-first closed-loop data engine where core data contracts are stable before advanced algorithms.

## 2. Core decision

Treat Kernel as the primary milestone:
- Kernel = data flow and orchestration contracts
- Business Functions = pluggable algorithms on top of Kernel

Priority:
1. make data identity/provenance reliable across machines
2. make stage contracts explicit and reproducible
3. then iterate PCS/ASF and training policies

## 3. Kernel modules (target)

1. DataLoader
- canonical ingestion entry
- id assignment
- format normalization
- manifest/event logging

2. DataSpider
- automated mining adapters
- can run in parallel with human collection

3. DataFilter bridge
- plugin interface to `filter1/filter2/...`
- unified decision schema

4. ModelLoader
- unified model/tool invocation abstraction

5. ThirdPartRunner
- adapters for ComfyUI, Label Studio, and other external capabilities
- ComfyUI adapter should support async-style queue submission/polling and multi-control image injection for research iteration speed
- third-party services should provide repo-local bootstrap contracts (check -> start), with docker compose as canonical startup surface for single-node research loops

6. ConfigurablePipeliner
- compose CLI stages by config
- no hidden runtime coupling

## 4. Multi-machine contract

Each producer must register identity:
- `producer_name`: machine/system identity (for example `node-a`, `node-b`, `node-c`)
- `producer_type`: comfyui/labelstudio/manual/spider/other

All produced samples must carry:
- `sample_id`, `dataset_id`, `run_id`
- producer fields
- provenance references to upstream tasks or samples

This enables A/B/C hosts to run heterogeneous workloads concurrently with deterministic traceability.

## 5. Phased rollout

M2 (current target):
- DataLoader contract
- DataFilter plugin bridge
- ConfigurablePipeliner baseline
- state/docs alignment

M3:
- initial PCS and ASF implementations
- HITL provenance merge into trainable dataset manifests

M4:
- feedback-driven automatic policy update loop
- multi-round policy history tracking

## 6. Guardrails

- every stage must be runnable with `python module.py --config config.yaml`
- no stage bypasses DataLoader manifest contracts
- policy updates are artifact outputs, not hidden mutable globals
- docs/state stays factual; docs/design stays aspirational
