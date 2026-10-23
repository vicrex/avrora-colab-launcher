"""Offline no-cost guards for the single hourly AVRORA FULL13 entrypoint."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLER = ROOT / ".github/workflows/colab-launcher.yml"
CALLED = ROOT / ".github/workflows/avrora-private-wave.yml"


class SingleHourlyFull13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caller = CALLER.read_text(encoding="utf-8")
        cls.called = CALLED.read_text(encoding="utf-8")

    def test_single_scheduler(self):
        self.assertEqual(
            self.caller.count("  schedule:") + self.called.count("  schedule:"),
            1,
            "Never have two scheduled Colab workflows competing for compute",
        )
        self.assertIn('    - cron: "7 * * * *"', self.caller)
        self.assertNotIn("  schedule:", self.called)

    def test_schedule_calls_full13_without_running_smoke(self):
        self.assertIn("  full13-scheduled:", self.caller)
        self.assertIn("    if: ${{ github.event_name == 'schedule' }}", self.caller)
        self.assertIn("    uses: ./.github/workflows/avrora-private-wave.yml", self.caller)
        self.assertIn("    secrets: inherit", self.caller)
        self.assertIn("  safety-smoke:", self.caller)
        self.assertIn("    if: ${{ github.event_name == 'workflow_dispatch' || github.event_name == 'push' }}", self.caller)

    def test_reusable_full13_still_manual_and_safe(self):
        self.assertIn("  workflow_call:", self.called)
        self.assertIn("  workflow_dispatch:", self.called)
        self.assertIn('      REAL: "OFF"', self.called)
        self.assertIn('      HOLDOUT: "SEALED"', self.called)
        self.assertIn("vars.AVRORA_FULL13_ENABLED == 'true'", self.called)
        self.assertIn("FULL13 SINGLE Colab run:", self.called)
        self.assertIn("PASS_PINNED_FULL13_DATASET_69576_M15", self.called)
        self.assertIn("  cancel-in-progress: false", self.called)

    def test_manual_smoke_cannot_consume_scheduled_compute(self):
        self.assertIn("RUN_REMOTE: ${{ github.event_name == 'schedule' || inputs.mode == 'colab' }}", self.caller)
        self.assertIn("    if: ${{ github.event_name == 'workflow_dispatch' || github.event_name == 'push' }}", self.caller)


if __name__ == "__main__":
    unittest.main()
