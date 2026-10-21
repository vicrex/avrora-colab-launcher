# H4 direction / ResCP-lite diagnosis — verified FULL13, 2026-10-21

## Immutable evidence

- Frozen research design PR: https://github.com/vicrex/avrora-colab-launcher/pull/19
- High-frequency O(N) correction: https://github.com/vicrex/avrora-colab-launcher/pull/20
- Fair six-symbol scheduler correction: https://github.com/vicrex/avrora-colab-launcher/pull/21
- Final independently verified Colab run V2: https://github.com/vicrex/avrora-colab-launcher/actions/runs/39587721894
- Exact aggregate-only artifact: https://github.com/vicrex/avrora-colab-launcher/actions/runs/39587721894/artifacts/12339882436
- Receipt SHA256 (canonical JSON excluding receipt_sha256): 0415583567cb91b44e246c0cf1755205dbdf251520446c1ee850efd8eb90e04c
- CHECK2: PASS_INDEPENDENT_DIRECTION_AND_LEDGER_CHECK2
- Data: existing SHA-pinned P816 12 previously used discovery weeks plus May AUX, 6 M15 symbols, 69,576 bars, 220 true warmup bars per period. Real OFF, Holdout SEALED, OOS false. These are **not fresh out-of-sample results**.

## Decisive diagnostic statistics

48,096 forecasts over 12 *previously seen* discovery weeks (84 days total);
separate May AUX 4,008 forecasts. Ridge H4 sign accuracy 50.5842%,
versus naive always-short 52.7549% because positive future-H4 outcome rate
was 47.2451%. Ridge MAE 96.907485 bps versus zero-forecast MAE 91.481108
bps (ridge is worse by 5.426377 bps). H4 targets overlap; do not assert
independent-trial statistical significance from individual candles.

Full 84-day discovery, two concurrent 500-USDT notional trade slots,
next-open H4-close **proxy**; 20bps round-trip cost, no maker fills proven,
no funding/slippage:

| Predeclared method | Closed shadow trades | Gross USDT | Net20 USDT | Net20 USDT/day |
|---|---:|---:|---:|---:|
| RIDGE_SIGN_0 | 4008 | +394.997842 | -3613.002158 | -43.011930 |
| RIDGE_SIGN_10 | 3984 | -387.616624 | -4371.616624 | -52.043055 |
| RIDGE_SIGN_20 | 3670 | -17.822941 | -3687.822941 | -43.902654 |
| MOM4_SIGN | 4008 | -877.942085 | -4885.942085 | -58.165977 |
| REVERSE_MOM4 | 4008 | +877.942085 | -3130.057915 | -37.262594 |

No method profitable even under the evaluated 20bps cost assumption.
The best gross case, reverse momentum, earns +877.942085 /4008 =
~0.219 USDT per 500-USDT trade, only ~4.38 gross bps versus 20 bps cost.
That is far below breakeven, ignoring funding and slippage.

Earlier V1 aggregate result was invalid for **six-symbol frequency** because
lexical symbol order repeatedly chose BTC and ETH whenever six simultaneous
signals filled two slots. V2 preserves old immutable artifact but instead
uses clock-based round-robin, reports accepted trades **per symbol**, and
independently checks every per-symbol total. The corrected RIDGE_SIGN_10
symbol count over the 84 days is:
BTC 457; ETH 635; LINK 795; NEAR 783; SOL 701; XRP 613.
The corresponding net20 USDT is -489.772083, -613.702494,
-778.290559, -841.654062, -1038.453833, -609.743592 respectively:
**all six negative**. The high turnover achieves counts >=4/day on
individual symbols but loses more money; trade frequency alone is not edge.

Late six discovery weeks are also negative after 20bps for **all five
predeclared methods**. May AUX is negative for all five too. Again neither
split is unseen holdout.

## Safety / interpretation

The 500-USDT proxy turnover assumes the synthetic simulation continues
despite aggregate losses of thousands of USDT. Against an initial 300-USDT
deposit a real account would be unable to sustain these cumulative losses
without additional funding; the reported total is **not** an implementable
equity curve or guarantee about margin/liquidation. Maker fills and
stop/target microstructure are NOT proven, and there is no live/OOS
evidence. No live orders were placed.

**Disposition:** REJECT frozen ridge H4 direction forecaster and the five
evaluated selectors for profitable automated trading. Do not tune these
thresholds post hoc on the same discovery weeks to manufacture a winner.
ResCP-inspired confidence selection remains separately rejected.

**Next scientifically justified family:** causally confirmed event-driven
structural trend-down short / liquidity continuation, paired with
control variants and falsifications, evaluated against a zero-strategy
baseline at 16/20/25/40bps and an honest 300-USDT equity/stop-out bound.
Keep sealed holdout sealed until genuinely preregistered and independently
verified development results support a final one-time test. Any fresh
method must be independently implemented and version-pinned before
outcome inspection, then checked with a distinct CHECK2; no arbitrary
public Issue code may run automatically.
