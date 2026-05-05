from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from common.config_io import load_config
from pipelines.run_serial_plan import _run_post_action, _should_run_post_action, parse_plan


class SerialPlanPostActionsTest(unittest.TestCase):
    def test_parse_fair_pose_ablation_plan(self) -> None:
        plan = load_config(Path("configs/coco_pose_2017__expansion/pipeline_fair_pose_ablation.yaml"))
        queue, continue_on_error = parse_plan(plan)
        self.assertFalse(continue_on_error)
        self.assertEqual(len(queue), 16)
        self.assertEqual(queue[0].task_name, "real_anchor_and_holdout")
        self.assertEqual(queue[-1].task_name, "pose_ablation_summary")

    def test_parse_plan_merges_global_stage_task_post_actions(self) -> None:
        plan = {
            "serial_plan": {
                "post_actions": [{"type": "comfyui.queue_empty_check"}],
                "stages": [
                    {
                        "name": "generation",
                        "post_actions": [{"type": "comfyui.free_memory"}],
                        "tasks": [
                            {
                                "name": "prompt_only",
                                "config": "configs/examples/a.yaml",
                                "post_actions": [{"type": "comfyui.queue_empty_check", "on": "failure"}],
                            }
                        ],
                    }
                ],
            }
        }
        queue, continue_on_error = parse_plan(plan)
        self.assertFalse(continue_on_error)
        self.assertEqual(len(queue), 1)
        self.assertEqual(
            [x["type"] for x in queue[0].post_actions],
            ["comfyui.queue_empty_check", "comfyui.free_memory", "comfyui.queue_empty_check"],
        )
        self.assertEqual(queue[0].post_actions[2]["on"], "failure")

    def test_should_run_post_action(self) -> None:
        self.assertTrue(_should_run_post_action({"enabled": True, "on": "always"}, task_ok=True))
        self.assertTrue(_should_run_post_action({"enabled": True, "on": "success"}, task_ok=True))
        self.assertFalse(_should_run_post_action({"enabled": True, "on": "success"}, task_ok=False))
        self.assertTrue(_should_run_post_action({"enabled": True, "on": "failure"}, task_ok=False))
        self.assertFalse(_should_run_post_action({"enabled": False, "on": "always"}, task_ok=True))

    @patch("pipelines.run_serial_plan._http_request_json")
    def test_run_post_action_queue_empty_check(self, mock_http: object) -> None:
        mock_http.return_value = {"queue_running": [], "queue_pending": []}
        details = _run_post_action(
            {
                "type": "comfyui.queue_empty_check",
                "timeout_sec": 5,
                "params": {"base_url": "http://127.0.0.1:8188"},
            }
        )
        self.assertEqual(details["running_count"], 0)
        self.assertEqual(details["pending_count"], 0)
        mock_http.assert_called_once()

    @patch("pipelines.run_serial_plan._http_request_json")
    def test_run_post_action_free_memory(self, mock_http: object) -> None:
        mock_http.return_value = {}
        details = _run_post_action(
            {
                "type": "comfyui.free_memory",
                "timeout_sec": 7,
                "params": {
                    "base_url": "http://127.0.0.1:8188",
                    "unload_models": True,
                    "free_memory": True,
                },
            }
        )
        self.assertTrue(details["unload_models"])
        self.assertTrue(details["free_memory"])
        mock_http.assert_called_once()


if __name__ == "__main__":
    unittest.main()
