"""Bounded, fail-closed catch-up for the existing AVRORA hourly shadow sweep.

Reads only public GitHub Actions aggregate artifacts and their matching private-
Drive delivery ACKs. No strategy data, Drive credentials, trading, or new timer.
A missed hour is eligible only when no public receipt exists for that hour.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone

REPOSITORY = "vicrex/avrora-colab-launcher"
API = f"https://api.github.com/repos/{REPOSITORY}/actions"
START_HOUR = 497940
LOOKBACK_HOURS = 24
LIMIT_PAGES = 8
MAX_ZIP_BYTES = 100_000
PREFIX_AGG = "avrora-multifamily-shadow-aggregate-"
PREFIX_ACK = "avrora-multifamily-private-drive-ack-"
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
RUN_RE = re.compile(r"^[0-9]{5,24}$")


class RecoveryBlocked(ValueError):
    pass


def fetch_bytes(url: str, token: str, limit: int = MAX_ZIP_BYTES) -> bytes:
    if not url.startswith(API + "/") and url != API + "/artifacts":
        raise RecoveryBlocked("BLOCKED_RECOVERY_UNEXPECTED_API_URL")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "avrora-shadow-catchup/1",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise RecoveryBlocked("BLOCKED_RECOVERY_RESPONSE_TOO_LARGE")
    return data


def read_archive(raw: bytes, expected: str, digest: str | None) -> dict:
    if digest:
        if not digest.startswith("sha256:") or hashlib.sha256(raw).hexdigest() != digest[7:]:
            raise RecoveryBlocked("BLOCKED_RECOVERY_ARTIFACT_SHA")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = z.infolist()
            if len(members) != 1 or members[0].filename != expected or members[0].file_size > 15_000:
                raise RecoveryBlocked("BLOCKED_RECOVERY_ARTIFACT_CONTENTS")
            result = json.loads(z.read(expected))
    except (zipfile.BadZipFile, KeyError, UnicodeError, ValueError) as exc:
        raise RecoveryBlocked("BLOCKED_RECOVERY_ARTIFACT_ZIP") from exc
    if not isinstance(result, dict):
        raise RecoveryBlocked("BLOCKED_RECOVERY_ARTIFACT_JSON")
    return result


def collect_artifacts(token: str, start_hour: int):
    """Return recent aggregate and ACK artifacts; reject incomplete API pagination."""
    entries = {}
    cutoff = (start_hour - 1) * 3600
    seen_old = False
    for page in range(1, LIMIT_PAGES + 1):
        url = f"{API}/artifacts?per_page=100&page={page}"
        payload = json.loads(fetch_bytes(url, token, 1_000_000))
        items = payload.get("artifacts")
        if not isinstance(items, list):
            raise RecoveryBlocked("BLOCKED_RECOVERY_INVALID_LIST")
        for obj in items:
            created = obj.get("created_at", "")
            try:
                at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except (ValueError, TypeError) as exc:
                raise RecoveryBlocked("BLOCKED_RECOVERY_INVALID_DATE") from exc
            if at.timestamp() < cutoff:
                seen_old = True
                continue
            name = obj.get("name", "")
            if name.startswith(PREFIX_AGG):
                typ, run_id = "aggregate", name[len(PREFIX_AGG):]
            elif name.startswith(PREFIX_ACK):
                typ, run_id = "ack", name[len(PREFIX_ACK):]
            else:
                continue
            if not RUN_RE.fullmatch(run_id) or not isinstance(obj.get("id"), int):
                raise RecoveryBlocked("BLOCKED_RECOVERY_INVALID_RUN_ID")
            if obj.get("expired"):
                raise RecoveryBlocked("BLOCKED_RECOVERY_EARLY_ARTIFACT_EXPIRY")
            if typ in entries.setdefault(run_id, {}):
                raise RecoveryBlocked("BLOCKED_RECOVERY_DUPLICATE_ARTIFACT_NAME")
            entries[run_id][typ] = obj
        if len(items) < 100 or seen_old:
            break
    else:
        raise RecoveryBlocked("BLOCKED_RECOVERY_PAGINATION_LIMIT")
    return entries


def verified_hours(entries: dict, token: str, start_hour: int, current_hour: int):
    """Pair authoritative SHA artifacts from the SAME run; partial means quarantine."""
    covered, partial = set(), set()
    for run_id, artifacts in entries.items():
        agg = artifacts.get("aggregate")
        if agg is None:
            raise RecoveryBlocked("BLOCKED_RECOVERY_ORPHAN_ACK")
        url = f"{API}/artifacts/{agg['id']}/zip"
        report = read_archive(fetch_bytes(url, token), "sweep_public_summary.json", agg.get("digest"))
        hour = report.get("research_hour_index")
        if (not isinstance(hour, int) or isinstance(hour, bool)
                or hour < START_HOUR or hour > current_hour
                or report.get("schema") != "AVRORA_PUBLIC_SHADOW_MULTIFAMILY_BATCH_V1"
                or str(report.get("run_id")) != run_id or report.get("tested") != 64
                or report.get("real") != "OFF" or report.get("holdout") != "SEALED"
                or report.get("oos") is not False
                or report.get("maker_fill_proven") is not False
                or not isinstance(report.get("private_report_sha256"), str)
                or not SHA_RE.fullmatch(report["private_report_sha256"])):
            raise RecoveryBlocked("BLOCKED_RECOVERY_BAD_AGGREGATE")
        if hour < start_hour:
            continue
        ack = artifacts.get("ack")
        if ack is None:
            partial.add(hour)
            continue
        receipt = read_archive(fetch_bytes(
            f"{API}/artifacts/{ack['id']}/zip", token),
            "sweep_private_drive_ack.json", ack.get("digest"))
        if (receipt.get("schema") != "AVRORA_PRIVATE_MULTIFAMILY_DRIVE_SHA_ACK_V1"
                or str(receipt.get("run_id")) != run_id
                or receipt.get("status") != "PRIVATE_DRIVE_BYTE_READBACK_VERIFIED"
                or receipt.get("sha256") != report["private_report_sha256"]
                or receipt.get("real") != "OFF" or receipt.get("holdout") != "SEALED"):
            raise RecoveryBlocked("BLOCKED_RECOVERY_BAD_DRIVE_ACK")
        covered.add(hour)
    return covered, partial


def select_hour(current_hour: int, covered: set[int], partial: set[int], lookback: int = LOOKBACK_HOURS):
    if current_hour < START_HOUR:
        raise RecoveryBlocked("BLOCKED_RECOVERY_BEFORE_START")
    start = max(START_HOUR, current_hour - lookback)
    for hour in range(start, current_hour + 1):
        if hour not in covered and hour not in partial:
            return hour
    return None


def main():
    if (os.environ.get("REAL", "OFF") != "OFF"
            or os.environ.get("HOLDOUT", "SEALED") != "SEALED"
            or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY):
        raise RecoveryBlocked("BLOCKED_RECOVERY_SAFETY_OR_REPO")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RecoveryBlocked("BLOCKED_RECOVERY_ACTIONS_READ_TOKEN")
    now_hour = int(datetime.now(timezone.utc).timestamp() // 3600)
    start = max(START_HOUR, now_hour - LOOKBACK_HOURS)
    entries = collect_artifacts(token, start)
    covered, partial = verified_hours(entries, token, start, now_hour)
    target = select_hour(now_hour, covered, partial)
    if target is None:
        status, target = "IDLE", ""
    else:
        status = "RUN"
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        raise RecoveryBlocked("BLOCKED_RECOVERY_OUTPUT")
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"status={status}\n")
        f.write(f"hour={target}\n")
    print("AVRORA_RECOVERY", status, "HOUR", target,
          "CONFIRMED", len(covered), "QUARANTINED_PARTIAL", len(partial),
          "LOOKBACK", LOOKBACK_HOURS)


if __name__ == "__main__":
    try:
        main()
    except (RecoveryBlocked, OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print("BLOCKED_SHADOW_RECOVERY_NO_NEW_BATCH", type(exc).__name__,
              str(exc) if isinstance(exc, RecoveryBlocked) else "UNVERIFIED_PROVIDER")
        sys.exit(3)
