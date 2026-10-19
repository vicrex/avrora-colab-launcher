#!/usr/bin/env bash
# One-time Drive read-only permission: distinct from Colab session secret.
set -euo pipefail
set +x
umask 077
REPO="vicrex/avrora-colab-launcher"
SECRET="AVRORA_DRIVE_READONLY_ADC_JSON_B64"

for tool in gh python3 base64; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "BLOCKED_COMMAND_NOT_FOUND: $tool" >&2; exit 2
  fi
done
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  gh auth login --hostname github.com --git-protocol https --web --scopes repo
fi
if [[ "$(gh api user --jq .login)" != "vicrex" ]]; then
  echo "BLOCKED_GITHUB_ACCOUNT_MUST_BE_VICREX" >&2; exit 3
fi
echo "Verified GitHub owner: vicrex"
venv="$HOME/.local/share/avrora-colab-auth-venv"
if [[ ! -f "$venv/bin/python" ]]; then
  python3 -m venv "$venv"
fi
"$venv/bin/python" -m pip --disable-pip-version-check -q install 'google-colab-cli==0.7.4'
file="$(mktemp)"
chmod 0600 "$file"
trap 'rm -f "$file"' EXIT
export AVRORA_DRIVE_ADC_OUTPUT="$file"
"$venv/bin/python" tools/authorize_drive_readonly.py
base64 -w 0 "$file" | gh secret set "$SECRET" --app actions --repo "$REPO"
if ! gh secret list --app actions --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$SECRET"; then
  echo "BLOCKED_SECRET_NAME_READBACK" >&2; exit 4
fi
echo "SUCCESS: encrypted Actions secret created and verified by NAME: $SECRET"
echo "Google Drive token scope: read-only; Colab token remains unchanged."
echo "The private local credential file will be removed on script exit."
