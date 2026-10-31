"""One-shot read-only inventory of official Bybit GitHub Actions artifacts.

This only enumerates metadata. Artifact names, CI status and GitHub digests
CANNOT prove provider bytes, complete trades, individual first-seen receipts,
HAWKES calibration, independent CHECK2 or executable order fills.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import urllib.request

from .hawkes_seven_day_archive_audit import (
    SCHEMA as SOURCE_SCHEMA, SYMBOLS, canonical, required_days, sha,
)

REPO = "vicrex/avrora-colab-launcher"
SCHEMA = "AVRORA_HAWKES_GITHUB_ARTIFACT_INVENTORY_V1"
NAME_RE = re.compile(
    r"^avrora-official-trades-(BTCUSDT|ETHUSDT|SOLUSDT|NEARUSDT|LINKUSDT|XRPUSDT)-"
    r"(\d{4}-\d{2}-\d{2})-(\d{8,})$")
PER_PAGE = 100
MAX_PAGES = 20


def inventory(pages, asof_date, complete_listing=True):
    days = required_days(asof_date)
    needed = {(sym, day.isoformat()) for sym in SYMBOLS for day in days}
    available = {}
    stale_expired = 0
    invalid_metadata = 0
    observed = set()
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("artifacts"),list):
            raise ValueError("BLOCKED_ARCHIVE_INVENTORY_API_SCHEMA")
        for item in page["artifacts"]:
            if not isinstance(item,dict):
                raise ValueError("BLOCKED_ARCHIVE_INVENTORY_ITEM_SCHEMA")
            match = NAME_RE.fullmatch(str(item.get("name","")))
            if not match:
                continue
            symbol, label, run_id = match.groups()
            key = (symbol,label)
            if key not in needed:
                continue
            artifact_id = item.get("id")
            if type(artifact_id) is not int or artifact_id <= 0:
                invalid_metadata += 1
                continue
            if item.get("expired") is True:
                stale_expired += 1
                continue
            if item.get("expired") is not False or item.get("name") in observed:
                invalid_metadata += 1
                continue
            observed.add(item["name"])
            available.setdefault(key,set()).add(artifact_id)
    complete = complete_listing and invalid_metadata == 0
    if not complete_listing:
        status = "BLOCKED_ARCHIVE_INVENTORY_PARTIAL_LISTING"
    elif invalid_metadata:
        status = "BLOCKED_ARCHIVE_INVENTORY_UNTRUSTED_METADATA"
    elif len(available) < len(needed):
        status = "BLOCKED_ARCHIVE_METADATA_COVERAGE_MISSING"
    else:
        status = "METADATA_42_PRESENT_BYTES_UNVERIFIED"
    missing = sorted(needed - set(available))
    result = {
        "schema":SCHEMA,
        "status":status,
        "asof_utc":asof_date.isoformat(),
        "expected_symbol_day_pairs":42,
        "found_symbol_day_pairs_with_unexpired_artifacts":len(available),
        "missing_symbol_days":[{"symbol":s,"day":d} for s,d in missing],
        "multiple_artifact_candidates_for_pair":sum(len(v)>1 for v in available.values()),
        "stale_expired_artifacts":stale_expired,
        "invalid_artifact_metadata":invalid_metadata,
        "api_listing_complete":bool(complete_listing),
        "metadata_listing_usable":bool(complete),
        "official_gzip_bytes_sha_verified":False,
        "provider_event_completeness_proven":False,
        "individual_event_first_seen_proven":False,
        "independent_check2":False,
        "hawkes_model_fit_ready":False,
        "oos_proven":False,
        "maker_fill_proven":False,
        "live_trading_authorized":False,
        "real":"OFF","holdout":"SEALED",
        "scope":"GITHUB_ARTIFACT_NAMES_ONLY_NOT_ARCHIVE_DOWNLOAD",
    }
    result["receipt_sha256"]=sha(canonical(result))
    return result


def fetch_metadata(token):
    if not isinstance(token,str) or len(token)<10:
        raise ValueError("BLOCKED_MISSING_ACTIONS_READ_TOKEN")
    pages = []
    full = False
    for page in range(1,MAX_PAGES+1):
        url=(f"https://api.github.com/repos/{REPO}/actions/artifacts"
             f"?per_page={PER_PAGE}&page={page}")
        request=urllib.request.Request(url,headers={
            "Authorization":"Bearer "+token,
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"AVRORA-readonly-public-artifact-inventory/1.0",
        })
        with urllib.request.urlopen(request,timeout=20) as response:
            if response.status!=200:
                raise ValueError("BLOCKED_ARCHIVE_INVENTORY_HTTP")
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:
                raise ValueError("BLOCKED_ARCHIVE_INVENTORY_RESPONSE_TOO_LARGE")
        body=json.loads(raw)
        if not isinstance(body.get("artifacts"),list):
            raise ValueError("BLOCKED_ARCHIVE_INVENTORY_API_SCHEMA")
        pages.append(body)
        if len(body["artifacts"]) < PER_PAGE:
            full=True
            break
    return pages, full


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--asof-utc",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    asof=date.fromisoformat(args.asof_utc)
    token=os.environ.get("GITHUB_TOKEN","")
    pages,complete=fetch_metadata(token)
    report=inventory(pages,asof,complete_listing=complete)
    output=Path(args.out)
    if output.exists():
        raise ValueError("BLOCKED_ARCHIVE_INVENTORY_OVERWRITE")
    output.write_bytes(canonical(report)+b"\n")
    print(report["status"],
          report["found_symbol_day_pairs_with_unexpired_artifacts"],
          report["expected_symbol_day_pairs"],
          report["receipt_sha256"])
    print("ARCHIVE_NAMES_NOT_SOURCE_BYTES_FIRSTSEEN_CHECK2_OOS")
    return 0 if complete else 3


if __name__=="__main__":
    raise SystemExit(main())
