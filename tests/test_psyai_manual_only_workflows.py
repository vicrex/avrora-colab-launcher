"""PsyAI Colab workflows are manual release gates, not background schedulers."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/psyai-colab-cpu-one-shot.yml",
    ".github/workflows/psyai-private-colab-acceptance.yml",
)


class PsyAIManualOnlyWorkflowTests(unittest.TestCase):
    def test_colab_acceptance_requires_manual_dispatch(self):
        for relative in WORKFLOWS:
            with self.subTest(workflow=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertRegex(text, r"(?m)^on:\s*$")
                self.assertRegex(text, r"(?m)^  workflow_dispatch:\s*$")
                self.assertNotRegex(text, r"(?m)^  schedule:\s*$")
                self.assertNotRegex(text, r"(?m)^\s*- cron:")
                self.assertNotRegex(text, r"(?m)^  (push|pull_request|workflow_call):")
                self.assertRegex(text, r"(?m)^concurrency:\s*$")
                self.assertRegex(text, r"(?m)^  cancel-in-progress: false\s*$")


if __name__ == "__main__":
    unittest.main()
