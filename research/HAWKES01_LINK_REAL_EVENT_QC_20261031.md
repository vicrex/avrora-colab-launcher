# AVRORA HAWKES01 — first actual Bybit event-ID and source-clock audit

**Source**: public delayed Bybit LINKUSDT completed 2026-10-30 historical trades,
SHA verified by original existing official transport in FULL13 run
[41202022188](https://github.com/vicrex/avrora-colab-launcher/actions/runs/41202022188).
GitHub artifact `13043072139`, archive `LINKUSDT2026-10-30.csv.gz`.
Original gzip SHA256:
`0d6b5e382d7679da6d7d1ddb4e0f394cba42db5e4966ab8d1822e7d106dcf163`.
Existing signed manifest SHA:
`a55816406bcf15e355a83aaca7ae84382393cdecb0cb43d641ea1690cf78f241`.
Archive receipt: `2026-10-31T12:38:46.719619Z`, **after the market day ended**.

**Real independent parsed event QC 2026-10-31** (not synthetic):
- 340,093 actual historical transaction records;
- 340,093 distinct exchange trdMatchID values, zero duplicate IDs;
- 165,248 aggressor Buy / 174,845 aggressor Sell;
- all 24 UTC hours with trade observations;
- timestamp sorting PASS (no time reversal); maximum observed gap 39.023s;
- 0 RPI flag rows; CSV schema exactly `timestamp,symbol,side,size,
  price,tickDirection,trdMatchID,grossValue,homeNotional,foreignNotional,RPI`.
- Aggregate canonical report SHA256
  `d2e0148a70d3048b0a9e748688bb23ddd6047d330503ec81648b192579eaef13`.

Read-only `tools/bybit_trade_event_qc.py` provides streaming full input
verification: independent source manifest SHA, gzip CRC and byte SHA from
existing `transport.verify`, strict timestamp precision and completed-day
UTC bounds, trade IDs, aggressor side, RPI/tick/positive quantity,
24 observed hourly bins and hard 750k row resource cap.
The *one-shot* existing workflow additionally rechecks 42/42 GitHub
artifact **metadata only**, downloads only the single known LINK gzip
into ephemeral runner storage and compares source QC SHA with this frozen
locally measured result. It does NOT download other historical days or
retry Colab/strategy tests.

**Boundary**: 42 names do not prove all 42 underlying gzip bytes yet.
Even 24 hourly observations and no duplicate IDs do not prove provider
complete market trade count. The official delayed archive received on
31 Oct contains event-exchange timestamps from 30 Oct, **NOT per-event
first-seen ingest timestamps from 30 Oct**. Neither genuine causal
seven-day HAWKES fitting/OOS nor independent CHECK2, maker fills,
fees/funding, SIM-replay parity or live trade authority can be derived.
`REAL=OFF`, `HOLDOUT=SEALED`. Research-only evidence.
