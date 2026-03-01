# filter/test.py: bitsandbytes missing + 4bit dtype fallback (2026-03-01)

## Scope
- Fix local `filter/test.py` execution failure in `dataengine` env.
- Keep change limited to test script robustness.

## Changes
- `filter/test.py`
  - Added resilient model loading:
    - Try 4-bit (`BitsAndBytesConfig(load_in_4bit=True)`) first.
    - If 4-bit load fails, fallback to non-quantized model load (`dtype=float16` on CUDA, else `float32`).
  - Added resilient forward pass:
    - If runtime dtype mismatch occurs in quantized path (`Half` vs `Byte`), reload non-quantized model and retry.
  - Kept script output behavior intact (prints probability line).

## Validation
```bash
conda run -n dataengine python filter/test.py
```
- Result: script completes without raising exception.
