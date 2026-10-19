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
    def test_manifest_never_accepts_urls_or_extra_fields(self):
        def b64(obj):
            return base64.b64encode(json.dumps(obj).encode()).decode()
        good=m.manifest_from_secret(b64({"csv_file_id":"A"*20,"zip_file_id":"B"*20}))
        self.assertEqual(len(good),2)
        for bad in ({"csv_file_id":"https://drive.google.com/123","zip_file_id":"B"*20},
                    {"csv_file_id":"A"*20,"zip_file_id":"A"*20},
                    {"csv_file_id":"A"*20,"zip_file_id":"B"*20,"holdout":"1"}):
            with self.assertRaises(ValueError):
                m.manifest_from_secret(b64(bad))

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
        wf=(ROOT/".github/workflows/avrora-wave-research.yml")
        if wf.exists():
            s=wf.read_text()
            self.assertIn("wave_research_enabled",s.lower())
            self.assertNotIn("pull_request:",s)


if __name__=="__main__":
    unittest.main()
