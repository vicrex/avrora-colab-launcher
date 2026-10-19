# AVRORA public Colab launcher

Safe, public CPU-only Google Colab smoke runner for the private AVRORA project. **No private AVRORA code, private Google Drive data, trading credentials or trading orders** are contained in this repository. All jobs run with `REAL=OFF` and `HOLDOUT=SEALED`.

## Deployment status

- Public GitHub Actions offline smoke was confirmed PASS, using free standard public repository runner.
- GitHub schedule: **hourly at minute 07 UTC** (`7 * * * *`).
- Remote Colab schedule remains **disabled** by repository variable `AVRORA_COLAB_AUTOSTART_ENABLED` (unset).
- Remote Google authorization must be completed once, then **one manual remote smoke must pass** before enabling the unattended Colab schedule. No real remote Colab smoke is yet verified. Free Colab uptime/quotas are not guaranteed.
- Existing separate AVRORA Google Apps Script timer is untouched.

## One-time Google authorization — least-privileged trial

We discovered the original `gcloud auth application-default login` method requests a broad Google Cloud `cloud-platform` permission as well as Colab. **Do not authorize that broad request** just to launch Colab.

An alternative one-time authorization script requests **only**:
- `openid`
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/colaboratory`

This narrower method uses the public installed-app OAuth client bundled in Google's
[google-colab-cli 0.7.4](https://github.com/googlecolab/google-colab-cli),
and writes the approved refresh token as an encrypted GitHub Actions secret
directly from a private temporary Cloud Shell file. It is **experimental**:
while the restricted consent parameters and offline scope checks have been written,
they still require real Google OAuth and remote Colab validation. The server may
reject the narrower grant; if so, stop rather than silently broadening permissions.

1. On your existing Google Cloud Shell terminal, **cancel** any pending broad
   `Google Auth Library` consent and press **Ctrl+C** if the previous
   `gcloud auth application-default login` is still awaiting a code.
2. From the existing cloned repository directory run:

```sh
cd ~/avrora-colab-launcher
git pull --ff-only
bash tools/connect_cloud_shell.sh
```

3. The script confirms GitHub user `vicrex`, prepares a private Python environment,
   prints a Google authorization URL, then asks for a one-time code
   **with hidden terminal input**. Verify the consent page only requests
   Colab and your email. If it shows broad Google Cloud or Drive access,
   cancel; do not grant unexpected scopes.
4. When successful it prints exactly
   `SUCCESS: encrypted GitHub Actions secret name verified: AVRORA_COLAB_ADC_JSON_B64`.
   The secret should appear by **name only** under
   [Settings → Actions secrets](https://github.com/vicrex/avrora-colab-launcher/settings/secrets/actions).
   Never paste codes, refresh tokens or ADC JSON into ChatGPT or an issue.

The GitHub CLI may store its account token on your Cloud Shell home directory:
after setup, consider running `gh auth logout --hostname github.com`.
The temporary Google ADC JSON is automatically erased when the script finishes.

## How the workflow runs

- GitHub Actions manual `mode=local` runs 4 offline smoke tests, plus 6
  minimum-scope OAuth contract tests, and emits a zero-orders SHA256 receipt.
- GitHub Actions manual `mode=colab` uses the encrypted repository secret,
  runs `colab --auth=adc run smoke.py`, then tears down the runtime.
- Scheduled runs are gated off until Google OAuth and a real remote smoke pass.
  Only then should `AVRORA_COLAB_AUTOSTART_ENABLED=true` be configured
  under GitHub repository Actions variables.

**Current boundary:** this is infrastructure smoke testing only, **not**
an automated replay of AVRORA strategies. Integrating the private strategy
queue and data access needs separate scoped ingestion, audit artifacts,
SHA256/readback, verifier, and safety review.

### References

- [Official Colab CLI Auth implementation](https://github.com/googlecolab/google-colab-cli/blob/main/src/colab_cli/auth.py)
- [Official Colab CLI operator guide](https://github.com/googlecolab/google-colab-cli/blob/main/skills/colab-operator/SKILL.md)
- [Google Cloud SDK ADC scopes](https://cloud.google.com/sdk/gcloud/reference/auth/application-default/login)
