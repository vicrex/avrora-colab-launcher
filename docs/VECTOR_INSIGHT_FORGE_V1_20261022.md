# AVRORA Vector Insight Forge — first testable slice (2026-10-22)

Tracker: [private Issue #61](https://github.com/vicrex/AVRORA/issues/61). The authoritative permanent **evidence graph** remains in private `vicrex/AVRORA/research/insight_map/` (`vector_map.json`, `knowledge_space.py`, `cloud_ingest.py`). This public slice does **not** create another authoritative state store or copy private graph contents.

## Research design before outcome

1. **New frozen short signal:** `SQUEEZE_BREAK_SHORT_V1` in `research/structural_short_prereg_v3.json`: preceding 8 completed M15 candles have high-low range <=70% of the preceding 8 and <=3 times ATR14 from bar t-1; completed breakout candle t closes below prior 8-bar low minus 0.10 ATR14, has bearish body >=0.35 ATR14, with EMA20 < falling EMA60, close below EMA20. Enter proxy at next open, stop first, gaps worse open, 12-bar time limit and same historical SHORT V1 original exit model; `REAL=OFF`.
2. Evaluate against historical predeclared `TREND_BREAK_SHORT_V1`, `BREAK_ONLY_SHORT_CONTROL_V1` and `TREND_RETEST_SHORT_V1`. The last three have previously measured economic results; do not count them as new independent evidence.
3. **Dedicated independent checker:** `tools/structural_short_check2.py` separately reconstructs signal timestamps from closed candle bars, entire trade fill/ledger, realized equity, 20bps cash path, weekly/symbol costs and skipped orders. No raw market data is published in public artifacts.
4. **Vector-insight stage:** after a successful real Colab+CHECK2 receipt, `tools/vector_insight_lab.py` checks pinned model/checker/receipt via the audited `engine.verify_receipt()`, demands all four results, 12 weeks/6 symbols and cost monotonicity, and exports a SHA256-bound `AVRORA_VECTOR_INSIGHT_DELTA_V1`. 13 numeric mechanism/parameter dimensions, after-cost outcomes, early/late-split, May AUX, number of profitable weeks, and loss-reason flags. Pairs record **descriptive distance**; performance difference on the same dataset is not an independent treatment effect.
5. **Preregistered future experiment queue:** `research/vector_squeeze_grid_prereg_v1.json` records 12 fixed ideas from 3 contraction ratios (0.55/0.70/0.85), 2 thresholds (0.05/0.10 ATR) and 2 body requirements (0.25/0.35 ATR). They are `PREREG_ONLY_NEEDS_REVIEWED_ADAPTER_AND_CHECK2`, with `economic_result=null`: **none of these 12 tests have been executed merely by generating the queue**. Bounded compute budget <=4 per approved Colab job, <=12 grid ideas. New reviewed grid execution adapter (not arbitrary issue code) is next implementation step.

## Anti-overfitting and safety gates

- 69,576 M15 bars of 12 **previously used** discovery weeks and May AUX (separate); six coins BTC, ETH, LINK, NEAR, SOL, XRP; 220 true preweek warm-up bars/period; no claim of unseen holdout/OOS.
- Initial 300 USDT bank, 500 USDT max per position, <=5 USDT initial stop-price risk, 10x margin proxy, two slots, one per symbol; fees 16/20/25/40 bps. Proxy ignores real fill uncertainty, funding, slippage, mark liquidation.
- No strategy receives a live promotion from the used discovery set. Massive sweeps **increase the risk** of false discoveries; no p-value, best-sample ranking or statistical alpha is claimed from shared weekly aggregates.
- Better insights need independent prospective validation and multiplicity-adjusted uncertainty (block-bootstrap / Reality Check or SPA). Late six used discovery weeks and May AUX are diagnostic only; do not call them OOS. The sealed holdout remains untouched unless separately authorized.
- GitHub Actions public workflow `.github/workflows/structural-short-full13.yml` executes on merge via existing push trigger, no new hourly timer, uses existing pinned read-only data and narrow Colab ADC. Aggregated vectors and idea grid archived as public Actions artifact only on verified completion.
- Until private knowledge graph consumes this validated delta, writes snapshots to private Drive and checks SHA+ACK, status `VECTOR_ARTIFACT_VERIFIED_GRAPH_ACK_PENDING`, **not** full autonomous vector exploration.

## Acceptance steps

- Offline unit tests reject wrong data shape, missing CHECK2, tampered cost/scope, duplicate or unsafe grid, change of feature schema, false retest/squeeze signals or future-bar leak.
- After PR merge, inspect real public workflow job and record exact source/code/checker/receipt SHA, economic decisions, and new vector artifact id and digest.
- Separate authorized consumer can then import with explicit schema review into **existing** protected `research/insight_map`, preserving all previously verified experiments; never rewrite it from the old 16-record seed.
- Next task: approved grid adapter capable of running each of the 12 preregistered settings in bounded batches (<=4/Colab run) with independent CHECK2, ordered append-only results, multiple-testing disclosure and a real archival ACK. This is not yet implemented.
