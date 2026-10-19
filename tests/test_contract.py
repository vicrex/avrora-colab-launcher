import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_receipt", ROOT / "tools" / "verify_receipt.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SmokeContract(unittest.TestCase):
    def test_real_local_smoke(self):
        p = subprocess.run([sys.executable, str(ROOT / "smoke.py")], check=True, text=True, capture_output=True)
        self.assertIn('"orders": 0', p.stdout)
        if sys.platform.startswith("linux"):
            self.assertEqual(module.extract(p.stdout)["source_rows"], 0)

    def test_reject_orders(self):
        with self.assertRaises(ValueError):
            module.extract('AVRORA_COLAB_SMOKE_RESULT={"orders":1}')

    def test_reject_empty(self):
        with self.assertRaises(ValueError):
            module.extract("no receipt")

    def test_reject_digest_tamper(self):
        receipt = {
            "marker": "AVRORA_COLAB_SMOKE_V1", "status": "PASS", "mode": "CPU_ONLY_NO_TRADING",
            "orders": 0, "source_rows": 0, "real": "OFF", "holdout": "SEALED",
            "python": "3.12.0", "platform": "Linux", "utc": "2026-10-19T00:00:00+00:00",
        }
        payload = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        receipt["payload_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
        self.assertEqual(module.extract("AVRORA_COLAB_SMOKE_RESULT=" + json.dumps(receipt))["orders"], 0)
        receipt["source_rows"] = 1
        with self.assertRaises(ValueError):
            module.extract("AVRORA_COLAB_SMOKE_RESULT=" + json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
