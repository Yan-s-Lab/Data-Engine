from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from filter.run_filter import (
    _apply_dual_signal_selection,
    _apply_topk_review_selection,
    _inject_anchor_real_rows,
    _resolve_filter_prompt_text,
    build_phase1_semantic_scores,
)


class FilterPhase1SemanticTest(unittest.TestCase):
    def test_phase1_v1_scoring_guided_and_prompt_only(self) -> None:
        rows = [
            {"sample_id": "s_guided", "source": "synthetic", "guide_image_id": "r1"},
            {"sample_id": "s_prompt", "source": "synthetic"},
        ]
        paired_scores = {"s_guided": {"s_semantic_pair": 0.9, "s_semantic_pair_hit": 1.0}}
        prompt_scores = {"s_guided": 0.2, "s_prompt": 0.8}
        phase1_cfg = {"enabled": True, "guided_marker_fields": ["guide_image_id"], "guided_w_anchor": 0.8, "guided_w_prompt": 0.2}
        out, state = build_phase1_semantic_scores(rows=rows, paired_scores=paired_scores, prompt_scores=prompt_scores, phase1_cfg=phase1_cfg)
        self.assertEqual(out["s_guided"]["phase1_route"], "guided")
        self.assertAlmostEqual(out["s_guided"]["s_anchor"], 0.9, places=6)
        self.assertAlmostEqual(out["s_guided"]["s_prompt"], 0.2, places=6)
        self.assertAlmostEqual(out["s_guided"]["s_final"], 0.76, places=6)
        self.assertEqual(out["s_prompt"]["phase1_route"], "prompt_only")
        self.assertAlmostEqual(out["s_prompt"]["w_anchor"], 0.0, places=6)
        self.assertAlmostEqual(out["s_prompt"]["w_prompt"], 1.0, places=6)
        self.assertAlmostEqual(out["s_prompt"]["s_final"], 0.8, places=6)
        self.assertEqual(state["guided_synth_count"], 1)
        self.assertEqual(state["prompt_only_synth_count"], 1)

    def test_phase1_guide_type_has_priority_for_route(self) -> None:
        rows = [
            {
                "sample_id": "s_prompt_typed",
                "source": "synthetic",
                "guide_type": "prompt",
                "guide_image_id": "r1",
            },
            {
                "sample_id": "s_image_guided_typed",
                "source": "synthetic",
                "guide_type": "image_guided",
                "guide_image_id": "r2",
            },
        ]
        paired_scores = {
            "s_prompt_typed": {"s_semantic_pair": 0.95, "s_semantic_pair_hit": 1.0},
            "s_image_guided_typed": {"s_semantic_pair": 0.75, "s_semantic_pair_hit": 1.0},
        }
        prompt_scores = {"s_prompt_typed": 0.4, "s_image_guided_typed": 0.3}
        phase1_cfg = {"enabled": True, "guided_w_anchor": 0.8, "guided_w_prompt": 0.2}
        out, state = build_phase1_semantic_scores(rows=rows, paired_scores=paired_scores, prompt_scores=prompt_scores, phase1_cfg=phase1_cfg)
        self.assertEqual(out["s_prompt_typed"]["phase1_route"], "prompt_only")
        self.assertEqual(out["s_image_guided_typed"]["phase1_route"], "guided")
        self.assertEqual(state["guided_synth_count"], 1)
        self.assertEqual(state["prompt_only_synth_count"], 1)

    def test_topk_review_selection(self) -> None:
        score_rows = [
            {"sample_id": "r1", "source": "real", "s_final": 1.0, "decision": "accept"},
            {"sample_id": "s1", "source": "synthetic", "s_final": 0.9, "phase1_route": "guided", "s_anchor": 0.92, "s_prompt": 0.1, "decision": "uncertain"},
            {"sample_id": "s2", "source": "synthetic", "s_final": 0.85, "phase1_route": "guided", "s_anchor": 0.5, "s_prompt": 0.1, "decision": "uncertain"},
            {"sample_id": "s3", "source": "synthetic", "s_final": 0.7, "phase1_route": "prompt_only", "s_anchor": 0.0, "s_prompt": 0.7, "decision": "uncertain"},
        ]
        filter_cfg = {
            "policy": {
                "ranking_review": {
                    "enabled": True,
                    "target_source": "synthetic",
                    "rank_metric": "s_final",
                    "keep_top_k": 2,
                    "review_rest": True,
                    "guided_min_anchor": 0.85,
                    "guided_min_prompt": 0.0,
                }
            }
        }
        state = _apply_topk_review_selection(score_rows=score_rows, filter_cfg=filter_cfg)
        self.assertTrue(state["enabled"])
        self.assertEqual(state["keep_count"], 2)
        self.assertEqual(score_rows[1]["decision"], "accept")
        self.assertEqual(score_rows[2]["decision"], "uncertain")
        self.assertEqual(score_rows[3]["decision"], "accept")
        self.assertEqual(state["reject_after_selection"], 0)

    def test_topk_review_selection_with_hard_reject(self) -> None:
        score_rows = [
            {"sample_id": "s1", "source": "synthetic", "s_final": 0.9, "phase1_route": "guided", "s_anchor": 0.7, "s_prompt": 0.1, "decision": "uncertain"},
            {"sample_id": "s2", "source": "synthetic", "s_final": 0.8, "phase1_route": "prompt_only", "s_anchor": 0.0, "s_prompt": 0.8, "decision": "uncertain"},
        ]
        filter_cfg = {
            "policy": {
                "ranking_review": {
                    "enabled": True,
                    "target_source": "synthetic",
                    "rank_metric": "s_final",
                    "keep_top_k": 1,
                    "review_rest": True,
                    "guided_min_anchor": 0.85,
                    "hard_reject": True,
                }
            }
        }
        state = _apply_topk_review_selection(score_rows=score_rows, filter_cfg=filter_cfg)
        self.assertEqual(state["eligible_total"], 1)
        self.assertEqual(score_rows[0]["decision"], "reject")
        self.assertEqual(score_rows[1]["decision"], "accept")

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
