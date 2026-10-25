#!/usr/bin/env bash
# One-time, owner-operated Drive OAuth authorization; existing Cloud Shell.
# NO new timers, NO ChatGPT Work, NO private research upload, NO live trading.
set -euo pipefail
set +x
umask 077

REPO="vicrex/avrora-colab-launcher"
SECRET="AVRORA_PRIVATE_DRIVE_ADC_JSON_B64"
SCOPE="https://www.googleapis.com/auth/drive"
CLIENT_JSON="${1:-}"

if [[ -z "$CLIENT_JSON" || ! -f "$CLIENT_JSON" ]]; then
  echo "USAGE: bash tools/connect_private_drive_cloud_shell.sh /path/to/desktop_oauth_client.json" >&2
  exit 2
fi
for cmd in gh gcloud python3 base64 mktemp; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED_MISSING_COMMAND_$cmd" >&2; exit 3; }
done
if [[ "$(gh api user --jq .login)" != "vicrex" ]]; then
  echo "BLOCKED_WRONG_GITHUB_ACCOUNT" >&2
  exit 4
fi
python3 - "$CLIENT_JSON" <<'PY'
import json,sys
j=json.load(open(sys.argv[1],encoding="utf-8"))
if not isinstance(j.get("installed"),dict) or not j["installed"].get("client_id"):
    raise SystemExit("BLOCKED_NOT_AN_OAUTH_DESKTOP_CLIENT_FILE")
print("PASS_OWNER_OAUTH_DESKTOP_CLIENT_STRUCTURE")
PY

echo "This explicitly authorizes Google Drive access for your private report archival."
echo "Google full Drive scope covers ALL files accessible to this account, not only AVRORA."
echo "Use a dedicated Google account for this operation if narrower account access is desired."
echo "Never paste the Google authorization code or any secret into a chat or GitHub issue."
echo "Existing Colab credential and existing GitHub hourly cron will not be changed."

temp_dir="$(mktemp -d)"
chmod 700 "$temp_dir"
cleanup() { rm -rf -- "$temp_dir"; }
trap cleanup EXIT
mkdir -p "$temp_dir/gcloud"
chmod 700 "$temp_dir/gcloud"
export CLOUDSDK_CONFIG="$temp_dir/gcloud"
touch "$temp_dir/validated.json"
chmod 600 "$temp_dir/validated.json"

# Exact one-scope request using user's own installed-app OAuth client; do NOT
# add Cloud Platform scopes or overwrite the system ADC configuration.
gcloud auth application-default login \
  --client-id-file="$CLIENT_JSON" \
  --scopes="$SCOPE" \
  --no-launch-browser \
  --disable-quota-project

adc="$CLOUDSDK_CONFIG/application_default_credentials.json"
if [[ ! -s "$adc" ]]; then
  echo "BLOCKED_DRIVE_ADC_NOT_CREATED" >&2
  exit 5
fi
venv="$temp_dir/venv"
python3 -m venv "$venv"
"$venv/bin/python" -m pip --disable-pip-version-check -q install 'google-auth>=2.35,<4' 'requests>=2.31,<3'
"$venv/bin/python" tools/verify_private_drive_adc.py \
  --input "$adc" --output "$temp_dir/validated.json"

if [[ ! -s "$temp_dir/validated.json" ]]; then
  echo "BLOCKED_DRIVE_PROBE_OR_VALIDATED_ADC" >&2
  exit 6
fi
# GitHub CLI encrypts the secret using repo public key; no OAuth token in stdout.
base64 -w 0 "$temp_dir/validated.json" | gh secret set "$SECRET" --app actions --repo "$REPO"
if ! gh secret list --app actions --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$SECRET"; then
  echo "BLOCKED_GITHUB_SECRET_NAME_READBACK" >&2
  exit 7
fi
echo "PASS_PRIVATE_DRIVE_SECRET_INSTALLED_AND_VERIFIED_BY_NAME"
echo "The temporary credentials have been securely marked for deletion on exit."
echo "Next existing GitHub hourly run must independently prove full JSON Drive SHA ACK."
