# Test Data + LFS Update (2026-02-24)

## Scope
- Add `test/testfilter` sample files to repository tracking.
- Add Git LFS attribute rules for test image assets.

## Files
- `.gitattributes`
- `test/testfilter/configs/filter_compose.yaml`
- `test/testfilter/input_manifest.jsonl`
- `test/testfilter/real_raw/images/*.png`

## Notes
- LFS is enabled for image files under `test/**` and `third_party/testdatasets/*`.
- This change is intentionally limited to test data and LFS setup only.
