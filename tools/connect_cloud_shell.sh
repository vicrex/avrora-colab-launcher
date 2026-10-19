#!/usr/bin/env bash
# Human-in-the-loop one-time Colab ADC setup from Google Cloud Shell.
# Review this file before execution. It NEVER prints the ADC JSON, refresh token,
# base64-encoded secret, or GitHub authentication token.
set -euo pipefail
set +x
umask 077

readonly REPO="vicrex/avrora-colab-launcher"
readonly SECRET="AVRORA_COLAB_ADC_JSON_B64"
readonly ADC="${CLOUDSDK_CONFIG:-$HOME/.config/gcloud}/application_default_credentials.json"

echo "AVRORA: interactive one-time Google Colab authorization."
echo "Target repository: ${REPO} (PUBLIC launcher)."
echo "Credentials go only to this repository's encrypted Actions secret."
echo "Keep REAL=OFF; HOLDOUT=SEALED. This script will NOT run Colab or enable schedules."

for cmd in gcloud gh python3 base64; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "MISSING_COMMAND: $cmd" >&2
    if [[ "$cmd" == "gh" ]]; then
      echo "Cloud Shell may install GitHub CLI with: sudo apt-get update && sudo apt-get install -y gh" >&2
    fi
    exit 2
  fi
done

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  echo "GitHub CLI needs an interactive device/browser sign-in."
  gh auth login --hostname github.com --git-protocol https --web --scopes repo
fi

login="$(gh api user --jq .login)"
if [[ "$login" != "vicrex" ]]; then
  echo "BLOCKED_WRONG_GITHUB_ACCOUNT (expected vicrex)." >&2
  exit 3
fi
echo "Verified GitHub owner: vicrex."

if [[ -e "$ADC" ]]; then
  echo "Existing local Google ADC file detected. This setup may replace it." >&2
  read -r -p "Proceed with Google reauthorization? Type YES: " existing_ok
  if [[ "$existing_ok" != "YES" ]]; then
    echo "Cancelled. No repository secrets changed."
    exit 4
  fi
fi

echo "Google will show an authorization URL and request a one-time code."
echo "Choose the Google account that should own the Colab sessions."
echo "NEVER share the returned code or ADC JSON in ChatGPT."
gcloud auth application-default login --no-launch-browser --disable-quota-project \
  --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory

if [[ ! -f "$ADC" ]]; then
  echo "BLOCKED_ADC_NOT_FOUND" >&2
  exit 5
fi

python3 - "$ADC" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
assert data.get("type") == "authorized_user", "ADC must use authorized_user"
assert all(isinstance(data.get(k), str) and data[k]
           for k in ("client_id", "client_secret", "refresh_token")), "Incomplete ADC"
print("Validated local Google ADC user-credential shape (values NOT printed).")
PY

# gh CLI encrypts the secret locally using the target repository's public key.
# The credential is read through stdin, not shown in shell arguments/logs.
base64 -w 0 "$ADC" | gh secret set "$SECRET" --app actions --repo "$REPO"

if ! gh secret list --app actions --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$SECRET"; then
  echo "BLOCKED_SECRET_READBACK_FAILED" >&2
  exit 6
fi
echo "SUCCESS: encrypted GitHub Actions secret name verified: ${SECRET}."
echo "No Colab run started. Schedule remains disabled until separately tested."
echo "Your Google ADC now also exists on Cloud Shell's persistent home volume."
echo "You may delete the LOCAL COPY after this upload, without revoking the remotely stored refresh token:"
echo "  rm -f \"$HOME/.config/gcloud/application_default_credentials.json\""
echo "You may sign out of the local GitHub CLI when finished: gh auth logout --hostname github.com"
