# Generation MVP Refine TODO

Last updated: 2026-02-20
Scope: `synth/run_generate.py` generation stage review findings

## Purpose

This TODO captures actionable fixes discovered during MVP review of the generation stage, so later refinement can be executed as a controlled checklist.

## Priority Legend

- P0: blocks stage correctness / pipeline execution
- P1: major behavior mismatch / high operational risk
- P2: quality / robustness / maintainability improvement

## TODO List

### P0-1 Fix runtime crash in size enrichment

- Status: `open`
- Problem:
  - `enrich_synth_rows_with_dimensions()` calls `image_size(...)`, but `image_size` is not defined in `synth/run_generate.py`.
  - Current behavior: generate stage crashes with `NameError`.
- Evidence:
  - file: `synth/run_generate.py:824`
  - repro command:
    - `python synth/run_generate.py --config /tmp/repro_generate_nameerror.yaml`
- Fix target:
  - add local `image_size(path: Path) -> tuple[int, int]` helper (or import from shared utility)
  - keep PIL open/close behavior consistent with dataloader style
- Acceptance criteria:
  - no `NameError` on local-stub run
  - `generate/report.json` is successfully written
  - `size_checked_count`/`size_match_count` fields are present and sane

### P1-1 Make timeout retry semantics truly honor `timeout_retries`

- Status: `open`
- Problem:
  - In blocking mode, `on_timeout=retry` path effectively performs only one extra wait and may fail before consuming configured retries.
- Evidence:
  - file: `synth/run_generate.py:765`
  - file: `synth/run_generate.py:768`
  - file: `synth/run_generate.py:776`
- Fix target:
  - refactor blocking timeout handling into explicit retry loop
  - ensure retry count matches configured policy exactly
  - unify log message format with non-blocking mode
- Acceptance criteria:
  - with `timeout_retries=N`, failed prompt can attempt up to N retries before fail/skip
  - `timeout_count` and `timeout_retry_count` in report are accurate
  - behavior for `fail|skip|retry` is deterministic and documented

### P1-2 Fail fast on invalid node injection targets

- Status: `open`
- Problem:
  - current node injection uses `setdefault(...)`, which can silently create non-existent nodes for:
    - seed injection
    - prompt text injection
    - filename_prefix injection
    - anchor image injection
  - this delays config errors until downstream ComfyUI request.
- Evidence:
  - file: `synth/run_generate.py:245`
  - file: `synth/run_generate.py:305`
  - file: `synth/run_generate.py:363`
  - file: `synth/run_generate.py:400`
- Fix target:
  - add strict node existence validation for configured `node_id`
  - raise clear `ValueError` with config path hint when node not found
- Acceptance criteria:
  - invalid node id fails before `/prompt` submission
  - error message explicitly includes offending config key and node id

### P2-1 Remove seed collision window in local stub backend

- Status: `open`
- Problem:
  - local-stub seed formula `seed_base + real_idx * 100 + k` can collide when `synth_per_real > 100`.
- Evidence:
  - file: `synth/run_generate.py:471`
- Fix target:
  - adopt collision-free mapping (for example: monotonic global synth index, or hash-based deterministic seed)
- Acceptance criteria:
  - no seed collision for practical `synth_per_real` range
  - deterministic reproducibility preserved across runs with same config

### P2-2 Clarify edge policy for `synth_per_real=0`

- Status: `open`
- Problem:
  - backend behavior is currently not explicitly documented/validated for zero synthetic target.
  - risk of inconsistent semantics between `local_stub` and `comfyui`.
- Fix target:
  - explicitly define policy: allow pass-through or fail-fast
  - enforce the same behavior across backends
  - document in `docs/README_PIPELINE_ZH.md`
- Acceptance criteria:
  - a config test with `synth_per_real=0` has deterministic expected outcome
  - report and logs reflect policy clearly

## Suggested Refine Order

1. P0-1 runtime crash
2. P1-1 timeout retry loop
3. P1-2 node-id validation
4. P2-1 seed strategy
5. P2-2 edge-case policy + docs sync

## Regression Checklist (after fixes)

- `generate.backend=local_stub` smoke run passes and emits:
  - `generate/synth_manifest.jsonl`
  - `generate/mixed_manifest.jsonl`
  - `generate/report.json`
- `generate.backend=comfyui` (history mode) basic run passes
- timeout policy matrix checked:
  - `on_timeout=fail`
  - `on_timeout=skip`
  - `on_timeout=retry` with retries > 1
- invalid injection node config fails fast before prompt submission
