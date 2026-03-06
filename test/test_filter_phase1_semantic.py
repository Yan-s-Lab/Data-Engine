from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from filter.filter_stages import aggregate_compare_texts_group_scores
from filter.pipeline_engine.phase1_dual_signal import compute_phase1_score_rows
from filter.run_filter import (
    _apply_dual_signal_selection,
    _inject_anchor_real_rows,
    _resolve_decision_policy,
    _resolve_filter_prompt_text,
)


class FilterPhase1SemanticTest(unittest.TestCase):
    def test_compare_texts_pairwise_margin_aggregation(self) -> None:
        agg = aggregate_compare_texts_group_scores(
            positive_logits=[0.8, 0.5],
            negative_logits=[0.2],
        )
        # pairwise margins: [0.6, 0.3] -> median 0.45, win_rate 1.0
        self.assertAlmostEqual(agg["s_prompt_pos"], 0.65, places=6)
        self.assertAlmostEqual(agg["s_prompt_neg"], 0.2, places=6)
        self.assertAlmostEqual(agg["s_prompt_margin"], 0.45, places=6)
        self.assertAlmostEqual(agg["s_prompt_win_rate"], 1.0, places=6)
        self.assertAlmostEqual(agg["s_prompt"], 1.0, places=6)

    def test_phase1_uses_compare_texts_when_configured(self) -> None:
        rows = [
            {"sample_id": "s1", "source": "synthetic", "image_path": "s1.png", "guide_type": "prompt"},
        ]
        filter_cfg = {
            "clip": {
                "model_id": "google/siglip2-so400m-patch16-naflex",
                "compare-texts": {
                    "positive": ["human", "visible deltoid"],
                    "negative": ["not human"],
                },
            },
            "phase1_semantic": {
                "enabled": True,
                "prompt_field": "prompt_text",
                "anchor_sid_fields": ["guide_image_id"],
            },
            "keep_real_always": True,
        }

        class _Runtime:
            device = "cpu"

        with (
            patch(
                "filter.pipeline_engine.phase1_dual_signal.build_image_embeddings",
                return_value=({}, _Runtime(), {"embed_cache_total": 1}),
            ),
            patch(
                "filter.pipeline_engine.phase1_dual_signal.compute_compare_texts_prompt_scores",
                return_value=(
                    {"s1": 0.77},
                    {
                        "enabled": True,
                        "algorithm": "pairwise_logit_margin_win_rate",
                        "groups": ["positive", "negative"],
                        "sample_details": {"s1": {"algorithm": "pairwise_logit_margin_win_rate"}},
                    },
                ),
            ) as mock_compare,
            patch(
                "filter.pipeline_engine.phase1_dual_signal.compute_prompt_scores",
                return_value={"s1": 0.11},
            ) as mock_prompt,
            patch(
                "filter.pipeline_engine.phase1_dual_signal.compute_paired_anchor_semantic_scores",
                return_value=({"s1": {"s_semantic_pair": 0.0, "s_semantic_pair_hit": 0.0}}, {"enabled": True}),
            ),
        ):
            score_rows, report = compute_phase1_score_rows(
                rows=rows,
                filter_dir=Path("."),
                filter_cfg=filter_cfg,
            )
        self.assertEqual(len(score_rows), 1)
        self.assertEqual(score_rows[0]["s_prompt"], 0.77)
        self.assertEqual(score_rows[0]["prompt_compare_log"]["algorithm"], "pairwise_logit_margin_win_rate")
        self.assertTrue(report["compare_texts"]["enabled"])
        self.assertEqual(report["compare_texts"]["algorithm"], "pairwise_logit_margin_win_rate")
        self.assertEqual(report["compare_texts"]["groups"], ["positive", "negative"])
        mock_compare.assert_called_once()
        mock_prompt.assert_not_called()

    def test_resolve_decision_policy_accepts_legacy_alias(self) -> None:
        self.assertEqual(
            _resolve_decision_policy({"policy": {"decision": "phase1_v1"}}),
            "phase1_dual_signal",
        )
        self.assertEqual(
            _resolve_decision_policy({"policy": {"decision": "phase1_dual_signal"}}),
            "phase1_dual_signal",
        )

    def test_resolve_decision_policy_rejects_unknown_value(self) -> None:
        with self.assertRaises(ValueError):
            _resolve_decision_policy({"policy": {"decision": "weighted"}})

    def test_dual_signal_selection(self) -> None:
        score_rows = [
            {"sample_id": "r1", "source": "real", "decision": "accept", "keep": True},
            {
                "sample_id": "s_guided_ok",
                "source": "synthetic",
                "phase1_route": "guided",
                "s_prompt": 0.82,
                "s_anchor": 0.88,
                "s_anchor_hit": 1.0,
                "decision": "uncertain",
                "keep": False,
            },
            {
                "sample_id": "s_guided_miss",
                "source": "synthetic",
                "phase1_route": "guided",
                "s_prompt": 0.91,
                "s_anchor": 0.0,
                "s_anchor_hit": 0.0,
                "decision": "uncertain",
                "keep": False,
            },
            {
                "sample_id": "s_prompt_ok",
                "source": "synthetic",
                "phase1_route": "prompt_only",
                "s_prompt": 0.74,
                "s_anchor": 0.0,
                "s_anchor_hit": 0.0,
                "decision": "uncertain",
                "keep": False,
            },
            {
                "sample_id": "s_prompt_low",
                "source": "synthetic",
                "phase1_route": "prompt_only",
                "s_prompt": 0.42,
                "s_anchor": 0.0,
                "s_anchor_hit": 0.0,
                "decision": "uncertain",
                "keep": False,
            },
        ]
        filter_cfg = {
            "phase1_dual_signal": {
                "enabled": True,
                "target_source": "synthetic",
                "prompt_accept_threshold": 0.7,
                "prompt_uncertain_threshold": 0.5,
                "pair_accept_threshold": 0.8,
                "pair_uncertain_threshold": 0.6,
                "missing_pair_policy": "uncertain",
                "hard_reject": True,
            }
        }
        state = _apply_dual_signal_selection(score_rows=score_rows, filter_cfg=filter_cfg)
        self.assertTrue(state["enabled"])
        self.assertEqual(score_rows[1]["decision"], "accept")
        self.assertEqual(score_rows[2]["decision"], "uncertain")
        self.assertEqual(score_rows[3]["decision"], "accept")
        self.assertEqual(score_rows[4]["decision"], "reject")

    def test_prompt_text_can_reuse_generate_template_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_phase1_prompt_") as td:
            root = Path(td)
            template_file = root / "prompt_template.txt"
            template_file.write_text("template prompt text", encoding="utf-8")

            generate_cfg = {
                "generate": {
                    "comfyui": {
                        "prompt": {
                            "template_file": str(template_file),
                        }
                    }
                }
            }
            generate_cfg_path = root / "generate_cfg.json"
            generate_cfg_path.write_text(json.dumps(generate_cfg, ensure_ascii=False), encoding="utf-8")

            filter_cfg = {
                "clip": {
                    "prompt_from_generate_config": str(generate_cfg_path),
                }
            }

            source = _resolve_filter_prompt_text(filter_cfg=filter_cfg, config_path=root / "filter_cfg.yaml")
            self.assertEqual(source, "clip.prompt_from_generate_config.template_file")
            self.assertEqual(filter_cfg["clip"]["prompt_text"], "template prompt text")

    def test_prompt_from_generate_config_supports_workspace_relative_template_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_phase1_prompt_") as td:
            root = Path(td)
            template_file = root / "prompt_template.txt"
            template_file.write_text("template prompt text", encoding="utf-8")

            # Simulate generation config uses workspace-relative path.
            generate_cfg = {
                "generate": {
                    "comfyui": {
                        "prompt": {
                            "template_file": str(template_file),
                        }
                    }
                }
            }
            generate_cfg_path = root / "generate_cfg.json"
            generate_cfg_path.write_text(json.dumps(generate_cfg, ensure_ascii=False), encoding="utf-8")

            filter_cfg = {
                "clip": {
                    "prompt_from_generate_config": str(generate_cfg_path),
                }
            }
            source = _resolve_filter_prompt_text(filter_cfg=filter_cfg, config_path=root / "filter_cfg.yaml")
            self.assertEqual(source, "clip.prompt_from_generate_config.template_file")
            self.assertEqual(filter_cfg["clip"]["prompt_text"], "template prompt text")

    def test_inject_anchor_rows_from_explicit_real_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="filter_phase1_anchor_") as td:
            root = Path(td)
            real_manifest = root / "real_manifest.jsonl"
            real_manifest.write_text(
                json.dumps({"sample_id": "real_001", "source": "real", "image_path": "real_001.png"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            rows = [
                {
                    "sample_id": "synth_001",
                    "source": "synthetic",
                    "image_path": "synth_001.png",
                    "guide_image_id": "real_001",
                }
            ]
            filter_cfg = {
                "anchor_real_manifest": str(real_manifest),
                "phase1_semantic": {
                    "enabled": True,
                    "anchor_sid_fields": ["guide_image_id"],
                    "guided_marker_fields": ["guide_image_id"],
                },
            }

            out_rows, state = _inject_anchor_real_rows(
                rows=rows,
                filter_cfg=filter_cfg,
                config_path=root / "filter_cfg.yaml",
                input_manifest_paths=[],
            )
            self.assertEqual(len(out_rows), 2)
            self.assertEqual(state["injected_anchor_count"], 1)
            self.assertEqual(state["unresolved_anchor_count"], 0)


if __name__ == "__main__":
    unittest.main()
