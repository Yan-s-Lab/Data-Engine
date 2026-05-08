# Open Source Cleanup

## 1) Summary
- Prepare the repository for public release after the arXiv submission by removing local/runtime artifacts from version control and tightening ignore rules.
- Fix repository documentation references that point to missing methodology files.

## 2) Scope
### In scope
- Ignore local run outputs, root-level model weights, local environment files, and transient filter outputs.
- Remove already tracked local environment and transient filter output files.
- Confirm the paper-level methodology reference points to an existing repository document.
- Remove stale TODO documentation that referred to missing methodology files.

### Out of scope
- Algorithm, pipeline, config, and experiment behavior changes.
- Rewriting archived design/history notes.
- Changing model training or evaluation logic.

## 3) Layer Placement (Orchestration / Components / Core)
- No runtime layer changes.
- Documentation and repository hygiene only: `.gitignore`, `AGENTS.md`, tracked local artifacts.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- None.
- Inputs: not applicable.
- Outputs: not applicable.
- Error handling: not applicable.

### Backward compatibility
- No code interfaces or config contracts change.
- Local users may need to recreate `third_party/label_studio/.env` from `third_party/label_studio/.env.example`.

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
  - `git status --short --branch`
  - `git check-ignore -v runs/pose/val3/BoxF1_curve.png yolo11s-pose.pt yolo26n.pt third_party/label_studio/.env filter/tmp/yk003/body_pose_coco/body_pose_coco_filter/body_pose_coco_siglip2_input_manifest.jsonl`

## 10) Risks & Mitigations
- Potential failure mode: removing a tracked local artifact that someone used as an implicit fixture.
  - Mitigation: keep formal test fixtures under `test/`; remove only local env and `filter/tmp` runtime output.
- Potential failure mode: AGENTS methodology reference becomes too broad.
  - Mitigation: point to existing, maintained fair experiment documentation instead of missing temporary files.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message: `chore: clean repository for public release`
- [x] Pushed to remote
