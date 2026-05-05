from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = Path("label/run_ai_annotation.py")
spec = importlib.util.spec_from_file_location("run_ai_annotation", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)


class RunAiAnnotationHelpersTest(unittest.TestCase):
    def test_resolve_manifest_image_path_prefers_absolute_image_path(self) -> None:
        row = {"image_path": "/tmp/example.png"}
        self.assertEqual(module.resolve_manifest_image_path(row), Path("/tmp/example.png"))

    def test_resolve_manifest_image_path_supports_relative_synth_manifest_rows(self) -> None:
        row = {"synthetic_image_path": "data/comfyui/output/sample.png"}
        self.assertEqual(
            module.resolve_manifest_image_path(row),
            Path.cwd() / "data/comfyui/output/sample.png",
        )

    def test_resolve_sample_id_uses_synthetic_id_then_image_stem(self) -> None:
        image_path = Path("/tmp/sample.png")
        self.assertEqual(
            module.resolve_sample_id({"synthetic_id": "syn-001"}, image_path),
            "syn-001",
        )
        self.assertEqual(module.resolve_sample_id({}, image_path), "sample")


if __name__ == "__main__":
    unittest.main()
