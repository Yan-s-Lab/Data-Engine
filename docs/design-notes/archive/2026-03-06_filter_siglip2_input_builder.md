## 1) Summary
- Add a minimal foundational function to build SigLIP2 filter input rows from filter config.
- The output row contract is fixed to 4 columns: `image_path`, `generative_type`, `guided_image`, `guided_prompt`.
- Purpose: provide low-coupling input preparation for later SigLIP2 logits/margin scoring.

## 2) Scope
### In scope
- Read `filter.input_manifests` from config.
- Read optional `filter.anchor_real_manifest` for `image_guided` guided image lookup.
- Normalize each input row into 4-column output contract.
- Convert `image_path` and `guided_image` to absolute paths.
- Provide output save capability for standalone execution.
- Add unit tests for prompt and image_guided rows.

### Out of scope
- SigLIP2 model inference and logits calculation.
- Margin computation logic (`top3mean(pos)-top3mean(neg)`).
- Filter pipeline decision policy.
- Any restoration of legacy filter logic.

## 3) Layer Placement (Orchestration / Components / Core)
- Changed layers:
  - Core: add reusable pure-ish data-prep utility in `common/` for config/manifests to 4-column rows.
  - Components: minimal reuse wiring from filter io module to call the common utility.
- Why:
  - This function is a cross-step foundational input contract utility and should not be tied to one filter stage implementation.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `common.filter_input_builder.build_siglip2_filter_inputs_from_config(config_path: Path) -> List[Dict[str, str]]`
  - Inputs:
    - `config_path`: YAML/JSON config path containing `filter` section.
  - Outputs:
    - list of dict rows with keys: `image_path`, `generative_type`, `guided_image`, `guided_prompt`.
  - Error handling:
    - raise `ValueError` when `filter` section is not a mapping.
    - raise `FileNotFoundError` when configured manifest path does not exist.

- `common.filter_input_builder.build_siglip2_filter_inputs(*, filter_cfg: Dict[str, Any], config_path: Path) -> List[Dict[str, str]]`
  - Inputs:
    - `filter_cfg`: loaded `filter` config mapping.
    - `config_path`: path for relative-path resolution base.
  - Outputs:
    - same 4-column rows.
  - Error handling:
    - same as above.

- `common.filter_input_builder.save_siglip2_filter_inputs_from_config(config_path: Path, *, output_path: Path | None = None) -> Path`
  - Inputs:
    - `config_path`: YAML/JSON config path.
    - `output_path`: optional override output path.
  - Outputs:
    - saved jsonl absolute path.
  - Error handling:
    - same config/manifest validation as builder.

### Backward compatibility
- No existing caller contract is broken.
- New function is additive.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Schema type: dict contract
- Required fields:
  - config root `filter` mapping.
  - `filter.input_manifests` (list or non-empty string).
- Optional fields + defaults:
  - `filter.anchor_real_manifest` optional; if absent, `guided_image` stays empty.

### Step Outputs
- Schema type: `List[Dict[str, str]]`
- Fields:
  - `image_path`: absolute path string
  - `generative_type`: `prompt` or `image_guided`
  - `guided_image`: absolute path string or empty string
  - `guided_prompt`: prompt string or empty string

## 6) Config Contract
- Config keys added/used:
  - used: `filter.input_manifests`, `filter.anchor_real_manifest`, `filter.siglip2_input_manifest_output`
- Defaults:
  - `guided_image` and `guided_prompt` default to empty string when not available.
  - `generative_type` fallback: infer as `image_guided` only when `guide_image_id` exists, otherwise `prompt`.
  - save output fallback: `run.artifacts_root/run.run_id/filter/siglip2_input_manifest.jsonl`
- Validation rules:
  - `input_manifests` must resolve to at least one manifest path.
- Example config snippet:
```yaml
filter:
  input_manifests:
    - artifacts/.../generate/synth_manifest.jsonl
  anchor_real_manifest: artifacts/.../dataloader/real_manifest.jsonl
  siglip2_input_manifest_output: artifacts/.../filter/siglip2_input_manifest.jsonl
```

## 7) Registry / Dispatch Plan (If applicable)
- Not applicable.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports:
  - unchanged
- Components imports:
  - `filter.pipeline_engine.io_ops` may import the new `common` utility wrapper.
- Core imports:
  - `common.filter_input_builder` imports only `common.config_io` and `common.manifest_io` + stdlib.

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - add tests for:
    - prompt rows produce empty `guided_image` and non-empty `guided_prompt`
    - image_guided rows resolve `guided_image` via `anchor_real_manifest`
    - all image paths become absolute
    - save function writes jsonl to configured output path
- Integration test to add/modify:
  - none for this step (pure input function only)
- How to run tests:
  - `pytest -q test/test_filter_siglip2_input_builder.py`

## 10) Risks & Mitigations
- Potential failure modes:
  - manifest field variants across runs (`synthetic_image_path` vs `image_path`, `guide_type` absent).
  - guide id not found in anchor manifest.
- Mitigations:
  - explicit fallback mapping for known field names.
  - missing guide mapping results in empty `guided_image` instead of crash.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [ ] Code changes implemented
- [ ] Tests added/updated
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
