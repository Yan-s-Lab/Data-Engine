# ComfyUI Model Download Dependencies Update (2026-02-25)

> Superseded on 2026-02-25 by `comfyui_model_download_jq_free_fix_2026-02-25.md`:
> downloader no longer depends on `yq/jq`; parser moved to `python3 + pyyaml`.

## Scope
- Ensure `third_party/comfyui/download_models.sh` required CLI tools are covered by project Python dependencies.

## Changes
- Updated `pyproject.toml`:
  - added `yq>=3.4.3` to `[project].dependencies`.
- Re-generated dependency artifacts:
  - updated `uv.lock`
  - updated `requirements.txt` via `uv export --no-hashes --format requirements-txt`

## Verification
- `uv run yq --version` returns `yq 3.4.3`.
- `uv run hf --help` exits successfully (CLI available from `huggingface-hub`).

## Notes
- `hf` dependency was already present through `huggingface-hub`.
- This change mainly closes the `yq` gap for model download bootstrap scripts.
