#!/usr/bin/env bash
# One-time user-authorized Colab OAuth setup from Google Cloud Shell.
# EXPERIMENTAL narrowed scopes (Colab + email + openid), no broad cloud-platform.
# Prints only the public authorization URL; NEVER prints tokens/secret JSON.
set -euo pipefail
set +x
umask 077

readonly REPO="vicrex/avrora-colab-launcher"
readonly SECRET="AVRORA_COLAB_ADC_JSON_B64"

echo "AVRORA: one-time Colab authorization with MINIMAL requested scopes."
echo "GitHub: ${REPO}. REAL=OFF, HOLDOUT=SEALED. No trading or runs."
echo "This OAuth method is experimental until the real remote Colab smoke succeeds."

for cmd in gh python3 base64; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "MISSING_COMMAND: $cmd" >&2
    exit 2
  fi
done

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  echo "GitHub CLI interactive login needed."
  gh auth login --hostname github.com --git-protocol https --web --scopes repo
fi
login="$(gh api user --jq .login)"
if [[ "$login" != "vicrex" ]]; then
  echo "BLOCKED_WRONG_GITHUB_ACCOUNT (expected vicrex)." >&2
  exit 3
fi
echo "Verified GitHub owner: vicrex."

# Isolate one-time dependency installation; do NOT touch Cloud Shell system Python.
venv="$HOME/.local/share/avrora-colab-auth-venv"
if [[ ! -f "$venv/bin/python" ]]; then
  python3 -m venv "$venv"
fi
"$venv/bin/python" -m pip --disable-pip-version-check -q install 'google-colab-cli==0.7.4'

# Script writes a secret-containing authorized-user ADC JSON ONLY to private temp.
tmp_adc="$(mktemp)"
chmod 0600 "$tmp_adc"
trap 'rm -f "$tmp_adc"' EXIT
export AVRORA_ADC_OUTPUT="$tmp_adc"

echo "Opening Google authorization for Colab + email only."
echo "If Google asks for broad Google Cloud access, CANCEL; do not consent."
"$venv/bin/python" tools/authorize_colab_minimal.py

if [[ ! -s "$tmp_adc" ]]; then
  echo "BLOCKED_ADC_MISSING" >&2
  exit 5
fi

# Copy encrypted through GitHub CLI; neither base64 nor token printed/logged.
base64 -w 0 "$tmp_adc" | gh secret set "$SECRET" --app actions --repo "$REPO"

if ! gh secret list --app actions --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$SECRET"; then
  echo "BLOCKED_SECRET_READBACK_FAILED" >&2
  exit 6
fi

echo "SUCCESS: encrypted GitHub Actions secret name verified: ${SECRET}."
echo "Secret data erased from local temporary file upon script exit."
echo "No remote Colab run was started; hourly remote job remains gated."
echo "For Cloud Shell hygiene: gh auth logout --hostname github.com"
