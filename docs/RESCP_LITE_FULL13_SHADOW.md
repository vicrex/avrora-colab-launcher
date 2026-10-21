# ResCP-inspired H4 shadow: pinned FULL13, no live execution

This is **NOT** an official implementation of ICLR-2026 ResCP and **NOT**
the DLinear backbone proposed by public Issue #15. The authors' public
repository currently advertises "Code coming soon" (2026-10-21).
The test is independently implemented as a **ResCP-inspired proxy**,
not a preregistered execution of the exact proposed research model.

## Frozen experiment

- Data: existing SHA-locked P816 complete FULL13, 12 already used discovery
  weeks + separate May AUX, six M15 symbols, 220 genuine preceding bars
  per period, 69,576 bars total. Never load the five sealed holdout weeks.
- Point backbone: a frozen ridge regression on 16 past log-returns,
  H4 log return target, fitted ONLY inside each 220-bar preweek.
  It is a causal linear proxy, not DLinear.
- Calibration: each H4 residual appears only when its label is mature
  (forecast origin +4 M15 bars). Minimum 96 matured examples.
- Method: fixed 12-neuron ring reservoir, fixed random seed, fixed
  sparse recurrent coefficient, similarity softmax + time decay, weighted
  90% absolute residual interval, ESS fallback to rolling 128.
- Baselines (same frozen point model): expanding global conformal,
  rolling 128 conformal, exponentially weighted conformal.
- Scores: coverage, mean width, Winkler score, coverage across realized
  trailing-volatility deciles and across all symbols/periods.
- Economic SHADOW: sign only when the confidence interval excludes zero,
  q<120bps, next-open H4-close *proxy*, notional $500 per trade, at most two
  concurrent positions and one per symbol, 16/20/25/40bps stress costs.
  May is AUX and excluded from the 84-day discovery PnL.
- Independent CHECK2 separately fits ridge, evolves reservoir, computes
  all weighted quantiles, all economic shadow fills and reports; mutation
  tests must fail. No maker fills, funding, slippage or OOS claims.

## Evidence and safety

Only the fixed, reviewed source files in the public repository are
run; no arbitrary public Issue code is executed. Before Colab invocation,
the workflow verifies exact owner, SHA-frozen accepted Issue #15 and
two authored bot receipts; fixed private-source SHA, checksum-verified
data and existing Colab ADC. No new PAT, new timer or Work.

The workflow is triggered **once by a push to main affecting the
prototype files/workflow**, or manually via its existing workflow_dispatch
entrypoint. No scheduled repeated paid compute. Code and CHECK2 hashes are
inside receipt; only aggregate statistics are uploaded to GitHub, never
raw candles or complete trade-level history.

A GREEN test alone is not profitability. A verified Colab result requires
GitHub Action success, candidate/receipt SHA readback, CHECK2 verification,
and honest economic decision. Official paper replication, DLinear,
full predeclared falsification suite, genuine maker-first parity, fresh
holdout and Drive delivery remain separate milestones.

References:
- https://arxiv.org/abs/2510.05060v3
- https://github.com/RobertoNeglia/reservoir-conformal-prediction
- https://github.com/vicrex/avrora-colab-launcher/issues/15
