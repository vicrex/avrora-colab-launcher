# Why ResCP-lite cannot be rescued by simply lowering its confidence gate

**Experiment:** H4-directional-edge audit v1, locked BEFORE historical calculation.
This is a diagnostic NOT optimization, model promotion, OOS validation,
ResCP paper replication, or maker-fill simulation.

Motivation: the prior pinned ResCP-inspired experiment on 84 previously used
discovery days produced 39 shadow trades and net20 -38.943587 USDT;
gross before all 20bps costs ~ +0.056413 USDT total. Reservoir conformal
lost to exponential conformal by Winkler score in all six symbols.

## Design, frozen before run

- Same causal 16-lag preweek-fitted ridge forecast as ResCP-lite.
- H4 forecast from finalized M15 close t; simulated entry next-bar OPEN
  and exit M15 close t+4. Never read future bars into signal formation.
- Five immutable selectors: sign-of-ridge with thresholds 0, 10 and
  20 forecast bps; last-four-bar momentum sign and its reversal (controls).
- No conformal filter is fitted or optimized for this study. This is
  forecast-edge only, not a new ResCP model or production trading strategy.
- All six pairs: BTC, ETH, LINK, NEAR, SOL, XRP.
- Same SHA-pinned P816 FULL13 historical panel (69,576 M15 bars,
  220 true warmup candles per week). Distinct 12 discovery weeks plus
  separate auxiliary May. Sealed OOS is never opened.
- At most two concurrent positions and only one per symbol; notional
  500 USDT per shadow trade; 16, 20, 25, 40 bps total trade costs.
  Slippage, funding and actual maker/taker fills are NOT modeled.
- Report 4 fixed groups: first six chronological discovery weeks,
  last six chronological discovery weeks, all twelve discovery weeks,
  May auxiliary. Both early and late groups are used discovery, NOT OOS.
- Metrics include raw sign accuracy, momentum accuracy and market-up
  base rate, MAE versus zero baseline, signal frequency, accepted trades,
  gross and cost-stressed net USDT and USDT/day.
- Independent CHECK2 refits ridge using separately implemented
  triangular solver, rebuilds entire 5-selector event/portfolio ledger
  from M15 bars, checks all aggregate fields and guards against edits.
- No adaptive threshold selection, parameter changes after results,
  execution of arbitrary Issue code, Work or new scheduler.

If fixed directional forecasts fail after fees and in the late six
discovery weeks, improve the underlying entry mechanism/forecast. Do not
loosen ResCP confidence thresholds post hoc or claim trade frequency
success without economic validity.

## Acceptance and one-shot mode

Offline CI runs Python unittest (no data, credentials or Colab). GitHub
workflow triggers only once on relevant push to main or on an explicit
manual dispatch. It reuses the existing private dataset checkout and
Colab credentials, first checks the public Issue #15 prereg/gate receipt.
The verified output is aggregate-only and marked
DIAGNOSTICS_ONLY_NO_PROMOTION. No scheduled repeats.

## V2 correction: no alphabetical portfolio allocation

V1 diagnostic trade-frequency and PnL summaries had a structural preference:
at the same entry timestamp, lexicographically first symbols occupied the
two allowed slots. In the dense ungated H4 strategies this strongly favors
BTC/ETH and does NOT demonstrate frequent trades across all six instruments.
V1 artifact remains preserved but should not be cited as six-symbol economic
evidence.

V2 uses only the finalized entry timestamp and a **predefined deterministic
rotation of the six-symbol priority** every four M15 bars. This is not a
data-dependent optimizer; it does not use outcomes or predicted returns to
rank symbols. Primary and independent CHECK2 independently reproduce the
rotation. Each selector now records actual accepted trades, trades/day, and
20bps net PnL by each symbol. V2 stays discovery-only and is not OOS or live
evidence. The fair-allocation rule was fixed after inspecting V1 aggregate
evidence, so do not use V2 as independent confirmation of profitability.
