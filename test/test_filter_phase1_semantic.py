from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from filter.run_filter import (
    _apply_topk_review_selection,
    _gate_applies_to_row,
    _resolve_filter_prompt_text,
    build_phase1_semantic_scores,
)


class FilterPhase1SemanticTest(unittest.TestCase):
    def test_guided_fusion_weighted_sum(self) -> None:
        rows = [{"sample_id": "s_guided", "source": "synthetic", "anchor_real_sample_id": "r1"}]
        semantic_scores = {"s_guided": {"s_semantic_anchor": 0.4}}
        paired_scores = {"s_guided": {"s_semantic_pair": 0.9, "s_semantic_pair_hit": 1.0}}
        prompt_scores = {"s_guided": 0.2}
        phase1_cfg = {
            "enabled": True,
            "guided_source": "semantic_pair",
            "prompt_only_source": "prompt_score",
            "fallback_source": "semantic_anchor",
            "guided_marker_fields": ["anchor_real_sample_id"],
            "guided_fusion": {
                "enabled": True,
                "method": "weighted_sum",
                "pair_weight": 0.8,
                "prompt_weight": 0.2,
            },
        }
        out, _ = build_phase1_semantic_scores(
            rows=rows,
            semantic_scores=semantic_scores,
            paired_scores=paired_scores,
            prompt_scores=prompt_scores,
            phase1_cfg=phase1_cfg,
        )
        self.assertEqual(out["s_guided"]["s_phase1_semantic_source"], "semantic_pair_fused")
        self.assertAlmostEqual(out["s_guided"]["s_phase1_semantic"], 0.76, places=6)

    def test_topk_review_selection(self) -> None:
        score_rows = [
            {"sample_id": "r1", "source": "real", "final_score": 1.0, "decision": "accept"},
            {"sample_id": "s1", "source": "synthetic", "final_score": 0.9, "decision": "reject"},
            {"sample_id": "s2", "source": "synthetic", "final_score": 0.7, "decision": "reject"},
            {"sample_id": "s3", "source": "synthetic", "final_score": 0.2, "decision": "reject"},
        ]
        filter_cfg = {
            "policy": {
                "ranking_review": {
                    "enabled": True,
                    "target_source": "synthetic",
                    "rank_metric": "final_score",
                    "keep_top_k": 2,
                    "review_rest": True,
                }
            }
        }
        state = _apply_topk_review_selection(score_rows=score_rows, filter_cfg=filter_cfg)
        self.assertTrue(state["enabled"])
        self.assertEqual(state["keep_count"], 2)
        self.assertEqual(score_rows[1]["decision"], "accept")
        self.assertEqual(score_rows[2]["decision"], "accept")
        self.assertEqual(score_rows[3]["decision"], "uncertain")

    def test_topk_review_selection_with_eligibility(self) -> None:
        score_rows = [
            {"sample_id": "s1", "source": "synthetic", "final_score": 0.9, "s_prompt": 0.0, "s_phase1_semantic_source": "semantic_pair_fused", "decision": "reject"},
            {"sample_id": "s2", "source": "synthetic", "final_score": 0.8, "s_prompt": 0.1, "s_phase1_semantic_source": "semantic_pair_fused", "decision": "reject"},
            {"sample_id": "s3", "source": "synthetic", "final_score": 0.7, "s_prompt": 0.2, "s_phase1_semantic_source": "semantic_pair_fused", "decision": "reject"},
        ]
        filter_cfg = {
            "policy": {
                "ranking_review": {
                    "enabled": True,
                    "target_source": "synthetic",
                    "rank_metric": "final_score",
                    "keep_top_k": 2,
                    "review_rest": True,
                    "accept_eligibility": [
                        {
                            "metric": "s_prompt",
                            "op": ">",
                            "threshold": 0.0,
                            "phase1_sources": ["semantic_pair"],
                        }
                    ],
                }
            }
        }
        state = _apply_topk_review_selection(score_rows=score_rows, filter_cfg=filter_cfg)
        self.assertEqual(state["eligible_total"], 2)
        self.assertEqual(score_rows[0]["decision"], "uncertain")
        self.assertEqual(score_rows[0]["decision_basis"], "policy_ranking_ineligible_review")
        self.assertEqual(score_rows[1]["decision"], "accept")
        self.assertEqual(score_rows[2]["decision"], "accept")

    def test_gate_condition_by_phase1_source(self) -> None:
        row = {"sample_id": "s_prompt", "source": "synthetic"}
        gate_cfg = {"metric": "s_phase1_semantic", "phase1_sources": ["semantic_pair", "semantic_anchor"]}
        self.assertFalse(_gate_applies_to_row(gate_cfg=gate_cfg, row=row, phase1_source="prompt_score"))
        self.assertTrue(_gate_applies_to_row(gate_cfg=gate_cfg, row=row, phase1_source="semantic_pair"))
        self.assertTrue(_gate_applies_to_row(gate_cfg=gate_cfg, row=row, phase1_source="semantic_pair_fused"))

    def test_phase1_routing_guided_prompt_and_fallback(self) -> None:
        rows = [
            {"sample_id": "r1", "source": "real"},
            {"sample_id": "s_guided", "source": "synthetic", "anchor_real_sample_id": "r1"},
            {"sample_id": "s_prompt", "source": "synthetic"},
            {"sample_id": "s_guided_miss", "source": "synthetic", "anchor_real_sample_id": "missing_real"},
        ]
        semantic_scores = {
            "r1": {"s_semantic_anchor": 0.3},
            "s_guided": {"s_semantic_anchor": 0.4},
            "s_prompt": {"s_semantic_anchor": 0.5},
            "s_guided_miss": {"s_semantic_anchor": 0.6},
        }
        paired_scores = {
            "s_guided": {"s_semantic_pair": 0.9, "s_semantic_pair_hit": 1.0},
            "s_guided_miss": {"s_semantic_pair": 0.0, "s_semantic_pair_hit": 0.0},
        }
        prompt_scores = {"s_prompt": 0.8}
        phase1_cfg = {
            "enabled": True,
            "guided_source": "semantic_pair",
            "prompt_only_source": "prompt_score",
            "fallback_source": "semantic_anchor",
            "guided_marker_fields": ["anchor_real_sample_id"],
        }

        out, state = build_phase1_semantic_scores(
            rows=rows,
            semantic_scores=semantic_scores,
            paired_scores=paired_scores,
            prompt_scores=prompt_scores,
            phase1_cfg=phase1_cfg,
        )

        self.assertEqual(out["s_guided"]["s_phase1_semantic_source"], "semantic_pair")
        self.assertAlmostEqual(out["s_guided"]["s_phase1_semantic"], 0.9, places=6)
        self.assertEqual(out["s_prompt"]["s_phase1_semantic_source"], "prompt_score")
        self.assertAlmostEqual(out["s_prompt"]["s_phase1_semantic"], 0.8, places=6)
        self.assertEqual(out["s_guided_miss"]["s_phase1_semantic_source"], "semantic_anchor")
        self.assertAlmostEqual(out["s_guided_miss"]["s_phase1_semantic"], 0.6, places=6)
        self.assertEqual(state["guided_synth_count"], 2)
        self.assertEqual(state["prompt_only_synth_count"], 1)

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


if __name__ == "__main__":
    unittest.main()
