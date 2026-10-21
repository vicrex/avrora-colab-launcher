# AVRORA structural SHORT full13 audit — 2026-10-21

## Verified provenance and dataset

- Research preregistration, source and independent-checker review: https://github.com/vicrex/avrora-colab-launcher/pull/23
- Immutable revision used by the run: b9bc14da470df46c590cd5b62789ac1797b5188c
- GitHub Actions read-only Colab FULL13 execution: https://github.com/vicrex/avrora-colab-launcher/actions/runs/39591015809
- Aggregate artifact: https://github.com/vicrex/avrora-colab-launcher/actions/runs/39591015809/artifacts/12342476470
- Exact manifest sha256: 54aa3b0f171a59c4b5ca93800608e0cabdfbf6a053e65035980d50d26f2b150d
- Receipt digest (canonical JSON without receipt_sha256): e3525036f77871511718a06702ba4fd927eab90fd51660b0e6b59de498ef4dbe
- Independent CHECK2: PASS_ALL_SHORT_SIGNALS_FILLS_AND_EQUITY (full accepted trade rows, derived signal stream, stop-first fills, portfolio and PnL recomputation)
- Pinned existing P816 source: 69,576 M15 candles, 6 pairs, 12 **previously used discovery weeks** (84 days) plus May AUX week separately; 220 preceding warm-up bars/period; HOLDOUT SEALED; NOT OOS.
- REAL=OFF; no orders or private raw candles/trade rows published.
- **Drive aggregate archive delivery is NOT YET VERIFIED**. GitHub artifact is the durable link established so far.

## Exactly two frozen hypotheses

- TREND_BREAK_SHORT_V1: a closed M15 bar breaks the lowest of 12 preceding lows by 0.1 ATR and has a bearish body >=0.35 ATR; EMA20 below EMA60, EMA60 falling, and close below EMA20. Next-open SHORT proxy with stop above signal high/1.25ATR, 1.8R TP, conservative stop-first intrabar, 12-bar maximum.
- BREAK_ONLY_SHORT_CONTROL_V1: same structural breakdown and exit, no EMA trend filter.
- Both: 8-bar signal cooldown, $300 closed-equity account, <=$5 initial stop-price risk, <=$500 notional, 10x margin *reservation proxy*, 2 concurrent positions; cannot reuse allocated margin, cease new entries below $20 realized capital. Non-outcome-driven six-symbol priority rotation.
- Primary equity uses total 20bps roundtrip costs. 16/25/40bp stresses reuse the fixed ledger; alternate stressed equity paths NOT recalculated.

## Discovery results across 84 previously used days

| Metric | Trend-filtered SHORT | Unfiltered breakout SHORT |
|---|---:|---:|
| Proposal events | 971 | 1,456 |
| Closed shadow trades | 612 | 826 |
| Trades / symbol / day | 1.214286 | 1.638889 |
| Gross total, USDT | +397.210323 | +474.504450 |
| Net at 16bps, USDT | -11.343732 | -78.790046 |
| Net at 20bps, USDT | -113.482246 | -217.113670 |
| Net at 25bps, USDT | -241.155388 | -390.018200 |
| Net at 40bps, USDT | -624.174815 | -908.731790 |
| Net20/day, USDT | -1.350979 | -2.584687 |
| Ending closed equity, USDT | 186.517754 | 82.886330 |
| Peak-to-trough realized drawdown, USDT | 251.270597 | 249.809211 |
| Margin/concurrency skipped | 359 | 629 |

Early 6 used discovery weeks: trend-filtered +50.192216 USDT vs control +5.197769.
Late 6 used discovery weeks: trend-filtered -163.674462 vs control -222.311439.
Trend-filtered is negative in 7/12 weeks; unfiltered negative in 9/12.

### Six-symbol breakdown, 20bps (trend SHORT)

| Pair | Trades | Net20 USDT over all 84 days |
|---|---:|---:|
| BTC | 89 | -98.747291 |
| ETH | 83 | -3.541826 |
| LINK | 125 | -14.889957 |
| NEAR | 114 | +1.683897 |
| SOL | 113 | +38.970716 |
| XRP | 88 | -36.957785 |

SOL/NEAR net positive **only** in used discovery. Selecting them after reading
this table would be a posthoc selection, not independently validated edge.

### Separate May auxiliary (not included in 84-day results)

- Trend-filtered: 17 closed shadow trades, -21.856926 USDT net20, 278.143074 ending equity.
- No-trend control: 42 closed shadow trades, -58.026217 USDT net20, 241.973783 ending equity.

## Interpretation and next research rules

**Both preregistered candidates are REJECT for real-money use** on this available evidence. Trend filtering reduces loss and turnover but still fails even at 16bps. The best-performing version's approximate gross edge is ~15.5bps of total notional, lower than the 16–40bps modeled trade cost. At 20bps its after-cost return is negative and far below the requested 4–5 trades/day/instrument. A real 300-USDT account can be liquidated or margin-constrained sooner than this simplistic cash/equity model because unrealized PnL, funding, slippage, margin-level liquidation, and maker queue are not modeled. The stop-price loss cap of $5 also does not prevent worse gap fills. Therefore the reported account equity is an optimistic *approximation*, not a deployable Bybit simulation.

The source has OHLC only: **this is NOT a liquidity/orderbook-wall strategy** and no assertion about limit-order fill reliability is made. No sealed holdout was unsealed. Early/late splits remain reused discovery, not fresh OOS. Avoid repeated parameter sweeps or cherry-picking two positive pairs on the same data.

Next scientifically useful step is to examine *causal execution and market structure* in dedicated genuine orderbook L2 datasets, with frozen fee/maker fill tests and independent time-of-knowledge accounting, then preregister a genuinely new strategy family before evaluating. Do not spend holdout or execute real orders automatically.
