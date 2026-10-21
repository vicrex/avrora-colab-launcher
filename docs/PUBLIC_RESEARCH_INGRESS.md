# Public AVRORA ingress — 2026-10-21

## What it fixes

The private AVRORA GitHub Actions ingress has a pre-runner failure. This patch moves **safe public preregistration** (not private code execution) to the already working public GitHub repository `vicrex/avrora-colab-launcher`.

New model hypotheses are submitted only as nonconfidential public Issue bodies. The workflow starts from the `issues` GitHub event, **not a new timer**. Only `vicrex`'s issues are processed. `workflow_dispatch` permits manual replay by issue number.

Each valid `AVRORA_RESEARCH_V1` request gets an idempotent comment containing its canonical SHA-256 and `PUBLIC_REGISTERED_BLOCKED_EXECUTION`. It is fetched back and checked before success. Duplicate identifiers and edits after preregistration are blocked. The workflow serializes all ingestion jobs and reads the live issue before recording a receipt, preventing races and outdated event snapshots. Public Issues are readable by anyone: **NEVER put private code, candle data, complete trade ledgers, financial credentials, account tokens or internal Drive IDs into an Issue.**

## Boundaries

- The launcher and FULL13 workflow remain unchanged; existing hourly cron remains the only public Colab schedule.
- All new proposals are `adapter=unreviewed-model-proposal`, `REAL=OFF`, `HOLDOUT=SEALED`; there is **no execution, verified profitability, holdout, maker fill or Drive ACK** from this ingress.
- No scope for private repo write, Colab credentials or Google Drive is added. GitHub's job token gets only `contents:read` and `issues:write`.
- The existing model-search automation should be retargeted to **public issues only after** this workflow merges and passes a live benign Issue test. The currently running private source and verified Colab jobs must not be broken.

## Test plan

Run `python -m unittest discover -s tests -v` in the project. Merge through a reviewed PR to `main`; the GitHub `issues` event does not work until the new workflow is on the default branch. Publish a harmless Issue from the repo owner and verify one comment and its SHA. Re-run with `workflow_dispatch` and verify no second comment. Mutate that Issue after acceptance and verify it is rejected.

The two consecutive **unattended GitHub→Drive cycles** are a separate acceptance condition and are NOT implied by the preregistration workflow.

## One-click Windows setup

Unzip the bundle. Double-click `INSTALL_ONE_CLICK.cmd` (Git for Windows, Python and authenticated git push required). It clones only the public repository into a new temporary directory, fetches the pre-existing feature branch, copies four allowlisted files, runs the complete public test suite, commits and pushes, then opens the GitHub PR comparison. Approve/merge that PR in GitHub; GitHub Issues workflows only become active when the workflow exists on the default branch. The script does **not** request or upload a token and never force-pushes.

When the GitHub connector refuses repository writes for security reasons, the package cannot be published directly from ChatGPT. This installer is an owner-authorized route using the owner's authenticated local Git credentials.
