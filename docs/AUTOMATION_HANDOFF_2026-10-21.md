# AVRORA automation handoff — 2026-10-21 (UTC)

## Source of truth
Public orchestrator: `vicrex/avrora-colab-launcher`, main `9181f0b3afa3f2031a948665c5137f17c96487ad`.
Private strategy research: `vicrex/AVRORA` (DO NOT publish private source, candles, keys, per-trade ledgers).
Execution: GitHub Actions scheduled workflow `.github/workflows/colab-launcher.yml` -> reusable `avrora-private-wave.yml` -> pinned private FULL13 source -> Google Colab CPU -> CHECK2 -> two aggregate-only GitHub Actions artifacts.
Safety invariants: `REAL=OFF`, `HOLDOUT=SEALED`, no live orders; 12 discovery weeks plus separate May (13 periods, six symbols, 69,576 source rows, 220 warmup bars per week).

## What is VERIFIED as of this handoff

- Public GitHub Actions scheduled runs: [39474595117](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39474595117), [39506465672](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39506465672) and [39527370117](https://github.com/vicrex/avrora-colab-launcher/actions/runs/39527370117) completed with success, but approximate gaps of 3h+ do NOT prove reliable hourly cadence.
- Run `39527370117`, event `schedule`, candidate `FIVE_WAVE_02`: true Colab FULL13 (not cache), CHECK2 verification; `REJECT_FOR_LIVE_DISCOVERY_ONLY` — this is NOT positive expectancy, OOS or proof of maker fills.
- GitHub artifact `12312799383` (verified receipt ZIP): `sha256:a323b31c761110456b5ae49b99bca548fdbbd7c00dedcb0fa0211237aa622eb4`, 2,092 bytes.
- GitHub artifact `12313619131` (vector delta ZIP): `sha256:3ae9e58143dcd963f843df92117e47bd625da536ed321134597689c6f4e700d1`, 1,413 bytes.
- Both ZIP artifacts from this run were delivered to the existing Google Drive research folder and independently fetched back. Downloaded Drive bytes matched both GitHub SHA-256 digests, no new archive copies required. **This was a manual connected-connector transfer inside ChatGPT, not an unattended GitHub-to-Drive execution.**
- Existing hourly ChatGPT task `AVRORA — 6 инструментов` is enabled, preserves the no-Work restriction, and already includes the exact transfer operation. No new scheduler was added.

## Exact verified transfer path (connector-only, no Work)

1. Read latest public run with `event=schedule`, locate both GitHub Actions artifacts using `fetch_workflow_run_artifacts`; read the `digest` property and require `expired=false`.
2. Before transfer, list existing Drive folder and deduplicate by exact file name and verified hash. Folder ID is held in the existing user's task settings; never embed it in public code.
3. Call `GitHub.download_workflow_artifact(repo_full_name='vicrex/avrora-colab-launcher', artifact_id=<integer>)`.
4. **IMPORTANT transport fix:** the current `Google_Drive.upload_file` schema accepts a STRING `file_uri`, despite textual documentation describing an object. Pass precisely the returned `file_uri.file_id` string (for example `file_000...`), not the object, not a local path or the download URL. Provide existing Drive folder ID, deterministic ZIP file name and `application/zip` MIME.
5. Fetch the uploaded Drive file again with `download_raw_file=true, include_base64=false`. Compare the actual ZIP byte SHA-256 with the published GitHub artifact `digest` and assert ZIP member names. Only after readback declare file delivery verified. A status in connector response alone is insufficient.
6. Each run is idempotent; if the exact verified ZIP already exists in Drive, do not re-upload or overwrite it. For failure, report `DELIVERY_BLOCKED`, keep artifacts, allow retry later.

## Unfinished / known blockers

1. **Fully unattended public GitHub-to-Drive delivery is NOT proven**. The two ZIP transfers in this handoff used an existing hourly ChatGPT task's connector path manually. The next natural task execution must demonstrate an unattended readback-verified delivery. Do not install a broader Drive permission into the existing Colab-only token. A GitHub-only alternative would need a separate, least-privileged archiver credential, verified before enablement.
2. The private `vicrex/AVRORA` `research-ingress-drain` workflow is failing before job steps (latest [39535965230](https://github.com/vicrex/AVRORA/actions/runs/39535965230), job `119012556257`, steps `[]`). Changing research Python or blind reruns cannot repair a pre-runner allocation failure. Investigate GitHub Actions billing/quota/status before claiming it fixed. Public GitHub Actions runners do work, but their `GITHUB_TOKEN` cannot automatically gain access to private resources.
3. The public bounded candidate catalog has only 12 SHA-frozen `FIVE_WAVE_01..12` candidates chosen by UTC hour modulo 12 and cached by dataset/code hash. This is **NOT automatic novel-hypothesis generation**; after all are tested, new code + reviewed adapter + preregistered source are required. Do not repeat rejected hypotheses as new evidence or unlock holdout.
4. No two consecutive **complete unattended** cycles have yet been verified from new hypothesis -> immutable preregistration -> actual Colab execution -> independent CHECK2 -> append-only graph ingest -> Drive proof -> ACK. No profitability claim.
5. This handoff is public and contains only operational metadata, no secret tokens, private source content, raw prices or per-trade trades.

## Next acceptance criteria

- Observe next public `event=schedule`, distinguish `cache-hit` from fresh Colab, and validate both GitHub artifacts (especially `*-vector-delta-<run>-<attempt>`).
- Existing authorized hourly consumer automatically uploads exactly once and verifies ZIP SHA-256 on Drive readback, then persists a durable ACK; inspect run logs, not model narration.
- Migrate the immutable research ingress trigger/receipt transport to a safe supported public orchestration boundary if private pre-runner quota remains broken, **without exposing private code/data**.
- Run a new approved/preregistered candidate through an independently verified FULL13/CHECK2 cycle; no automatic REAL promotion.
- No new timers, no paid services, no ChatGPT Work/Cloud Browser/Computer Use without new user authorization.
