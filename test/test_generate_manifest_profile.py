from __future__ import annotations

import unittest

from synth.run_generate import _normalize_manifest_cfg, build_trace_rows


class GenerateManifestProfileTest(unittest.TestCase):
    def test_manifest_cfg_defaults(self) -> None:
        cfg = _normalize_manifest_cfg({})
        self.assertEqual(cfg["profile"], "core")
        self.assertFalse(cfg["write_trace_artifacts"])

    def test_manifest_cfg_rejects_invalid_profile(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_manifest_cfg({"manifest": {"profile": "unknown"}})

    def test_build_trace_rows_has_core_tracking_fields(self) -> None:
        rows = [
            {
                "sample_id": "prompt_only_0_20260225_00005_",
                "source": "synthetic",
                "image_path": "data/comfyui/output/prompt_only_0_20260225_00005_.png",
                "width": 1024,
                "height": 1024,
                "seed": 11,
                "effective_prompt_text": "demo prompt",
                "anchor_real_sample_id": "real_0001",
                "effective_anchor_input": "data/comfyui/input/real_0001.png",
                "comfy_prompt_graph_source": "configs/examples/comfyui/demo.json",
                "synthetic_image_ids": ["prompt_only_0_20260225_00005_", "prompt_only_0_20260225_00006_"],
            }
        ]
        out = build_trace_rows(rows, default_config_ref="generate_config.yaml")
        self.assertEqual(len(out), 1)
        row = out[0]
        self.assertEqual(row["sample_id"], "prompt_only_0_20260225_00005_")
        self.assertEqual(row["source"], "synthetic")
        self.assertEqual(row["prompt_text"], "demo prompt")
        self.assertEqual(row["seed"], 11)
        self.assertEqual(row["guide_image"], "data/comfyui/input/real_0001.png")
        self.assertEqual(row["guide_type"], "image_guided")
        self.assertEqual(row["width"], 1024)
        self.assertEqual(row["height"], 1024)
        self.assertEqual(row["config_ref"], "configs/examples/comfyui/demo.json")
        self.assertEqual(row["anchor_real_sample_id"], "real_0001")
        self.assertEqual(
            row["synthetic_image_ids"],
            ["prompt_only_0_20260225_00005_", "prompt_only_0_20260225_00006_"],
        )

    def test_build_trace_rows_prompt_only_guide_type(self) -> None:
        rows = [
            {
                "sample_id": "prompt_only_1_20260226_00001_",
                "source": "synthetic",
                "image_path": "data/comfyui/output/prompt_only_1_20260226_00001_.png",
                "prompt_text": "plain prompt",
            }
        ]
        out = build_trace_rows(rows, default_config_ref="generate_config.yaml")
        row = out[0]
        self.assertEqual(row["guide_type"], "prompt")
        self.assertEqual(row["guide_image"], "")
        self.assertEqual(row["synthetic_image_ids"], ["prompt_only_1_20260226_00001_"])


if __name__ == "__main__":
    unittest.main()
