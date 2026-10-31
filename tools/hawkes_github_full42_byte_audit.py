"""Read-only, one-shot, sequential real SHA/CRC audit of 42 official archives.

Artifact names alone are never source-byte evidence. This downloads GitHub's
original uploaded ZIP for each frozen 24-30 Oct six-symbol pair, checks GitHub
ZIP digest, tight ZIP shape, original signed manifest, Bybit gzip SHA and CRC.
The archives are historical, NOT individual first-seen, independent OOS or fills.
"""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from . import bybit_official_archive_transport as transport
from .hawkes_github_artifact_inventory import (
    fetch_metadata, inventory, NAME_RE, REPO,
)
from .hawkes_seven_day_archive_audit import (
    SYMBOLS, canonical, required_days, sha, validate_one_manifest,
)

SCHEMA = "AVRORA_HAWKES_GITHUB_42_REAL_ARCHIVE_BYTE_AUDIT_V1"
GITHUB_DIGEST = re.compile(r"sha256:([0-9a-f]{64})\Z")
OVERHEAD_CAP = 10_000_000
CHUNK = 1024 * 1024


def select(pages, asof):
    meta = inventory(pages, asof, complete_listing=True)
    if (meta["status"] != "METADATA_42_PRESENT_BYTES_UNVERIFIED"
            or meta["multiple_artifact_candidates_for_pair"] != 0
            or meta["invalid_artifact_metadata"] != 0):
        raise ValueError("BLOCKED_GITHUB_42_METADATA_OR_DUPLICATES")
    expected = {(s, d.isoformat()) for d in required_days(asof) for s in SYMBOLS}
    chosen = {}
    for page in pages:
        for item in page["artifacts"]:
            m = NAME_RE.fullmatch(str(item.get("name", "")))
            if not m:
                continue
            symbol, day_str, _ = m.groups()
            key = (symbol, day_str)
            if key not in expected or item.get("expired") is not False:
                continue
            number = item.get("id")
            size = item.get("size_in_bytes")
            digest = item.get("digest")
            cap = transport.LIMITS[symbol][0] + OVERHEAD_CAP
            if (key in chosen or type(number) is not int or number <= 0
                    or type(size) is not int or not 100 < size <= cap
                    or not isinstance(digest, str)
                    or GITHUB_DIGEST.fullmatch(digest) is None):
                raise ValueError("BLOCKED_GITHUB_ARTIFACT_UNTRUSTED_METADATA")
            chosen[key] = item
    if set(chosen) != expected or len(chosen) != 42:
        raise ValueError("BLOCKED_GITHUB_42_MISSING_SOURCE_ARTIFACTS")
    return chosen, meta


def gh_download(artifact_id, path, timeout=240):
    # GitHub CLI follows the GitHub-signed Actions ZIP redirect, without
    # handing the bearer token to a hand-written arbitrary redirect handler.
    with Path(path).open("xb") as out:
        subprocess.run(
            ["gh", "api", f"repos/{REPO}/actions/artifacts/{artifact_id}/zip"],
            stdout=out, stderr=subprocess.PIPE, check=True,
            timeout=timeout,
        )


def digest_file(path, cap):
    h = hashlib.sha256()
    n = 0
    with Path(path).open("rb") as stream:
        while chunk := stream.read(CHUNK):
            n += len(chunk)
            if n > cap:
                raise ValueError("BLOCKED_GITHUB_ZIP_RESOURCE_CAP")
            h.update(chunk)
    return n, h.hexdigest()


