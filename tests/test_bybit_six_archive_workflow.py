"""No-cost static safety contract for scheduled AND existing GAS fallback archive."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / ".github/workflows/colab-launcher.yml").read_text()
GAS = (ROOT / ".github/workflows/avrora-private-wave.yml").read_text()
ARCHIVE = (ROOT / ".github/workflows/bybit-official-archive.yml").read_text()


class SixArchiveWorkflowContracts(unittest.TestCase):
    def test_one_original_cron_and_six_allowlisted_jobs(self):
        self.assertEqual(MAIN.count('cron: "7 * * * *"'), 1)
        self.assertNotIn("  schedule:", GAS)
        self.assertNotIn("  schedule:", ARCHIVE)
        self.assertEqual(ARCHIVE.count("matrix:"), 1)
        self.assertIn(
            "symbol: [BTCUSDT, ETHUSDT, SOLUSDT, NEARUSDT, LINKUSDT, XRPUSDT]",
            ARCHIVE,
        )
        self.assertIn("fail-fast: false", ARCHIVE)
        self.assertIn("lag=\"$((hour % 7 + 1))\"", ARCHIVE)
        self.assertIn('date -u -d "$lag days ago"', ARCHIVE)

    def test_direct_gas_fallback_does_not_double_run_parent(self):
        self.assertIn("  capture-official-six-archive:", MAIN)
        self.assertIn("uses: ./.github/workflows/bybit-official-archive.yml", MAIN)
        self.assertIn("  official-archive-gas-fallback:", GAS)
        section = GAS.split("  official-archive-gas-fallback:", 1)[1].split(
            "  private-wave:", 1
        )[0]
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && inputs.mode == 'full13'",
            section,
        )
        self.assertIn("uses: ./.github/workflows/bybit-official-archive.yml", section)

    def test_provider_wait_does_not_mark_cache_or_deliver(self):
        self.assertIn('if [[ "$status" -eq 3 ]]', ARCHIVE)
        self.assertIn('echo "captured=false"', ARCHIVE)
        self.assertIn("steps.archive.outputs.captured == 'true'", ARCHIVE)
        self.assertIn("actions/upload-artifact@v4", ARCHIVE)
        self.assertIn("actions/cache/save@v4", ARCHIVE)
        self.assertIn("bybit-official-six-v2-", ARCHIVE)
        self.assertIn("tests/test_bybit_six_symbol_archive.py", MAIN)

    def test_strict_research_and_security_scope(self):
        self.assertIn('REAL: "OFF"', ARCHIVE)
        self.assertIn('HOLDOUT: "SEALED"', ARCHIVE)
        self.assertIn("contents: read", ARCHIVE)
        self.assertNotIn("actions: write", ARCHIVE)
        self.assertNotIn("AVRORA_COLAB_ADC_JSON_B64", ARCHIVE)
        self.assertNotIn("api.bybit.com", ARCHIVE)
        self.assertIn("--symbol", ARCHIVE)
        self.assertIn("github.run_id", ARCHIVE)


if __name__ == "__main__":
    unittest.main()
