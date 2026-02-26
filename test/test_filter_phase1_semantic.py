from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from filter.run_filter import (
    _apply_topk_review_selection,
    _resolve_filter_prompt_text,
    build_phase1_semantic_scores,
)


class FilterPhase1SemanticTest(unittest.TestCase):
    def test_phase1_v1_scoring_guided_and_prompt_only(self) -> None:
        rows = [
            {"sample_id": "s_guided", "source": "synthetic", "anchor_real_sample_id": "r1"},
            {"sample_id": "s_prompt", "source": "synthetic"},
        ]
        paired_scores = {"s_guided": {"s_semantic_pair": 0.9, "s_semantic_pair_hit": 1.0}}
        prompt_scores = {"s_guided": 0.2, "s_prompt": 0.8}
        phase1_cfg = {"enabled": True, "guided_marker_fields": ["anchor_real_sample_id"], "guided_w_anchor": 0.8, "guided_w_prompt": 0.2}
        out, state = build_phase1_semantic_scores(rows=rows, semantic_scores={}, paired_scores=paired_scores, prompt_scores=prompt_scores, phase1_cfg=phase1_cfg)
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
