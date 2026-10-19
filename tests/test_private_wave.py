import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("private_wave_colab", ROOT/"tools"/"private_wave_colab.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PrivateWaveTest(unittest.TestCase):
    def test_does_not_require_broad_google_drive_permission(self):
        self.assertFalse(hasattr(m, "fetch_private_inputs"))
        self.assertFalse(hasattr(m, "discover_drive_id"))
        source=(ROOT/"tools"/"private_wave_colab.py").read_text()
        self.assertNotIn("drive.readonly", source)
        self.assertNotIn("https://www.googleapis.com/drive", source)

    def test_hash_rejects_unverified_inputs(self):
        with self.assertRaises(ValueError):
            m.validate_source(b"ZIP",b"CSV")

    def test_remote_script_only_contains_pass_marker_and_no_external_endpoints(self):
        s=m.build_remote_script({"engine.py":"print('engine')","check2_independent.py":"print('checker')",
                                 "tests.py":"print('tests')"},b"hello")
        self.assertIn("AVRORA_PRIVATE_WAVE_RESULT=",s)
        self.assertNotIn("drive.google.com",s)
        self.assertNotIn("api.github.com",s)
        self.assertNotIn("refresh_token",s)
        compile(s, "remote_generated.py", "exec")

    def test_receipt_rejects_tampering_and_allows_exact_approved_totals(self):
        obj={"status":"PASS","real":"OFF","holdout":"SEALED","source_rows":8064,
             "models":{k:{"trades":v["accepted"],"net20_usdt":v["net20_usdt"]}
                       for k,v in m.EXPECTED.items()}}
        h=m.sha(json.dumps(obj,sort_keys=True,separators=(",",":")).encode())
        obj["receipt_sha256"]=h
        s=m.MARKER+json.dumps(obj)
        self.assertEqual(m.verify_remote_receipt(s)["status"],"PASS")
        obj["models"]["WAVE_123_CONFIRM"]["trades"]=1
        with self.assertRaises(ValueError): m.verify_remote_receipt(m.MARKER+json.dumps(obj))
        with self.assertRaises(ValueError): m.verify_remote_receipt(s+"\n"+s)

    def test_patch_is_exactly_one_location_per_independent_source(self):
        self.assertEqual(set(m.PATCHES),{"engine.py","check2_independent.py"})
        for value in m.PATCHES.values():
            self.assertIn("+900000",value[1])

    def test_private_workflow_omits_pull_request_triggers(self):
        wf=(ROOT/".github/workflows/avrora-private-wave.yml")
        if wf.exists():
            s=wf.read_text()
            self.assertIn("avrora_private_wave_enabled",s.lower())
            self.assertNotIn("pull_request:",s)
            self.assertIn("repository: vicrex/avrora-wave-source",s)
            self.assertIn("persist-credentials: false",s)
            self.assertIn("ssh-strict: true",s)
            self.assertIn("AVRORA_WAVE_SOURCE_DEPLOY_KEY",s)
            self.assertNotIn("AVRORA_DRIVE_READONLY_ADC_JSON_B64",s)


if __name__=="__main__":
    unittest.main()
