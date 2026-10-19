#!/usr/bin/env bash
# One-time, user-authorized, read-only deploy key for a DEDICATED private source repo.
# Public launcher can read ONLY vicrex/avrora-wave-source, not the rest of AVRORA.
# Run interactively on your own Google Cloud Shell after signing into 'vicrex' gh CLI.
set -euo pipefail
set +x
umask 077

SOURCE_REPO="vicrex/avrora-wave-source"
PUBLIC_REPO="vicrex/avrora-colab-launcher"
SECRET_NAME="AVRORA_WAVE_SOURCE_DEPLOY_KEY"
TITLE="AVRORA-COLAB-WAVE-READONLY-20261019"
created_id=""
temp="$(mktemp -d)"
cleanup() {
  code=$?
  if [[ $code -ne 0 && -n "$created_id" ]]; then
    gh api --method DELETE "repos/$SOURCE_REPO/keys/$created_id" >/dev/null 2>&1 || true
  fi
  rm -rf "$temp"
}
trap cleanup EXIT

for cmd in gh ssh-keygen; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED_MISSING_COMMAND_$cmd"; exit 2; }
done
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  echo "GitHub CLI interactive login needed for the repository owner."
  gh auth login --hostname github.com --git-protocol https --web --scopes repo
fi
if [[ "$(gh api user --jq .login)" != "vicrex" ]]; then
  echo "BLOCKED_WRONG_GITHUB_ACCOUNT"; exit 3
fi
if [[ "$(gh api "repos/$SOURCE_REPO" --jq .private)" != "true" ]]; then
  echo "BLOCKED_SOURCE_NOT_PRIVATE"; exit 4
fi
existing="$(gh api "repos/$SOURCE_REPO/keys" --jq ".[] | select(.title == \"$TITLE\") | .id")"
if [[ -n "$existing" ]]; then
  echo "BLOCKED_READONLY_KEY_ALREADY_EXISTS: Do not generate duplicate; inspect settings."
  exit 5
fi

ssh-keygen -t ed25519 -q -N '' -C "$TITLE" -f "$temp/deploy"
status="$(gh api --method POST "repos/$SOURCE_REPO/keys" \
  -f title="$TITLE" -f key="$(cat "$temp/deploy.pub")" -F read_only=true \
  --jq '[.id,.read_only] | join(" ")')"
read -r created_id is_read_only <<<"$status"
if [[ ! "$created_id" =~ ^[0-9]+$ || "$is_read_only" != "true" ]]; then
  echo "BLOCKED_KEY_NOT_READONLY"; exit 6
fi
echo "Dedicated private GitHub repository accepted a READ-ONLY deploy key."

gh secret set "$SECRET_NAME" --app actions --repo "$PUBLIC_REPO" < "$temp/deploy"
if ! gh secret list --app actions --repo "$PUBLIC_REPO" --json name --jq '.[].name' | grep -Fxq "$SECRET_NAME"; then
  echo "BLOCKED_SECRET_READBACK_FAILED"; exit 7
fi
echo "SUCCESS: restricted GitHub deploy key stored as an encrypted Actions secret."
echo "Scope: read-only access to vicrex/avrora-wave-source ONLY."
echo "Secret private-key material removed from Cloud Shell temporary directory."
echo "No trading or remote wave research job was started."
