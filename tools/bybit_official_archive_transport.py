"""Delayed official Bybit perpetual-trades transport for AVRORA's six symbols.

One immutable UTC day and ONE allowlisted linear USDT symbol per invocation.
Read-only HTTPS from public.bybit.com; no exchange keys, proxies, live orders,
hidden holdout access, signal timing or maker-fill claims.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import zlib

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "LINKUSDT", "XRPUSDT")
SYMBOL = "SOLUSDT"  # Backward-compatible legacy offline tests.
BASE = "https://public.bybit.com/trading/SOLUSDT/"
FIRST_DAY = date(2026, 10, 23)
MAX_GZ = 150_000_000  # Legacy SOL cap.
MAX_RAW = 800_000_000  # Legacy SOL uncompressed cap.
# Hard resource ceilings per symbol; oversize is an explicit BLOCKED status.
# Never truncate an archive, or silently claim all six symbols were collected.
LIMITS = {
    "BTCUSDT": (600_000_000, 3_000_000_000),
    "ETHUSDT": (450_000_000, 2_500_000_000),
    "SOLUSDT": (MAX_GZ, MAX_RAW),
    "NEARUSDT": (150_000_000, 800_000_000),
    "LINKUSDT": (150_000_000, 800_000_000),
    "XRPUSDT": (250_000_000, 1_500_000_000),
}
CHUNK = 1024 * 1024


def require_symbol(symbol):
    if symbol not in SYMBOLS:
        raise ValueError("BLOCKED_NONALLOWLIST_BYBIT_SYMBOL")
    return symbol


def archive_filename(day, symbol=SYMBOL):
    symbol = require_symbol(symbol)
    if day < FIRST_DAY:
        raise ValueError("BLOCKED_PRE_FREEZE_SOURCE_DATE")
    return f"{symbol}{day.isoformat()}.csv.gz"


def archive_url(day, symbol=SYMBOL):
    symbol = require_symbol(symbol)
    return f"https://public.bybit.com/trading/{symbol}/" + archive_filename(day, symbol)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def validate_gzip(path, symbol=SYMBOL):
    symbol = require_symbol(symbol)
    compressed = Path(path)
    limit_gz, limit_raw = LIMITS[symbol]
    if compressed.stat().st_size < 20 or compressed.stat().st_size > limit_gz:
        raise ValueError("BLOCKED_GZIP_SIZE")
    n = 0
    count_lines = 0
    with gzip.open(compressed, "rb") as source:
        try:
            while True:
                block = source.read(CHUNK)
                if not block:
                    break
                n += len(block)
                count_lines += block.count(b"\n")
                if n > limit_raw:
                    raise ValueError("BLOCKED_RAW_BYTES_CAP")
        except (EOFError, OSError, zlib.error) as exc:
            raise ValueError("BLOCKED_GZIP_CRC_OR_STRUCTURE") from exc
    if n < 10 or count_lines < 2:
        raise ValueError("BLOCKED_EMPTY_ARCHIVE")
    return n, count_lines


def collect(day, output_dir, fetcher=None, now=None, symbol=SYMBOL):
    """Download exactly one completed, explicitly allowlisted day/symbol.

    A provider 404 returns None (WAIT) and must NOT be cached/uploaded as
    success. All other invalid responses are BLOCKED.
    """
    symbol = require_symbol(symbol)
    expected = archive_filename(day, symbol)
    seen = datetime.now(timezone.utc) if now is None else now
    if seen.tzinfo is None:
        raise ValueError("BLOCKED_NAIVE_OBSERVATION_TIME")
    if day >= seen.astimezone(timezone.utc).date():
        raise ValueError("BLOCKED_DAY_NOT_COMPLETED")
    folder = Path(output_dir)
    if folder.exists():
        raise ValueError("BLOCKED_OUTPUT_ALREADY_EXISTS")
    url = archive_url(day, symbol)
    folder.mkdir(parents=True)
    path = folder / expected
    req = urllib.request.Request(url, headers={
        "User-Agent": "AVRORA-official-delayed-six-trades/2.0"})
    if fetcher is None:
        fetcher = urllib.request.urlopen
    try:
        with fetcher(req, timeout=100) as response:
            final = urllib.parse.urlparse(response.geturl())
            if (final.scheme != "https" or final.hostname != "public.bybit.com"
                    or final.port is not None or final.username is not None
                    or final.password is not None or final.query or final.fragment
                    or final.path != f"/trading/{symbol}/{expected}"):
                raise ValueError("BLOCKED_UNTRUSTED_ARCHIVE_REDIRECT")
            if response.status != 200:
                raise ValueError("BLOCKED_ARCHIVE_HTTP_STATUS")
            limit_gz = LIMITS[symbol][0]
            head = response.headers.get("Content-Length")
            if head and int(head) > limit_gz:
                raise ValueError("BLOCKED_ARCHIVE_SOURCE_TOO_BIG")
            digest = hashlib.sha256()
            size = 0
            with path.open("xb") as fd:
                while True:
                    buf = response.read(CHUNK)
                    if not buf:
                        break
                    size += len(buf)
                    if size > limit_gz:
                        raise ValueError("BLOCKED_ARCHIVE_SOURCE_TOO_BIG")
                    digest.update(buf)
                    fd.write(buf)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # Publication may lag by hours. A partial date is NOT done.
            return None
        raise ValueError("BLOCKED_ARCHIVE_PROVIDER_HTTP") from None
    size_raw, lines = validate_gzip(path, symbol)
    received = datetime.now(timezone.utc) if now is None else now
    manifest = {
        "schema": "AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2",
        "kind": "DELAYED_PUBLIC_HISTORICAL_TRADES",
        "source": "public.bybit.com/trading",
        "url": url,
        "symbol": symbol,
        "day_utc": day.isoformat(),
        "file_name": expected,
        "source_gz_sha256": digest.hexdigest(),
        "source_compressed_bytes": size,
        "source_uncompressed_bytes": size_raw,
        "source_text_lines": lines,
        "archive_received_at_utc": received.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "causally_usable_not_before_utc": received.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "signal_realtime_available": False,
        "fill_proven": False,
        "trade_return_proven": False,
        "new_oos_proven": False,
        "real": "OFF",
        "holdout": "SEALED",
        "note": "Archived completed-day trades; no historical live availability, maker queue or fill evidence.",
    }
    manifest["manifest_sha256"] = hashlib.sha256(canonical(manifest)).hexdigest()
    (folder / "manifest.json").write_bytes(canonical(manifest) + b"\n")
    return manifest


def verify(folder, symbol=SYMBOL):
    """Independent file+manifest readback before GitHub artifact publication."""
    symbol = require_symbol(symbol)
    root = Path(folder)
    m = json.loads((root / "manifest.json").read_bytes())
    sha = m.pop("manifest_sha256")
    if hashlib.sha256(canonical(m)).hexdigest() != sha:
        raise ValueError("BLOCKED_MANIFEST_SHA_MISMATCH")
    if (m.get("schema") != "AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2"
            or m.get("symbol") != symbol or m.get("real") != "OFF"
            or m.get("holdout") != "SEALED"
            or m.get("signal_realtime_available") is not False
            or m.get("new_oos_proven") is not False
            or m.get("fill_proven") is not False):
        raise ValueError("BLOCKED_ARCHIVE_MANIFEST_SCOPE")
    day = date.fromisoformat(m["day_utc"])
    expected = archive_filename(day, symbol)
    if m.get("file_name") != expected or m.get("url") != archive_url(day, symbol):
        raise ValueError("BLOCKED_ARCHIVE_MANIFEST_SOURCE")
    path = root / expected
    size = 0
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while buf := source.read(CHUNK):
            digest.update(buf)
            size += len(buf)
    if digest.hexdigest() != m["source_gz_sha256"] or size != m["source_compressed_bytes"]:
        raise ValueError("BLOCKED_ARCHIVE_BYTES_SHA_MISMATCH")
    size_raw, lines = validate_gzip(path, symbol)
    if size_raw != m["source_uncompressed_bytes"] or lines != m["source_text_lines"]:
        raise ValueError("BLOCKED_ARCHIVE_DECOMPRESSED_SCOPE")
    return sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--day", default=None, help="UTC archive day YYYY-MM-DD")
    ap.add_argument("--symbol", choices=SYMBOLS, default=SYMBOL)
    args = ap.parse_args()
    today = datetime.now(timezone.utc).date()
    day = date.fromisoformat(args.day) if args.day else today - timedelta(days=1)
    if day >= today:
        raise ValueError("BLOCKED_DAY_NOT_COMPLETED")
    if day < FIRST_DAY:
        print("WAIT_FIRST_NEW_SOURCE_DAY_2026_10_23")
        return 3
    manifest = collect(day, args.output_dir, symbol=args.symbol)
    if manifest is None:
        print("WAIT_OFFICIAL_ARCHIVE_NOT_YET_PUBLISHED", args.symbol, day)
        return 3
    check = verify(args.output_dir, args.symbol)
    print("PASS_OFFICIAL_ARCHIVE_SHA_AND_GZIP_CRC", args.symbol, day,
          manifest["source_gz_sha256"], check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
