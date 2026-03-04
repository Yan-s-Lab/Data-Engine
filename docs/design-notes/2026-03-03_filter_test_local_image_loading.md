## 1) Summary
- Fix `filter/test.py` image loading when using local filesystem paths.
- The script currently passes a local path into `requests.get(...)`, which only supports HTTP/HTTPS URLs.

## 2) Scope
### In scope
- Update `filter/test.py` to support both local path and remote URL image sources.
- Make the script import-safe for tests by moving execution to `main()`.
- Add minimal unit tests for local image-source loading behavior.

### Out of scope
- Any algorithmic change to SigLIP2 scoring.
- Any pipeline/orchestrator/filter policy change.

## 3) Layer Placement (Orchestration / Components / Core)
- Changed layer: component-support script in `filter/` (`filter/test.py`).
- Why: this is a standalone diagnostic runner for model prompt scoring and should own source loading logic for its own inputs.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `load_image_source(image_source: str) -> Image.Image`
  - Inputs: image source string (HTTP/HTTPS URL or local path).
  - Outputs: RGB PIL image.
  - Error handling: raises `requests.HTTPError` for failed URL fetch; raises `FileNotFoundError` for missing local file.
- `main() -> None`
  - Moves executable logic under CLI entry to avoid side effects on import.

### Backward compatibility
- Existing direct `python filter/test.py` invocation remains supported.
- Added optional `--image` argument; default remains the local sample image.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Script input contract:
  - `image_source: str`
    - HTTP/HTTPS URL, or
    - local filesystem path (absolute or relative).

### Step Outputs
- `load_image_source`: returns `PIL.Image.Image` with mode `RGB`.
- Script terminal output: unchanged probability print lines.

## 6) Config Contract
- No pipeline config keys added/changed.
- No registry/config wiring changes.

## 7) Registry / Dispatch Plan (If applicable)
- Not applicable.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports: none changed.
- Components imports: `filter/test.py` imports external libs only (`requests`, `PIL`, `transformers`, `torch`).
- Core imports: none.

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - Add `test/test_filter_test_local_image_loading.py` covering:
    - local PNG path loads successfully.
    - missing local path raises `FileNotFoundError`.
- Integration test to add/modify:
  - None required (no pipeline path change).
- How to run tests:
  - `python -m unittest discover -s test -p 'test_filter_test_local_image_loading.py' -v`

## 10) Risks & Mitigations
- Risk: moving runtime logic may change script behavior.
- Mitigation: preserve inference path and print behavior; only isolate execution into `main()` and image-source loader helper.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message: `fix(filter): support local image loading in filter test script`
- [ ] Pushed to remote
