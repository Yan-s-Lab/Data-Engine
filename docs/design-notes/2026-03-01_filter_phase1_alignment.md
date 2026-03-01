# 1) Summary
- What is the change?
  - Align Filter phase1 implementation with `AGENTS.md` and `docs/architecture/style.md` by:
    - splitting oversized phase1 functions to satisfy function-length constraints,
    - making policy config handling consistent with current dual-signal pipeline,
    - aligning configs/docs/tests to avoid `phase1_v1` vs `phase1_dual_signal` drift.
- Why is it needed?
  - Current implementation is structurally modular but not fully compliant on complexity limits and config/doc consistency, causing avoidable runtime/config mismatch risk.

## 2) Scope
### In scope
- `filter/pipeline_engine/phase1_dual_signal.py` function refactor (no algorithm change).
- `filter/run_filter.py` policy decision compatibility normalization.
- Filter configs/docs/tests that still reference legacy `phase1_v1`.
- Add/update unit tests for policy normalization and dual-signal decision path.

### Out of scope
- New filtering phases beyond `phase1_dual_signal`.
- Changes to generation/dataloader/training logic.
- Reworking managed pipeline architecture.

## 3) Layer Placement (Orchestration / Components / Core)
- Which layer(s) will change?
  - Orchestration: `filter/run_filter.py` policy decision validation/normalization.
  - Components: `filter/pipeline_engine/phase1_dual_signal.py` internal decomposition.
  - Documentation/config/testing layer updates under `docs/`, `configs/`, `test/`.
- Why is this the correct placement?
  - Policy key validation belongs to entry orchestration.
  - Per-phase scoring/selection logic belongs to component layer.
  - No algorithmic primitive changes are required in core filter_stages.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `filter/run_filter.py`:
  - `_resolve_decision_policy(filter_cfg: Dict[str, Any]) -> str` (new helper)
  - behavior: accepts `phase1_dual_signal` and legacy `phase1_v1`, canonicalizes to `phase1_dual_signal`.
- `filter/pipeline_engine/phase1_dual_signal.py`:
  - `compute_phase1_score_rows(...) -> tuple[List[Dict[str, Any]], Dict[str, Any]]` unchanged signature.
  - `apply_dual_signal_selection(...) -> Dict[str, Any]` unchanged signature.
  - internal helper split only; external contract unchanged.

Inputs:
- Existing row dict contracts (`sample_id`, `source`, optional guide fields) unchanged.

Outputs:
- score rows/report keys unchanged.

Error handling:
- Invalid `policy.decision` raises `ValueError` with explicit accepted values.

### Backward compatibility
- Does this break existing callers/configs?
  - Existing `policy.decision=phase1_dual_signal` callers unaffected.
  - Legacy `policy.decision=phase1_v1` becomes accepted and mapped to dual-signal.
- If yes, migration plan:
  - No hard break expected; docs/config examples will be updated to canonical dual-signal key.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Schema type (dataclass/pydantic/dict contract): dict contract.
- Required fields:
  - `sample_id: str`
  - `source: str` (`real` or `synthetic` expected)
  - `image_path: str` (for embedding stage)
- Optional fields + defaults:
  - guided markers: `guide_image_id`, `anchor_real_sample_id`, etc.
  - phase score fields default to `0.0` when missing.

### Step Outputs
- Schema type: dict contract.
- Fields:
  - `decision`, `decision_basis`, `keep`
  - `s_prompt`, `s_anchor`, `s_anchor_hit`, `s_final`
  - phase routing and runtime metadata.

## 6) Config Contract
- Config keys added/used:
  - `filter.policy.decision`: accepts `phase1_dual_signal` (canonical), `phase1_v1` (legacy alias).
  - `filter.phase1_dual_signal.*`: existing thresholds and policies.
- Defaults:
  - unchanged defaults in code (`target_source=synthetic`, thresholds default `0.5`, `hard_reject=false`).
- Validation rules:
  - policy decision must be one of allowed values.
- Example config snippet:
```yaml
filter:
  mode: compose
  policy:
    decision: phase1_dual_signal
  pipeline:
    phases:
      - id: phase1_dual_signal
        enabled: true
  phase1_dual_signal:
    enabled: true
    prompt_accept_threshold: 0.7
    prompt_uncertain_threshold: 0.5
    pair_accept_threshold: 0.8
    pair_uncertain_threshold: 0.6
    hard_reject: false
    missing_pair_policy: uncertain
```

## 7) Registry / Dispatch Plan (If applicable)
- Registry name/location:
  - phase registry in `filter/pipeline_engine/orchestrator.py`.
- Step name(s) registered:
  - `phase1_dual_signal`.
- How config resolves to implementation:
  - `filter.pipeline.phases[].id` -> registry runner function.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports:
  - `filter/run_filter.py` imports `filter.pipeline_engine` only.
- Components imports:
  - `filter/pipeline_engine/phase1_dual_signal.py` imports `filter.filter_stages` and local io helpers.
- Core imports:
  - `filter/filter_stages/*` do not import orchestration/component modules.

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - Extend `test/test_filter_phase1_semantic.py` with policy decision normalization coverage.
  - Keep existing dual-signal selection and input resolution tests green.
- Integration test to add/modify:
  - Not required for this alignment-only change (no pipeline topology change).
- How to run tests:
  - `PYTHONPATH=. python test/test_filter_phase1_semantic.py`
  - `PYTHONPATH=. python test/test_filter_input_manifest_resolution.py`

## 10) Risks & Mitigations
- Potential failure modes:
  - Legacy alias acceptance may hide stale configs if behavior diverges from historical `phase1_v1` semantics.
  - Refactor could accidentally alter decision counting.
- Mitigations:
  - Keep external outputs/keys unchanged.
  - Add focused unit tests for decision behavior and alias normalization.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
