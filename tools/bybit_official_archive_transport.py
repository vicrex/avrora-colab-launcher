"""Public transport of *delayed historical* SOLUSDT Bybit trades, NOT trading research.

Uses only Bybit's official public.bybit.com daily gzip URL. No proxy,
exchange keys, order requests, strategy calculations or simulated maker fills.
Causally available_at is archive HTTP completion time, never trade timestamp.
"""
from __future__ import annotations
import argparse
from datetime import datetime,date,timedelta,timezone
import gzip
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

SYMBOL="SOLUSDT"
BASE="https://public.bybit.com/trading/SOLUSDT/"
FIRST_DAY=date(2026,10,23)
MAX_GZ=150_000_000
MAX_RAW=800_000_000
CHUNK=1024*1024

def archive_filename(day):
    if day<FIRST_DAY:raise ValueError("BLOCKED_PRE_FREEZE_SOURCE_DATE")
    return f"{SYMBOL}{day.isoformat()}.csv.gz"

def archive_url(day):
    return BASE+archive_filename(day)

def validate_gzip(path):
    compressed=Path(path)
    if compressed.stat().st_size<20 or compressed.stat().st_size>MAX_GZ:
        raise ValueError("BLOCKED_GZIP_SIZE")
    n=0
    count_lines=0
    with gzip.open(compressed,"rb") as source:
        try:
            while True:
                block=source.read(CHUNK)
                if not block:break
                n+=len(block)
                count_lines+=block.count(b"\n")
                if n>MAX_RAW:raise ValueError("BLOCKED_RAW_BYTES_CAP")
        except (EOFError,OSError) as e:
            raise ValueError("BLOCKED_GZIP_CRC_OR_STRUCTURE") from e
    if n<10 or count_lines<2:
        raise ValueError("BLOCKED_EMPTY_ARCHIVE")
    return n,count_lines

def collect(day,output_dir,fetcher=None,now=None):
    """Exit status WAIT not error when Bybit has not published yesterday's archive."""
    expected=archive_filename(day)
    folder=Path(output_dir)
    if folder.exists():
        raise ValueError("BLOCKED_OUTPUT_ALREADY_EXISTS")
    url=archive_url(day)
    folder.mkdir(parents=True)
    path=folder/expected
    seen=datetime.now(timezone.utc) if now is None else now
    try:
        req=urllib.request.Request(url,headers={
            "User-Agent":"AVRORA-public-readonly-archive-v1/1.0"})
        if fetcher is None:fetcher=urllib.request.urlopen
        with fetcher(req,timeout=100) as response:
            final=response.geturl()
            info=urllib.parse.urlparse(final)
            if (info.scheme!="https" or info.hostname!="public.bybit.com"
                or info.path!="/trading/SOLUSDT/"+expected):
                raise ValueError("BLOCKED_UNTRUSTED_ARCHIVE_REDIRECT")
            if response.status!=200:
                raise ValueError("BLOCKED_ARCHIVE_HTTP_STATUS")
            head=response.headers.get("Content-Length")
            if head and int(head)>MAX_GZ:
                raise ValueError("BLOCKED_ARCHIVE_SOURCE_TOO_BIG")
            digest=hashlib.sha256()
            size=0
            with path.open("xb") as fd:
                while True:
                    buf=response.read(CHUNK)
                    if not buf:break
                    size+=len(buf)
                    if size>MAX_GZ:
                        raise ValueError("BLOCKED_ARCHIVE_SOURCE_TOO_BIG")
                    digest.update(buf)
                    fd.write(buf)
    except urllib.error.HTTPError as e:
        if e.code==404:
            # Publication delayed; do not create a false data artifact.
            return None
        raise ValueError("BLOCKED_ARCHIVE_PROVIDER_HTTP") from None
    received=datetime.now(timezone.utc) if now is None else now
    size_raw,rows=validate_gzip(path)
    manifest={
        "schema":"AVRORA_BYBIT_STATIC_SOL_ARCHIVE_TRANSPORT_V1",
        "kind":"DELAYED_PUBLIC_HISTORICAL_TRADES",
        "url":url,"day_utc":day.isoformat(),"symbol":SYMBOL,
        "source_gz_sha256":digest.hexdigest(),
        "source_compressed_bytes":size,"source_uncompressed_bytes":size_raw,
        "source_text_lines":rows,"file_name":expected,
        "archive_received_at_utc":received.isoformat().replace("+00:00","Z"),
        "signal_realtime_available":False,"fill_proven":False,
        "trade_return_proven":False,"new_oos_proven":False,
        "real":"OFF","holdout":"SEALED",
        "note":"Archived tick CSV arrives after the trade day. Cannot support exact next-open execution claims."
    }
    (folder/"manifest.json").write_text(
       json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
       encoding="utf-8")
    return manifest

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-dir",required=True)
    ap.add_argument("--day",default=None,help="UTC archive day, YYYY-MM-DD")
    a=ap.parse_args()
    today=datetime.now(timezone.utc).date()
    day=date.fromisoformat(a.day) if a.day else today-timedelta(days=1)
    if day>=today:raise ValueError("BLOCKED_DAY_NOT_COMPLETED")
    if day<FIRST_DAY:
        print("WAIT_FIRST_NEW_SOURCE_DAY_2026_10_23")
        return 3
    record=collect(day,a.output_dir)
    if record is None:
        print("WAIT_OFFICIAL_ARCHIVE_NOT_YET_PUBLISHED")
        return 3
    print("PASS_OFFICIAL_ARCHIVE_SHA_AND_GZIP_CRC",
          record["day_utc"],record["source_gz_sha256"])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
