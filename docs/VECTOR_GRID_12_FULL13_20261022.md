# AVRORA — FULL13 vector grid batch executor, 12 real research tests

Tracker: [AVRORA private Issue #61](https://github.com/vicrex/AVRORA/issues/61).
The original `research/vector_squeeze_grid_prereg_v1.json` committed in PR #44 is
**unchanged**. All parameter vectors were frozen BEFORE running this new batch.
No parameter tuning is based on any of the 12 outcomes.

## Exact architecture

- User-approved existing public repository `vicrex/avrora-colab-launcher`;
  new event-triggered (push-once or manual, **NO CRON**) workflow
  `.github/workflows/vector-squeeze-grid-full13.yml`.
- Matrix batches `0,1,2`, `max-parallel: 1`, each at most four
  SHA-preregistered variants in ONE Colab CPU operation. Each batch independently
  checks the complete 69,576 M15 candle source (13 periods, 6 symbols, 220 true warmup).
- All three batches share the same read-only private-source SHA and **existing**
  `AVRORA_COLAB_ADC_JSON_B64` temporary authentication, with no added scope.
  No private raw bars/transactions in public runner logs or artifacts.
- `tools/vector_squeeze_grid.py` evaluates the four candidates in its selected
  batch. `tools/vector_squeeze_grid_check2.py` computes all signal
  timestamps, fills, complete trade-by-trade ledger, bankroll decisions
  and independent per-week and per-symbol summaries WITHOUT calling primary
  `book` or primary `find_squeeze_events`. Fail hard on *any* difference.
- A batch publishes `AVRORA_VECTOR_SQUEEZE_GRID_FULL13_V1` receipt,
  immutable frozen spec hash for each candidate, source/code/checker SHA,
  early6/late6, May AUX, costs 16/20/25/40 bps, complete six symbols,
  `real=OFF`, `holdout=SEALED`, `oos=false`.
- Require original GitHub artifact SHA and byte-for-byte SHA of Google Drive
  readback before `ZIP_DELIVERY_VERIFIED`. A green GitHub check without
  CHECK2 is NOT valid evidence.

## Discovery and false discovery control

Tests share **the same previously seen** discovery 84 days and separate May AUX.
They are *not* twelve independent validations, and no winner should be declared
based on highest discovered PnL. Each trade's execution is a next-open OHLC proxy,
not a proven Bybit PostOnly fill. Earnings can remain optimistic in absence of
funding, slippage, queue position and real liquidation.

The goal is to extract stable *mechanism-level* patterns, not tune a knob
until one backtest looks green. Full prospective statistical validation would
require a separate preregistered evaluation beyond this shared discovery set,
plus multiple-test adjustment and single final frozen holdout review.

## Stop conditions / permissions

- No Work, Cloud Browser or Computer Use without new user authorization.
- REAL off, HOLDOUT sealed and no exchange live credentials or orders.
- Stop/fail closed for no GitHub runner, incomplete source, any
  CHECK2 mismatch, hash conflict, evidence leak, missing Colab ADC.
- Use existing hourly automation as **consumer** for artifacts and graph import;
  do not add another repeating clock. The 12-idea sweep runs only on code merge
  or explicit manual dispatch.
- The **private authoritative vector graph** `vicrex/AVRORA/research/insight_map`
  must ingest aggregate verified 12 receipts with schema reviewed and durable
  append-only snapshot/ACK; generating public reports does NOT silently
  update that private graph.

## Acceptance

1. Unit-test 12 parameter/case distinctness and ledger parity, synthetic
   compression, future-bar impossibility, REAL and sealed-holdout gates.
2. Merge only after green offline PR CI.
3. Observe three real Colab/CHECK2 batches. Record run_id, attempt, artifact_id,
   source/candidate hash, empirical economics.
4. Deliver and read back all three ZIP SHA-256s to pinned Drive folder.
5. Log evidence to Issue #61 and private handoff. No automatic strategy promotion.
