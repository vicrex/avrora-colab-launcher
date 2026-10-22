# AVRORA structural retest SHORT V2 — FULL13 CHECK2 result, 2026-10-22

## Provenance

- Pre-registered implementation and manifest: [PR #43](https://github.com/vicrex/avrora-colab-launcher/pull/43), merged commit `53a4dcfb57f0f5d9c4a9a6e9189df2e9ba914098`.
- New complete real Google Colab FULL13 execution: [run 39722290962](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39722290962), event=push, **success**.
- Actual job: offline tests PASS; prereg SHA gate PASS; credentials and pinned private source PASS; 69,576 M15 bars PASS; Colab executed; independent CHECK2 PASS; aggregate receipt artifact preserved.
- [GitHub artifact 12401751864](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39722290962/artifacts/12401751864), ZIP SHA256 `e66133b5b6bf1c02e2fe35f60b233b62fbb268fff44358a15851d176a80c268c`.
- [Verified Google Drive copy](https://drive.google.com/file/d/1-fj-YjSDfk1rfwio22CmOzkBmeRHCjDF/view): `RESEARCH_39722290962_V1_STRUCTURAL_RETEST_V2_CHECK2.zip`, exact SHA256 readback match.
- JSON canonical receipt SHA256 `620159d65ba26609efe31a697a52a6891e27f7e20c2a705dc22b0b3cb3b73505`, independently recomputed and verified; `independent_check2=PASS_ALL_SHORT_SIGNALS_FILLS_AND_EQUITY`.
- Three allowlisted IDs, source panel SHA pin, bars=69576, REAL=OFF, HOLDOUT=SEALED, OOS=false.

## 84 *previously seen* discovery days, six symbols

| Preset | Trades | Trades / symbol / day | Net16 USDT | Net20 USDT | Net25 USDT | Net40 USDT | Net20 USDT/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| TREND_RETEST_SHORT_V1 (**new**) | 350 | 0.694444 | +47.294305 | **-9.173631** | -79.758551 | -291.513311 | -0.109210 |
| TREND_BREAK_SHORT_V1 (frozen control) | 612 | 1.214286 | -11.343732 | -113.482246 | -241.155388 | -624.174815 | -1.350979 |
| BREAK_ONLY_SHORT_CONTROL_V1 (frozen control) | 826 | 1.638889 | -78.790046 | -217.113670 | -390.018200 | -908.731790 | -2.584687 |

The retest concept reduces losses but **fails** the primary 20bps and both
25/40bps stress costs. The zero-trade comparator (0 USDT net) is better
at 20bps. Its 16bps gain has no verified maker execution. Implied
fixed-ledger break-even cost around 19.35 bps; this is *not* a measured
achievable execution fee/slippage on Bybit.

### Temporal falsification

- Retest early six previously used weeks: +66.444508 USDT /164 trades.
- Retest late six previously used weeks: -75.618139 USDT /186 trades.
- May AUX, separately evaluated with reset equity, 12 trades: net20
  **-20.297745 USDT**. This is not new OOS.
- Discovery realized-equity proxy end 290.826369 USDT from 300 USDT,
  peak-to-trough drawdown 124.608414 USDT. Does not model liquidations,
  mark-to-market exposure, maker queue, funding or slippage.

### Instrument-level caveat

The frozen six-symbol portfolio includes 350 total trades; rate 0.69/day
per symbol, nowhere near target 4–5/day/symbol. Some symbols have positive
in-sample net20 numbers (LINK, NEAR, SOL), but selecting them after seeing
these results is a post-hoc alteration. **Do not promote** a selected
subportfolio or switch to 16bps without validated real fill mechanics.

## Decision: REJECT_FOR_LIVE / RESERVE_AS_DIAGNOSTIC_CONTROL

The experiment is a successfully executed, independent FULL13
**discovery-only** result; it is *not* evidence of positive deployable
expectancy or unattended research-autonomy completion. Holdout remains
sealed and real orders OFF. Further improvements require a preregistered
genuinely distinct causal mechanism with data that supports its input
features (for example independently timestamped L2/OFI and maker
fill tests), rather than repeated retrospective retuning on these same
used weeks. Do not conduct posthoc fee optimization.

## Remaining operations

New receipt was archived to Drive with GitHub SHA256-matched ZIP.
Separate private graph importer/ACK not yet verified for V2. Public
hourly runner remains unchanged; its post-PR42 cached-receipt fix
must still be observed on a naturally triggered scheduled run.
