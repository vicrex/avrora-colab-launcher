# AVRORA: catch-up of missed GAS shadow hours — 2026-10-26

## Why this patch
Real evidence on 2026-10-26 showed confirmed hourly holes including 498030, 498040,
498043, 498045 and 498048, while the existing GAS FULL13 direct dispatch did
produce 64-case multifamily runs and authenticated private Drive ACKs on other hours.

A green GitHub job by itself is NOT evidence of 64 delivered candidate results.
A successful public aggregate artifact must match a separate private-GAS
`AVRORA_PRIVATE_MULTIFAMILY_DRIVE_SHA_ACK_V1` for the SAME run, receipt SHA,
and safety flags.

## Operational path (no new scheduler)
* Existing GitHub public hourly cron remains exactly `7 * * * *`.
* Existing GAS `workflow_dispatch(mode=full13)` remains unchanged.
* Both routes enter the **same** reusable
  `.github/workflows/multifamily-sweep-smoke.yml` with its existing
  concurrency group and `cancel-in-progress: false`.
* Before checking out ANY private repo, `python -m tools.shadow_hour_recovery`
  reads only recent non-sensitive GitHub Actions artifact metadata/ZIPs using
  the existing GitHub Actions token with `actions:read`.
* Within the past **24** UTC hours, it picks the oldest missing hour for a
  deterministic 64-case historical discovery-only sweep. Valid pairs of aggregate
  receipt + Drive SHA ACK mark hours complete. Incomplete aggregate-only hours
  are quarantined, never blindly recalculated. Orphan ACKs, SHA mismatches,
  malformed artifacts, provider/API/permission errors fail closed.
* With all hours covered, the job is IDLE; expensive private clones/replay and
  new public/private artifact uploads are skipped.
* All immutable private source SHA pins, reporting, delivery via the existing
  FREE owner GAS, and private cleanup remain unchanged. No extra service,
  Drive token, trading key, timer, Work, or REAL/holdout access.

## Acceptance gates
1. PR-only read-only CI: `test_shadow_hour_recovery.py`,
   `test_gas_shadow_fallback_route.py`, and public offline safety suite PASS.
2. After merging to `main`, inspect the FIRST actual existing GAS or native
   cron run: `AVRORA_RECOVERY RUN HOUR <n>` or `IDLE`, no exposure of private
   strategies in logs.
3. For a recovered hour, require 64/64 verified source cases, full private Drive
   JSON, separate verified SHA ACK, and subsequent private graph ACK. Public
   artifact presence or green job alone is not enough.
4. Rerun while a just-completed hour is within the lookback: no duplicate
   receipt or graph event for its 64 candidate IDs.
5. Record any still-missing hours: both GAS time triggers and GitHub cron are
   best effort; recovery can act ONLY if at least one later clock fires.
6. Confirm independent CHECK2 and forward market economics separately before
   any claim of profit or safe SIM/REAL promotion.

## Scientific boundary
`REAL=OFF`, `HOLDOUT=SEALED`. 64 cases are historical P816
discovery-only on previously seen data, not independent OOS. Public aggregate
still explicitly marks `check2=NOT_INDEPENDENTLY_RECONSTRUCTED`,
`oos=false`, `maker_fill_proven=false`. Partial recovery, restored uptime,
or many positive historical candidates do not demonstrate executable alpha.

## Repos
* Public orchestrator: https://github.com/vicrex/avrora-colab-launcher
* Private research: https://github.com/vicrex/AVRORA
* Audit thread: https://github.com/vicrex/AVRORA/issues/61
* Source/receipt Drive destination: https://drive.google.com/drive/folders/1MXTBe21rTm1fVYzjUQ6NNf8cJzOQ0NKX
