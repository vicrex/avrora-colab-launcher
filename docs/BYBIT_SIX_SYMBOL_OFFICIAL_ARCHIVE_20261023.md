# AVRORA — official Bybit six-symbol archive ingest v2 (2026-10-23)

Status: **public code patched and offline-tested; first new source day 2026-10-23 UTC can ONLY appear after 2026-10-24 UTC starts.** A completed GitHub run with publication WAIT means NO source was obtained. Do not mislabel data as realtime/OOS/live fill.

## What changed

- Exact official folders: `https://public.bybit.com/trading/{BTCUSDT,ETHUSDT,SOLUSDT,NEARUSDT,LINKUSDT,XRPUSDT}/` with filename `SYMBOLYYYY-MM-DD.csv.gz`. **Trading derivative tick archives, NOT spot, not orderbook L2.**
- `tools/bybit_official_archive_transport.py --symbol BTCUSDT --day YYYY-MM-DD --output-dir official_source` downloads ONE symbol/day from the allowlist. Other five analogous. `--symbol` defaults to legacy SOL for compatibility.
- Streaming gzip integrity check, CRC, file SHA256, manifest SHA256, exact original URL/redirect protection, resource ceilings, UTC `archive_received_at_utc`, `causally_usable_not_before_utc`, `signal_realtime_available=false`, `new_oos_proven=false`, `fill_proven=false`; no REST, proxies, VPN, credentials or orders.
- Missing archive HTTP404 -> `WAIT_OFFICIAL_ARCHIVE_NOT_YET_PUBLISHED`, **no artifact, no done cache**; other HTTP errors/oversize/broken CRC -> BLOCKED/FAIL.
- Reusable `.github/workflows/bybit-official-archive.yml` runs SIX isolated symbol jobs. Each hour selects one frozen UTC day from the last SEVEN via `lag=UTC_hour%7+1`; hence six jobs/hour, not 42, and old delayed or missed publication dates are retried for one week. **No new schedule.** Dedicated per-symbol/day cache is created only after GitHub artifact upload succeeds.
- Called by EXISTING `colab-launcher.yml` schedule `7 * * * *` and, **only when directly invoked**, EXISTING GAS `avrora-private-wave.yml workflow_dispatch(mode=full13)`. The scheduled parent already owns its archive job; direct fallback is skipped on parent `workflow_call`. Never install second GAS trigger.
- Artifacts per successful symbol/date: `avrora-official-trades-SYMBOL-YYYY-MM-DD-RUNID`, contents `SYMBOLYYYY-MM-DD.csv.gz` and `manifest.json`. Compression disabled in Actions artifact to avoid re-compressing .gz; artifact ZIP SHA is separate from original source gzip SHA.

## Delivery & acceptance (NOT yet proven end-to-end)

1. After 2026-10-24 UTC, look for genuine GitHub job `Official trades SOLUSDT (completed UTC day)` and five counterparts with an **actual** `PASS_OFFICIAL_ARCHIVE_SHA_AND_GZIP_CRC SYMBOL DATE SHA MANIFEST_SHA`; WAIT is not success.
2. Confirm downloadable per-symbol/day GitHub artifact. Its GitHub artifact ZIP digest and manifest's `source_gz_sha256` are **two different hashes**. Verify both, including `tools.bybit_official_archive_transport.verify(folder,symbol)` on original files.
3. Existing destination private Google Drive research folder: https://drive.google.com/drive/folders/1MXTBe21rTm1fVYzjUQ6NNf8cJzOQ0NKX . The current GitHub/Colab ADC secret **lacks Drive LIST/CREATE permissions (403)**. GitHub runner intentionally does not contain a Drive write token. Do **NOT** claim GitHub artifact alone is Drive delivery; do **NOT** repeat 403 with the same ADC or inject a token into public Actions.
4. The already configured **hourly connected ChatGPT AVRORA consumer** can, when its connector is available, locate new GitHub artifacts, copy them by byte-stable file URI to the existing Drive folder, independently download/read back, compare ZIP SHA256 to the GitHub artifact digest, and append a private delivery ACK keyed by (symbol, date, GitHub artifact id). This connected-consumer delivery is **NOT** an independently proven unattended service and may hit upload-size limits. Flag `DRIVE_DELIVERY_BLOCKED` or `UNVERIFIED` unless verified.
5. Private research ingestion into `vicrex/AVRORA` must separately verify source receipts, missing dates, six-symbol panel alignment, tick schema, M15 aggregation, first-seen timestamp, 220 M15 warmup, data crisis flags and complete independent check. **No direct automatic SIM/replay injection until reviewed.**
6. For the first data day 2026-10-23, the FIRST test must see one genuine post-day publication and provider byte SHA, not just a green offline CI job. For all six instruments over a given date, require six separate valid archives + six unique SHA receipts + six Drive ACKs before classifying the day as a complete research input. No OOS until truly preregistered forward evaluation.

## Safety

`REAL=OFF`, `HOLDOUT=SEALED`; no maker queue, MarkPrice funding, true realtime, OHLC quality, or trading profit implied by delayed trade archives. Protect against future lookahead by using archive reception time, never the underlying trade timestamps, as the time source became observable.
