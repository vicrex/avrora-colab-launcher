"""Free Google Apps Script private-Drive transport, using only HTTPS and HMAC.

The user's existing Apps Script identity owns the Drive write permission.
No Google Cloud billing, OAuth refresh token, new clock or public private-data artifact.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from tools.private_multifamily_drive_delivery import canon, validate_report

MAX_BYTES = 4_000_000


def validate_url(value: str) -> None:
    parsed = urlparse(value)
    if (parsed.scheme != "https" or parsed.hostname != "script.google.com"
            or parsed.port is not None or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or not parsed.path.startswith("/macros/s/") or not parsed.path.endswith("/exec")):
        raise ValueError("BLOCKED_GAS_WEBAPP_URL_UNTRUSTED")


def signing_message(run_id: str, digest: str, base64_data: str) -> str:
    return run_id + "\n" + digest + "\n" + base64_data


def payload_and_ack(raw: bytes, run_id: str, secret_hex: str) -> tuple[dict, dict]:
    if not run_id.isdecimal() or len(run_id) > 24:
        raise ValueError("BLOCKED_GAS_RUN_ID")
    if not isinstance(secret_hex, str) or len(secret_hex) != 64:
        raise ValueError("BLOCKED_GAS_HMAC_SECRET")
    try:
        bytes.fromhex(secret_hex)  # reject nonhex keys; GAS signs with the 64-character ASCII key
        secret_bytes = secret_hex.encode("ascii")
    except ValueError as e:
        raise ValueError("BLOCKED_GAS_HMAC_SECRET") from e
    digest, receipt_sha = validate_report(raw)
    encoded = base64.b64encode(raw).decode("ascii")
    sig = hmac.new(secret_bytes, signing_message(run_id, digest, encoded).encode("ascii"), hashlib.sha256).hexdigest()
    envelope = {"schema": "AVRORA_PRIVATE_GAS_DELIVERY_V1", "run_id": run_id,
                "sha256": digest, "body_base64": encoded, "signature": sig}
    ack = {"schema": "AVRORA_PRIVATE_MULTIFAMILY_DRIVE_SHA_ACK_V1", "run_id": run_id,
           "status": "PRIVATE_DRIVE_BYTE_READBACK_VERIFIED", "sha256": digest,
           "bytes": len(raw), "private_receipt_sha256": receipt_sha,
           "transport": "GOOGLE_APPS_SCRIPT_OWNER_DRIVE", "real": "OFF", "holdout": "SEALED"}
    return envelope, ack


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--receipt", required=True)
    opts = ap.parse_args()
    secret = os.environ.get("AVRORA_GAS_REPORT_HMAC_KEY", "")
    webapp = os.environ.get("AVRORA_GAS_REPORT_WEBAPP_URL", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if os.environ.get("REAL", "OFF") != "OFF" or os.environ.get("HOLDOUT", "SEALED") != "SEALED":
        raise SystemExit("BLOCKED_GAS_REAL_OR_HOLDOUT")
    try:
        validate_url(webapp)
        raw = Path(opts.input).read_bytes()
        if len(raw) > MAX_BYTES:
            raise ValueError("BLOCKED_GAS_REPORT_UNBOUNDED")
        envelope, ack = payload_and_ack(raw, run_id, secret)
        if Path(opts.receipt).exists():
            raise ValueError("BLOCKED_GAS_ACK_ALREADY_EXISTS")
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
        raise SystemExit("BLOCKED_GAS_DELIVERY_PREFLIGHT") from None
    stage = "POST"
    try:
        import requests
        response = requests.post(webapp, json=envelope, timeout=100, allow_redirects=True)
        # Redirects from script.google.com ContentService must stay on a Google host.
        for item in [*response.history, response]:
            host = urlparse(item.url).hostname
            if host not in ("script.google.com", "script.googleusercontent.com"):
                raise ValueError("unexpected redirect host")
        response.raise_for_status()
        stage = "ACK"
        result = response.json()
        if (not isinstance(result, dict) or result.get("status") != "PASS_PRIVATE_DRIVE_READBACK"
                or result.get("run_id") != run_id or result.get("sha256") != ack["sha256"]
                or result.get("bytes") != ack["bytes"]):
            raise ValueError("unverified receipt")
        Path(opts.receipt).write_bytes(canon(ack) + b"\n")
    except Exception:
        # No redirect URL, exception text, private content, Drive ID or HMAC is printed.
        raise SystemExit("BLOCKED_GAS_PRIVATE_DELIVERY_" + stage) from None
    print("PASS_PRIVATE_MULTIFAMILY_DRIVE_READBACK_SHA", ack["sha256"], ack["bytes"])


if __name__ == "__main__":
    main()
