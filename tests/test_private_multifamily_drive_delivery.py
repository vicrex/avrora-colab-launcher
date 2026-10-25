"""Offline safety contract: no Drive network access, no private strategy data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from tools.private_multifamily_drive_delivery import canon, validate_report


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multifamily-sweep-smoke.yml"


def valid_payload():
    ids = [f"{i:064x}" for i in range(64)]
    report = {
        "schema": "AVRORA_MULTIFAMILY_SHADOW_SWEEP_V1",
        "count": 64,
        "candidate_ids": ids,
        "models": [{"candidate_id": cid, "train": {}, "validation": {}} for cid in ids],
        "real": "OFF", "holdout": "SEALED",
        "oos_proven": False, "fill_proven": False,
    }
    report["receipt_sha256"] = hashlib.sha256(canon(report)).hexdigest()
    return canon(report) + b"\n"


class PrivateDriveDeliveryContract(unittest.TestCase):
    def test_valid_frozen_64_report_uses_exact_byte_digest(self):
        raw = valid_payload()
        full, receipt = validate_report(raw)
        self.assertEqual(full, hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt, json.loads(raw)["receipt_sha256"])

    def test_modified_report_rejected_after_receipt(self):
        raw = valid_payload().replace(b'"count":64', b'"count":63')
        with self.assertRaises(ValueError):
            validate_report(raw)

    def test_swapped_model_order_rejected(self):
        obj = json.loads(valid_payload())
        obj["models"][0], obj["models"][1] = obj["models"][1], obj["models"][0]
        obj.pop("receipt_sha256")
        obj["receipt_sha256"] = hashlib.sha256(canon(obj)).hexdigest()
        with self.assertRaises(ValueError):
            validate_report(canon(obj))

    def test_partial_ledger_rejected(self):
        obj = json.loads(valid_payload())
        obj["models"].pop()
        obj.pop("receipt_sha256")
        obj["receipt_sha256"] = hashlib.sha256(canon(obj)).hexdigest()
        with self.assertRaises(ValueError):
            validate_report(canon(obj))

    def test_public_runner_fails_closed_without_private_readback(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("private_multifamily_drive_delivery.py", text)
        self.assertIn("Upload full private 64-candidate ledger", text)
        self.assertIn("sweep_private_drive_ack.json", text)
        self.assertIn("AVRORA_PRIVATE_DRIVE_ADC_JSON_B64", text)
        self.assertIn("Checkout PUBLIC executor helpers", text)
        self.assertNotIn("AVRORA_COLAB_ADC_JSON_B64", text)
        self.assertIn("Destroy all private code, raw panel, result ledger and logs", text)
        self.assertIn('REAL: "OFF"', text)
        self.assertIn('HOLDOUT: "SEALED"', text)
        self.assertNotIn("cron:", text)
        self.assertIn("path: sweep_public_summary.json", text)
        self.assertNotIn("path: sweep_private_full.json", text)


if __name__ == "__main__":
    unittest.main()
