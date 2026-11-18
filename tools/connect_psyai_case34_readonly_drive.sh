#!/usr/bin/env bash
# ONE-TIME owner-operated OAuth setup for privately reading exact CASE34.
# This file NEVER reads the CASE34 text itself, prints keys or modifies AVRORA.
# Google OAuth consent is the ONE unavoidable user action; no new Colab login.
set -euo pipefail
set +x
umask 077

REPO='vicrex/avrora-colab-launcher'
PRIVATE='vicrex/PSYAI_PROFESSIONAL'
BRANCH='fix/psyai-case34-e2e-receipts-20261118'
SECRET='PSYAI_CASE34_DRIVE_READONLY_ADC_B64'
SCOPE='https://www.googleapis.com/auth/drive.readonly'
CLIENT_JSON="${1:-}"

if [[ -z "$CLIENT_JSON" || ! -s "$CLIENT_JSON" ]]; then
  echo 'BLOCKED_NEED_EXISTING_OAUTH_DESKTOP_CLIENT_JSON: usage: bash tools/connect_psyai_case34_readonly_drive.sh /path/to/oauth_desktop_client.json' >&2
  exit 2
fi
for cmd in gh gcloud git python3 base64 mktemp grep; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "BLOCKED_MISSING_TOOL_$cmd" >&2; exit 3;
  }
done
if [[ "$(gh api user --jq .login 2>/dev/null)" != 'vicrex' ]]; then
  echo 'BLOCKED_WRONG_GITHUB_IDENTITY' >&2
  exit 4
fi
gh api "repos/$REPO" --jq .full_name >/dev/null
gh api "repos/$PRIVATE" --jq .full_name >/dev/null

if gh secret list --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$SECRET"; then
  echo 'BLOCKED_SECRET_ALREADY_INSTALLED_DO_NOT_OVERWRITE'
  exit 5
fi

python3 - "$CLIENT_JSON" <<'PY'
import json,sys
try:
    entry=json.load(open(sys.argv[1],encoding="utf-8"))
    installed=entry.get("installed")
    if not isinstance(installed,dict) or not installed.get("client_id") or not installed.get("client_secret"):
        raise ValueError()
except Exception:
    raise SystemExit("BLOCKED_INVALID_EXISTING_DESKTOP_OAUTH_CLIENT") from None
print("PASS_OAUTH_CLIENT_STRUCTURE")
PY

echo 'ATTENTION: drive.readonly can read ALL files accessible in this Google account.'
echo 'It cannot write/delete Drive files. For a narrower scope, use a separate Google account'
echo 'where ONLY the intended CASE34 file was privately shared with that account.'
echo 'Owner must explicitly approve the Google consent screen. No token is pasted into chat.'

temp="$(mktemp -d)"
chmod 700 "$temp"
cleanup() {
  unset PSYAI_CASE34_PRIVATE_DRIVE_ADC_B64 || true
  rm -rf -- "$temp"
}
trap cleanup EXIT
mkdir -m 700 "$temp/gcloud" "$temp/work"
export CLOUDSDK_CONFIG="$temp/gcloud"
export PYTHONDONTWRITEBYTECODE=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

echo 'GOOGLE_OWNER_CONSENT_REQUIRED_ONCE'
gcloud auth application-default login \
  --client-id-file="$CLIENT_JSON" \
  --scopes="$SCOPE" \
  --no-launch-browser \
  --disable-quota-project

raw_adc="$CLOUDSDK_CONFIG/application_default_credentials.json"
if [[ ! -s "$raw_adc" ]]; then
  echo 'BLOCKED_ADC_NOT_CREATED'
  exit 6
fi
validated="$temp/readonly-verified.json"
# gcloud may not serialize the scope field: explicitly bind this local
# credential declaration to the already user-approved scope; validate the
# REAL token scope via the private preflight before storing any GitHub secret.
python3 - "$raw_adc" "$validated" <<'PY'
import json,os,sys
scope="https://www.googleapis.com/auth/drive.readonly"
raw=json.load(open(sys.argv[1],encoding="utf-8"))
keys=("type","client_id","client_secret","refresh_token")
if raw.get("type")!="authorized_user" or any(not isinstance(raw.get(k),str) or not raw[k] for k in keys):
    raise SystemExit("BLOCKED_ADC_NOT_AUTHORIZED_USER")
safe={k:raw[k] for k in keys}
safe["token_uri"]=raw.get("token_uri","https://oauth2.googleapis.com/token")
safe["scopes"]=[scope]
with open(sys.argv[2],"w",encoding="utf-8") as dest:
    json.dump(safe,dest,separators=(",",":"),sort_keys=True)
os.chmod(sys.argv[2],0o600)
print("PASS_READONLY_OAUTH_CREDENTIAL_FORMAT_NO_VALUES")
PY
python3 -m venv "$temp/venv"
"$temp/venv/bin/python" -m pip install -q 'google-auth==2.35.0' 'requests==2.32.3'
gh repo clone "$PRIVATE" "$temp/work/psyai" -- --quiet --depth=1 --single-branch --branch "$BRANCH"
preflight="$temp/work/psyai/tools/case34_private_drive_preflight.py"
if [[ ! -s "$preflight" ]]; then
  echo 'BLOCKED_PINNED_PRIVATE_CASE34_PREFLIGHT_MISSING'
  exit 7
fi

export PSYAI_CASE34_PRIVATE_DRIVE_ADC_B64
PSYAI_CASE34_PRIVATE_DRIVE_ADC_B64="$(base64 -w 0 "$validated")"
"$temp/venv/bin/python" -B "$preflight" --receipt "$temp/readonly-proof.json"
unset PSYAI_CASE34_PRIVATE_DRIVE_ADC_B64
"$temp/venv/bin/python" - "$temp/readonly-proof.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1],encoding="utf-8"))
assert (j.get("status")=="PASS" and j.get("source_verified") is True
        and j.get("turns")==34 and j.get("client_turns")==17
        and j.get("therapist_turns")==17 and j.get("source_uploaded") is False
        and j.get("model_started") is False), "BLOCKED_SOURCE_GATE_NOT_PASS"
print("PASS_REAL_PRIVATE_CASE34_SOURCE_SHA_AND_17_17")
PY

# gh encrypts the secret for GitHub Actions. Never print it, persist it
# in source control, or send it into ChatGPT.
base64 -w 0 "$validated" | gh secret set "$SECRET" --repo "$REPO"
if ! gh secret list --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$SECRET"; then
  echo 'BLOCKED_GITHUB_SECRET_READBACK_FAILED'
  exit 8
fi
echo 'PASS_PSYAI_CASE34_READONLY_SECRET_CREATED_GITHUB_NO_SOURCE_UPLOAD'
echo 'NEXT: Github Actions -> PsyAI CASE34 secure source readiness (NO GPU) -> Run workflow (main), once.'
