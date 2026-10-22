# AVRORA FULL13: pre-registered causal SHORT after support retest (2026-10-22)

## Immutable research hypothesis / temporal ordering

The new candidate is `TREND_RETEST_SHORT_V1`, added to the *new*
`research/structural_short_prereg_v2.json`. The original immutable V1
manifest, results and rejection are retained unchanged; the two previous
loss-making candidates serve as frozen controls here and are **not**
new findings.

After a completed M15 bar breaks the 12 completed prior lows by 0.10 ATR14,
has bearish body >=0.35 ATR and satisfies the original predeclared
EMA20<EMA60 / declining EMA60 trend filter, retain the old support
level and the original breakout ATR. Search only the **next 4 completed**
M15 bars for a rejection: high touches support minus 0.15 *original ATR*;
close is strictly below former support; bearish candle real body >=0.15
*original ATR*. Only at this retest bar's close does the new candidate
have a signal. Hypothetical entry is the FOLLOWING bar's open.
Recompute ATR14 using only data through retest bar for original-V1 risk:
stop at max(retest high, entry +1.25 ATR), target 1.8 R, time horizon
12 bars, intrabar stop-first, adverse stop gaps. No event uses a future
post-entry bar for entry or position sizing. Compare against both
unchanged original variants and a zero-trade baseline; enforce
CHECK2 independent derivation, full ledger & equity-parity.

## Frozen safety and acceptance

- 12 already seen discovery weeks (84 days), May separate AUX; 6 instruments
  and 220 genuine preweek warmup bars; all 69,576 M15 OHLC points are
  hash pinned, NO new OOS, SEALED holdout.
- Real trading OFF; no orders, no maker-fill claim, no orderbook or
  liquidity claim, no funding/slippage guarantee.
- 300 USDT starting closed equity, 500 USDT maximal notional,
  <=5 USDT initial stop-price risk, 10x approximate margin reserve,
  max 2 simultaneous positions and one per symbol.
- Cost stress 16/20/25/40 bps, with the 20 bps ledger determining the
  equity path, per-symbol/day and per-week economics; explicit
  early/late reused discovery weeks and May AUX.
- Only a real Colab job with independent CHECK2 and immutable receipt
  counts as an economic observation. New hypothesis is REJECT by
  default for any live trading; no automatic promotion at any PnL.
- Never select a survivor by post-hoc looking at six-symbol or weekly
  subsets. If negative at stress costs / lacking replicability, reject.

## Deployment contract

Existing `.github/workflows/structural-short-full13.yml` triggers
*one* run when its frozen files are merged into `main` (or existing
manual dispatch), without adding any schedule or secrets. It runs
offline tests first, verifies existing pinned private FULL13 data,
then existing ADC via Colab, then independent CHECK2, then publishes
only an aggregate receipt. Keep original research evidence immutable
and do not mistake a green CI run for profitable economics.

If the private source, runner or credential is unavailable, fail closed
and record BLOCKED. Existing public hourly FULL13 scheduler remains
unchanged and continues to handle its own 12 immutable FIVE_WAVE
candidates.
