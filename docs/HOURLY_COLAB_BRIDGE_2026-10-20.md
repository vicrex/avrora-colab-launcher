# AVRORA hourly private-Colab candidate bridge (2026-10-20)

## Scope
This branch connects the already working **hourly** `avrora-private-wave.yml` to the 12 preregistered five-wave discovery hypotheses from 2026-10-19. It does **not** add a timer, reconfigure the user's paid Colab, request broader Drive OAuth, access sealed holdout, trade, or alter the legacy Wave/Fib replay. `REAL=OFF`, `HOLDOUT=SEALED`.

## Why the prior hourly run did not search new strategies
The scheduled workflow pinned private source at `9c607da975dda64b7f50fe34004fa78e7225ff68`. Its valid SHA256 cache omitted Colab on repeat runs, hence it never executed the frozen 12-case five-wave proposal catalog. A previously tested engine existed only in [draft PR #1](https://github.com/vicrex/avrora-colab-launcher/pull/1), without cloud deployment.

## Implementation
1. Import preregistered, offline-tested causal signal engine and independent full-trade/portfolio CHECK2 from draft PR #1; strengthen candidate ID/order validation to prevent output injection.
2. Within the **existing 37-minute hourly schedule**, select 1 of 12 strictly allowlisted candidates. Identity is `FIVE_WAVE_01..12`. Each is paired with pinned dataset, prereg and code hashes.
3. Restore aggregate-only SHA-keyed per-candidate cache. Verify the stored receipt using pinned engine+checker hashes. On HIT: `IDLE_NO_NEW_APPROVED_CANDIDATE`. On MISS: use existing narrow Colab credentials and read-only private source checkout, execute research in ephemeral Colab and independently verify full proposal/trade ledger.
4. Upload only the verified aggregate receipt as a 7-day artifact and cache it keyed by dataset+code+prereg+candidate. On failure: no verified artifact, fail closed. Remove temporary private checkout and credentials even on failure.
5. The old Wave/Fib replay cache is separate from the new candidate cache. Wave cache HIT must **not** prevent candidate work.

## Truthful limits
- May and July source was previously used for discovery. All 12 variants are **discovery only, not OOS**.
- The M15 OHLC model does not prove Bybit maker fills, order book queue, or funding; positive discovery would require separate independent review, not auto-promotion.
- GitHub Actions schedules are best effort. Candidate assignment uses the executing UTC hour modulo 12; a skipped hour can delay the corresponding variant until the next cycle.
- GitHub Actions cache may expire/evict. It is not a durable cross-month ledger, and public aggregate artifacts retain for 7 days. **Automatic Google Drive delivery and durable queue ingestion remain separate, unverified integration tasks**; never claim full research autonomy from this partial bridge.
- Merging onto `main` activates candidate work under the **already enabled** `AVRORA_PRIVATE_WAVE_ENABLED=true` flag at the next hourly tick. First real Colab replay and subsequent cache HIT both need proof URLs.

## Acceptance evidence
PR CI: `python -m unittest discover -s tests -v` under Python 3.12; independent source+payload hash tests, causal tests, adversarial receipt tests, schedule/cache tests. Real remote execution must be separately observed; absence of such a run is not a PASS.
