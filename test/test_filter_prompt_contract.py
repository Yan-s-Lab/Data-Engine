from __future__ import annotations

import unittest

from common.filter_prompt_contract import resolve_prompt_groups


class FilterPromptContractTest(unittest.TestCase):
    def test_resolve_prompt_groups_precedence(self) -> None:
        clip_cfg = {
            "compared_prompt": {"positive": ["legacy_pos"], "negative": ["legacy_neg"]},
            "compare_texts": {"positive": ["snake_pos"], "negative": ["snake_neg"]},
            "compare-texts": {"positive": ["dash_pos"], "negative": ["dash_neg"]},
        }
        groups, source = resolve_prompt_groups(clip_cfg)
        self.assertEqual(source, "clip.compare-texts")
        self.assertEqual(groups["positive"], ["dash_pos"])
        self.assertEqual(groups["negative"], ["dash_neg"])

    def test_resolve_prompt_groups_accepts_compared_prompt(self) -> None:
        clip_cfg = {
            "compared_prompt": {"positive": ["a", "  ", 3], "negative": ["b"]},
        }
        groups, source = resolve_prompt_groups(clip_cfg)
        self.assertEqual(source, "clip.compared_prompt")
        self.assertEqual(groups["positive"], ["a", "3"])
        self.assertEqual(groups["negative"], ["b"])

    def test_resolve_prompt_groups_returns_empty_when_invalid(self) -> None:
        groups, source = resolve_prompt_groups({"compare-texts": {"positive": ["a"]}})
        self.assertEqual(source, "")
        self.assertEqual(groups, {"positive": [], "negative": []})


if __name__ == "__main__":
    unittest.main()
