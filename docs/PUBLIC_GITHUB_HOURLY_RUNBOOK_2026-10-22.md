## 2026-10-23 — why hourly discovery disappears, and fixed fallback route

**Verified root cause by inspecting the 21-Oct operational GAS runbook and current public YAML:**
- GitHub `schedule: 7 * * * *` on `colab-launcher.yml` is best-effort; the actual events have multi-hour gaps. A successful run after a gap proves one recovery, not an hourly SLA.
- The existing Google Apps Script `avroraHourlyTick` already POSTs `workflow_dispatch` to `avrora-private-wave.yml` with `ref=main, inputs.mode=full13`. Its local 55-minute cooldown and GitHub recent-run check suppress some duplicates. It does **not** dispatch `colab-launcher.yml`.
- BEFORE this change the scheduled 64-case job `multifamily-shadow-scheduled` existed only in `colab-launcher.yml` with `if: github.event_name == 'schedule'`. Thus during missed cron hours, GAS could recover FULL13/cache but **NOT** the actual 64-case hypothesis search. Repeated cache results looked green yet discovery had stopped.

**Routing change:** in `avrora-private-wave.yml`, direct `workflow_dispatch(mode=full13)` from the existing GAS now also invokes the **existing** `multifamily-sweep-smoke.yml` through reusable workflow_call with inherited GitHub encrypted secrets. On `workflow_call` (parent scheduled route), that new job is SKIPPED: the parent continues to own the one original multifamily scheduled job. Manual `mode=preflight` and `mode=wave` never invoke new research. Research is still pinned private read-only, 64 frozen historical shadow cases, `REAL=OFF`, `HOLDOUT=SEALED`, without maker or OOS claims. No extra cron, trigger, token, service, Drive scope, or ChatGPT Work. A second GAS timer must NOT be installed.

**Regression:** `tests/test_gas_shadow_fallback_route.py` checks routing, one unchanged public cron, workflow_call, pinned private code+data SHAs, REAL/HOLDOUT invariants. The existing public `safety-smoke` now runs offline on main pushes affecting these routes; `RUN_REMOTE=false` for push (no Colab credential access). The `workflow_dispatch mode=local` offline path remains.

**Acceptance, required before claiming a fix is proven live:**
1. Main branch GitHub Actions push safety-smoke SUCCESS and 3 new routing contract tests PASS, exact commit SHA.
2. Existing GAS execution must be **Time-driven** (not user manual); record timestamp `DISPATCH_ACCEPTED_HTTP_204` or `SKIP_RECENT_GITHUB_RUN`.
3. Match a dispatched `avrora-private-wave.yml` run with the same hour; require both child jobs: `private-wave` + `multifamily-shadow-first64`, with 64 actual P816 observations and SHA artifact.
4. Verify next two unattended hours contain research (either cron main or GAS fallback) and no double-computed same-hour batch. Without this evidence classify `ROUTING_PATCH_DEPLOYED_UNVERIFIED_HOURLY`.
5. Final economic correctness still BLOCKED by missing multifamily independent CHECK2, private full-JSON persistence, new prospective OOS and actual maker-fill/portfolio replay. Never promote to SIM/REAL.

# AVRORA — public GitHub hourly runbook (2026-10-22)

## MANDATORY EXECUTION TOPOLOGY (user-confirmed, 2026-10-22)

