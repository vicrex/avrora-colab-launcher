"""Offline, transport-only QC for six completed UTC days of public Bybit trades.

Accept only 6 exact public GitHub ZIP digests, verify both ZIP and original .gz
SHA256 and CRC, reconstruct M15 coverage without publishing raw market data.
Never assert realtime first-seen, OOS, maker queues, L2, funding or trades.
No API credentials, network access, strategy execution or scheduling.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "LINKUSDT", "XRPUSDT")
OUTPUT_SCHEMA = "AVRORA_OFFICIAL_ARCHIVE_SIX_SYMBOL_M15_QC_V1"
SOURCE_SCHEMA = "AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2"


def canon(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def assert_gate(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("BLOCKED_" + code)


def verify_one(path: Path, *, symbol: str, day: str, expected_zip_sha: str) -> dict:
    assert_gate(symbol in SYMBOLS, "SYMBOL")
    assert_gate(len(expected_zip_sha) == 64 and
                all(c in "0123456789abcdef" for c in expected_zip_sha),
                "EXPECTED_ZIP_SHA")
    data = path.read_bytes()
    assert_gate(sha(data) == expected_zip_sha, "ZIP_SHA")
    day_start = dt.datetime.strptime(day, "%Y-%m-%d").replace(
        tzinfo=dt.timezone.utc).timestamp()
    day_end = day_start + 86400
    gz_name = f"{symbol}{day}.csv.gz"
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        assert_gate(set(bundle.namelist()) == {gz_name, "manifest.json"}, "ZIP_MEMBERS")
        manifest = json.loads(bundle.read("manifest.json"))
        assert_gate(type(manifest) is dict, "MANIFEST_TYPE")
        claimed_manifest_sha = manifest.get("manifest_sha256")
        core = dict(manifest)
        core.pop("manifest_sha256", None)
        assert_gate(claimed_manifest_sha == sha(canon(core)), "MANIFEST_SHA")
        assert_gate(manifest.get("schema") == SOURCE_SCHEMA
                    and manifest.get("symbol") == symbol
                    and manifest.get("day_utc") == day, "MANIFEST_SCOPE")
        assert_gate(manifest.get("real") == "OFF"
                    and manifest.get("holdout") == "SEALED"
                    and manifest.get("new_oos_proven") is False
                    and manifest.get("fill_proven") is False
                    and manifest.get("signal_realtime_available") is False,
                    "NO_REALTIME_OR_FILL_CLAIM")
        assert_gate(manifest.get("kind") == "DELAYED_PUBLIC_HISTORICAL_TRADES",
                    "SOURCE_KIND")
        gz_bytes = bundle.read(gz_name)
        assert_gate(len(gz_bytes) == manifest.get("source_compressed_bytes")
                    and sha(gz_bytes) == manifest.get("source_gz_sha256"),
                    "ORIGINAL_GZIP_SHA")
        with gzip.GzipFile(fileobj=io.BytesIO(gz_bytes)) as inflated:
            with io.TextIOWrapper(inflated, encoding="utf-8", newline="") as text:
                reader = csv.DictReader(text)
                assert_gate({"timestamp", "symbol", "side", "size", "price",
                             "trdMatchID"}.issubset(reader.fieldnames or []),
                            "TRADE_SCHEMA")
                buckets = [0] * 96
                rows = 0
                prev = -1.0
                first = None
                last = None
                for trade in reader:
                    t = float(trade["timestamp"])
                    price = float(trade["price"])
                    quantity = float(trade["size"])
                    assert_gate(math.isfinite(t) and math.isfinite(price) and
                                math.isfinite(quantity) and
                                day_start <= t < day_end and price > 0 and quantity > 0,
                                "INVALID_TRADE")
                    assert_gate(trade["symbol"] == symbol and
                                trade["side"] in ("Buy", "Sell") and
                                bool(trade["trdMatchID"]), "TRADE_FIELDS")
                    assert_gate(t >= prev, "UNSORTED_TRADES")
                    prev = t
                    b = int((t - day_start) // 900)
                    assert_gate(0 <= b < 96, "M15_BUCKET")
                    buckets[b] += 1
                    rows += 1
                    if first is None:
                        first = t
                    last = t
                # gzip CRC is checked when its stream reaches EOF.
    assert_gate(rows > 0 and manifest.get("source_text_lines") == rows + 1,
                "ROW_COUNT")
    assert_gate(all(buckets), "MISSING_M15_BAR")
    return {
        "symbol": symbol, "trade_rows": rows, "m15_bars": 96,
        "min_m15_trades": min(buckets), "max_m15_trades": max(buckets),
        "first_trade_epoch_s": first, "last_trade_epoch_s": last,
        "zip_sha256": expected_zip_sha,
        "original_gzip_sha256": manifest["source_gz_sha256"],
        "manifest_sha256": claimed_manifest_sha,
        "archive_first_available_utc": manifest["causally_usable_not_before_utc"],
        "zip_gzip_crc_verified": True,
        "realtime_available_proven": False, "oos_proven": False,
        "maker_fill_proven": False,
    }


def validate_six(folder: Path, *, day: str, github_digests: dict) -> dict:
    dt.datetime.strptime(day, "%Y-%m-%d")
    assert_gate(type(github_digests) is dict and
                set(github_digests) == set(SYMBOLS), "EXACT_SIX_EXPECTED_ZIP_DIGESTS")
    findings = []
    for symbol in SYMBOLS:
        paths = list(folder.glob(f"BYBIT_TRADES_{symbol}_{day}_*.zip"))
        assert_gate(len(paths) == 1, "EXACTLY_ONE_ZIP_PER_SYMBOL_DAY")
        digest = github_digests[symbol]
        assert_gate(type(digest) is str, "EXPECTED_ZIP_SHA_TYPE")
        if digest.startswith("sha256:"):
            digest = digest[7:]
        findings.append(verify_one(paths[0], symbol=symbol, day=day,
                                   expected_zip_sha=digest))
    report = {
        "schema": OUTPUT_SCHEMA, "date_utc": day,
        "status": "PASS_PUBLIC_HISTORICAL_TRANSPORT_ONLY",
        "real": "OFF", "holdout": "SEALED",
        "independent_economic_check2": False, "realtime_oos_proven": False,
        "maker_fill_proven": False, "total_m15_bars": 576,
        "total_trades": sum(x["trade_rows"] for x in findings),
        "symbols": findings,
    }
    report["report_sha256"] = sha(canon(report))
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--archive-dir", type=Path, required=True)
    p.add_argument("--day", required=True)
    p.add_argument("--github-digests", type=Path, required=True,
                   help="Local JSON: six symbols -> authoritative Github ZIP SHA256")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        assert_gate(not args.output.exists(), "OUTPUT_ALREADY_EXISTS")
        digests = json.loads(args.github_digests.read_text(encoding="utf-8"))
        report = validate_six(args.archive_dir, day=args.day,
                              github_digests=digests)
        args.output.write_bytes(canon(report) + b"\n")
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError,
            zipfile.BadZipFile, gzip.BadGzipFile, EOFError, UnicodeError):
        raise SystemExit("BLOCKED_SIX_SYMBOL_ARCHIVE_QC") from None
    print("PASS_PUBLIC_HISTORICAL_SIX_M15", report["total_trades"],
          report["total_m15_bars"], report["report_sha256"])


if __name__ == "__main__":
    main()
