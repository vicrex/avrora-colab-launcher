"""Prevent a formatted cached report from bypassing receipt validation."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools import verify_cached_wave

class CachedWaveProofTests(unittest.TestCase):
    def fixture(self):
        row={
          "schema":"AVRORA_WAVE_COLAB_DISCOVERY_V1",
          "status":"PASS","real":"OFF","holdout":"SEALED",
          "oos":False,"source_rows":8064,
          "models":{
            "WAVE_123_CONFIRM":{"trades":32,"net20_usdt":-26.458036},
            "FIB_618_RETRACE":{"trades":106,"net20_usdt":-88.815211},
          },
        }
        digest=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        row["receipt_sha256"]=digest
        return row
    def test_pretty_json_cache_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"proof.json"
            p.write_text(json.dumps(self.fixture(),indent=2))
            self.assertEqual(verify_cached_wave.verify(p)["status"],"PASS")
    def test_cache_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"proof.json"
            row=self.fixture()
            row["models"]["WAVE_123_CONFIRM"]["net20_usdt"]=-5.0
            p.write_text(json.dumps(row,indent=2))
            with self.assertRaises(ValueError):verify_cached_wave.verify(p)
if __name__=="__main__":unittest.main()