**ALL AVRORA launches, CI/testing, researcher jobs, Full13 Colab orchestration and independent CHECK2 happen from the PUBLIC GitHub repository [vicrex/avrora-colab-launcher](https://github.com/vicrex/avrora-colab-launcher), or through an explicitly reviewed job dispatched from that public executor.** The private [vicrex/AVRORA](https://github.com/vicrex/AVRORA) is source-of-truth for private code, private graph, issues and the handoff; its Actions runner is **NOT a prerequisite and never a reason to declare public launches blocked**.

For PR #62 private graph importer, run offline verification in the **existing public** launcher with a reviewed read-only pinned checkout/approved limited adapter; never copy private code/graph/data into a PUBLIC artifact. Only then merge the private PR and deliver new private graph snapshot via Drive with SHA readback and separate ACK. Do not silently call the graph updated merely because public calculations finished. No ChatGPT Work, no new timers, REAL OFF, HOLDOUT SEALED.

## Immutable operating constraints
- Execution via existing public GitHub Actions only; **never** ChatGPT Work, Cloud Browser, Computer Use, new timers, paid services, or live trading.
- REAL=OFF; HOLDOUT=SEALED. Do not open holdout. Never claim maker fills, OOS, profitability or autonomy without evidence.
- Never print credentials, private checkout contents, raw market data or sensitive logs in public Actions.
- No blind reruns for private pre-runner failures; steps=[] and runner_id=0 imply investigate runner/platform before Python changes.

## Repositories and entry points
- Public scheduler: https://github.com/vicrex/avrora-colab-launcher
- Workflow: .github/workflows/colab-launcher.yml (workflow ID 389014912), existing cron `7 * * * *`; no additional clocks.
- Scheduled job `full13-scheduled` calls reusable `.github/workflows/avrora-private-wave.yml`, job `private-wave`.
- Private pipeline: https://github.com/vicrex/AVRORA (research-ingress-drain/CI).
- Private SHA-pinned read-only dataset source in reusable workflow: vicrex/avrora-wave-source; do not reveal its contents.
- Drive delivery folder ID: 1MXTBe21rTm1fVYzjUQ6NNf8cJzOQ0NKX.

## Hourly observation and triage
1. List workflow runs for workflow 389014912, filter event=schedule; record run_id, attempt, created_at, status, conclusion, and head SHA. If no new scheduled run >90 minutes, mark SCHEDULE_TRIGGER_MISSING. GitHub scheduled events can be delayed or dropped; do not conflate a missing event with job-level `if` skips.
2. For each new run inspect jobs `full13-scheduled` and `private-wave`, step conclusions and logs. Inspect whether workflow is disabled and whether default branch contains the cron. Check repository Actions permissions, workflow enabled status, GitHub incident status, and default-branch activity before modifying YAML.
3. Reusable workflow has gate `vars.AVRORA_PRIVATE_WAVE_ENABLED == 'true' || vars.AVRORA_FULL13_ENABLED == 'true'` for schedule. If unset, scheduled job may be skipped even though event exists. Verify actual repository variable values, not assumptions; prefer explicit FULL13 enablement only after confirming authorization and secrets. Do not expose variable values if sensitive.
4. Distinguish fresh FULL13 Colab execution from SHA-keyed cache-hit using actual steps and receipt; `success` alone does not prove fresh compute. Record candidate and failure codes.
5. Check FULL13 dataset: 13 periods (12 discovery + May), 6 symbols, 78 series, 69,576 M15 bars, 220 warmup bars per period, SHA pin and independent CHECK2. Reject missing/partial evidence.
6. For private vicrex/AVRORA Actions research-ingress-drain/CI inspect runner_id and steps; if steps=[]/runner_id=0 label PRE_RUNNER_BLOCKED. Prior retry run 39504593892 attempt 2 failed before steps. Do not rerun without changed condition.
7. Discover artifacts `avrora-full13-vector-delta-<run>-<attempt>` and optionally `avrora-full13-verified-*`. Confirm absent from Drive before upload. Deterministic names: `HOUR_<run>_V1_FULL13_VECTOR_DELTA.zip`, `HOUR_<run>_V1_FULL13_VERIFIED_RECEIPT.zip`.
8. Use GitHub download_workflow_artifact; pass **string** `result.file_uri.file_id` as Google_Drive.upload_file(file_uri=...,parent_folder_id=folder_id,file_name=...,mime_type='application/zip'). Never pass file_uri object.
9. After upload read Drive metadata and **raw ZIP bytes** back; compute SHA256 and compare against GitHub artifact.digest (normalize `sha256:` prefix). Only mark DELIVERY_VERIFIED on exact match. Otherwise DELIVERY_UNVERIFIED/BLOCKED; no duplicate uploads. If readback or digest unavailable, do not assert verification.
10. Notify only for newly confirmed delivery, new failure, >90 minute missing schedule, or newly recovered private runner. Include run ID, event, candidate, cached/fresh, Drive file ID, SHA and URL where available.

## Prior observed evidence, not new proof
- Scheduled run 39474595117: successful fresh FIVE_WAVE_07.
- Scheduled run 39506465672: successful cached FIVE_WAVE_11. Delta already in Drive file 1unOm17dHGpgcu8MfR6tfSWm68doqnbfz, ZIP SHA256 3a8c12454fb4919db426e362d2cafd29d2ba0030f85bae05071fca35138607f2; **never upload duplicate**.
- Run 39685011449: previously reported last scheduled run, subsequent >90 minute gap; recheck live state.
- No claim of end-to-end autonomy until two complete unattended cycles verified.

## Incident decision tree
- No schedule event: inspect enabled workflow/default branch/cron/platform; do not edit Python or claim gate caused missing event.
- Event exists, job skipped: inspect reusable workflow `if` and repository vars.
- Job starts, Colab fails: inspect sanitized logs, credential presence, SHA pin, CHECK2, 69,576 bars and source validation; preserve explicit failure.
- Artifact exists, Drive missing: transfer once; independently read back and hash.
- Private runner absent: informational private-repository condition only; do not block or rerun the PUBLIC executor. Route tests/research through public Actions using reviewed pinned source checkout.

## Change log
- 2026-10-22: audited current public workflow source. Existing cron is `7 * * * *`; reusable private-wave job has variable gate. No confirmed root cause for missing event from YAML alone. This runbook documents the verification and repair protocol. No workflow code or timer changed by this documentation commit.

## Bybit forward M15 capture: US-hosted runner blocked (2026-10-22)

Public launcher [run 39739961146](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39739961146) executed read-only six-symbol M15 collector; synthetic offline test PASS, actual `api.bybit.com/v5/market/kline` returned HTTP 403 **before any data**. Official [Bybit V5 integration guide](https://bybit-exchange.github.io/docs/v5/guide) states US/Mainland-China IPs receive 403. Public GitHub-hosted runners often egress from the US; do not try third-party proxies or region bypass. This is **not** a trading signal failure and generated **zero approved forward M15 records**. `AVRORA_FORWARD_CAPTURE_ENABLED` must remain unset/false on US GitHub-hosted runners. The existing hourly `7 * * * *` FULL13 job is unchanged. Collect only via legitimate authorized data/runner later.

Separate [run 39739308363](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39739308363) verified the existing public runner requires a **dedicated** read-only private AVRORA code checkout key: `BLOCKED_PRIVATE_AVRORA_READONLY_CODE_KEY_MISSING`. The existing `AVRORA_WAVE_SOURCE_DEPLOY_KEY` is scoped to the DATA repo and must NOT be assumed to authorize source code. Zero private code was checked out on that run. Private [PR #64](https://github.com/vicrex/AVRORA/pull/64) contains SHA-exact migrated SQ05 engine/checkers and seven original tests; code parity by blob is established but runner test still BLOCKED. No real orders, HOLDOUT sealed, no new schedule, no Work.

