"""Offline compatibility/safety checks for the free Apps Script Drive route.

Never sends private research data to Google or uses any third-party credential.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import unittest

from tools.private_gas_drive_delivery import (
    payload_and_ack, signing_message, validate_url, classify_receiver_ack,
)
from tools.private_multifamily_drive_delivery import canon

ROOT = Path(__file__).resolve().parents[1]
KEY = "0123456789abcdef" * 4
RECEIVER = ROOT / "tools/avrora_private_drive_receiver.gs"
WORKFLOW = ROOT / ".github/workflows/multifamily-sweep-smoke.yml"


def frozen_sample(count=64):
    ids = [f"{i:064x}" for i in range(count)]
    obj = {
        "schema": "AVRORA_MULTIFAMILY_SHADOW_SWEEP_V1",
        "count": count, "candidate_ids": ids,
        "models": [{"candidate_id": i, "train": {}, "validation": {}} for i in ids],
        "real": "OFF", "holdout": "SEALED",
        "oos_proven": False, "fill_proven": False,
    }
    obj["receipt_sha256"] = hashlib.sha256(canon(obj)).hexdigest()
    return canon(obj) + b"\n"


class FreeDriveGasTests(unittest.TestCase):
    def test_valid_signed_payload_sha_and_empty_secret_output(self):
        raw = frozen_sample()
        payload, ack = payload_and_ack(raw, "40181486935", KEY)
        self.assertEqual(payload["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(ack["status"], "PRIVATE_DRIVE_BYTE_READBACK_VERIFIED")
        self.assertEqual(ack["bytes"], len(raw))
        self.assertNotIn(KEY, json.dumps(payload) + json.dumps(ack))
        expected = hmac.new(
            KEY.encode("ascii"),
            signing_message("40181486935", payload["sha256"], payload["body_base64"]).encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(expected, payload["signature"])

    def test_valid_terminal_32_signed_payload(self):
        raw = frozen_sample(32)
        payload, ack = payload_and_ack(raw, "41028031248", KEY)
        self.assertEqual(ack["bytes"], len(raw))
        self.assertEqual(payload["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertIn('"count":32', raw.decode("utf-8"))

    def test_gas_receiver_source_gate_preserves_32_64_and_model_parity(self):
        source = RECEIVER.read_text(encoding="utf-8")
        self.assertIn("count !== 64 && count !== 32", source)
        self.assertIn("report.models.length !== count", source)
        self.assertIn("report.candidate_ids.length !== count", source)
        self.assertIn("report.models[idx].candidate_id !== cid", source)
        self.assertIn("seenCandidateIds[cid]", source)
        self.assertIn("BLOCKED_CANDIDATE_PARITY", source)

    def test_refuse_modified_source_receipt(self):
        with self.assertRaises(ValueError):
            payload_and_ack(frozen_sample().replace(b'"count":64', b'"count":63'), "99", KEY)

    def test_refuse_short_key_and_invalid_run_id(self):
        with self.assertRaises(ValueError):
            payload_and_ack(frozen_sample(), "99", "abcd")
        with self.assertRaises(ValueError):
            payload_and_ack(frozen_sample(), "not-a-run", KEY)

    def test_accept_only_deployed_script_google_url(self):
        validate_url("https://script.google.com/macros/s/AKfycbExample123/exec")
        for bad in (
            "http://script.google.com/macros/s/AK/exec",
            "https://script.google.com.evil.example/macros/s/AK/exec",
            "https://script.google.com/macros/s/AK/dev",
            "https://script.google.com/macros/s/AK/exec?secret=bad",
            "https://script.google.com@evil.example/macros/s/AK/exec",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_url(bad)

    def test_receiver_checks_hmac_before_creating_file_and_reads_back(self):
        js = RECEIVER.read_text(encoding="utf-8")
        self.assertIn("Utilities.computeHmacSha256Signature", js)
        self.assertIn("Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes)", js)
        self.assertIn("LockService.getScriptLock()", js)
        self.assertIn("getFilesByName(name)", js)
        self.assertIn("entry.getBlob().getBytes()", js)
        self.assertIn("PASS_PRIVATE_DRIVE_READBACK", js)
        self.assertIn("terminal_32_supported: true", js)
        self.assertLess(js.index("BLOCKED_INVALID_HMAC"), js.index("folder.createFile("))
        self.assertNotIn("createTrigger(", js)
        self.assertNotIn("ScriptApp.newTrigger(", js)

    def test_receiver_ack_diagnostic_bounded_no_secret_and_exact_validation(self):
        sample = frozen_sample()
        _payload, ack = payload_and_ack(sample, "40181486935", KEY)
        valid = {"status": "PASS_PRIVATE_DRIVE_READBACK", "run_id": "40181486935",
                 "sha256": ack["sha256"], "bytes": ack["bytes"]}
        self.assertEqual(classify_receiver_ack(valid, "40181486935", ack), "PASS")
        self.assertEqual(
            classify_receiver_ack({"status": "BLOCKED_PRIVATE_DRIVE_DELIVERY",
                                   "private_key": KEY}, "40181486935", ack),
            "OWNER_GAS_RECEIVER_REJECTED")
        self.assertEqual(classify_receiver_ack({"unexpected": "SECRET"}, "40181486935", ack),
                         "UNKNOWN_ACK_STATUS")
        self.assertEqual(classify_receiver_ack("SECRET", "40181486935", ack),
                         "NON_OBJECT_ACK")
        self.assertEqual(classify_receiver_ack({**valid, "bytes": 1}, "40181486935", ack),
                         "ACK_FIELDS_MISMATCH")

    def test_gas_receiver_logs_only_owner_visible_sanitized_stage(self):
        js = RECEIVER.read_text(encoding="utf-8")
        self.assertIn('var stage = "VALIDATE_ENVELOPE";', js)
        for stage in ("CHECK_HMAC", "VERIFY_REPORT", "DRIVE_LOCK_AND_FOLDER",
                      "DRIVE_CREATE_OR_REUSE", "DRIVE_READBACK"):
            self.assertIn('stage = "' + stage + '";', js)
        self.assertIn('console.error("AVRORA_GAS_OWNER_AUDIT stage="', js)
        self.assertIn('kind=" + safeKind', js)
        self.assertIn('return avroraReply_({status: "BLOCKED_PRIVATE_DRIVE_DELIVERY"});', js)
        self.assertNotIn("console.error(err)", js)
        self.assertNotIn("console.error(safeMessage)", js)

    def test_public_64_case_job_prefers_free_gas_and_never_publishes_private_json(self):
        yml = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("AVRORA_GAS_REPORT_WEBAPP_URL", yml)
        self.assertIn("AVRORA_GAS_REPORT_HMAC_KEY", yml)
        self.assertIn("python -m tools.private_gas_drive_delivery", yml)
        self.assertIn("BLOCKED_PRIVATE_REPORT_DELIVERY_NOT_AUTHORIZED", yml)
        self.assertLess(yml.index("python -m tools.private_gas_drive_delivery"),
                        yml.index("private_multifamily_drive_delivery.py"))
        self.assertIn("path: sweep_private_drive_ack.json", yml)
        self.assertNotIn("path: sweep_private_full.json", yml)
        self.assertIn('REAL: "OFF"', yml)
        self.assertIn('HOLDOUT: "SEALED"', yml)
        self.assertNotIn("cron:", yml)


if __name__ == "__main__":
    unittest.main()
