#!/usr/bin/env python3
"""One-time, interactive, minimum-scope Colab OAuth authorization.

Uses the PUBLIC OAuth client distributed with the official google-colab-cli.
Never outputs an access token, refresh token, auth code, or ADC JSON to stdout.
Only writes to a private temporary file supplied by the local Bash wrapper.

This path is EXPERIMENTAL until verified against a real Colab backend. It
intentionally bypasses gcloud ADC login, which mandates cloud-platform scope.
"""
import getpass
import json
import os
from pathlib import Path
import sys

COLAB_SCOPE = "https://www.googleapis.com/auth/colaboratory"
EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
REQUESTED_SCOPES = ("openid", EMAIL_SCOPE, COLAB_SCOPE)
ALLOWED_SCOPES = frozenset(REQUESTED_SCOPES) | frozenset({
    "email", "profile", "https://www.googleapis.com/auth/userinfo.profile"
})
REMOTE_REDIRECT_URI = "https://sdk.cloud.google.com/applicationdefaultauthcode.html"


def build_adc(credentials):
    """Pure conversion and independent scope checks; no network or file I/O."""
    info = json.loads(credentials.to_json())
    granted = getattr(credentials, "granted_scopes", None)
    if not granted:
        raise ValueError("BLOCKED: server did not confirm granted scopes")
    grants = set(granted)
    if not {EMAIL_SCOPE, COLAB_SCOPE} <= grants:
        raise ValueError("BLOCKED: required Colab and email scopes not granted")
    if grants - ALLOWED_SCOPES:
        raise ValueError("BLOCKED: unexpected Google permissions")
    if any(not info.get(k) for k in ("client_id", "client_secret", "refresh_token")):
        raise ValueError("BLOCKED: no refreshable user credentials")
    return {
        "type": "authorized_user",
        "client_id": info["client_id"],
        "client_secret": info["client_secret"],
        "refresh_token": info["refresh_token"],
        "token_uri": info.get("token_uri", "https://oauth2.googleapis.com/token"),
        "scopes": sorted(grants),
    }


def main():
    target = os.environ.get("AVRORA_ADC_OUTPUT")
    if not target:
        raise SystemExit("BLOCKED: no private output path")
    from importlib import resources
    from google_auth_oauthlib.flow import InstalledAppFlow

    config_path = resources.files("colab_cli").joinpath("oauth_config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    flow = InstalledAppFlow.from_client_config(config, list(REQUESTED_SCOPES))
    flow.redirect_uri = REMOTE_REDIRECT_URI
    url, _ = flow.authorization_url(prompt="consent", token_usage="remote")
    print("\nGoogle will request Colab access and your email address.", file=sys.stderr)
    print("It should NOT ask for broad Google Cloud access.", file=sys.stderr)
    print("If the consent page includes broad Google Cloud/Drive scopes, cancel.", file=sys.stderr)
    print("\nOpen this Google authorization URL in your own browser:", file=sys.stderr)
    print(url, file=sys.stderr)
    code = getpass.getpass("\nPaste the one-time Google code HERE (hidden): ").strip()
    if not code:
        raise SystemExit("BLOCKED: no authorization code")
    flow.fetch_token(code=code)
    adc = build_adc(flow.credentials)
    path = Path(target)
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise SystemExit("BLOCKED: output file absent or insecure")
    path.write_text(json.dumps(adc, sort_keys=True), encoding="utf-8")
    print("Minimal Colab credential created in a private temporary file.", file=sys.stderr)
    print("No tokens or code have been printed.", file=sys.stderr)


if __name__ == "__main__":
    main()
