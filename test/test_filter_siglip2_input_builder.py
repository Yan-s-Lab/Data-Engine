from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from common.filter_input_builder import build_siglip2_filter_inputs_from_config, save_siglip2_filter_inputs_from_config


class FilterSiglip2InputBuilderTest(unittest.TestCase):
    def test_prompt_manifest_row(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_siglip2_input_") as td:
            root = Path(td)
            images_dir = root / "images"
            manifests_dir = root / "manifests"
            images_dir.mkdir(parents=True, exist_ok=True)
            manifests_dir.mkdir(parents=True, exist_ok=True)

            image = images_dir / "prompt.png"
            image.write_text("", encoding="utf-8")

            synth_manifest = manifests_dir / "synth_prompt.jsonl"
            synth_manifest.write_text(
                json.dumps(
                    {
                        "synthetic_image_path": str(image),
                        "guide_type": "prompt",
                        "prompt_text": "a person standing",
                        "guide_image_id": "",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            cfg = root / "filter.json"
            cfg.write_text(
                json.dumps(
                    {
                        "filter": {
                            "input_manifests": [str(synth_manifest)],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            rows = build_siglip2_filter_inputs_from_config(cfg)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["sample_id"], "row_0000000")
            self.assertTrue(Path(rows[0]["image_path"]).is_absolute())

    def test_image_guided_row_is_treated_as_plain_input_row(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_siglip2_input_") as td:
            root = Path(td)
            images_dir = root / "images"
            manifests_dir = root / "manifests"
            images_dir.mkdir(parents=True, exist_ok=True)
            manifests_dir.mkdir(parents=True, exist_ok=True)

            synth_image = images_dir / "synth.png"
            synth_image.write_text("", encoding="utf-8")

            synth_manifest = manifests_dir / "synth_guided.jsonl"
            synth_manifest.write_text(
                json.dumps(
                    {
                        "synthetic_image_path": str(synth_image),
                        "guide_type": "image_guided",
                        "guide_image_id": "real_001",
                        "prompt_text": "a full body photo",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            cfg = root / "filter.json"
            cfg.write_text(
                json.dumps(
                    {
                        "filter": {
                            "input_manifests": [str(synth_manifest)],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            rows = build_siglip2_filter_inputs_from_config(cfg)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["sample_id"], "row_0000000")
            self.assertTrue(Path(rows[0]["image_path"]).is_absolute())

    def test_save_manifest_uses_config_output_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_siglip2_input_") as td:
            root = Path(td)
            image = root / "synth.png"
            image.write_text("", encoding="utf-8")

            synth_manifest = root / "synth.jsonl"
            synth_manifest.write_text(
                json.dumps({"synthetic_image_path": str(image), "guide_type": "prompt"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            out_path = root / "out" / "siglip2_input_manifest.jsonl"
            cfg = root / "filter.json"
            cfg.write_text(
                json.dumps(
                    {
                        "run": {"run_id": "demo", "artifacts_root": str(root / "artifacts")},
                        "filter": {
                            "input_manifests": [str(synth_manifest)],
                            "siglip2_input_manifest_output": str(out_path),
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            saved = save_siglip2_filter_inputs_from_config(cfg)
            self.assertEqual(saved, out_path.resolve())
            self.assertTrue(saved.exists())
            lines = [line for line in saved.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
