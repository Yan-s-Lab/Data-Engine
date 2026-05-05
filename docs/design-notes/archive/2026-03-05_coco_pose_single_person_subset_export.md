## 1) Summary
- Add a local utility script to build a COCO pose single-person subset.
- The script downloads selected images into an `images/` directory and writes a new COCO annotation JSON containing only downloaded samples.

## 2) Scope
### In scope
- Add one script under `artifacts/datasets/rawdatasets/coco_pose/`.
- Support single-person filtering (exactly one person annotation per image).
- Support max download count (default 300).
- Emit subset annotation JSON and metadata JSON under the same output directory.
- Add minimal unit test for core selection/export behavior.

### Out of scope
- Integrating this utility into the project pipeline registry.
- Changing existing orchestration pipelines/config files.
- Multi-class COCO handling beyond person category.

## 3) Layer Placement (Orchestration / Components / Core)
- Layer changed: Orchestration-style local utility script only.
- Reason: this task is an external dataset preparation utility with explicit file I/O and network download, not a reusable pipeline step.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `load_coco(path: Path) -> dict`
- `group_person_annotations_by_image(data: dict, category_id: int, keep_crowd: bool) -> dict[int, list[dict]]`
- `select_single_person_samples(data: dict, max_download: int, min_num_keypoints: int, category_id: int, keep_crowd: bool) -> list[dict]`
- `build_subset_coco(data: dict, selected: list[dict]) -> dict`
- `download_images(selected: list[dict], images_dir: Path, timeout_sec: float, retries: int) -> dict`
- CLI entry: `python artifacts/datasets/rawdatasets/coco_pose/build_single_person_pose_subset.py ...`

- Inputs:
  - COCO keypoints annotation JSON path.
  - Output directory path.
  - Numeric filters and max download count.
- Outputs:
  - Downloaded images under `<output_dir>/images/`.
  - Subset annotation JSON under `<output_dir>/pose_annotations_single_person_subset.json`.
  - Metadata JSON under `<output_dir>/pose_subset_metadata.json`.
- Error handling:
  - Invalid/missing annotation path raises clear `FileNotFoundError`.
  - HTTP failures are recorded in metadata; process continues.

### Backward compatibility
- No existing caller is changed.
- New standalone script and test only.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Schema type: dict contract from COCO JSON.
- Required fields:
  - `images: list[dict]` with `id`, `file_name`, `coco_url`, `width`, `height`.
  - `annotations: list[dict]` with `image_id`, `category_id`, `bbox`, `num_keypoints`, `iscrowd`.
  - `categories`, `licenses`, `info`.

### Step Outputs
- Schema type: COCO-like dict.
- Fields:
  - `info`, `licenses`, `images`, `annotations`, `categories`.
  - `images` and `annotations` include only selected image IDs.

## 6) Config Contract
- This utility uses CLI args (local config surface):
  - `--ann-file`
  - `--output-dir`
  - `--max-download` (default `300`)
  - `--min-num-keypoints` (default `1`)
  - `--category-id` (default `1`)
  - `--keep-crowd` (default false)
  - `--timeout-sec` (default `20`)
  - `--retries` (default `2`)
- Validation rules:
  - `max-download > 0`
  - `min-num-keypoints >= 0`
  - `timeout-sec > 0`
  - `retries >= 0`

Example:
```bash
python artifacts/datasets/rawdatasets/coco_pose/build_single_person_pose_subset.py \
  --ann-file artifacts/datasets/rawdatasets/coco_pose/annotations/person_keypoints_train2017.json \
  --output-dir artifacts/datasets/rawdatasets/coco_pose \
  --max-download 300
```

## 7) Registry / Dispatch Plan (If applicable)
- Not applicable. No pipeline step registration is added.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports:
  - standard library (`argparse`, `json`, `pathlib`, `collections`)
  - external (`requests`)
- Components imports: none.
- Core imports: none.

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - Add test for `select_single_person_samples` and `build_subset_coco` on synthetic mini-COCO input.
- Integration test to add/modify:
  - None (network download intentionally excluded from test).
- How to run tests:
  - `python -m unittest test/test_coco_pose_single_person_subset.py`

## 10) Risks & Mitigations
- Risk: duplicated image downloads when rerunning.
  - Mitigation: skip if file exists.
- Risk: unstable network.
  - Mitigation: timeout + retries + failure accounting.
- Risk: malformed keypoints data.
  - Mitigation: check minimum field availability and keypoint count filters.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
