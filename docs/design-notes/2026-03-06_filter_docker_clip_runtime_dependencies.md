# 1) Summary
- Add missing runtime dependencies for filter CLIP/SigLIP execution in managed Docker pipeline: `torch` and `transformers`.
- This is needed because filter phase currently fails at runtime with `ModuleNotFoundError: No module named 'torch'` in container execution.

## 2) Scope
### In scope
- Update project dependency contract in `pyproject.toml`.
- Regenerate `requirements.txt` used by `deploy/pipeline/Dockerfile`.
- Add a minimal test that guards required filter runtime dependencies are declared.
- Update docs with operator note for Docker rebuild after dependency changes.

### Out of scope
- Algorithmic changes in filter scoring/selection.
- Changes to pipeline ordering or registry behavior.
- CUDA/quantization tuning.

## 3) Layer Placement (Orchestration / Components / Core)
- Changed layer: Orchestration/runtime packaging boundary (dependency + deployment contract).
- Why: Failure occurs before business logic, at runtime import stage in filter component; dependency declaration belongs to project/runtime setup, not filter algorithm code.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- No Python function/class signatures changed.

### Backward compatibility
- Existing configs/callers remain compatible.
- Runtime environment contract changes: images built from repo dependencies now include filter-required libraries.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Unchanged.

### Step Outputs
- Unchanged.

## 6) Config Contract
- No config keys added/changed.
- Existing keys used by failing path (unchanged):
  - `pipeline.steps`
  - `filter.clip.model_id`
  - `filter.input_manifests`

Example snippet (unchanged):
```yaml
pipeline:
  steps: [filter]
```

## 7) Registry / Dispatch Plan (If applicable)
- Not applicable (no registry/dispatch changes).

## 8) Dependency Direction Check
Confirm imports follow: Orchestration -> Components -> Core
- No import graph changes in pipeline/filter code.
- Only package dependency manifest updated.

## 9) Test Plan (Minimum)
- Add unit test:
  - Verify `pyproject.toml` declares `torch` and `transformers`.
  - Verify `requirements.txt` includes both packages after export.
- Run:
  - `python -m unittest test/test_runtime_dependency_contract.py`

## 10) Risks & Mitigations
- Risk: Dependency version drift or heavyweight installs increase build time.
- Mitigation: Use broad minimum constraints in `pyproject.toml`, keep install path centralized through exported `requirements.txt` and Docker rebuild process.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [x] Git commit message: `fix(filter): include torch/transformers in pipeline runtime deps`
- [x] Pushed to remote
