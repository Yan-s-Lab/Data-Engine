## 1) Summary
- Refine the current filter refactor by fixing broken module links introduced by file moves and by reducing config contract drift across existing filter entrypoints.
- Scope is limited to already-shipped filter functionality (`run_filter.py`, `pipeline_engine`, `filter1` helpers), excluding any `filter2/filter3` implementation.

## 2) Scope
### In scope
- Restore manifest builder import chain after `filter/manifest_builder.py` move.
- Reintroduce a stable `filter.filter_stages` export surface used by current pipeline/tests.
- Add a single shared prompt-group config resolver so `compare-texts/compare_texts/compared_prompt` are interpreted consistently.
- Update affected tests for refined contracts where required.

### Out of scope
- New phase algorithms and `filter2/filter3` implementation.
- Re-architecting the full filter module layout.
- Changing threshold/margin algorithm semantics beyond compatibility fixes.

## 3) Layer Placement (Orchestration / Components / Core)
- Orchestration:
  - `filter/run_filter.py` (no behavior expansion, wiring compatibility only).
- Components:
  - `filter/pipeline_engine/io_ops.py`
  - `filter/pipeline_engine/phase1_dual_signal.py`
  - `filter/filter_stages/__init__.py` (compat export boundary)
- Core:
  - `common/filter_prompt_contract.py` (shared config contract resolver)

Why this placement:
- Entry and pipeline code remain wiring/step logic.
- Shared config parsing belongs in `common` to avoid duplicated behavior in multiple components.
- `filter.filter_stages` is kept as a component-level compatibility facade, not business logic owner.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `common.filter_prompt_contract.resolve_prompt_groups(clip_cfg: Dict[str, Any]) -> Dict[str, List[str]]`
  - Inputs: clip config dict
  - Outputs: normalized groups `{ "positive": [...], "negative": [...] }` (possibly empty lists)
  - Error handling: never raises for missing keys; returns empty groups.

- `filter.filter_stages` exports (compat surface)
  - `aggregate_compare_texts_group_scores(...)`
  - `compute_compare_texts_prompt_scores(...)`
  - `compute_prompt_margin_scores(...)`
  - `compute_prompt_scores(...)`
  - `compute_paired_anchor_semantic_scores(...)`
  - `build_image_embeddings(...)`

### Backward compatibility
- Keep current import paths used by pipeline/tests intact.
- Keep existing config keys valid; add cross-key compatibility resolution.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- `filter.clip` dict supports:
  - `compare-texts` or `compare_texts` (phase1 compose style)
  - `compared_prompt` (filter1 threshold style)
- Each group field is normalized to list[str], trimming empty values.

### Step Outputs
- No new output artifact types.
- Existing report fields retained; prompt-group parsing source is internalized.

## 6) Config Contract
- Keys used:
  - `filter.clip.compare-texts`
  - `filter.clip.compare_texts`
  - `filter.clip.compared_prompt`
- Resolution precedence:
  1. `compare-texts`
  2. `compare_texts`
  3. `compared_prompt`
- Validation:
  - If either group is empty, caller decides whether to disable or raise.

## 7) Registry / Dispatch Plan (If applicable)
- No new phases added.
- Existing `phase1_dual_signal` registry path remains unchanged.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports:
  - `filter/run_filter.py` -> `filter.pipeline_engine` and `common.*`
- Components imports:
  - `filter/pipeline_engine/*` -> `common.*`, `filter.filter_stages` facade
- Core imports:
  - `common/filter_prompt_contract.py` -> stdlib typing only

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - Add tests for prompt group resolver precedence and normalization.
  - Keep existing filter phase/input tests passing with compatibility facade restored.
- Integration test to add/modify:
  - Minimal import-level integration: `filter.run_filter` and phase modules import successfully.
- How to run tests:
  - `python -m unittest discover -s test -p 'test_filter_phase1_semantic.py'`
  - `python -m unittest discover -s test -p 'test_filter_input_manifest_resolution.py'`
  - `python -m unittest discover -s test -p 'test_filter1_main.py'`
  - `python -m unittest discover -s test -p 'test_filter_siglip2_input_builder.py'`

## 10) Risks & Mitigations
- Risk: restored `filter.filter_stages` may still diverge from future internals.
  - Mitigation: keep it as a thin facade and route shared contract parsing into `common`.
- Risk: config precedence changes expected behavior in edge cases.
  - Mitigation: explicit test for precedence and no-hidden fallback order.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
