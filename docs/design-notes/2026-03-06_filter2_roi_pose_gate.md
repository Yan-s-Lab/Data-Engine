## 1) Summary
- Add `filter2` as a new task-oriented ROI + pose validity stage for body-pose filtering.
- `filter2` consumes candidate rows (default from `filter1` accept split), runs YOLO pose (+ optional detector), and routes samples to `accept/reject/uncertain`.

## 2) Scope
### In scope
- New core gate logic for person ROI + keypoint-count validation.
- New `filter/filter_stages/filter2/main.py` CLI stage.
- Config contract under `filter.phase2_roi_pose`.
- Unit tests for gate logic and config resolution.
- Pipeline doc update with `filter2` run command.

### Out of scope
- Multi-person matching strategy redesign.
- Temporal/video logic.
- Integrating `filter2` into managed pipeline orchestration stage registry.

## 3) Layer Placement (Orchestration / Components / Core)
- Components:
  - `filter/filter_stages/filter2/main.py` implements stage I/O and runtime wiring.
- Core:
  - `common/pose_roi_gate.py` implements pure decision logic for ROI + keypoints.
- Why this placement:
  - Stage-specific I/O and model runtime belong to Components.
  - Threshold and pass/fail policy logic belongs to Core for unit testing and reuse.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `common.pose_roi_gate.select_best_person_detection(detections, min_person_score) -> dict | None`
- `common.pose_roi_gate.evaluate_pose_roi_gate(person_detection, pose_detection, image_size, min_person_score, min_keypoints, keypoint_score_threshold, min_bbox_area_ratio, max_bbox_area_ratio, roi_area_ratio_override=None) -> dict`
- `filter/filter_stages/filter2/main.py --config [--output-dir]`

Inputs:
- Config path and filter stage config keys.
- JSONL rows with `image_path` (or `imagepath`/`path`) and optional `sample_id`.

Outputs:
- `filter2_scores.jsonl`
- `splits/filter2_accept.jsonl`
- `splits/filter2_reject.jsonl`
- `splits/filter2_uncertain.jsonl`
- `filter2_report.json`

Error handling:
- Missing config keys or malformed manifests raise `ValueError`.
- Runtime load/import failures raise `RuntimeError` with actionable message.

### Backward compatibility
- No breaking change to existing `filter1` outputs.
- `filter2` is opt-in and standalone CLI; existing `filter1` flow remains valid.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Manifest row contract (dict):
  - Required: `image_path` (fallback keys `imagepath`, `path`).
  - Optional: `sample_id` (auto-generated fallback).

### Step Outputs
- Score row contract:
  - `sample_id`, `image_path`, `decision`
  - `person_score`, `bbox_area_ratio`, `valid_keypoints`
  - `min_keypoints`, `keypoint_score_threshold`
  - `reject_reasons` (list)

## 6) Config Contract
- `filter.phase2_roi_pose.enabled`: bool, default `false`.
- `filter.phase2_roi_pose.input_manifest`: optional; default `<run_dir>/filter/splits/accept.jsonl`.
- `filter.phase2_roi_pose.device`: `auto|cpu|cuda`, default `auto`.
- `filter.phase2_roi_pose.min_person_score`: float in `[0,1]`, default `0.25`.
- `filter.phase2_roi_pose.min_keypoints`: int, default `12`.
- `filter.phase2_roi_pose.keypoint_score_threshold`: float, default `0.5`.
- `filter.phase2_roi_pose.min_bbox_area_ratio`: float in `[0,1]`, default `0.05`.
- `filter.phase2_roi_pose.max_bbox_area_ratio`: float in `(0,1]`, default `1.0`.
- `filter.phase2_roi_pose.pose.model`: default `third_party/yolo26x-pose.pt`.
- `filter.phase2_roi_pose.detection.enabled`: optional detector branch; default `false`.
- `filter.phase2_roi_pose.segmentation.enabled`: when true, allow ROI area ratio from manifest field.
- `filter.phase2_roi_pose.routing.*_action`: per-reason route action (`reject|uncertain`).

Example snippet:
```yaml
filter:
  phase2_roi_pose:
    enabled: true
    input_manifest: artifacts/runs/yk003/body_pose_coco/body_pose_coco_filter/filter/splits/accept.jsonl
    device: auto
    min_person_score: 0.25
    min_keypoints: 12
    keypoint_score_threshold: 0.5
    min_bbox_area_ratio: 0.05
    max_bbox_area_ratio: 1.0
    pose:
      enabled: true
      model: third_party/yolo26x-pose.pt
    detection:
      enabled: false
    segmentation:
      enabled: false
      area_ratio_field: person_mask_area_ratio
    routing:
      keypoint_fail_action: uncertain
      bbox_fail_action: reject
      no_person_fail_action: reject
      pose_missing_action: uncertain
```

## 7) Registry / Dispatch Plan (If applicable)
- No orchestrator registry change in this task.
- Stage is executed directly by CLI (`filter/filter_stages/filter2/main.py`).

## 8) Dependency Direction Check
- Orchestration imports:
  - N/A for this change.
- Components imports:
  - `filter/filter_stages/filter2/main.py` imports only `common/*` and third-party runtime libs.
- Core imports:
  - `common/pose_roi_gate.py` imports only stdlib.

## 9) Test Plan (Minimum)
- Unit tests:
  - `test/test_pose_roi_gate.py` for detection selection and gate decisions.
  - `test/test_filter2_main.py` for manifest/param resolution behavior.
- Integration:
  - Not added in this patch (no stable local model weights fixture).
- Run:
  - `conda run -n dataengine python -m unittest test/test_pose_roi_gate.py test/test_filter2_main.py`

## 10) Risks & Mitigations
- Risk: ultralytics package may be missing in runtime env.
- Mitigation: fail fast with actionable install message.
- Risk: hard keypoint rejection can drop useful hard cases.
- Mitigation: default keypoint/pose-missing route to `uncertain`.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
