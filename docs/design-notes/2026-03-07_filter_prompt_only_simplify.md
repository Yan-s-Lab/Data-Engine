## 1) Summary
- Simplify current filter1 pipeline to prompt-only mode and remove anchor/image-guided specific fields from input/output contracts.
- Keep existing threshold calibration + filter1 execution flow unchanged in purpose.

## 2) Scope
### In scope
- Simplify siglip2 input builder output schema.
- Remove image-guided/anchor-specific parsing logic from input builder.
- Simplify filter1 row normalization and decision output fields.
- Update tests and docs to reflect prompt-only minimal contract.

### Out of scope
- Any new phase (filter2/filter3).
- Changes to threshold algorithm (`compute_margin` / threshold sweep).
- Changes to compose pipeline (`run_filter.py`) behavior.

## 3) Layer Placement (Orchestration / Components / Core)
- Components:
  - `filter/filter_stages/filter1/main.py`
  - `filter/utils/build_siglip2_input_manifest.py` (no interface change, behavior simplified)
- Core:
  - `common/filter_input_builder.py`

Rationale:
- Builder and filter1 are step-level components using shared core parsing logic.
- No orchestration layer refactor needed for this scope.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `common.filter_input_builder.build_siglip2_filter_inputs(...) -> List[Dict[str, str]]`
  - Output schema changes to minimal fields:
    - `sample_id`
    - `image_path`

- `filter/filter_stages/filter1/main.py` output rows (`filter1_scores.jsonl`)
  - Keep minimal fields:
    - `sample_id`, `image_path`, `margin`, `threshold`, `decision`

### Backward compatibility
- This is an intentional contract simplification for prompt-only flow.
- Removed fields (`generative_type`, `guided_image`, `guided_prompt`, `pos_score`, `neg_score`) are no longer guaranteed.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Input manifest row requires only resolvable image path:
  - `synthetic_image_path` or `image_path`
- `sample_id` optional; auto-generated when missing.

### Step Outputs
- SigLIP2 input manifest row schema:
  - `sample_id: str`
  - `image_path: str` (absolute)
- Filter1 score row schema:
  - `sample_id: str`
  - `image_path: str`
  - `margin: float`
  - `threshold: float`
  - `decision: accept|reject`

## 6) Config Contract
- Used keys remain:
  - `filter.input_manifests`
  - `filter.siglip2_input_manifest_output`
  - `filter.clip.compare-texts|compare_texts|compared_prompt`
  - `filter.siglip2_margin_threshold` (fallback)
- `filter.anchor_real_manifest` is ignored by prompt-only builder path.

## 7) Registry / Dispatch Plan (If applicable)
- Not applicable.

## 8) Dependency Direction Check
- Components import core only; no reverse imports introduced.

## 9) Test Plan (Minimum)
- Update unit tests:
  - `test_filter_siglip2_input_builder.py`
  - `test_filter1_main.py`
- Run:
  - `python -m unittest discover -s test -p 'test_filter_siglip2_input_builder.py'`
  - `python -m unittest discover -s test -p 'test_filter1_main.py'`
  - `python -m unittest discover -s test -p 'test_filter_prompt_contract.py'`

## 10) Risks & Mitigations
- Risk: callers still reading removed fields.
  - Mitigation: document contract change in kernel docs; keep change scoped to filter1 chain.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
