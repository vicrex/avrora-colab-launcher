"""Fail-closed PRIVATE delivery of AVRORA multifamily ledger to the user's Drive folder.

Executed by the existing PUBLIC runner, but never emits private hypotheses,
candlestick data or the complete per-candidate ledger to a public artifact/log.
The Google authorized_user credentials must have *effective* write/read rights.
The known 403 credentials CANNOT be repaired by changing a public GitHub link.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path

FOLDER = "1MXTBe21rTm1fVYzjUQ6NNf8cJzOQ0NKX"
API = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
SCHEMA = "AVRORA_MULTIFAMILY_SHADOW_SWEEP_V1"
MAX_BYTES = 4_000_000
NAME = re.compile(r"AVRORA_PRIVATE_MULTIFAMILY_[0-9]+[.]json\Z")


def canon(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def validate_report(payload: bytes) -> tuple[str, str]:
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError("BLOCKED_PRIVATE_REPORT_SIZE")
    report = json.loads(payload)
    if not isinstance(report, dict):
        raise ValueError("BLOCKED_PRIVATE_REPORT_SCHEMA")
    count = report.get("count")
    if (report.get("schema") != SCHEMA or count not in (32, 64)
            or report.get("real") != "OFF" or report.get("holdout") != "SEALED"
            or report.get("oos_proven") is not False
            or report.get("fill_proven") is not False):
        raise ValueError("BLOCKED_PRIVATE_REPORT_UNSAFE")
    models = report.get("models")
    ids = report.get("candidate_ids")
    if (not isinstance(models, list) or not isinstance(ids, list)
            or len(models) != count or len(ids) != count):
        raise ValueError("BLOCKED_PRIVATE_REPORT_INCOMPLETE")
    if len(set(ids)) != count or any(not isinstance(i, str) or len(i) != 64 for i in ids):
        raise ValueError("BLOCKED_PRIVATE_REPORT_CANDIDATES")
    if any(not isinstance(m, dict) or m.get("candidate_id") != candidate
           for m, candidate in zip(models, ids)):
        raise ValueError("BLOCKED_PRIVATE_REPORT_CANDIDATE_PARITY")
    signed = report.copy()
    receipt_sha = signed.pop("receipt_sha256", None)
    if not isinstance(receipt_sha, str) or hashlib.sha256(canon(signed)).hexdigest() != receipt_sha:
        raise ValueError("BLOCKED_PRIVATE_REPORT_RECEIPT_SHA")
    return hashlib.sha256(payload).hexdigest(), receipt_sha


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--receipt", required=True)
    args = p.parse_args()
    if not NAME.fullmatch(args.name):
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_BAD_NAME")
    if args.name != f"AVRORA_PRIVATE_MULTIFAMILY_{os.environ.get('GITHUB_RUN_ID', '')}.json":
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_RUN_ID_MISMATCH")
    if os.environ.get("REAL", "OFF") != "OFF" or os.environ.get("HOLDOUT", "SEALED") != "SEALED":
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_SAFETY_GATE")
    if not os.environ.get("AVRORA_PRIVATE_DRIVE_ADC_JSON_B64"):
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_ADC_MISSING")
    input_bytes = Path(args.input).read_bytes()
    try:
        digest, receipt_sha = validate_report(input_bytes)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_REPORT_INVALID") from None
    if Path(args.receipt).exists():
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_ACK_EXISTS")
    stage = "CREDENTIAL_PARSE"
    try:
        import requests
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = json.loads(base64.b64decode(os.environ["AVRORA_PRIVATE_DRIVE_ADC_JSON_B64"], validate=True))
        if not isinstance(creds, dict) or creds.get("type") != "authorized_user":
            raise ValueError("wrong credential type")
        configured = set(creds.get("scopes") or [])
        allowed = {"https://www.googleapis.com/auth/drive",
                   "https://www.googleapis.com/auth/drive.file"}
        if not (configured & allowed):
            raise SystemExit("BLOCKED_PRIVATE_DRIVE_SCOPE_MISSING")
        credential = Credentials.from_authorized_user_info(creds)
        stage = "TOKEN_REFRESH"
        credential.refresh(Request())
        headers = {"Authorization": "Bearer " + credential.token}
        stage = "LIST"
        q = "name = '" + args.name + "' and '" + FOLDER + "' in parents and trashed = false"
        response = requests.get(API, headers=headers,
                                params={"q": q, "fields": "files(id,name),nextPageToken",
                                        "pageSize": 10}, timeout=30)
        response.raise_for_status()  # In particular, HTTP 403 must NEVER be treated as success.
        listing = response.json()
        if listing.get("nextPageToken") or len(listing.get("files", [])) > 1:
            raise ValueError("ambiguous existing result")
        matches = listing.get("files", [])
        if matches:
            file_id = matches[0]["id"]
        else:
            stage = "CREATE"
            meta = json.dumps({"name": args.name, "parents": [FOLDER],
                               "mimeType": "application/json"}, separators=(",", ":")).encode()
            boundary = "AVRORA_PRIVATE_REPORT_BOUNDARY"
            body = (b"--" + boundary.encode() + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                    + meta + b"\r\n--" + boundary.encode() + b"\r\nContent-Type: application/json\r\n\r\n"
                    + input_bytes + b"\r\n--" + boundary.encode() + b"--\r\n")
            response = requests.post(UPLOAD, headers={**headers,
                                        "Content-Type": "multipart/related; boundary=" + boundary},
                                     params={"uploadType": "multipart", "fields": "id"}, data=body,
                                     timeout=120)
            response.raise_for_status()
            file_id = response.json()["id"]
        stage = "READBACK"
        response = requests.get(f"{API}/{file_id}", headers=headers, params={"alt": "media"}, timeout=120)
        response.raise_for_status()
        if response.content != input_bytes or hashlib.sha256(response.content).hexdigest() != digest:
            raise ValueError("private report readback differs")
        stage = "ACK"
        # Public ACK contains hashes and run ID only, never the Drive file ID or private strategy contents.
        ack = {"schema": "AVRORA_PRIVATE_MULTIFAMILY_DRIVE_SHA_ACK_V1",
               "run_id": os.environ["GITHUB_RUN_ID"],
               "status": "PRIVATE_DRIVE_BYTE_READBACK_VERIFIED",
               "sha256": digest, "bytes": len(input_bytes),
               "private_receipt_sha256": receipt_sha,
               "real": "OFF", "holdout": "SEALED"}
        Path(args.receipt).write_bytes(canon(ack) + b"\n")
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        kind = "HTTP_" + str(status) if type(status) is int else "FAILED"
        # No exception string, response body, bearer token or private filename is logged.
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_" + stage + "_" + kind) from None
    print("PASS_PRIVATE_MULTIFAMILY_DRIVE_READBACK_SHA", digest, len(input_bytes))


if __name__ == "__main__":
    main()
