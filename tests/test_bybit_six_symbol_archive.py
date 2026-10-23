"""Six-symbol official Bybit archive transport: synthetic inputs ONLY."""
from datetime import date, datetime, timezone
import gzip
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from tools import bybit_official_archive_transport as t

DAY = date(2026, 10, 23)
NOW = datetime(2026, 10, 24, 8, 0, tzinfo=timezone.utc)


class Response:
    status = 200

    def __init__(self, data, url, headers=None):
        self.stream = io.BytesIO(data)
        self.url = url
        self.headers = {"Content-Length": str(len(data))} if headers is None else headers

    def geturl(self):
        return self.url

    def read(self, n):
        return self.stream.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def body(symbol):
    return gzip.compress(
        f"timestamp,symbol,side,size,price\n100,{symbol},Buy,1,123\n".encode(),
        mtime=0,
    )


def fake(symbol, redirect=None):
    def fetch(request, timeout):
        assert request.full_url == t.archive_url(DAY, symbol)
        assert timeout == 100
        return Response(body(symbol), redirect or request.full_url)
    return fetch


class SixSymbolArchiveTests(unittest.TestCase):
    def test_six_symbols_exact_and_distinct(self):
        self.assertEqual(t.SYMBOLS, (
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "LINKUSDT", "XRPUSDT"
        ))
        self.assertEqual(len(set(t.archive_url(DAY, s) for s in t.SYMBOLS)), 6)
        for s in t.SYMBOLS:
            self.assertEqual(
                t.archive_url(DAY, s),
                f"https://public.bybit.com/trading/{s}/{s}2026-10-23.csv.gz",
            )
        for bad in ("BTCUSD", "DOGEUSDT", "../BTCUSDT", "SOLUSDT/../../",
                    "BTCUSDT?x=1", ""):
            with self.assertRaisesRegex(ValueError, "BLOCKED_NONALLOWLIST"):
                t.archive_url(DAY, bad)

    def test_collect_and_independent_verify_for_every_symbol(self):
        with tempfile.TemporaryDirectory() as temp:
            for sym in t.SYMBOLS:
                root = Path(temp) / sym
                m = t.collect(DAY, root, fake(sym), NOW, sym)
                self.assertEqual(m["symbol"], sym)
                self.assertEqual(m["schema"], "AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2")
                self.assertEqual(m["source_text_lines"], 2)
                self.assertTrue((root / m["file_name"]).is_file())
                self.assertEqual(t.verify(root, sym), m["manifest_sha256"])
                self.assertEqual(m["archive_received_at_utc"], NOW.isoformat().replace("+00:00", "Z"))
                self.assertFalse(m["signal_realtime_available"])
                self.assertFalse(m["fill_proven"])
                self.assertFalse(m["new_oos_proven"])

    def test_no_incomplete_or_future_day(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "BLOCKED_DAY_NOT_COMPLETED"):
                t.collect(DAY, Path(temp) / "notyet", fake("BTCUSDT"),
                          datetime(2026, 10, 23, 23, 59, tzinfo=timezone.utc),
                          "BTCUSDT")
            with self.assertRaisesRegex(ValueError, "BLOCKED_PRE_FREEZE"):
                t.collect(date(2026, 10, 22), Path(temp) / "tooearly",
                          fake("BTCUSDT"), NOW, "BTCUSDT")

    def test_404_retries_without_false_manifest(self):
        def missing(req, timeout):
            raise HTTPError(req.full_url, 404, "Not yet published", {}, None)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "unavailable"
            self.assertIsNone(t.collect(DAY, root, missing, NOW, "NEARUSDT"))
            self.assertFalse((root / "manifest.json").exists())

    def test_reject_wrong_symbol_redirect_and_content_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "badredirect"
            with self.assertRaisesRegex(ValueError, "BLOCKED_UNTRUSTED_ARCHIVE_REDIRECT"):
                t.collect(DAY, root, fake("BTCUSDT",
                    t.archive_url(DAY, "ETHUSDT")), NOW, "BTCUSDT")
            root = Path(temp) / "good"
            t.collect(DAY, root, fake("BTCUSDT"), NOW, "BTCUSDT")
            archive = root / t.archive_filename(DAY, "BTCUSDT")
            archive.write_bytes(archive.read_bytes() + b"corrupt")
            with self.assertRaisesRegex(ValueError, "BLOCKED_ARCHIVE_BYTES_SHA_MISMATCH"):
                t.verify(root, "BTCUSDT")

    def test_reject_forged_manifest_or_mismatched_symbol(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            t.collect(DAY, root, fake("LINKUSDT"), NOW, "LINKUSDT")
            with self.assertRaisesRegex(ValueError, "BLOCKED_MANIFEST_SHA_MISMATCH"):
                t.verify(root, "SOLUSDT")
            mpath = root / "manifest.json"
            obj = json.loads(mpath.read_text())
            obj["fill_proven"] = True
            mpath.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError, "BLOCKED_MANIFEST_SHA_MISMATCH"):
                t.verify(root, "LINKUSDT")

    def test_symbol_specific_size_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            sym = "BTCUSDT"
            def over(req, timeout):
                return Response(body(sym), req.full_url,
                    {"Content-Length": str(t.LIMITS[sym][0] + 1)})
            with self.assertRaisesRegex(ValueError, "BLOCKED_ARCHIVE_SOURCE_TOO_BIG"):
                t.collect(DAY, Path(temp) / "size", over, NOW, sym)


if __name__ == "__main__":
    unittest.main()
