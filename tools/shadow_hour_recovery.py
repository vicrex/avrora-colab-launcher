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
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile
from datetime import datetime, timezone

REPOSITORY = "vicrex/avrora-colab-launcher"
API = f"https://api.github.com/repos/{REPOSITORY}/actions"
START_HOUR = 497940
SPACE_SIZE = 12000
PER_BATCH = 64
BATCH_COUNT = (SPACE_SIZE + PER_BATCH - 1) // PER_BATCH
LOOKBACK_HOURS = 24
LIMIT_PAGES = 8
MAX_ZIP_BYTES = 100_000
MAX_FETCH_ATTEMPTS = 4
RETRYABLE_HTTP = {500, 502, 503, 504}
PREFIX_AGG = "avrora-multifamily-shadow-aggregate-"
PREFIX_ACK = "avrora-multifamily-private-drive-ack-"
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
RUN_RE = re.compile(r"^[0-9]{5,24}$")


class RecoveryBlocked(ValueError):
    pass


class GitHubArtifactRedirect(urllib.request.HTTPRedirectHandler):
    """Allow HTTPS artifact storage redirects but never forward the API bearer."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        src, dst = urlsplit(req.full_url), urlsplit(newurl)
        host = (dst.hostname or "").lower()
        trusted_storage = (
            host == "api.github.com" or host == "github.com"
            or host.endswith(".githubusercontent.com")
            or host.endswith(".blob.core.windows.net")
        )
        if (dst.scheme != "https" or not trusted_storage
                or dst.username or dst.password or dst.port not in (None, 443)):
            raise RecoveryBlocked("BLOCKED_RECOVERY_UNTRUSTED_STORAGE_REDIRECT")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and host != (src.hostname or "").lower():
            for key in ("Authorization", "X-GitHub-Api-Version"):
                redirected.remove_header(key)
        return redirected


def fetch_bytes(url: str, token: str, limit: int = MAX_ZIP_BYTES) -> bytes:
    if not url.startswith(API + "/") and url != API + "/artifacts":
        raise RecoveryBlocked("BLOCKED_RECOVERY_UNEXPECTED_API_URL")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "avrora-shadow-catchup/1",
    })
    opener = urllib.request.build_opener(GitHubArtifactRedirect())
    for attempt in range(MAX_FETCH_ATTEMPTS):
        try:
            with opener.open(req, timeout=25) as resp:
                data = resp.read(limit + 1)
            break
        except urllib.error.HTTPError as exc:
            # GitHub artifact storage occasionally returns transient 5xx while
            # an otherwise valid immutable ZIP is available. Retry only those
            # provider failures; authorization, integrity and policy failures
            # remain fail-closed on the first response.
            if exc.code in RETRYABLE_HTTP and attempt + 1 < MAX_FETCH_ATTEMPTS:
                time.sleep(0.5 * (2 ** attempt))
                continue
            # Expose status and *numeric* artifact ID only: redirected signed
            # URLs contain temporary credentials and MUST NOT enter public logs.
            match = re.search(r"/artifacts/([0-9]+)/zip$", url)
            label = "ZIP_" + match.group(1) if match else "LIST"
            raise RecoveryBlocked(f"BLOCKED_RECOVERY_HTTP_{exc.code}_{label}") from None
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
            group = entries.setdefault(run_id, {}).setdefault(typ, [])
            # GitHub may retain several attempts under the same run_id/name.
            # One receipt is authoritative ONLY for its matching report SHA.
            if not any(item["id"] == obj["id"] for item in group):
                group.append(obj)
        if len(items) < 100 or seen_old:
            break
    else:
        raise RecoveryBlocked("BLOCKED_RECOVERY_PAGINATION_LIMIT")
    return entries


def expected_count(hour: int) -> int:
    if type(hour) is not int or hour < START_HOUR:
        raise RecoveryBlocked("BLOCKED_RECOVERY_BAD_HOUR")
    remaining = SPACE_SIZE - ((hour - START_HOUR) % BATCH_COUNT) * PER_BATCH
    return min(PER_BATCH, remaining)


def verified_hours(entries: dict, token: str, start_hour: int, current_hour: int):
    """Pair individual attempt SHA receipts; quarantine unmatched retries."""
    covered, partial = set(), set()
    for run_id, artifacts in entries.items():
        aggregates = artifacts.get("aggregate", [])
        acknowledgements = artifacts.get("ack", [])
        if not aggregates:
            raise RecoveryBlocked("BLOCKED_RECOVERY_ORPHAN_ACK")
        reports = []
        for aggregate in aggregates:
            report = read_archive(
                fetch_bytes(f"{API}/artifacts/{aggregate['id']}/zip", token),
                "sweep_public_summary.json", aggregate.get("digest"))
            hour = report.get("research_hour_index")
            digest = report.get("private_report_sha256")
            if (not isinstance(hour, int) or isinstance(hour, bool)
                    or hour < START_HOUR or hour > current_hour
                    or report.get("schema") != "AVRORA_PUBLIC_SHADOW_MULTIFAMILY_BATCH_V1"
                    or str(report.get("run_id")) != run_id
                    or report.get("tested") != expected_count(hour)
                    or report.get("real") != "OFF" or report.get("holdout") != "SEALED"
                    or report.get("oos") is not False
                    or report.get("maker_fill_proven") is not False
                    or not isinstance(digest, str) or not SHA_RE.fullmatch(digest)):
                raise RecoveryBlocked("BLOCKED_RECOVERY_BAD_AGGREGATE")
            reports.append((hour, digest))
        ack_hashes = []
        for ack in acknowledgements:
            receipt = read_archive(
                fetch_bytes(f"{API}/artifacts/{ack['id']}/zip", token),
                "sweep_private_drive_ack.json", ack.get("digest"))
            sha = receipt.get("sha256")
            if (receipt.get("schema") != "AVRORA_PRIVATE_MULTIFAMILY_DRIVE_SHA_ACK_V1"
                    or str(receipt.get("run_id")) != run_id
                    or receipt.get("status") != "PRIVATE_DRIVE_BYTE_READBACK_VERIFIED"
                    or not isinstance(sha, str) or not SHA_RE.fullmatch(sha)
                    or receipt.get("real") != "OFF" or receipt.get("holdout") != "SEALED"):
                raise RecoveryBlocked("BLOCKED_RECOVERY_BAD_DRIVE_ACK")
            ack_hashes.append(sha)
        for hour, digest in reports:
            if hour < start_hour:
                continue
            if digest in ack_hashes:
                covered.add(hour)
            else:
                partial.add(hour)
        # The ack must match an aggregate, even when historical attempts repeat.
        # If the aggregate predates the lookback it may have been excluded by
        # the created_at cutoff; that case must not turn into a fake success.
        if any(sha not in [digest for _, digest in reports] for sha in ack_hashes):
            raise RecoveryBlocked("BLOCKED_RECOVERY_ORPHAN_ACK_HASH")
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
