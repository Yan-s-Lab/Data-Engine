## 1) Summary
- Remove legacy filter implementation and keep only the SigLIP2 margin workflow.
- Standardize filter execution path to:
  1) build input manifest
  2) evaluate threshold
  3) apply threshold filtering.

## 2) Scope
### In scope
- Delete legacy filter entry/modules/tests tied to compose/phase1 flow.
- Keep and wire only:
  - `filter/utils/build_siglip2_input_manifest.py`
  - `filter/utils/evaluate_siglip2_margin_threshold.py`
  - `filter/filter_stages/filter1/main.py`
- Update pipeline stage mapping for `filter`.
- Update primary docs and sample config path.

### Out of scope
- New model algorithms and policy redesign.
- Historical state-doc cleanup.

## 3) Layer Placement (Orchestration / Components / Core)
- Orchestration: `pipelines/run_yaml_pipeline.py`, `pipelines/filter_train_eval_round.py`.
- Components: `filter/filter_stages/filter1/main.py`, utility CLIs under `filter/utils/`.
- Core: reuse existing `common/*` contracts.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `build_siglip2_input_manifest.py --config --out`
  - now supports both `filter` and `filter_input_configs` config roots.
- `run_yaml_pipeline.py`
  - `filter` stage script changed to `filter/filter_stages/filter1/main.py`.

### Backward compatibility
- Not preserved by design:
  - `filter/run_filter.py`
  - `filter.pipeline_engine.*`
  - compose/phase1 policy configs.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- `filter1/main.py` requires:
  - `filter.input_manifests`
  - `filter.clip.compared_prompt.positive[]`
  - `filter.clip.compared_prompt.negative[]`
  - threshold from CLI/report/config.

### Step Outputs
- `filter/filter_stages/filter1/main.py` outputs:
  - `filter1_scores.jsonl`
  - `splits/accept.jsonl`
  - `splits/reject.jsonl`
  - `report.json`

## 6) Config Contract
- Input construction config supports:
  - `filter_input_configs.input_manifests`
  - `filter_input_configs.anchor_real_manifest` (optional)
  - top-level `output`
- Filter runtime config supports:
  - `filter.input_manifests`
  - `filter.siglip2_baseline_labeled`
  - `filter.clip.compared_prompt.{positive,negative}`

## 7) Registry / Dispatch Plan (If applicable)
- Pipeline stage registry mapping:
  - `filter` -> `filter/filter_stages/filter1/main.py`

## 8) Dependency Direction Check
- Orchestration imports components/core only.
- Component layer imports `common/*` only.
- Core has no orchestration dependency.

## 9) Test Plan (Minimum)
- Keep/update:
  - `test_filter1_main.py`
  - `test_filter_siglip2_input_builder.py`
  - `test_siglip2_margin_threshold.py`
- Remove legacy phase1/compose tests.

## 10) Risks & Mitigations
- Risk: old docs/configs still mention deleted entry.
- Mitigation: update top-level README and CN pipeline doc to new 3-step flow.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
