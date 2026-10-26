"""Offline adversarial tests: recovery must never infer a delivered hour from a green job."""
import hashlib
import io
import json
import unittest
import zipfile

from tools.shadow_hour_recovery import RecoveryBlocked, read_archive, select_hour


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


if __name__ == "__main__":
    unittest.main()
