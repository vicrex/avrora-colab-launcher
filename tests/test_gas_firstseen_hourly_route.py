"""Offline contract for public real firstseen capture on EXISTING hourly GAS.

No second scheduler, network in tests, private endpoint, secret or trade path.
The real public WebSocket collector stays deliberately bounded to 180 seconds.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
GAS = ROOT / ".github/workflows/avrora-private-wave.yml"
CAPTURE = ROOT / ".github/workflows/avrora-public-firstseen-one-shot.yml"
CLOCK = ROOT / ".github/workflows/colab-launcher.yml"
SOURCE = ROOT / "tools/avrora_public_market_firstseen_probe.py"


def job_block(doc, job):
    start = f"  {job}:\n"
    if doc.count(start) != 1:
        raise AssertionError(f"{job}: missing or duplicate")
    suffix = doc.split(start, 1)[1]
    match = re.search(r"(?m)^  [a-zA-Z0-9_-]+:\s*$", suffix)
    return suffix[:match.start()] if match else suffix


class ExistingHourlyGASFirstseenRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gas = GAS.read_text(encoding="utf-8")
        cls.capture = CAPTURE.read_text(encoding="utf-8")
        cls.clock = CLOCK.read_text(encoding="utf-8")
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_only_existing_full13_gas_dispatch_triggers_new_capture(self):
        block = job_block(self.gas, "firstseen-market-source-gas-hourly")
        self.assertIn(
            "if: ${{ github.event_name == 'workflow_dispatch' && inputs.mode == 'full13' }}",
            block)
        self.assertIn(
            "uses: ./.github/workflows/avrora-public-firstseen-one-shot.yml",
            block)
        self.assertNotIn("secrets: inherit", block)
        self.assertNotIn("runs-on:", block)
        self.assertNotIn("schedule:", block)
        self.assertNotIn("cron:", block)
        self.assertNotIn("workflow_dispatch:", block)
        self.assertNotIn("colab", block.lower().split("name:", 1)[-1].split("\n", 1)[0])

    def test_no_new_cron_and_no_unconditional_call(self):
        self.assertEqual(self.clock.count('cron: "7 * * * *"'), 1)
        self.assertNotIn("  schedule:", self.gas)
        self.assertNotIn("  schedule:", self.capture)
        self.assertNotIn("repository_dispatch:", self.capture)
        self.assertIn("  workflow_call:", self.capture)
        self.assertIn("  workflow_dispatch:", self.capture)
        self.assertEqual(self.gas.count(
            "  firstseen-market-source-gas-hourly:\n"), 1)
        self.assertIn(
            "uses: ./.github/workflows/avrora-private-wave.yml",
            job_block(self.clock, "full13-scheduled"))
        self.assertNotIn("avrora-public-firstseen-one-shot.yml", self.clock)
        self.assertNotIn("firstseen-market-source-gas-hourly", self.clock)
        self.assertIn(
            "uses: ./.github/workflows/bybit-official-archive.yml",
            job_block(self.gas, "official-archive-gas-fallback"))
        self.assertIn(
            "uses: ./.github/workflows/multifamily-sweep-smoke.yml",
            job_block(self.gas, "multifamily-shadow-hourly-fallback"))

    def test_capture_is_real_market_bytes_with_independent_raw_check2(self):
        block = job_block(self.capture, "public-observation")
        self.assertIn("python -m tools.avrora_public_market_firstseen_probe --seconds 180", block)
        self.assertIn("python -m tools.avrora_firstseen_check2", block)
        self.assertIn("observed_ws_frames.jsonl.gz", block)
        self.assertIn("probe_receipt.json", block)
        self.assertIn("independent_raw_check2.json", block)
        self.assertIn("if-no-files-found: warn", block)
        self.assertIn("retention-days: 14", block)
        self.assertIn('REAL: "OFF"', block)
        self.assertIn('HOLDOUT: "SEALED"', block)
        self.assertIn("contents: read", self.capture)
        self.assertNotIn("secrets:", self.capture)
        self.assertIn("timeout-minutes: 8", block)
        self.assertIn("first-observed", self.capture)
        self.assertNotIn("colab --auth", block)
        self.assertNotIn("order/create", block)

    def test_collector_uses_public_ws_only_and_rejects_trading_claims(self):
        self.assertIn('ENDPOINT="wss://stream.bybit.com/v5/public/linear"', self.source)
        for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT",
                    "XRPUSDT", "LINKUSDT", "NEARUSDT"):
            self.assertIn(sym, self.source)
        self.assertIn("MAX_SECONDS=240", self.source)
        self.assertIn("MAX_FRAMES=100_000", self.source)
        self.assertIn("MAX_UNCOMPRESSED=160_000_000", self.source)
        self.assertIn('"no_market_feed_gaps_proven":False', self.source)
        self.assertIn('"oos_proven":False', self.source)
        self.assertIn('"strategy_net_profit_proven":False', self.source)
        self.assertIn('"live_trading_authorized":False', self.source)
        self.assertNotIn("/v5/private", self.source)
        self.assertNotIn("/v5/order/create", self.source)


if __name__ == "__main__":
    unittest.main()
