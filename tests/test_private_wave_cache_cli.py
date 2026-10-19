"""Regression tests for workflow's cached private-wave receipt CLI entrypoint.

No Google token, market data, Colab runtime or trading dependency.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "verify_cached_wave.py"
EXPECTED = {
    "WAVE_123_CONFIRM": {"accepted": 32, "net20_usdt": -26.458036},
    "FIB_618_RETRACE": {"accepted": 106, "net20_usdt": -88.815211},
}


def fixture():
    body = {
        "status": "PASS",
        "real": "OFF",
        "holdout": "SEALED",
        "oos": False,
        "source_rows": 8064,
        "models": {
            k: {"trades": v["accepted"], "net20_usdt": v["net20_usdt"]}
            for k, v in EXPECTED.items()
        },
    }
    body["receipt_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


class CachedWaveCliTest(unittest.TestCase):
    def run_cli(self, obj, as_module=False):
        env = dict(os.environ)
        # Reproduce an ordinary fresh hosted runner without a custom PYTHONPATH.
        env.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "wave_research_summary.json"
            path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
            cmd = ([sys.executable, "-m", "tools.verify_cached_wave", str(path)]
                   if as_module else [sys.executable, str(SCRIPT), str(path)])
            return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                                  text=True, timeout=15, check=False)

    def test_workflow_exact_cli_cache_hit_is_idle_and_skips_colab(self):
        result = self.run_cli(fixture())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "IDLE_NO_NEW_APPROVED_CANDIDATE")

    def test_module_mode_is_consistent(self):
        result = self.run_cli(fixture(), as_module=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "IDLE_NO_NEW_APPROVED_CANDIDATE")

    def test_tampered_cache_fails_closed_in_both_modes(self):
        data = fixture()
        data["models"]["FIB_618_RETRACE"]["net20_usdt"] = 999
        for mode in (False, True):
            with self.subTest(as_module=mode):
                result = self.run_cli(data, as_module=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("BLOCKED_INVALID_CACHED_WAVE_RECEIPT", result.stderr)
                self.assertNotIn("IDLE_NO_NEW_APPROVED_CANDIDATE", result.stdout)


if __name__ == "__main__":
    unittest.main()
