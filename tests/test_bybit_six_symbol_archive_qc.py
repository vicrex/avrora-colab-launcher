"""Six-source offline transport audit: synthetic public trades only, no keys/network."""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import bybit_six_symbol_archive_qc as q


DAY = "2026-10-24"
START = int(dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc).timestamp())


def public_zip(sym: str, *, skip_bar: int | None = None,
               reverse: bool = False, unsafe: bool = False) -> bytes:
    rows = [
        ["timestamp", "symbol", "side", "size", "price", "tickDirection",
         "trdMatchID", "grossValue", "homeNotional", "foreignNotional", "RPI"]
    ]
    for i in range(96):
        if i == skip_bar:
            continue
        rows.append([str(START + i * 900 + 1), sym,
                     "Buy", "1", "20.0", "PlusTick", f"{sym}-{i}",
                     "2000000000", "1", "20", "0"])
    if reverse:
        rows[1], rows[2] = rows[2], rows[1]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    payload = buf.getvalue().encode()
    gz = gzip.compress(payload, mtime=0)
    manifest = {
        "schema": "AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2",
        "symbol": sym, "day_utc": DAY, "real": "OFF",
        "holdout": "SEALED",
        "kind": "DELAYED_PUBLIC_HISTORICAL_TRADES",
        "new_oos_proven": unsafe,
        "fill_proven": False, "signal_realtime_available": False,
        "source_compressed_bytes": len(gz), "source_gz_sha256": q.sha(gz),
        "source_text_lines": len(rows),
        "causally_usable_not_before_utc": "2026-10-25T08:00:00Z",
    }
    manifest["manifest_sha256"] = q.sha(q.canon(manifest))
    result = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(result, "w") as z:
        z.writestr(sym + DAY + ".csv.gz", gz)
        z.writestr("manifest.json", q.canon(manifest))
    return result.getvalue()


class SixSymbolArchiveQCTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.digests = {}
        for sym in q.SYMBOLS:
            zipped = public_zip(sym)
            (self.path / f"BYBIT_TRADES_{sym}_{DAY}_12345.zip").write_bytes(zipped)
            self.digests[sym] = "sha256:" + q.sha(zipped)

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_six_symbol_day_and_sha(self):
        report = q.validate_six(self.path, day=DAY, github_digests=self.digests)
        self.assertEqual(report["total_m15_bars"], 576)
        self.assertEqual(report["total_trades"], 576)
        self.assertEqual(report["status"], "PASS_PUBLIC_HISTORICAL_TRANSPORT_ONLY")
        self.assertFalse(report["realtime_oos_proven"])
        self.assertFalse(report["independent_economic_check2"])
        digest = report.pop("report_sha256")
        self.assertEqual(digest, q.sha(q.canon(report)))

    def test_unknown_or_missing_source_is_blocked(self):
        self.digests.pop("XRPUSDT")
        with self.assertRaisesRegex(ValueError, "EXACT_SIX"):
            q.validate_six(self.path, day=DAY, github_digests=self.digests)

    def test_zip_sha_tamper_is_blocked(self):
        self.digests["BTCUSDT"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "ZIP_SHA"):
            q.validate_six(self.path, day=DAY, github_digests=self.digests)

    def test_empty_m15_bucket_is_blocked(self):
        sym = "BTCUSDT"
        zip_bytes = public_zip(sym, skip_bar=42)
        f = self.path / f"BYBIT_TRADES_{sym}_{DAY}_12345.zip"
        f.write_bytes(zip_bytes)
        self.digests[sym] = q.sha(zip_bytes)
        with self.assertRaisesRegex(ValueError, "MISSING_M15_BAR"):
            q.validate_six(self.path, day=DAY, github_digests=self.digests)

    def test_out_of_order_is_blocked(self):
        sym = "BTCUSDT"
        zip_bytes = public_zip(sym, reverse=True)
        (self.path / f"BYBIT_TRADES_{sym}_{DAY}_12345.zip").write_bytes(zip_bytes)
        self.digests[sym] = q.sha(zip_bytes)
        with self.assertRaisesRegex(ValueError, "UNSORTED_TRADES"):
            q.validate_six(self.path, day=DAY, github_digests=self.digests)

    def test_unproved_realtime_never_upgraded_to_oos(self):
        sym = "BTCUSDT"
        zip_bytes = public_zip(sym, unsafe=True)
        (self.path / f"BYBIT_TRADES_{sym}_{DAY}_12345.zip").write_bytes(zip_bytes)
        self.digests[sym] = q.sha(zip_bytes)
        with self.assertRaisesRegex(ValueError, "NO_REALTIME_OR_FILL_CLAIM"):
            q.validate_six(self.path, day=DAY, github_digests=self.digests)

    def test_duplicate_symbol_day_is_blocked(self):
        original = next(self.path.glob(f"BYBIT_TRADES_BTCUSDT_{DAY}_*.zip"))
        (self.path / f"BYBIT_TRADES_BTCUSDT_{DAY}_98765.zip").write_bytes(
            original.read_bytes())
        with self.assertRaisesRegex(ValueError, "EXACTLY_ONE_ZIP"):
            q.validate_six(self.path, day=DAY, github_digests=self.digests)


if __name__ == "__main__":
    unittest.main()
