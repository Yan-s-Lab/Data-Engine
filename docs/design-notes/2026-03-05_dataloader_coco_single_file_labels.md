## 1) Summary
- Add COCO single-annotation-file label compatibility to `ingest/run_dataloader.py`.
- Keep existing per-image label directory behavior unchanged.
- Goal: allow `dataloader` to read labels from one COCO JSON file without requiring per-image txt labels.

## 2) Scope
### In scope
- Update dataloader config contract with optional COCO label mode.
- Implement COCO annotation indexing and per-image annotation lookup in dataloader.
- Keep manifest contract backward-compatible while adding COCO metadata fields when available.
- Add tests for COCO single-file label mode.
- Update dataloader kernel doc.

### Out of scope
- Converting COCO annotations into YOLO txt files.
- Changing generation/filter orchestration behavior.
- Adding new pipeline steps or registries.

## 3) Layer Placement (Orchestration / Components / Core)
- Layer changed: Orchestration script (`ingest/run_dataloader.py`) and docs/tests.
- Reason: dataloader is a pipeline entry-stage script handling config + I/O normalization.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `ingest/run_dataloader.py` config inputs:
  - `dataloader.label_format: "per_file" | "coco"` (default: `per_file`)
  - `dataloader.label_file: str` (required when `label_format: coco` unless `label_dir` points to the COCO json)
- Internal helper functions (module-private):
  - `_load_coco_annotation_index(label_file: Path) -> dict[str, Any]`
  - `_resolve_coco_label_for_image(image_path: Path, index: dict[str, Any]) -> dict[str, Any] | None`

- Inputs:
  - Existing image files and dataloader config.
  - COCO JSON when `label_format: coco`.
- Outputs:
  - Existing `real_manifest.jsonl`, `anchor_stats.json`, `report.json`.
  - Manifest row may include:
    - `label_path` (COCO JSON path)
    - `label_format: "coco"`
    - `coco_image_id`, `coco_annotation_count`
- Error handling:
  - Unsupported `label_format` raises `ValueError`.
  - Missing COCO label file raises `FileNotFoundError`.

### Backward compatibility
- Existing `label_dir + label_ext` per-file flow remains default and unchanged.
- Existing configs without new keys continue to run.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Schema type: dict config contract.
- Required fields:
  - Existing: `dataloader.real_dir`, `dataloader.image_dir` (or resolvable defaults).
- Optional fields:
  - Existing per-file labels: `label_dir`, `label_ext`, `require_labels`.
  - New COCO mode: `label_format`, `label_file`.

### Step Outputs
- Schema type: JSONL row dict.
- Existing required row fields remain unchanged: `sample_id`, `source`, `image_path`, `width`, `height`.
- Optional fields:
  - Existing: `label_path`.
  - New in COCO mode: `label_format`, `coco_image_id`, `coco_annotation_count`.

## 6) Config Contract
- Config keys added/used:
  - `dataloader.label_format`:
    - `per_file` (default): current behavior with `label_dir/sample_id{label_ext}`.
    - `coco`: labels resolved from one COCO JSON file.
  - `dataloader.label_file`:
    - path to COCO annotation JSON when `label_format: coco`.
- Defaults:
  - `label_format` defaults to `per_file`.
- Validation rules:
  - `label_format` must be `per_file` or `coco`.
  - In `coco` mode, COCO json path must exist.

Example:
```yaml
dataloader:
  image_dir: artifacts/datasets/rawdatasets/coco_pose/sub/images
  label_format: coco
  label_file: artifacts/datasets/rawdatasets/coco_pose/sub/pose_annotations_single_person_subset.json
  require_labels: true
```

## 7) Registry / Dispatch Plan (If applicable)
- Not applicable. No new step registration or pipeline-order changes.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports:
  - `ingest/run_dataloader.py` adds only stdlib usage (`collections.defaultdict`).
- Components imports:
  - none.
- Core imports:
  - none.

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - Extend `test/test_dataloader_pipeline_smoke.py` with COCO-label-mode smoke test.
- Integration test to add/modify:
  - Reuse existing CLI smoke style by invoking `ingest/run_dataloader.py` with temp config.
- How to run tests:
  - `python -m unittest test/test_dataloader_pipeline_smoke.py`

## 10) Risks & Mitigations
- Risk: image name mismatch between local files and COCO `file_name`.
  - Mitigation: lookup by full `file_name`, basename, and stem fallback.
- Risk: COCO has duplicate basenames causing ambiguity.
  - Mitigation: ambiguous mapping treated as missing label for safety.
- Risk: downstream expecting per-image label files.
  - Mitigation: preserve `label_path` field and add explicit `label_format` metadata.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
