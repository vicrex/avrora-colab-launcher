#!/usr/bin/env python3
"""One-time Google Drive READ-ONLY OAuth (separate from existing Colab token).

Review consent; it must ask ONLY to VIEW Drive files plus email sign-in.
Do not authorize Drive write, Cloud Platform, or broad identity scopes.
"""
import getpass
import json
import os
from pathlib import Path
import sys

SCOPES = ("openid",
          "https://www.googleapis.com/auth/userinfo.email",
          "https://www.googleapis.com/auth/drive.readonly")
ALLOWED = set(SCOPES) | {"email", "profile", "https://www.googleapis.com/auth/userinfo.profile"}
REDIRECT = "https://sdk.cloud.google.com/applicationdefaultauthcode.html"


def validate_scopes(scopes):
    granted = set(scopes or [])
    if not set(SCOPES).issubset(granted):
        raise ValueError("BLOCKED_REQUIRED_READONLY_SCOPE_NOT_GRANTED")
    if granted - ALLOWED:
        raise ValueError("BLOCKED_UNEXPECTED_GOOGLE_SCOPE")


def main():
    path = Path(os.environ["AVRORA_DRIVE_ADC_OUTPUT"])
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise SystemExit("BLOCKED_PRIVATE_OUTPUT_FILE")
    from importlib import resources
    from google_auth_oauthlib.flow import InstalledAppFlow
    client = json.loads(resources.files("colab_cli").joinpath("oauth_config.json").read_text())
    flow = InstalledAppFlow.from_client_config(client, list(SCOPES))
    flow.redirect_uri = REDIRECT
    link, _ = flow.authorization_url(prompt="consent", token_usage="remote")
    print("Open the following Google Drive read-only authorization link:")
    print(link)
    print("Check requested scopes: Google Drive VIEW access ONLY and email.")
    print("If Google asks for edit/delete/Cloud Platform access, CANCEL.")
    code = getpass.getpass("Paste the one-time Google code HERE (hidden): ").strip()
    if not code:
        raise SystemExit("BLOCKED_NO_GOOGLE_CODE")
    flow.fetch_token(code=code)
    creds = flow.credentials
    validate_scopes(creds.granted_scopes)
    obj = json.loads(creds.to_json())
    if not all(obj.get(x) for x in ("client_id","client_secret","refresh_token")):
        raise SystemExit("BLOCKED_NOT_REFRESHABLE")
    payload = {k:obj[k] for k in ("client_id","client_secret","refresh_token")}
    payload.update(type="authorized_user",
                   token_uri=obj.get("token_uri","https://oauth2.googleapis.com/token"),
                   scopes=sorted(set(creds.granted_scopes)))
    path.write_text(json.dumps(payload, sort_keys=True),encoding="utf-8")
    print("READONLY_DRIVE_ADC_CREATED: secret written only to private temporary file.")


if __name__=="__main__":
    main()
