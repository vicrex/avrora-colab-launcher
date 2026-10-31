"""AVRORA: independently audit 6x7 official daily-trade archive bytes.

Original public.bybit.com daily .csv.gz contains HISTORICAL trades, but NO
first-seen per-event receipt time. A 42/42 ZIP/CRC/SHA match must NEVER become
an as-of live replay/OOS, HAWKES model-fit, or PostOnly fill authorization.
This is a read-only data lineage tool, not a market downloader/executor.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

from . import bybit_official_archive_transport as transport

SCHEMA = "AVRORA_HAWKES_SEVEN_DAY_SIX_SYMBOL_ARCHIVE_AUDIT_V1"
SYMBOLS = transport.SYMBOLS
DAY_COUNT = 7
REQUIRED_TOTAL = len(SYMBOLS) * DAY_COUNT
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def utc_time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("BLOCKED_SOURCE_UNVERIFIED_UTC_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("BLOCKED_SOURCE_UNVERIFIED_UTC_TIMESTAMP") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError("BLOCKED_SOURCE_UNVERIFIED_UTC_TIMESTAMP")
    return parsed


def required_days(asof_utc):
    if type(asof_utc) is not date:
        raise ValueError("BLOCKED_HAWKES_SOURCE_ASOF_DATE")
    if asof_utc < transport.FIRST_DAY + timedelta(days=DAY_COUNT):
        raise ValueError("BLOCKED_HAWKES_SOURCE_BEFORE_CAPTURE_FREEZE")
    return tuple(asof_utc - timedelta(days=offset)
                 for offset in range(DAY_COUNT, 0, -1))


def validate_one_manifest(obj, symbol, day, asof):
    if not isinstance(obj, dict) or "manifest_sha256" not in obj:
        raise ValueError("BLOCKED_HAWKES_SOURCE_MANIFEST_FORMAT")
    proof = obj["manifest_sha256"]
    if not isinstance(proof, str) or not SHA_RE.fullmatch(proof):
        raise ValueError("BLOCKED_HAWKES_SOURCE_MANIFEST_DIGEST")
    unsigned = {k: v for k, v in obj.items() if k != "manifest_sha256"}
    if sha(canonical(unsigned)) != proof:
        raise ValueError("BLOCKED_HAWKES_SOURCE_MANIFEST_TAMPER")
    expected = transport.archive_filename(day, symbol)
    if (obj.get("schema") != "AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2"
            or obj.get("kind") != "DELAYED_PUBLIC_HISTORICAL_TRADES"
            or obj.get("source") != "public.bybit.com/trading"
            or obj.get("symbol") != symbol
            or obj.get("day_utc") != day.isoformat()
            or obj.get("file_name") != expected
            or obj.get("url") != transport.archive_url(day, symbol)
            or obj.get("real") != "OFF" or obj.get("holdout") != "SEALED"
            or obj.get("signal_realtime_available") is not False
            or obj.get("fill_proven") is not False
            or obj.get("trade_return_proven") is not False
            or obj.get("new_oos_proven") is not False):
        raise ValueError("BLOCKED_HAWKES_SOURCE_MANIFEST_SCOPE")
    data_sha = obj.get("source_gz_sha256")
    if not isinstance(data_sha, str) or not SHA_RE.fullmatch(data_sha):
        raise ValueError("BLOCKED_HAWKES_SOURCE_GZIP_SHA")
    bytes_compressed = obj.get("source_compressed_bytes")
    bytes_raw = obj.get("source_uncompressed_bytes")
    lines = obj.get("source_text_lines")
    cap_compressed, cap_raw = transport.LIMITS[symbol]
    if (type(bytes_compressed) is not int
            or not 20 <= bytes_compressed <= cap_compressed
            or type(bytes_raw) is not int
            or not 10 <= bytes_raw <= cap_raw
            or type(lines) is not int or lines < 2):
        raise ValueError("BLOCKED_HAWKES_SOURCE_FILE_COUNTS")
    received = utc_time(obj.get("archive_received_at_utc"))
    not_before = utc_time(obj.get("causally_usable_not_before_utc"))
    day_finish = datetime.combine(day + timedelta(days=1),
                                  datetime.min.time(), tzinfo=timezone.utc)
    if received < day_finish or not_before < received:
        raise ValueError("BLOCKED_HAWKES_SOURCE_ARCHIVAL_CLOCK")
    cutoff = datetime.combine(asof, datetime.min.time(), tzinfo=timezone.utc)
    return {"available_as_of": not_before <= cutoff, "manifest_sha256": proof,
            "source_gz_sha256": data_sha}


def audit(root, asof_utc):
    days = required_days(asof_utc)
    root = Path(root)
    if not root.is_dir():
        raise ValueError("BLOCKED_HAWKES_SOURCE_FOLDER_NOT_FOUND")
    found = 0
    byte_verified = 0
    asof_available = 0
    missing = []
    source_lineage = hashlib.sha256()
    for day in days:
        for symbol in SYMBOLS:
            directory = root / symbol / day.isoformat()
            manifest_path = directory / "manifest.json"
            if not manifest_path.is_file():
                missing.append((day.isoformat(), symbol))
                continue
            try:
                manifest = json.loads(manifest_path.read_bytes())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("BLOCKED_HAWKES_SOURCE_MANIFEST_PARSE") from exc
            source = validate_one_manifest(manifest, symbol, day, asof_utc)
            found += 1
            # Do not treat a self-signed manifest as byte attestation.
            try:
                actual_proof = transport.verify(directory, symbol)
            except (OSError, ValueError, EOFError) as exc:
                raise ValueError("BLOCKED_HAWKES_SOURCE_BYTES_OR_CRC") from exc
            if actual_proof != source["manifest_sha256"]:
                raise ValueError("BLOCKED_HAWKES_SOURCE_INDEPENDENT_VERIFY")
            byte_verified += 1
            asof_available += int(source["available_as_of"])
            source_lineage.update(canonical({
                "day": day.isoformat(), "symbol": symbol,
                "gz_sha256": source["source_gz_sha256"],
                "manifest_sha256": source["manifest_sha256"],
            }))
    all_bytes = byte_verified == REQUIRED_TOTAL and not missing
    status = ("PASS_ARCHIVED_42_FILES_NOT_REALTIME"
              if all_bytes else "BLOCKED_HAWKES_42_ARCHIVES_MISSING")
    report = {
        "schema": SCHEMA,
        "status": status,
        "asof_utc": asof_utc.isoformat(),
        "required_days": [d.isoformat() for d in days],
        "required_symbols": list(SYMBOLS),
        "expected_symbol_day_files": REQUIRED_TOTAL,
        "manifest_files_present": found,
        "gz_byte_sha_and_crc_verified": byte_verified,
        "not_available_asof_count": found - asof_available,
        "missing_symbol_days": [
            {"day": d, "symbol": s} for d,s in missing
        ],
        "source_lineage_sha256": source_lineage.hexdigest(),
        "archive_complete_by_our_42_byte_checks": all_bytes,
        "provider_trade_count_completeness_proven": False,
        "per_event_historical_first_seen_proven": False,
        "hawkes_model_fit_ready": False,
        "independent_check2": False,
        "oos_proven": False,
        "maker_fill_proven": False,
        "live_trading_authorized": False,
        "real": "OFF", "holdout": "SEALED",
        "scope": "ARCHIVED_COMPLETED_DAYS_ONLY_NOT_EVENT_TIME_REPLAY",
    }
    report["receipt_sha256"] = sha(canonical(report))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True,
                        help="Folder with <symbol>/<YYYY-MM-DD>/manifest.json and gzip")
    parser.add_argument("--asof-utc", required=True,
                        help="UTC midnight cutoff as YYYY-MM-DD")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        cutoff = date.fromisoformat(args.asof_utc)
    except ValueError as exc:
        raise ValueError("BLOCKED_HAWKES_SOURCE_ASOF_DATE") from exc
    report = audit(args.root, cutoff)
    destination = Path(args.out)
    if destination.exists():
        raise ValueError("BLOCKED_HAWKES_REPORT_OVERWRITE")
    destination.write_bytes(canonical(report) + b"\n")
    print(report["status"], report["gz_byte_sha_and_crc_verified"],
          report["expected_symbol_day_files"], report["receipt_sha256"])
    print("HAWKES01_FIRST_SEEN_CHECK2_L2_REPLAY_BLOCKED")
    return 0 if report["archive_complete_by_our_42_byte_checks"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
