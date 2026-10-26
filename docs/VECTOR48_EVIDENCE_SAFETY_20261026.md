# AVRORA 48D evidence vectors — public-safe stage

The existing six-symbol hourly research pipeline computes 64 historical candidates. This PR adds an **offline stdlib-only postprocessor** running after the SHA-pinned private engine and before the unchanged private Drive delivery. It checks the original full report receipt, verifies 64 unique IDs, recomputes weekly totals and the 20bps fee model, and outputs one 48-dimensional raw feature vector and missing-value mask per candidate.

**Private boundary:** `sweep_private_vector48.json` contains private candidate IDs and metrics. It MUST NEVER be an Actions artifact, stdout body, log dump, PR attachment, or public repository file. GitHub output includes only count and SHA256 of this transient delta. It is securely deleted during the workflow cleanup on success/failure. The ORIGINAL full private report remains saved through the preexisting owner GAS/Drive delivery with independent readback. A separate private Drive indexer can reconstruct the vectors from those durable original reports.

**No fabricated proof:** candidate parameters unavailable inside the original report are `null`; `graph_attested=null` until Drive append ACK. `oos_verified=false`, `maker_fill_verified=false`, `funding_verified=false`, `l2_queue_verified=false`. These are price-path simulations only, no exchange calls. The fixed 48 dimensions cover family, side, parameters, portfolio constraints, train/previously-viewed validation and fee stress, missingness, and evidence quality. The private full index/HTML uses PCA visualization and parameter-only neighborhood diagnostics; **neither is a trading signal**.

**Scheduling:** Uses the exact preexisting multifamily job. No extra cron, GAS timer, Work, Colab service, broker credentials, holdout openings or orders. `REAL=OFF`, `HOLDOUT=SEALED`.

Test via `python -m unittest discover -s tests -p 'test_strategy_vector48.py' -v`. The public 10 synthetic tests cover 48D schema, candidate preservation, null masks, deterministic SHA, tampering, fee/weekly arithmetic, unsupported family/side, duplicate IDs and no false OOS/fill promotion.
