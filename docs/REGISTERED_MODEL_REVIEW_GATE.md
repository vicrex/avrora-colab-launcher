# AVRORA: public Issue → immutable review gate

Status: implementation in public \`vicrex/avrora-colab-launcher\`.
This bridge **does not** turn model proposals into executable strategies. It is the
first independently testable handoff after preregistration.

## Trigger and exact verified flow

1. Existing hourly ChatGPT model search writes a **public, owner-authored** \`AVRORA_RESEARCH_V1\` Issue. The sender pre-validates max 1000-character fields (prefer <=850).
2. The existing \`public-research-ingress.yml\` \`prereg\` job reads the current Issue via GitHub API, verifies the strict schema and \`REAL=OFF / HOLDOUT=SEALED\`, and writes SHA-256-bound \`AVRORA_PUBLIC_PREREG\` comment.
3. New \`review_gate\` job starts only after \`prereg\` succeeded, using the **same event**. No additional cron, Cloud Browser, Work, PAT or Google Drive privilege. Reads current Issue + comments.
4. Requires exact Issue owner \`vicrex\`, one intact prereg receipt authored by \`github-actions[bot]\`, exact canonical SHA and matching current Issue body. No private data, arbitrary shell, model package or URL is executed.
5. Writes a single durable \`AVRORA_EVALUATION_GATE_V1\` comment with \`BLOCKED_ADAPTER_NOT_REVIEWED_NO_EXECUTION\` and verifies the GitHub comment readback. Repeated event is an idempotent no-op, specification mutation or forged receipt is a hard block.
6. Saves an aggregate-only \`evaluation_gate.json\` artifact for the GitHub Action.

**Meaning of success:** reliable transport from registered hypothesis to reviewed-or-blocked decision. \`economic_run: NOT_RUN\`, \`drive_ack: NOT_DELIVERED\`, \`real: OFF\`, \`holdout: SEALED\`. Workflow green DOES NOT mean the candidate ran in Colab, has market PnL, or passed independent CHECK2.

## Next required engineering step to truly backtest CoRA-TTM / ResCP

Each novel model needs a **separately reviewed and pinned** implementation, e.g. an adapter with exact model/dependency SHA, locked six-symbol 13-week dataset read policy, strict causal H4 labels, no future leakage, frozen prereg hyperparameters, and an **independent checker**. The existing FULL13 execution code only recognizes frozen \`FIVE_WAVE_01..12\` IDs; mapping any unrelated research Issue to those IDs would produce fraudulent evidence and is prohibited.

A future approved adapter must be explicitly registered in a reviewed code change. **Do not** execute Python snippets, git URLs, arbitrary model code, parameters, or shell commands from public Issues. Only an approved adapter on a pinned private input may enter the Colab execution stage, with separate CHECK1/CHECK2, model/data hash verification, fee stress (16/20/25/40 bps), maker fill uncertainty, per-symbol/weekly economics in USDT/day, source integrity and readback on Drive. Until that exists the review gate must remain blocked rather than silently replacing ResCP with a generic baseline.

## Smoke test / rollback

Run \`python -m unittest discover -s tests -v\`; CI \`launcher-pr-offline.yml\` runs all tests on the PR without data or credentials.

After merge into \`main\`, edit an existing owner Issue title (without changing its accepted JSON body) to trigger safe \`issues.edited\` and verify **one** gate comment and artifact. Alternatively, manually dispatch existing \`public-research-ingress.yml\` with \`issue_number=14\`. Repeating must not duplicate the gate comment.

Rollback by reverting this PR's appended \`review_gate\` job and its code; preserve immutable prereg and gate comments. Keep GitHub Actions and GAS schedules as-is. No changes to real trading.
