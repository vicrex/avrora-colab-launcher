# AVRORA SHORT structural breakdown: preregistered FULL13 experiment

Status: **candidate-only**, frozen in research/structural_short_prereg_v1.json
and the separate PR BEFORE reading the strategy's historical PnL.

## Purpose
Previous H4 Ridge direction and ResCP-lite failed after 16–40bps
costs. The six-symbol used-discovery H4 directional audit had ~50.58%
sign accuracy. We need event-driven SHORT trend context, not generic
direction forecasting or post-hoc confidence threshold tuning.

## Exactly two fixed methods
1. TREND_BREAK_SHORT_V1: M15 closes below the lowest low of the
preceding 12 *completed* bars by >0.1 ATR14; bearish real body >=0.35
ATR14; bar range <=2.5 ATR14; EMA20<EMA60; EMA60 below its value
eight bars before; close<EMA20. Eight completed candles cooldown per pair.
2. BREAK_ONLY_SHORT_CONTROL_V1: identical breakdown and candle-quality
conditions, without the EMA trend filter, to measure trend context value.

Neither method uses order book liquidity walls or volume: the
SHA-locked FULL13 panel has only M15 OHLC. "Liquidity confirmation" is
NOT CLAIMED. No request to private orderbook data is made.

## Entry/exit, equity and safety
- All signals established on fully closed candle t. Earliest entry
  next-bar open t+1 (SIMULATION PROXY, **not proven maker fill**).
- Short stop is MAX(signal candle high, next open + 1.25 ATR14).
  Profit target is entry - 1.8 times initial price risk.
- SL has priority if TP and SL hit in same bar; a gap beyond SL
  exits at the worse bar open. Time stop at next-open+12 bars.
- Every accepted trade has >=25 and <=500 USDT notional and
  <=5 USDT initial stop-price risk; 10x isolated margin approximation,
  2 maximum concurrent trades and 1 per pair.
- START with $300 simulated realized equity across all 12 discovery
  weeks (84 days). Reserve capital for open trades, and block new
  entries at <=20 USDT or after depletion. May AUX is a separate
  7-day 300-USDT shadow account. Does NOT simulate Bybit liquidation
  thresholds, funding, mark-to-market unrealized exposure, maker queue
  or slippage; gap losses can still exceed nominal $5 stop risk.
- The primary 20bps cost determines *position sizing and equity path*.
  The 16/25/40bps alternatives are **fixed-ledger stress PnL only**,
  not separately margin-sized equity curves.
- Symbol priority rotates deterministically every four closed M15
  bars; never rank by future outcome. Report by symbol, by week,
  early and late six USED discovery weeks, and May AUX separately.
  Late six are not an unobserved OOS dataset.

## Independent verification
The independent checker in tools/structural_short_check2.py
separately computes rolling support, ATR, EMA, complete signal
proposals, stop-first fills, gap prices, all accepted trade rows,
simulated cash/margin book, reasons for skipping trades, PnL and
by-symbol/by-period numbers. Only verified **aggregate** receipt
is uploaded; raw private bars and trade ledger are not logged.

### Interpret decision
This predeclared comparison either rejects the idea or supports only
further research. It must not promote a candidate based on 84
previously used discovery days. TRUE OOS remains SEALED and would
require a separate preregistered and explicit approval later.
No real orders, Work or additional recurring triggers.
