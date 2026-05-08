# Remove External Paper Artifacts

## 1) Summary
- Remove external-server aggregation results, private data samples, and paper figure plotting scripts from the public repository.
- Add ignore rules so future local copies of those artifacts are not accidentally committed under core package directories.

## 2) Scope
### In scope
- Delete tracked CSV/SVG/paper plotting files under `train/val_datasets/`.
- Delete paper figure plotting scripts under `eval/`.
- Delete paper result summary docs that point to private/local figures.
- Delete tracked private/sample image and manifest fixtures from `filter/`, `test/test-filters/`, and `test/test-generation/`.
- Replace static image fixtures needed by tests with runtime-generated tiny placeholder images.
- Remove stale test-generation configs that referenced deleted local run artifacts.
- Update active serial-plan examples so they no longer reference deleted test fixture configs.
- Remove archived internal process notes that referenced deleted private fixtures and obsolete experiment paths.
- Ignore `train/val_datasets/` going forward.
- Record the repository boundary decision.

### Out of scope
- Changing Data Engine training/evaluation behavior.
- Reworking paper figure generation into a supported reproducibility package.
- Moving external experiment results into this repository.

## 3) Layer Placement (Orchestration / Components / Core)
- No runtime layer changes.
- This is repository hygiene for non-core paper artifacts that were placed under training/evaluation package trees.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- None.
- Inputs: not applicable.
- Outputs: not applicable.
- Error handling: not applicable.

### Backward compatibility
- No Data Engine API/config compatibility impact for training/evaluation runners.
- Test code should create minimal local fixtures at runtime instead of storing private data in Git.
- Users needing the external aggregation results should retrieve them from the original experiment server or a separate paper artifact release.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Schema type: not applicable.
- Required fields: not applicable.
- Optional fields + defaults: not applicable.

### Step Outputs
- Schema type: not applicable.
- Fields: not applicable.

## 6) Config Contract
- Config keys added/used: none.
- Defaults: none.
- Validation rules: none.
- Example config snippet: not applicable.

## 7) Registry / Dispatch Plan (If applicable)
- Registry name/location: not applicable.
- Step name(s) registered: none.
- How config resolves to implementation: not applicable.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration -> Components -> Core

- Orchestration imports: unchanged.
- Components imports: unchanged.
- Core imports: unchanged.

## 9) Test Plan (Minimum)
- Unit tests to add/modify: none; no functional code changes.
- Integration test to add/modify: none; no pipeline behavior changes.
- How to run tests:
- `rg -n "val_datasets|iou_gap|only_synthetic|wpd_datasets|ap_vs_iou|iou_50|iou_mix|plot_ablation|plot_feature_distribution|ablation_results_summary" . -g '!artifacts/**' -g '!data/**' -g '!runs/**' -g '!*.pyc'`
- `git ls-files | rg '\\.(png|jpg|jpeg|csv|jsonl|svg)$'`
- `rg -n "test/test-filters|test/test-generation/runs|test/test-generation/config" README.md ROADMAP.md docs configs deploy eval train test pipelines .gitignore`
- `python -m unittest discover -s test -p 'test_managed_pipeline_smoke.py'`
- `git check-ignore --no-index -v train/val_datasets/plot.py`

## 10) Risks & Mitigations
- Potential failure mode: paper figure reproducibility assets are no longer in this core repository.
  - Mitigation: document that these are external paper artifacts and should live in a separate paper artifact release if needed.
- Potential failure mode: stale references remain after removal.
  - Mitigation: search for references before completion.
- Potential failure mode: archived design/history context is less complete in the public repository.
  - Mitigation: keep current architecture docs and active design notes only.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message: `chore: remove external val dataset artifacts`
- [x] Pushed to remote
