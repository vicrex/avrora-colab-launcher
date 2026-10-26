# AVRORA — eligible-day six-symbol Bybit backfill (2026-10-26)

**Scope: transport-only, delayed official public trade archives.** This is a
startup-coverage fix to the existing `bybit-official-archive.yml` workflow.
No new cron, no additional matrix jobs, no Work or new credentials.

## Verified root cause
Real GAS direct `workflow_dispatch` run [40275323257](https://github.com/vicrex/avrora-colab-launcher/actions/runs/40275323257)
had six transport jobs all green, but for the 05 UTC hour selected fixed
`lag = hour % 7 + 1 = 6`, i.e. **2026-10-20**, before frozen
`FIRST_DAY=2026-10-23`. BTC job `121416747518` logged
`WAIT_FIRST_NEW_SOURCE_DAY_2026_10_23` and
`WAIT_BYBIT_OFFICIAL_ARCHIVE_BTCUSDT`. This is a **WAIT**, not new data.

## Fix
Selector `tools.bybit_archive_day_selector` computes days actually completed
since FIRST_DAY=2026-10-23 UTC. Use the bounded window
`min(7, eligible_completed_days)` and existing UTC-hour modulo that window.
Before even the first new source day completes, short-circuit the six
transport jobs to WAIT (without attempting source download). This avoids
wasting early post-freeze hourly slots on unsupported archives.

For UTC 2026-10-26: the window is three days (Oct 23, 24, 25).
Hour 05 -> Oct 23 (cached), hour 06 -> Oct 25 (newest), hour 07 -> Oct 24.
No guarantee of publication: 404 is still WAIT, and a green workflow without
six actual source ZIP artifacts is not a successful new six-symbol day.

Acceptance: six artifacts + original gz and manifest hashes, GitHub ZIP digest,
Google Drive private delivery/readback SHA for each symbol, 96 nonempty
M15 slots, panel alignment and no causal first-seen mislabeling. For a model
with 220 M15 warm-up and 12 exit bars, at least 234 consecutive M15 bars
must be present before offline feature evaluation. Three completed consecutive
days provide 288 bars per symbol, but still are **retrospective-only**.

No strategy or SIM/REAL promotion. `REAL=OFF`, `HOLDOUT=SEALED`,
`oos_proven=false`, no L2 queue, funding or maker-fill proof.
