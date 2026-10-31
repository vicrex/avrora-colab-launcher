# HAWKES01: six-symbol seven-day archival-source gate (2026-10-31)

## Why this is required

The HAWKES01 estimator in private `vicrex/AVRORA`
(`research/strategy_search/hawkes01_fit.py`) verifies that each of seven
UTC days contains observations, **not** that all Bybit transactions have
been captured. The official archive transport in the public launcher
provides one signed `.csv.gz` + `manifest.json` for each completed day
and symbol, with archive download receipt time, **not individual
historical first-seen trade receipt times**.

The 1,000-case Colab CPU success (run 41192607985) was explicitly
SYNTHETIC mathematical stress, not source completeness or actual market
HAWKES calibration.

## What this module proves, and what it cannot

For a specified midnight UTC `asof`, require exactly the seven preceding
complete UTC dates, and the six fixed Bybit instruments BTC, ETH, SOL,
XRP, LINK, NEAR (42 symbol-day archive files). Each pair must have its
own old existing `AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2` manifest and
underlying `.csv.gz` verified by the *existing independent transport
verifier*, not by the manifest's own claimed hash. Check:

- exact provider allowlist, symbol, filename, date, HTTPS path;
- SHA256 of manifest, SHA256 of actual archive, compressed/decompressed
  sizes, gzip CRC and row counts; missing/altered data blocks;
- UTC archive downloaded only *after* the day finished, with honest
  `causally_usable_not_before_utc`, including detection of a source
  that arrived **after** the requested evaluation cutoff;
- no realtime signal, OOS, maker fill, PnL, or real-mode flags.

Even with 42/42 verified archives, **no provider trade-count
completeness proof** exists here, and individual `received_ms` events
are absent. Therefore the output can say only
`PASS_ARCHIVED_42_FILES_NOT_REALTIME`; it ALWAYS keeps
`hawkes_model_fit_ready=false`, `per_event_historical_first_seen_proven=false`,
`independent_check2=false`, `live_trading_authorized=false`.
A later independent completeness/first-seen source is still necessary
before genuine causal HAWKES fitting and price execution claims.

## Reproduction without network access

Place only existing approved historical public archives in
`<ROOT>/<SYMBOL>/<YYYY-MM-DD>/manifest.json` with the matching
`.csv.gz`. Then:

```bash
python -m tools.hawkes_seven_day_archive_audit \
  --root <ROOT> --asof-utc 2026-10-31 \
  --out new-private-research-archive-coverage.json
```

The 31 Oct cutoff requires 2026-10-24 through 2026-10-30, six symbols
per day. The new file is SHA-bound; no overwrite. Missing files return
exit code 3 and the precise missing pairs, rather than silently using
filled-in, repeated or truncated days. Nothing is downloaded by the
auditor; there is **no new hourly task, authorization or trading path**.

First validation on Linux CI uses **synthetic archived CSV+gzip**
fixtures for 42 files and adversarial missing, tampered, bad UTC,
future receipt, false-realtime and CRC checks. Passing these tests is
not real-source PASS. `REAL=OFF`, `HOLDOUT=SEALED`.
