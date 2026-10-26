"""Offline adversarial tests: recovery must never infer a delivered hour from a green job."""
import hashlib
import io
import json
import unittest
import zipfile
from unittest.mock import patch

from tools.shadow_hour_recovery import RecoveryBlocked, read_archive, select_hour, verified_hours


def archive(name, obj):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, json.dumps(obj))
    return buf.getvalue()


class RecoveryUnitTests(unittest.TestCase):
    def test_missing_hour_is_recovered_before_new_work(self):
        self.assertEqual(select_hour(498052, {498048, 498050, 498051}, set(), lookback=4), 498049)

    def test_partial_delivery_is_quarantined_never_duplicated(self):
        self.assertEqual(select_hour(498052, {498048, 498051}, {498049}, lookback=4), 498050)

    def test_idles_when_entire_window_has_proof(self):
        self.assertIsNone(select_hour(498051, set(range(498048, 498052)), set(), lookback=3))

    def test_never_replays_an_hour_before_frozen_start(self):
        self.assertEqual(select_hour(497940, set(), set()), 497940)
        with self.assertRaises(RecoveryBlocked):
            select_hour(497939, set(), set())

    def test_verified_zip_and_hash(self):
        raw = archive("sweep_public_summary.json", {"research_hour_index": 498051})
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        self.assertEqual(read_archive(raw, "sweep_public_summary.json", digest)["research_hour_index"], 498051)
        with self.assertRaises(RecoveryBlocked):
            read_archive(raw + b"x", "sweep_public_summary.json", digest)

    def test_archive_rejects_extra_files_and_large_content(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("sweep_public_summary.json", "{}")
            z.writestr("private_prices.json", "{}")
        with self.assertRaises(RecoveryBlocked):
            read_archive(buf.getvalue(), "sweep_public_summary.json", None)
        with self.assertRaises(RecoveryBlocked):
            read_archive(archive("sweep_public_summary.json", {"pad": "X" * 16000}),
                         "sweep_public_summary.json", None)


    def test_actual_matching_aggregate_and_drive_ack_are_required(self):
        runid = "40265080154"
        sha = "c" * 64
        report = {
            "schema": "AVRORA_PUBLIC_SHADOW_MULTIFAMILY_BATCH_V1",
            "research_hour_index": 498051, "run_id": runid,
            "tested": 64, "real": "OFF", "holdout": "SEALED",
            "oos": False, "maker_fill_proven": False,
            "private_report_sha256": sha,
        }
        ack = {
            "schema": "AVRORA_PRIVATE_MULTIFAMILY_DRIVE_SHA_ACK_V1",
            "run_id": runid, "status": "PRIVATE_DRIVE_BYTE_READBACK_VERIFIED",
            "sha256": sha, "real": "OFF", "holdout": "SEALED",
        }
        def get(url, token, limit=100000):
            name = ("sweep_private_drive_ack.json" if "/artifacts/2/" in url
                    else "sweep_public_summary.json")
            return archive(name, ack if name.startswith("sweep_private") else report)
        entries = {runid: {"aggregate": [{"id": 1}], "ack": [{"id": 2}]}}
        with patch("tools.shadow_hour_recovery.fetch_bytes", side_effect=get):
            self.assertEqual(verified_hours(entries, "TOKEN", 498049, 498052),
                             ({498051}, set()))
            self.assertEqual(verified_hours(
                {runid: {"aggregate": [{"id": 1}]}}, "TOKEN", 498049, 498052),
                (set(), {498051}))
            ack["sha256"] = "f" * 64
            with self.assertRaises(RecoveryBlocked):
                verified_hours(entries, "TOKEN", 498049, 498052)

    def test_orphan_ack_is_never_trusted_as_a_delivered_hour(self):
        with self.assertRaises(RecoveryBlocked):
            verified_hours({"40265080154": {"ack": [{"id": 2}]}}, "TOKEN",
                           498049, 498052)


    def test_rerun_duplicate_artifact_names_preserve_only_sha_matched_receipt(self):
        runid = "40187814133"
        good_sha, unacknowledged_sha = "a" * 64, "b" * 64
        def report(hour, sha):
            return {
                "schema": "AVRORA_PUBLIC_SHADOW_MULTIFAMILY_BATCH_V1",
                "research_hour_index": hour, "run_id": runid,
                "tested": 64, "real": "OFF", "holdout": "SEALED",
                "oos": False, "maker_fill_proven": False,
                "private_report_sha256": sha,
            }
        receipt = {
            "schema": "AVRORA_PRIVATE_MULTIFAMILY_DRIVE_SHA_ACK_V1",
            "run_id": runid, "status": "PRIVATE_DRIVE_BYTE_READBACK_VERIFIED",
            "sha256": good_sha, "real": "OFF", "holdout": "SEALED",
        }
        blobs = {
            "11": archive("sweep_public_summary.json", report(498030, good_sha)),
            "12": archive("sweep_public_summary.json", report(498031, unacknowledged_sha)),
            "13": archive("sweep_private_drive_ack.json", receipt),
        }
        def fake_get(url, token, limit=100000):
            return blobs[url.split("/artifacts/")[1].split("/")[0]]
        entries = {runid: {"aggregate": [{"id": 11}, {"id": 12}],
                           "ack": [{"id": 13}]}}
        with patch("tools.shadow_hour_recovery.fetch_bytes", side_effect=fake_get):
            covered, partial = verified_hours(entries, "TOKEN", 498029, 498052)
        self.assertEqual(covered, {498030})
        self.assertEqual(partial, {498031})
        self.assertNotEqual(select_hour(498031, covered, partial, lookback=1), 498030)

if __name__ == "__main__":
    unittest.main()
