# M1 Milestone: Minimal Runnable Loop (filter -> train -> eval)

## Goal

Deliver a local runnable, artifact-connected loop for:

`filter -> train -> eval`

This milestone is intentionally stubbed, but executable and reproducible.

## Scope (Implemented)

1. `filter/run_filter.py`
- Reads `--config` (YAML/JSON)
- Ingests `filter.input_manifest` or auto-builds stub manifest
- Produces:
  - `filter/manifest_in.jsonl`
  - `filter/filter_scores.jsonl`
  - `filter/splits/{accept,reject,uncertain}.jsonl`
  - `filter/report.json`

2. `train/run_train.py`
- Consumes `filter/splits/accept.jsonl`
- Produces:
  - `train/train_manifest.jsonl`
  - `train/mix_report.json`
  - `train/models/model_stub.bin`
  - `train/model_stub.json`

3. `eval/run_eval.py`
- Consumes `train/model_stub.json` and `filter/filter_scores.jsonl`
- Produces:
  - `eval/metrics.json`
  - `eval/slice_report.json`
  - `eval/failure_cases.jsonl`
  - `eval/policy_feedback.json`

4. Pipeline entry
- `pipelines/filter_train_eval_round.py`
- Runs three stage CLIs in sequence.

## Run Command (Conda)

Use environment `open_data_engine`:

```bash
conda run -n open_data_engine python pipelines/filter_train_eval_round.py \
  --config <archived-or-custom-config.yaml>
```

## Artifact Contract

The contract for M1 is:

1. Filter creates split artifacts.
2. Train consumes `accept` split and emits model stub.
3. Eval consumes model + filter scores and emits:
- metrics
- failure cases
- next-round filter policy suggestion (`policy_feedback.json`)

This closes a minimal policy feedback path while keeping algorithmic complexity low.

## Explicit Non-Goals in M1

- Real ASF/PCS implementation
- Actual model optimization
- Real slice taxonomy (pose/BMI/lighting)
- HITL integration in the same pipeline run
- Auto-writing policy back into config
