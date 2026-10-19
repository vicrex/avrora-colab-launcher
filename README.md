# AVRORA Colab Launcher

Public **CPU-only smoke runner**. It contains no private AVRORA source, trading signals, market datasets, Drive IDs, private reports, access tokens, or trading API keys. All jobs enforce REAL=OFF and HOLDOUT=SEALED.

## Current capabilities

- GitHub Actions manually starts an **offline** smoke test without credentials.
- After *user-owned* Google ADC secret configuration, a separate manual mode can run the same harmless smoke in a remote Colab CPU session.
- The schedule is `7 */3 * * *` (every three hours UTC), but the job is **disabled** until repository variable `AVRORA_COLAB_AUTOSTART_ENABLED=true` is explicitly set. Do not enable that variable until authenticated remote smoke, evidence and Colab quota review pass.

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

The existing AVRORA Apps Script every-3-hours trigger is untouched.

Sources: https://github.com/googlecolab/google-colab-cli and https://docs.github.com/en/billing/concepts/product-billing/github-actions
