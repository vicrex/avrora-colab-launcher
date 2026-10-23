"""Offline contract for the existing GAS hourly fallback; no API calls or real orders."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_WAVE = ROOT / ".github/workflows/avrora-private-wave.yml"
PUBLIC_LAUNCHER = ROOT / ".github/workflows/colab-launcher.yml"
SWEEP = ROOT / ".github/workflows/multifamily-sweep-smoke.yml"


class GasFallbackRoutingTests(unittest.TestCase):
    def test_existing_gas_full13_dispatch_runs_shadow_once(self):
        text = PRIVATE_WAVE.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("      - full13", text)
        self.assertEqual(text.count("  multifamily-shadow-hourly-fallback:\n"), 1)
        fallback = text.split("  multifamily-shadow-hourly-fallback:\n", 1)[1]
        fallback = fallback.split("\n  private-wave:", 1)[0]
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && inputs.mode == 'full13'",
            fallback,
        )
        self.assertIn("uses: ./.github/workflows/multifamily-sweep-smoke.yml", fallback)
        self.assertIn("secrets: inherit", fallback)
        self.assertNotIn("cron:", fallback)

    def test_schedule_keeps_single_original_shadow_path(self):
        launcher = PUBLIC_LAUNCHER.read_text(encoding="utf-8")
        private_wave = PRIVATE_WAVE.read_text(encoding="utf-8")
        self.assertEqual(launcher.count('cron: "7 * * * *"'), 1)
        self.assertEqual(launcher.count("  multifamily-shadow-scheduled:\n"), 1)
        self.assertIn("github.event_name == 'schedule'", launcher)
        self.assertIn("uses: ./.github/workflows/multifamily-sweep-smoke.yml", launcher)
        self.assertNotIn("  schedule:", private_wave)
        self.assertNotIn("  repository_dispatch:", private_wave)

    def test_sweep_stays_read_only_shadow_and_sha_pinned(self):
        sweep = SWEEP.read_text(encoding="utf-8")
        self.assertIn("  workflow_call:", sweep)
        self.assertIn('REAL: "OFF"', sweep)
        self.assertIn('HOLDOUT: "SEALED"', sweep)
        self.assertIn("ref: 90c3d85a8234d2b640f772be25dd88fd0f547acc", sweep)
        self.assertIn("ref: 3352275492bf192dd4c6d7abfcf9bbaae19ac983", sweep)
        self.assertIn("NOT_INDEPENDENTLY_RECONSTRUCTED", sweep)


if __name__ == "__main__":
    unittest.main()
