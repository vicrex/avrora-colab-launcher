# AVRORA public Colab launcher

Safe, public CPU-only Google Colab smoke runner for the private AVRORA project. **No private AVRORA code, private Google Drive data, trading credentials or trading orders** are contained in this repository. All jobs run with `REAL=OFF` and `HOLDOUT=SEALED`.

## Private P900 Wave/Fibonacci Colab replay — live and gated (2026-10-19)

**Verified end-to-end from GitHub Actions through a real Google Colab CPU session**. [Run #39238496834](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39238496834) has GitHub job conclusion SUCCESS; remote result marker `AVRORA_COLAB_PRIVATE_WAVE_REPLAY_PASS`. Its publicly accessible **aggregate-only** artifact is named `avrora-wave-verified-39238496834`; independently verified receipt SHA256:
`1696a112e7a4ed7ca71297945904103b9d932abc6be24ae0ec9395b8fec2eb1e`.
The artifact contains one JSON summary only, with NO private code, price series, tokens, or per-trade ledger.

The launcher uses two **distinct and verified** secrets:
- `AVRORA_COLAB_ADC_JSON_B64` is the pre-existing least-scope Google Colab API credential.
- `AVRORA_WAVE_SOURCE_DEPLOY_KEY` is the encrypted private half of a GitHub **READ-ONLY deploy key**, scoped to **ONLY** the [dedicated private repo `vicrex/avrora-wave-source`](https://github.com/vicrex/avrora-wave-source). It does not authorize Google Drive or the full private `vicrex/AVRORA` repository. An owner-led Cloud Shell script created this key once and erased its temporary private-key file. GitHub UI verified key read-only status and secret presence.

Frozen P900 discovery inputs (8064 M15 candles across 6 instruments and May/July 2026, not OOS) and original engine archive were byte-reconciled against Google Drive and pinned inside the private source repository. The runner reconstructs the inputs and checks their SHA256, repairs the known portfolio time-accounting bug in both engine and independent checker, executes both on Colab, verifies CHECK2 field parity, and accepts only the SHA256-bound aggregate receipt.

Actual Colab proof, 20 basis points modeled round-trip costs:
| Model | Closed trades | Net20, total 14 days | PF20 |
| --- | ---: | ---: | ---: |
| WAVE_123_CONFIRM | 32 | **−26.458036 USDT** | 0.6419 |
| FIB_618_RETRACE | 106 | **−88.815211 USDT** | 0.6026 |

**Enabled** GitHub Actions variable `AVRORA_PRIVATE_WAVE_ENABLED=true`, verified after success of first real wave replay. [Private-source workflow](https://github.com/vicrex/avrora-colab-launcher/actions/workflows/avrora-private-wave.yml) has best-effort GitHub cron `37 * * * *` for hourly, CPU-only, zero-trading repeat verification. The independent public launcher CPU smoke also remains enabled at `7 * * * *` under its **separate unchanged** variable `AVRORA_COLAB_AUTOSTART_ENABLED=true`.

Important limits: the first **scheduled** (rather than manual) private replay is not yet independently observed. Free-tier Colab quota and schedule timing are not guaranteed. Replaying identical consumed discovery data hourly **does not constitute fresh strategy discovery or OOS evidence**. It is automated regression/reproducibility verification, not autonomous profitability optimization, not native PostOnly fills, not safe live trading. `REAL=OFF`; `HOLDOUT=SEALED`. Do not promote negative models to REAL.

After resolving this infrastructure task, research autonomy still needs private versioned data ingests, novel preregistered wave variants, independent out-of-sample candidate evaluation, and a verified stateful queue. No unapproved strategies or sealed holdout are run here.

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
