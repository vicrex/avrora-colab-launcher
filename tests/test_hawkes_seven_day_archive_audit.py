"""Synthetic 42-file Bybit archive coverage/lineage tests (NO live data)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import hawkes_seven_day_archive_audit as a
from tools import bybit_official_archive_transport as t

ASOF = date(2026, 10, 31)
DAYS = a.required_days(ASOF)
DAY_SAMPLE = b"timestamp,symbol,side,size,price\n123,BTCUSDT,Buy,1,123\n"


def materialize(root, missing=None, late=None):
    for day in DAYS:
        for symbol in a.SYMBOLS:
            if (day,symbol)==missing:
                continue
            p=Path(root)/symbol/day.isoformat()
            p.mkdir(parents=True)
            compressed=gzip.compress(
                DAY_SAMPLE.replace(b"BTCUSDT",symbol.encode()),mtime=0)
            filename=t.archive_filename(day,symbol)
            (p/filename).write_bytes(compressed)
            at=datetime.combine(day+timedelta(days=1),
                                datetime.min.time(),tzinfo=timezone.utc)
            if (day,symbol)==late:
                at+=timedelta(days=2)
            when=at.isoformat().replace("+00:00","Z")
            m={
                "schema":"AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2",
                "kind":"DELAYED_PUBLIC_HISTORICAL_TRADES",
                "source":"public.bybit.com/trading",
                "url":t.archive_url(day,symbol),
                "symbol":symbol,"day_utc":day.isoformat(),
                "file_name":filename,
                "source_gz_sha256":hashlib.sha256(compressed).hexdigest(),
                "source_compressed_bytes":len(compressed),
                "source_uncompressed_bytes":len(
                    DAY_SAMPLE.replace(b"BTCUSDT",symbol.encode())),
                "source_text_lines":2,
                "archive_received_at_utc":when,
                "causally_usable_not_before_utc":when,
                "signal_realtime_available":False,
                "fill_proven":False,
                "trade_return_proven":False,
                "new_oos_proven":False,
                "real":"OFF","holdout":"SEALED",
                "note":"Synthetic historical archive for local tests only",
            }
            m["manifest_sha256"]=a.sha(a.canonical(m))
            (p/"manifest.json").write_bytes(a.canonical(m)+b"\n")


def resign(path, edit):
    m=json.loads(path.read_bytes())
    edit(m)
    m["manifest_sha256"]=a.sha(a.canonical({
        k:v for k,v in m.items() if k!="manifest_sha256"}))
    path.write_bytes(a.canonical(m)+b"\n")


class SevenDayArchiveTests(unittest.TestCase):
    def test_complete_42_bytes_is_still_not_hawkes_model_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp)
            report=a.audit(tmp,ASOF)
            self.assertEqual(report["status"],"PASS_ARCHIVED_42_FILES_NOT_REALTIME")
            self.assertEqual(report["gz_byte_sha_and_crc_verified"],42)
            self.assertEqual(report["manifest_files_present"],42)
            self.assertEqual(report["missing_symbol_days"],[])
            self.assertTrue(report["archive_complete_by_our_42_byte_checks"])
            self.assertFalse(report["provider_trade_count_completeness_proven"])
            self.assertFalse(report["per_event_historical_first_seen_proven"])
            self.assertFalse(report["hawkes_model_fit_ready"])
            self.assertFalse(report["independent_check2"])
            self.assertFalse(report["oos_proven"])
            self.assertFalse(report["maker_fill_proven"])
            self.assertFalse(report["live_trading_authorized"])
            self.assertEqual((report["real"],report["holdout"]),("OFF","SEALED"))
            self.assertEqual(report["receipt_sha256"],a.sha(a.canonical({
                k:v for k,v in report.items() if k!="receipt_sha256"})))
            self.assertEqual(report,a.audit(tmp,ASOF))

    def test_missing_one_symbol_day_blocks_without_padding(self):
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp,missing=(DAYS[-1],"XRPUSDT"))
            r=a.audit(tmp,ASOF)
            self.assertEqual(r["status"],"BLOCKED_HAWKES_42_ARCHIVES_MISSING")
            self.assertEqual(r["gz_byte_sha_and_crc_verified"],41)
            self.assertEqual(r["missing_symbol_days"],[{
                "day":DAYS[-1].isoformat(),"symbol":"XRPUSDT"}])
            self.assertFalse(r["archive_complete_by_our_42_byte_checks"])

    def test_42_archives_after_decision_do_not_prove_asof_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp,late=(DAYS[-1],"NEARUSDT"))
            r=a.audit(tmp,ASOF)
            self.assertEqual(r["gz_byte_sha_and_crc_verified"],42)
            self.assertEqual(r["not_available_asof_count"],1)
            self.assertFalse(r["per_event_historical_first_seen_proven"])
            self.assertFalse(r["hawkes_model_fit_ready"])

    def test_bad_archive_sha_byte_readback_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp)
            p=Path(tmp)/"BTCUSDT"/DAYS[0].isoformat()/t.archive_filename(
                DAYS[0],"BTCUSDT")
            p.write_bytes(p.read_bytes()+b"tamper")
            with self.assertRaisesRegex(ValueError,"BYTES_OR_CRC"):
                a.audit(tmp,ASOF)

    def test_false_realtime_flag_even_with_resigned_manifest_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp)
            p=Path(tmp)/"BTCUSDT"/DAYS[0].isoformat()/"manifest.json"
            resign(p,lambda m:m.__setitem__("signal_realtime_available",True))
            with self.assertRaisesRegex(ValueError,"MANIFEST_SCOPE"):
                a.audit(tmp,ASOF)

    def test_unsigned_manifest_change_fails_before_gzip(self):
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp)
            p=Path(tmp)/"SOLUSDT"/DAYS[1].isoformat()/"manifest.json"
            obj=json.loads(p.read_bytes())
            obj["source_text_lines"]+=1
            p.write_bytes(a.canonical(obj))
            with self.assertRaisesRegex(ValueError,"MANIFEST_TAMPER"):
                a.audit(tmp,ASOF)

    def test_prepublication_time_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp)
            p=Path(tmp)/"BTCUSDT"/DAYS[0].isoformat()/"manifest.json"
            resign(p,lambda m:m.__setitem__(
                "archive_received_at_utc",
                DAYS[0].isoformat()+"T12:00:00Z"))
            with self.assertRaisesRegex(ValueError,"ARCHIVAL_CLOCK"):
                a.audit(tmp,ASOF)

    def test_frozen_window_and_no_imputed_days(self):
        self.assertEqual(len(DAYS),7)
        self.assertEqual(DAYS[0].isoformat(),"2026-10-24")
        self.assertEqual(DAYS[-1].isoformat(),"2026-10-30")
        with self.assertRaisesRegex(ValueError,"BEFORE_CAPTURE_FREEZE"):
            a.required_days(date(2026,10,29))
        with self.assertRaisesRegex(ValueError,"ASOF_DATE"):
            a.required_days("2026-10-31")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"FOLDER_NOT_FOUND"):
                a.audit(Path(tmp)/"does-not-exist",ASOF)

    def test_bad_utc_and_counts_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp)
            p=Path(tmp)/"LINKUSDT"/DAYS[0].isoformat()/"manifest.json"
            resign(p,lambda m:m.__setitem__(
                "archive_received_at_utc", "2026-10-26T23:00:00+03:00"))
            with self.assertRaisesRegex(ValueError,"UTC_TIMESTAMP"):
                a.audit(tmp,ASOF)
        with tempfile.TemporaryDirectory() as tmp:
            materialize(tmp)
            p=Path(tmp)/"LINKUSDT"/DAYS[0].isoformat()/"manifest.json"
            resign(p,lambda m:m.__setitem__("source_text_lines",True))
            with self.assertRaisesRegex(ValueError,"FILE_COUNTS"):
                a.audit(tmp,ASOF)


if __name__=="__main__":
    unittest.main()