def verify_one(path, symbol, day, asof, item):
    size, digest = digest_file(path, transport.LIMITS[symbol][0] + OVERHEAD_CAP)
    if size != item["size_in_bytes"] or "sha256:" + digest != item["digest"]:
        raise ValueError("BLOCKED_GITHUB_ZIP_TRANSFER_DIGEST")
    expected = transport.archive_filename(day, symbol)
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if (len(infos) != 2 or set(i.filename for i in infos)
                != {"manifest.json", expected}):
            raise ValueError("BLOCKED_GITHUB_ZIP_MEMBER_SHAPE")
        for i in infos:
            if (i.is_dir() or i.flag_bits & 1
                    or i.file_size < 0
                    or i.file_size > (4096 if i.filename == "manifest.json"
                                      else transport.LIMITS[symbol][0])):
                raise ValueError("BLOCKED_GITHUB_ZIP_MEMBER_RESOURCE_CAP")
        with tempfile.TemporaryDirectory(prefix="avrora_archive_") as tmp:
            root = Path(tmp)
            for info in infos:
                with z.open(info) as source, (root / info.filename).open("xb") as dst:
                    shutil.copyfileobj(source, dst, CHUNK)
            m = json.loads((root / "manifest.json").read_bytes())
            v = validate_one_manifest(m, symbol, day, asof)
            if transport.verify(root, symbol) != v["manifest_sha256"]:
                raise ValueError("BLOCKED_GITHUB_SOURCE_INDEPENDENT_VERIFY")
    return {
        "symbol": symbol, "day_utc": day.isoformat(),
        "artifact_id": item["id"], "artifact_zip_sha256": digest,
        "source_gz_sha256": v["source_gz_sha256"],
        "manifest_sha256": v["manifest_sha256"],
        "source_compressed_bytes": m["source_compressed_bytes"],
        "source_uncompressed_bytes": m["source_uncompressed_bytes"],
        "source_text_lines": m["source_text_lines"],
        "archive_received_at_utc": m["archive_received_at_utc"],
        "available_by_asof_midnight": v["available_as_of"],
        "gzip_crc_verified": True, "github_zip_sha_verified": True,
        "individual_first_seen_proven": False,
    }


def audit(pages, asof, *, downloader=gh_download):
    chosen, meta = select(pages, asof)
    receipts = []
    lineage = hashlib.sha256()
    for day in required_days(asof):
        for symbol in SYMBOLS:
            item = chosen[(symbol, day.isoformat())]
            with tempfile.TemporaryDirectory(prefix="avrora_42_zip_") as tmp:
                zip_path = Path(tmp) / "source.zip"
                downloader(item["id"], zip_path)
                result = verify_one(zip_path, symbol, day, asof, item)
            receipts.append(result)
            lineage.update(canonical({
                "day":day.isoformat(), "symbol":symbol,
                "gz_sha256":result["source_gz_sha256"],
                "manifest_sha256":result["manifest_sha256"],
            }))
            print("PASS_ARCHIVE_ORIGINAL_SHA_GZIP_CRC", symbol, day,
                  result["source_gz_sha256"], flush=True)
    report = {
        "schema":SCHEMA, "status":"PASS_ARCHIVED_42_FILES_NOT_REALTIME",
        "asof_utc":asof.isoformat(),
        "required_days":[x.isoformat() for x in required_days(asof)],
        "expected_pairs":42, "source_gzip_sha_crc_verified":len(receipts),
        "github_original_zip_sha_verified":len(receipts),
        "distinct_symbol_day_pairs":len(set(
            (x["symbol"], x["day_utc"]) for x in receipts)),
        "source_lineage_sha256":lineage.hexdigest(),
        "not_available_by_asof_midnight":sum(
            not x["available_by_asof_midnight"] for x in receipts),
        "metadata_inventory_sha256":meta["receipt_sha256"],
        "receipts":receipts,
        "provider_trade_count_completeness_proven":False,
        "individual_historical_first_seen_proven":False,
        "hawkes_real_time_fit_proven":False,
        "independent_check2":False,
        "prospective_oos_proven":False,
        "maker_fill_proven":False,
        "live_trading_authorized":False,
        "real":"OFF", "holdout":"SEALED",
        "scope":"42_DELAYED_ARCHIVAL_BYTES_NOT_REALTIME_REPLAY",
    }
    report["receipt_sha256"] = sha(canonical(report))
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    asof = date.fromisoformat(args.asof_utc)
    destination = Path(args.out)
    if destination.exists():
        raise ValueError("BLOCKED_42_RECEIPT_OVERWRITE")
    token = os.environ.get("GH_TOKEN", "")
    pages, complete = fetch_metadata(token)
    if not complete:
        raise ValueError("BLOCKED_GITHUB_42_PARTIAL_API_LISTING")
    receipt = audit(pages, asof)
    destination.write_bytes(canonical(receipt) + b"\n")
    print("PASS_ARCHIVE_42_BYTE_SHA_GZIP_CRC_NOT_FIRSTSEEN",
          receipt["source_gzip_sha_crc_verified"], receipt["receipt_sha256"])


if __name__ == "__main__":
    main()
