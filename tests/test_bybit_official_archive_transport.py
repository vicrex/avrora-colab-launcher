"""Offline-only archive transport tests; never calls Bybit."""
from __future__ import annotations
from datetime import date,datetime,timezone
import gzip
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from tools import bybit_official_archive_transport as t

class MockResponse:
    status=200
    def __init__(self,data,url,head=None):
        self.stream=io.BytesIO(data)
        self.url=url
        self.headers={"Content-Length":str(len(data))} if head is None else head
    def geturl(self):return self.url
    def read(self,n):return self.stream.read(n)
    def __enter__(self):return self
    def __exit__(self,*args):return False

class ArchiveTests(unittest.TestCase):
    DAY=date(2026,10,23)
    NOW=datetime(2026,10,24,8,12,tzinfo=timezone.utc)
    def source(self):
        return gzip.compress(b"timestamp,symbol,price,size\n123,SOLUSDT,100,1\n",mtime=0)
    def fetcher(self,data=None,url=None,head=None):
        raw=data if data is not None else self.source()
        link=url if url is not None else t.archive_url(self.DAY)
        return lambda req,timeout:MockResponse(raw,link,head=head)

    def test_allowlist_and_freeze(self):
        self.assertEqual(t.archive_filename(self.DAY),"SOLUSDT2026-10-23.csv.gz")
        with self.assertRaisesRegex(ValueError,"BLOCKED_PRE_FREEZE"):
            t.archive_url(date(2026,10,22))

    def test_download_digest_and_gzip_crc(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"new"
            m=t.collect(self.DAY,out,fetcher=self.fetcher(),now=self.NOW)
            self.assertEqual(m["day_utc"],"2026-10-23")
            self.assertEqual(m["source_compressed_bytes"],len(self.source()))
            self.assertEqual(m["source_text_lines"],2)
            self.assertFalse(m["signal_realtime_available"])
            self.assertFalse(m["new_oos_proven"])
            self.assertEqual(m["real"],"OFF")
            self.assertEqual(m["holdout"],"SEALED")
            self.assertEqual(json.loads((out/"manifest.json").read_text())["source_gz_sha256"],m["source_gz_sha256"])

    def test_untrusted_redirect_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"BLOCKED_UNTRUSTED_ARCHIVE_REDIRECT"):
                t.collect(self.DAY,Path(d)/"bad",
                   fetcher=self.fetcher(url="https://example.org/trading/SOLUSDT/steal.gz"),now=self.NOW)

    def test_truncated_gzip_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            truncated=self.source()[:-7]
            with self.assertRaisesRegex(ValueError,"BLOCKED_GZIP_CRC_OR_STRUCTURE"):
                t.collect(self.DAY,Path(d)/"broken",
                   fetcher=self.fetcher(data=truncated),now=self.NOW)

    def test_provider_404_is_wait_not_success(self):
        def missing(request,timeout):
            raise HTTPError(t.archive_url(self.DAY),404,"not yet published",{},None)
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(t.collect(self.DAY,Path(d)/"new",
                 fetcher=missing,now=self.NOW))
            self.assertFalse((Path(d)/"new"/"manifest.json").exists())

    def test_oversize_and_repeated_output_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"BLOCKED_ARCHIVE_SOURCE_TOO_BIG"):
                t.collect(self.DAY,Path(d)/"new",fetcher=self.fetcher(
                    head={"Content-Length":str(t.MAX_GZ+1)}),now=self.NOW)
            with self.assertRaisesRegex(ValueError,"BLOCKED_OUTPUT_ALREADY_EXISTS"):
                t.collect(self.DAY,Path(d)/"new",fetcher=self.fetcher(),now=self.NOW)

if __name__=="__main__":
    unittest.main()
