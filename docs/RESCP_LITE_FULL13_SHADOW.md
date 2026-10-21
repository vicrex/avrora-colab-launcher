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

## Verified execution, 2026-10-21 (actual Colab)

- Source: [GitHub Actions #39583909044](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39583909044), triggered on merged PR #18; **SUCCESS**.
- CI: 97 offline tests passed, all pinned-source and issue-SHA gate steps passed.
- FULL13: 69,576 M15 candles verified; 44,382 H4 forecast intervals scored over 12 already-seen discovery weeks + May auxiliary, no holdout.
- Independent CHECK2: \`PASS_RECOMPUTED_ALL_INTERVALS_AND_ECONOMICS\`.
- Global / rolling / exponential / reservoir coverage: 86.5644% / 89.3177% / 88.7139% / 88.0762%.
- Mean Winkler bps: 718.999967 / 684.635914 / 662.332279 / **679.755393**. Reservoir is **worse than exponential**; no statistical or economic promotion.
- Worst retrospective volatility-decile coverage: global 75.9126%, rolling 86.8635%, exponential 87.0888%, reservoir 86.9761%. Descriptive within used data.
- Discovery: 39 hypothetical entries, 0.077381 trades/symbol/day. Net16 -31.143587, net20 -38.943587, net25 -48.693587, net40 -77.943587 USDT across 84 used days, net20/day -0.463614 USDT. **All negative.**
- May AUX (not mixed into discovery): 1 trade; net20 +0.253671 USDT; no inference from a single observation.
- Hard decision: \`REJECT_FOR_LIVE_DISCOVERY_ONLY\`; no official ResCP claim, no fresh OOS, no maker-fill proof.
- [Verified Google Drive copy](https://drive.google.com/file/d/1ocwM6PtFHL21Gc1UGAXZvF9aV0aJOePt/view): \`AVRORA_RESCP_LITE_FULL13_CHECK2_20261021_RUN39583909044.zip\`.
- GitHub artifact ZIP SHA256 \`cec88f8203510f9af92b85113467f1dd5c946a35d994452fd29534434d33f5a7\`, **byte-for-byte equal** to downloaded Drive copy.
- JSON canonical \`receipt_sha256=ba2593eff94dc555a2c90829cc4d94658ebce89ffa72814e8d71b220c0eb36c3\`, independently recomputed and matching.

This entry is a permanent research handoff; the original Issue #15 is still *unreviewed* for its specified DLinear/official ResCP architecture. No automatic promotion to production, no trade orders.
