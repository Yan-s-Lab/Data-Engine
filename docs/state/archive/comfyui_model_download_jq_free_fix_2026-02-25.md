# ComfyUI Model Downloader jq-Free Fix (2026-02-25)

## Problem
- Running `./third_party/comfyui/download_models.sh` failed with:
  - `yq: Error starting jq ... No such file or directory: 'jq'`

## Root Cause
- The script used Python `yq`, which requires a separate system `jq` binary on `PATH`.
- `jq` is not a Python package dependency and was not guaranteed in runtime environments.

## Changes
- Updated `third_party/comfyui/download_models.sh`:
  - removed `yq` usage completely.
  - parse `models.yaml` via `python3 + pyyaml`.
  - keep existing download behavior (`hf download` / `curl`).
- Updated dependency manifests to match new implementation:
  - removed `yq` from `pyproject.toml`.
  - regenerated `uv.lock` and `requirements.txt`.

## Verification
- `bash -n third_party/comfyui/download_models.sh` passes.
- YAML parsing sanity check:
  - `models=16`
  - `download_rows=21`
- `requirements.txt` no longer contains:
  - `yq`
  - `argcomplete`
  - `tomlkit`
  - `xmltodict`

## Outcome
- Model download bootstrap no longer depends on system `jq`.
- Existing environment (`python + requirements.txt`) is sufficient for manifest parsing.
