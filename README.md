# AVRORA Colab Launcher

Public **CPU-only smoke runner**. It contains no private AVRORA source, trading signals, market datasets, Drive IDs, private reports, access tokens, or trading API keys. All jobs enforce REAL=OFF and HOLDOUT=SEALED.

## Current capabilities

- GitHub Actions manually starts an **offline** smoke test without credentials.
- After *user-owned* Google ADC secret configuration, a separate manual mode can run the same harmless smoke in a remote Colab CPU session.
- The schedule is `7 * * * *` (hourly at minute 07 UTC, subject to GitHub scheduling delays), but the job is **disabled** until repository variable `AVRORA_COLAB_AUTOSTART_ENABLED=true` is explicitly set. Do not enable that variable until authenticated remote smoke, evidence and Colab quota review pass.

## Easiest one-time setup: Google Cloud Shell (no Windows installation)

This method uses the free Google Cloud Shell terminal in your browser and
requires **two interactive authorizations by the account owner** (GitHub CLI and Google ADC).
Do not hand the authorization code or credentials to an agent or paste them into chat.

1. Open https://shell.cloud.google.com/?show=terminal using the Google account intended for Colab. If Cloud Shell asks you to authorize access, review and approve the official Google prompt yourself.
2. In the Cloud Shell terminal, run:

```bash
git clone --depth 1 https://github.com/vicrex/avrora-colab-launcher.git
cd avrora-colab-launcher
bash tools/connect_cloud_shell.sh
```

The script is published for review at
[tools/connect_cloud_shell.sh](https://github.com/vicrex/avrora-colab-launcher/blob/main/tools/connect_cloud_shell.sh).
It stops unless the GitHub CLI account is exactly **vicrex**, asks the user to
authorize Google ADC with the four Colab scopes, validates but never prints ADC
secret fields, and uploads the base64-encoded ADC JSON via a **pipe** to GitHub
CLI, which encrypts it for the repository. It confirms **only the secret name**.
The script does not run Colab, enable schedules, fetch private code, or trade.
If `gh` is missing, install GitHub CLI through Cloud Shell's package manager
before rerunning the script. Do not share terminal output containing authorization
codes.

3. Once the script reports **SUCCESS**, tell ChatGPT only `Готово`, without
credentials or screenshots of authorization codes. The assistant can then
run one **manual** `mode=colab` test and verify the remote, no-trading receipt.

No Google Cloud project or billing authorization should be created for this
launcher; stop if Google asks to enable a paid service.

## Test

GitHub → Actions → **AVRORA public Colab launcher** → Run workflow → mode: `local`.

A successful first test shows **4 unit tests passing**, produces a receipt with exactly zero trades and data rows, and uploads a short sanitized artifact. The local test is not proof of remote Colab execution.

## One-time Google authorization for remote CPU smoke (not yet done)

Use a trusted PC and a Google account with minimal rights:

```sh
gcloud auth application-default login --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory
```

The resulting Application Default Credentials JSON contains a **high-value refresh token**. NEVER upload the JSON to this PUBLIC repository, commit it, post it in an issue, or paste it into a chat. Base64 is only transport encoding, not encryption. An account owner must locally encode the entire JSON into GitHub repository **Actions secret** `AVRORA_COLAB_ADC_JSON_B64` (Settings → Secrets and variables → Actions). Protect the repository write access; consider revocation/rotation of the refresh token.

### Windows PowerShell: securely prepare the GitHub secret

After the Google Cloud CLI command above finishes successfully, on **your own Windows PC** run:

```powershell
$adc = Join-Path $env:APPDATA 'gcloud\application_default_credentials.json'
if (-not (Test-Path $adc)) { throw 'ADC file not found; first finish gcloud auth application-default login' }
[Convert]::ToBase64String([IO.File]::ReadAllBytes($adc)) | Set-Clipboard
```

This copies a sensitive credential to the local clipboard. Immediately open
[New GitHub Actions secret](https://github.com/vicrex/avrora-colab-launcher/settings/secrets/actions/new),
enter the name `AVRORA_COLAB_ADC_JSON_B64`, paste the clipboard value into **Secret**, and save.
Then clear the clipboard with `Set-Clipboard -Value ''`.
Do not send the contents to ChatGPT or upload them as a file.

Then manually run the workflow with mode: `colab` and verify the receipt `AVRORA_REMOTE_COLAB_PASS`; check Colab VM teardown. Fail closed if authorization or quota is unavailable.

## Not in scope

There is currently **no authenticated import of private AVRORA strategies or Drive data, no approved strategy adapter, no preregistered replay, no automated profit research, and no actual remote Colab run**. Such integration needs separate scoped permissions, SHA256/readback, deterministic CHECK2 verification and audit trails before scheduling. Free Colab availability is not guaranteed.

The existing separate AVRORA Apps Script every-3-hours trigger is untouched. Its hourly conversion needs a separate authenticated Apps Script update; this public launcher cannot change that timer.

Sources: https://github.com/googlecolab/google-colab-cli and https://docs.github.com/en/billing/concepts/product-billing/github-actions
