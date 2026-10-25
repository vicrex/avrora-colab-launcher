#!/usr/bin/env python3
"""Verify isolated Google Drive OAuth ADC with an actual folder write/read/delete.

Never prints tokens, OAuth client material, Google account identifiers, Drive
response bodies, or sensitive file contents. Writes validated ADC only after
successful, independently hashed Drive probe and cleanup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import uuid

SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER = "1MXTBe21rTm1fVYzjUQ6NNf8cJzOQ0NKX"
API = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
ALLOW_ADDITIONAL = {
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
}
VALID_CREDENTIAL_KEYS = {"type", "client_id", "client_secret", "refresh_token",
                         "token_uri", "scopes", "quota_project_id",
                         "universe_domain", "account"}


def validate_scopes(granted: set[str]) -> None:
    if SCOPE not in granted or granted - ({SCOPE} | ALLOW_ADDITIONAL):
        raise ValueError("BLOCKED_DRIVE_SCOPE_NOT_EXCLUSIVE")


def validate_adc_fields(data: dict) -> None:
    if not isinstance(data, dict) or data.get("type") != "authorized_user":
        raise ValueError("BLOCKED_DRIVE_ADC_WRONG_TYPE")
    if any(not isinstance(data.get(k), str) or not data[k]
           for k in ("client_id", "client_secret", "refresh_token")):
        raise ValueError("BLOCKED_DRIVE_ADC_FIELDS_MISSING")
    scopes = data.get("scopes")
    if scopes is not None:
        if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
            raise ValueError("BLOCKED_DRIVE_ADC_BAD_SCOPES")
        validate_scopes(set(scopes))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    source, target = Path(a.input), Path(a.output)
    if not source.is_file() or not target.is_file():
        raise SystemExit("BLOCKED_PRIVATE_ADC_MISSING_TEMP_FILE")
    if source.resolve() == target.resolve():
        raise SystemExit("BLOCKED_PRIVATE_ADC_INPUT_OUTPUT_COLLISION")
    stage = "ADC_CHECK"
    file_id = None
    try:
        import requests
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        data = json.loads(source.read_text(encoding="utf-8"))
        validate_adc_fields(data)
        credentials = Credentials.from_authorized_user_info(data, scopes=[SCOPE])
        stage = "REFRESH"
        credentials.refresh(Request())
        headers = {"Authorization": "Bearer " + credentials.token}
        stage = "GRANT_CHECK"
        r = requests.get(TOKENINFO, params={"access_token": credentials.token}, timeout=35)
        r.raise_for_status()
        scopes = set(r.json().get("scope", "").split())
        validate_scopes(scopes)
        print("PASS_VERIFIED_DRIVE_ONLY_SCOPE")

        stage = "FOLDER"
        r = requests.get(f"{API}/{FOLDER}", headers=headers,
                         params={"fields": "id,mimeType,trashed"}, timeout=35)
        r.raise_for_status()
        metadata = r.json()
        if metadata.get("id") != FOLDER or metadata.get("mimeType") != "application/vnd.google-apps.folder" or metadata.get("trashed"):
            raise ValueError("wrong folder")

        # This test uses only a throwaway, non-sensitive file, and deletes it
        # before any GitHub secret is changed.
        name = "AVRORA_OAUTH_PROBE_" + uuid.uuid4().hex + ".txt"
        payload = b"AVRORA_DRIVE_AUTH_PROBE_NO_PRIVATE_RESEARCH\n"
        stage = "PROBE_CREATE"
        r = requests.post(API, headers={**headers, "Content-Type": "application/json"},
                          json={"name": name, "parents": [FOLDER],
                                "mimeType": "text/plain"}, timeout=35)
        r.raise_for_status()
        file_id = r.json()["id"]
        stage = "PROBE_UPLOAD"
        r = requests.patch(f"{UPLOAD}/{file_id}", headers={**headers,
                           "Content-Type": "text/plain"},
                           params={"uploadType": "media"}, data=payload, timeout=35)
        r.raise_for_status()
        stage = "PROBE_READBACK"
        r = requests.get(f"{API}/{file_id}", headers=headers,
                         params={"alt": "media"}, timeout=35)
        r.raise_for_status()
        if r.content != payload or hashlib.sha256(r.content).digest() != hashlib.sha256(payload).digest():
            raise ValueError("probe bytes changed")
        print("PASS_PROBE_BYTES_AND_SHA")

        stage = "PROBE_CLEANUP"
        r = requests.delete(f"{API}/{file_id}", headers=headers, timeout=35)
        r.raise_for_status()
        file_id = None
        print("PASS_PROBE_DELETED")

        stage = "WRITE_SECRET_INPUT"
        # Scope *must* be persisted; the hourly uploader checks it and
        # refuses generic/cloud-only or Colab-only credentials.
        safe = {k: data[k] for k in ("type", "client_id", "client_secret", "refresh_token")}
        safe["token_uri"] = data.get("token_uri", "https://oauth2.googleapis.com/token")
        safe["scopes"] = [SCOPE]
        encoded = json.dumps(safe, sort_keys=True, separators=(",", ":"))
        with target.open("w", encoding="utf-8") as fh:
            fh.write(encoded)
        os.chmod(target, 0o600)
        print("PASS_VERIFIED_TEMP_ADC_READY")
    except Exception as exc:
        if file_id:
            try:
                requests.delete(f"{API}/{file_id}", headers=headers, timeout=35)
            except Exception:
                pass
        status = getattr(getattr(exc, "response", None), "status_code", None)
        code = "HTTP_" + str(status) if isinstance(status, int) else "FAILED"
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_SETUP_" + stage + "_" + code) from None


if __name__ == "__main__":
    main()
