# AVRORA public Colab launcher

Safe, public CPU-only Google Colab smoke runner for the private AVRORA project. **No private AVRORA code, private Google Drive data, trading credentials or trading orders** are contained in this repository. All jobs run with `REAL=OFF` and `HOLDOUT=SEALED`.

## Private-source Wave/Fibonacci Colab replay — pending read-only deploy key (2026-10-19)

This pathway **does NOT request access to Google Drive** and requires **no second Google account**. Original data still resides on Google Drive, but byte-identical, SHA256-pinned snapshots live in **private** [vicrex/avrora-wave-source](https://github.com/vicrex/avrora-wave-source), which contains **only** the P900 discovery May/July 2026 CSV (8064 M15 rows for BTC, ETH, SOL, NEAR, LINK, XRP), the frozen 2026-10-18 wave/Fibonacci archive and an explanatory README. No HOLDOUT material or exchange secrets were copied.

[Private research workflow](https://github.com/vicrex/avrora-colab-launcher/actions/workflows/avrora-private-wave.yml) was installed with an hourly `37 * * * *` schedule but its **AVRORA_PRIVATE_WAVE_ENABLED** variable is deliberately **not set**. Thus no private replay is running unattended yet. Its `mode=preflight` was executed with 16/16 tests PASS: [Run 39236857986](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39236857986). The separate hourly public CPU smoke continues unchanged.

**Remaining one-time setup:** the owner of `vicrex` needs to generate a **read-only GitHub deploy key ONLY for `vicrex/avrora-wave-source`** and store its private half as encrypted GitHub Actions secret `AVRORA_WAVE_SOURCE_DEPLOY_KEY` in this launcher. This does NOT grant access to the original private `vicrex/AVRORA` repository, Google Drive or any unrelated repo.

In your existing Google Cloud Shell (`vicfbin@cloudshell`, signed in to GitHub CLI as `vicrex`) execute:

```bash
cd ~/avrora-colab-launcher
git pull --ff-only
bash tools/connect_private_source_cloud_shell.sh
```

The committed script checks source-repository private visibility and GitHub account `vicrex`, creates an Ed25519 deploy key with **read_only=true**, uploads private key directly to GitHub encrypted Actions secret using `gh secret set`, validates by name and erases local key files. No secret contents are printed. A setup attempt through graphical Cloud Shell automation **could not focus the terminal**. As of the last explicit check, the deploy key and `AVRORA_WAVE_SOURCE_DEPLOY_KEY` secret are both absent: do not claim this step complete until verified in GitHub.

After the setup success, run **one manual workflow `mode=wave`** and verify the remote Colab receipt, independent checker, source hashes, and aggregate economic metrics. **Only after that pass**, enable `AVRORA_PRIVATE_WAVE_ENABLED=true`. Repeating immutable discovery input yields no new out-of-sample evidence or newly discovered strategies, so regular executions should later become **change-driven** rather than costly repeats.

Published preflight and remote paths use `REAL=OFF`, `HOLDOUT=SEALED`, private-source SHA256 checks, no private source in public repository, and upload **only aggregate receipt**. The previous P900 discovered wave result is negative (32 WAVE trades, -26.458036 USDT net20; after portfolio timing fix, 106 Fibonacci trades, -88.815211 USDT net20). It is not proof of tradeability.

---

## Deployment status

- Public GitHub Actions offline smoke was confirmed PASS, using free standard public repository runner.
- GitHub schedule: **hourly at minute 07 UTC** (`7 * * * *`).
- Remote Colab **hourly schedule is enabled**: repository Actions variable `AVRORA_COLAB_AUTOSTART_ENABLED=true` verified in GitHub Settings on 2026-10-19. Jobs run on GitHub's best-effort cron `7 * * * *` (may be delayed or skipped by provider).
- **First authenticated real remote Colab smoke PASSED** on 2026-10-19: [GitHub Actions run #5](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39225306888), commit `bb87e58`, receipt SHA256 validated, `AVRORA_REMOTE_COLAB_PASS`, zero orders/data. The GitHub Actions secret is installed by user and never committed. Free Colab uptime/quotas are not guaranteed.
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
directly from a private temporary Cloud Shell file. The Google consent completed and the real remote Colab smoke passed on 2026-10-19. This confirms CPU smoke with narrow scopes; it does not grant Drive research-data access.

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
- Scheduled remote CPU-only smokes are **enabled hourly** with `AVRORA_COLAB_AUTOSTART_ENABLED=true` following successful Google OAuth and remote test #5. The first actual scheduled event has not yet been observed or verified.

**Current boundary:** this is infrastructure smoke testing only, **not**
an automated replay of AVRORA strategies. Integrating the private strategy
queue and data access needs separate scoped ingestion, audit artifacts,
SHA256/readback, verifier, and safety review.

### References

- [Official Colab CLI Auth implementation](https://github.com/googlecolab/google-colab-cli/blob/main/src/colab_cli/auth.py)
- [Official Colab CLI operator guide](https://github.com/googlecolab/google-colab-cli/blob/main/skills/colab-operator/SKILL.md)
- [Google Cloud SDK ADC scopes](https://cloud.google.com/sdk/gcloud/reference/auth/application-default/login)
