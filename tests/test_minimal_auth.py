"""Offline tests; do not need Google authentication or internet."""
import importlib.util
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("authorize_colab_minimal", ROOT / "tools" / "authorize_colab_minimal.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FakeCreds:
    def __init__(self, grants=None, refresh="SECRET_VALUE"):
        self.granted_scopes = grants
        self.refresh = refresh
    def to_json(self):
        return json.dumps({"client_id": "public-id", "client_secret": "public-client",
                           "refresh_token": self.refresh, "token_uri": "https://oauth2.googleapis.com/token",
                           "scopes": self.granted_scopes})

class MinimalOauthScopeContract(unittest.TestCase):
    def test_request_excludes_cloud_and_drive(self):
        self.assertEqual(len(mod.REQUESTED_SCOPES), 3)
        self.assertNotIn("https://www.googleapis.com/auth/cloud-platform", mod.REQUESTED_SCOPES)
        self.assertFalse(any("/drive" in s for s in mod.REQUESTED_SCOPES))
    def test_valid_minimal_adc(self):
        adc = mod.build_adc(FakeCreds(list(mod.REQUESTED_SCOPES)))
        self.assertEqual(adc["type"], "authorized_user")
        self.assertIn(mod.COLAB_SCOPE, adc["scopes"])
        self.assertNotIn("https://www.googleapis.com/auth/cloud-platform", adc["scopes"])
    def test_reject_broad_scope(self):
        with self.assertRaises(ValueError):
            mod.build_adc(FakeCreds(list(mod.REQUESTED_SCOPES) + ["https://www.googleapis.com/auth/cloud-platform"]))
    def test_reject_partial(self):
        with self.assertRaises(ValueError):
            mod.build_adc(FakeCreds(["openid", mod.COLAB_SCOPE]))
    def test_reject_missing_refresh_token(self):
        with self.assertRaises(ValueError):
            mod.build_adc(FakeCreds(list(mod.REQUESTED_SCOPES), refresh=""))
    def test_reject_unconfirmed_grants(self):
        with self.assertRaises(ValueError):
            mod.build_adc(FakeCreds(None))
if __name__ == "__main__":
    unittest.main()
