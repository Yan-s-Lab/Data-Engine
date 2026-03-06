from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RuntimeDependencyContractTests(unittest.TestCase):
    def test_pyproject_declares_filter_runtime_dependencies(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"huggingface-hub[cli]>=0.24.0,<1.0"', text)
        self.assertIn('"torch>=2.3.0"', text)
        self.assertIn('"transformers>=4.57.1"', text)

    def test_requirements_includes_filter_runtime_dependencies(self) -> None:
        text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("huggingface-hub==0.36.0", text)
        self.assertIn("torch==2.3.0", text)
        self.assertIn("transformers==4.57.1", text)


if __name__ == "__main__":
    unittest.main()
