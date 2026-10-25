"""Offline checks for the one-time owner-side OAuth Drive setup (no network)."""
from __future__ import annotations
import json
from pathlib import Path
import unittest

from tools.verify_private_drive_adc import SCOPE, validate_scopes, validate_adc_fields

ROOT=Path(__file__).resolve().parents[1]


class PrivateDriveAuthSetupContract(unittest.TestCase):
    def test_correct_scope_allowed(self):
        validate_scopes({SCOPE})
        validate_scopes({SCOPE, "openid"})

    def test_colab_only_scope_rejected(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED_DRIVE_SCOPE"):
            validate_scopes({"https://www.googleapis.com/auth/colaboratory"})

    def test_broad_cloud_extra_scope_rejected(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED_DRIVE_SCOPE"):
            validate_scopes({SCOPE, "https://www.googleapis.com/auth/cloud-platform"})

    def test_reject_nonuser_or_missing_credentials(self):
        with self.assertRaises(ValueError):
            validate_adc_fields({"type": "service_account"})
        with self.assertRaises(ValueError):
            validate_adc_fields({"type": "authorized_user"})

    def test_valid_adc_with_exact_drive_scope(self):
        validate_adc_fields({"type": "authorized_user","client_id":"a",
                             "client_secret":"b", "refresh_token":"c",
                             "scopes":[SCOPE]})

    def test_reject_invalid_scope_format(self):
        with self.assertRaises(ValueError):
            validate_adc_fields({"type": "authorized_user","client_id":"a",
                                 "client_secret":"b", "refresh_token":"c",
                                 "scopes":"https://www.googleapis.com/auth/drive"})

    def test_cloud_shell_never_changes_colab_secret_or_cron(self):
        s=(ROOT/"tools/connect_private_drive_cloud_shell.sh").read_text()
        self.assertIn("AVRORA_PRIVATE_DRIVE_ADC_JSON_B64",s)
        self.assertNotIn("AVRORA_COLAB_ADC_JSON_B64",s)
        self.assertIn("--client-id-file=",s)
        self.assertIn("--scopes=",s)
        self.assertIn("--no-browser",s)
        self.assertNotIn("--no-launch-browser",s)
        self.assertIn("verify_private_drive_adc.py",s)
        self.assertIn("gh secret set",s)
        self.assertNotIn("cron:",s)

    def test_probe_cleanup_before_secret_install(self):
        a=(ROOT/"tools/verify_private_drive_adc.py").read_text()
        b=(ROOT/"tools/connect_private_drive_cloud_shell.sh").read_text()
        self.assertIn("PROBE_READBACK",a)
        self.assertIn("PROBE_CLEANUP",a)
        self.assertIn("requests.delete",a)
        self.assertIn("PASS_VERIFIED_TEMP_ADC_READY",a)
        self.assertLess(b.index("verify_private_drive_adc.py"), b.index("gh secret set"))

if __name__=="__main__":
    unittest.main()
