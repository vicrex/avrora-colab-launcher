"""Offline six-symbol M15 panel derived only from SHA-verified, delayed Bybit trades.

Transport / retrospective QC, NOT an order executor, not first-seen market data.
All source ZIPs are verified by the existing independent six-symbol QC gate.
No real trades, sealed holdout access, API credentials, network or scheduler.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile

from tools import bybit_six_symbol_archive_qc as qc

SCHEMA = "AVRORA_BYBIT_DELAYED_M15_SIX_SYMBOL_PANEL_V1"
BAR_SECONDS = 900
BARS_PER_DAY = 96
WARMUP_BARS = 220
EXIT_BARS = 12
MIN_FEATURE_BARS = WARMUP_BARS + EXIT_BARS + 2


def fail(code: str) -> None:
    raise ValueError("BLOCKED_" + code)


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def utc_timestamp(day: str) -> int:
    try:
        return int(datetime.combine(date.fromisoformat(day),
                                    datetime.min.time(),
                                    timezone.utc).timestamp())
    except (ValueError, TypeError):
        fail("INVALID_UTC_DATE")


def source_filename(symbol: str, day: str) -> str:
    return f"{symbol}{day}.csv.gz"


def _iso(when: str) -> datetime:
    try:
        out = datetime.fromisoformat(when.replace("Z", "+00:00"))
        if out.tzinfo is None or out.utcoffset() != timedelta():
            fail("SOURCE_AVAILABILITY_NOT_UTC")
        return out
    except (ValueError, AttributeError):
        fail("SOURCE_AVAILABILITY_TIMESTAMP")


def build_one_day(path: Path, *, symbol: str, day: str) -> tuple[list[dict], dict]:
    """Parse the verified ZIP once more, retaining only 96 fixed-size M15 bars."""
    first_epoch = utc_timestamp(day)
    expected = source_filename(symbol, day)
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
        received = _iso(manifest["causally_usable_not_before_utc"])
        if received < datetime.fromtimestamp(first_epoch+86400, timezone.utc):
            fail("ARCHIVE_RECEIVED_BEFORE_UTC_DAY_ENDED")
        if manifest.get("signal_realtime_available") is not False or (
            manifest.get("new_oos_proven") is not False or
            manifest.get("fill_proven") is not False or
            manifest.get("real") != "OFF" or manifest.get("holdout") != "SEALED"
        ):
            fail("SOURCE_MISREPRESENTS_REALTIME_OR_FILL")
        gz_bytes = z.read(expected)
    buckets: list[dict | None] = [None] * BARS_PER_DAY
    with gzip.GzipFile(fileobj=io.BytesIO(gz_bytes)) as gz:
        with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
            for trade in csv.DictReader(text):
                # int(float(epoch)) is exact for every positive second at these dates,
                # including boundary events at XX:15:00, and ignores subsecond noise.
                epoch = int(float(trade["timestamp"]))
                slot = (epoch - first_epoch) // BAR_SECONDS
                if not 0 <= slot < BARS_PER_DAY:
                    fail("TRADE_OUTSIDE_SOURCE_DAY")
                try:
                    price = Decimal(trade["price"])
                    size = Decimal(trade["size"])
                except InvalidOperation:
                    fail("INVALID_TRADE_PRICE_OR_SIZE")
                if not price.is_finite() or not size.is_finite() or price <= 0 or size <= 0:
                    fail("NONPOSITIVE_OR_NONFINITE_PRICE_OR_SIZE")
                side = trade["side"]
                if side not in ("Buy", "Sell"):
                    fail("UNKNOWN_AGGRESSOR_SIDE")
                bar = buckets[slot]
                if bar is None:
                    bar = {
                        "timestamp_ms": (first_epoch + slot * BAR_SECONDS)*1000,
                        "open": price, "high": price, "low": price,
                        "close": price, "volume": Decimal(0),
                        "turnover": Decimal(0), "buy_volume": Decimal(0),
                        "sell_volume": Decimal(0), "trade_count": 0,
                    }
                    buckets[slot] = bar
                bar["high"] = max(bar["high"], price)
                bar["low"] = min(bar["low"], price)
                bar["close"] = price
                bar["volume"] += size
                bar["turnover"] += size * price
                bar["buy_volume" if side == "Buy" else "sell_volume"] += size
                bar["trade_count"] += 1
    if any(bar is None for bar in buckets):
        fail("MISSING_M15_BAR")
    decoded = []
    for bar in buckets:
        assert bar is not None
        if bar["buy_volume"] + bar["sell_volume"] != bar["volume"]:
            fail("AGGRESSOR_FLOW_CONSERVATION")
        if not bar["low"] <= bar["open"] <= bar["high"] or (
                not bar["low"] <= bar["close"] <= bar["high"]):
            fail("OHLC_INTEGRITY")
        decoded.append({
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in bar.items()
        })
    return decoded, {
        "symbol": symbol, "day_utc": day,
        "manifest_sha256": manifest["manifest_sha256"],
        "source_gz_sha256": manifest["source_gz_sha256"],
        "archive_usable_not_before_utc": received.isoformat(),
        "m15_bars": len(decoded),
        "trade_count": sum(item["trade_count"] for item in decoded),
    }


def build_panel(folder: Path, *, days: list[str], github_digests: dict) -> dict:
    if len(days) < 1 or len(days) != len(set(days)):
        fail("EMPTY_OR_DUPLICATE_DAYS")
    parsed = [date.fromisoformat(day) for day in days]
    if days != sorted(days) or any(b != a + timedelta(days=1)
                                  for a,b in zip(parsed, parsed[1:])):
        fail("NONCONSECUTIVE_OR_UNSORTED_DAYS")
    if set(github_digests) != set(days):
        fail("DIGEST_DAYS_MISMATCH")
    # Verify bytes, CRC, exact symbol/day coverage and sorted trades before
    # computing even retrospective features. This is deliberately expensive.
    verified = [qc.validate_six(folder, day=day, github_digests=github_digests[day])
                for day in days]
    bars = {symbol: [] for symbol in qc.SYMBOLS}
    lineage = []
    for day in days:
        for symbol in qc.SYMBOLS:
            files = list(folder.glob(f"BYBIT_TRADES_{symbol}_{day}_*.zip"))
            if len(files) != 1:
                fail("DUPLICATE_OR_MISSING_SYMBOL_DAY")
            portion, source = build_one_day(files[0], symbol=symbol, day=day)
            before = bars[symbol][-1]["timestamp_ms"] if bars[symbol] else None
            if before is not None and portion[0]["timestamp_ms"] != before + 900000:
                fail("NONCONTIGUOUS_CROSS_DAY_M15")
            bars[symbol].extend(portion)
            lineage.append(source)
    sizes = {symbol: len(bars[symbol]) for symbol in qc.SYMBOLS}
    if len(set(sizes.values())) != 1:
        fail("UNEVEN_SYMBOL_PANEL")
    count = next(iter(sizes.values()))
    if count != len(days) * BARS_PER_DAY:
        fail("UNEXPECTED_M15_COUNT")
    for symbol in qc.SYMBOLS:
        if any(b["timestamp_ms"] != a["timestamp_ms"] for a,b in
               zip(bars[qc.SYMBOLS[0]],bars[symbol])):
            fail("PANEL_NOT_ALIGNED")
    source_available = max(source["archive_usable_not_before_utc"] for source in lineage)
    usable = count >= MIN_FEATURE_BARS
    report = {
        "schema": SCHEMA,
        "status": "PASS_TRANSPORT_ONLY_FEATURE_WARMUP_AVAILABLE" if usable
                  else "BLOCKED_INSUFFICIENT_220_M15_WARMUP_AND_EXIT_LOOKAHEAD",
        "days_utc": days, "symbols": list(qc.SYMBOLS),
        "timeframe_seconds": BAR_SECONDS,
        "symbol_bars": sizes,
        "all_bars_per_symbol": count,
        "required_warmup_bars": WARMUP_BARS,
        "required_exit_bars": EXIT_BARS,
        "minimum_engine_input_bars": MIN_FEATURE_BARS,
        "offline_feature_input_sufficient": usable,
        "max_retro_model_exit_bars": max(0, count-WARMUP_BARS-EXIT_BARS-1),
        "source_already_observed_in_past": True,
        "earliest_all_sources_available_utc": source_available,
        "real": "OFF", "holdout": "SEALED",
        "realtime_signal_proven": False, "independent_oos_proven": False,
        "maker_queue_fill_proven": False, "markprice_funding_proven": False,
        "live_or_sim_strategy_executable": False,
        "verified_archives": [{
            "date_utc": d,
            "report_sha256": v["report_sha256"],
            "total_trades": v["total_trades"],
        } for d,v in zip(days,verified)],
        "lineage": lineage,
        "bars": bars,
    }
    report["panel_sha256"] = hashlib.sha256(canonical(report)).hexdigest()
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--days", nargs="+", required=True,
                   help="Consecutive completed UTC days YYYY-MM-DD")
    p.add_argument("--github-digests", type=Path, required=True,
                   help="JSON {day: {symbol: sha256:HEX}} from authoritative GitHub artifacts")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        fail("OUTPUT_ALREADY_EXISTS")
    digests = json.loads(args.github_digests.read_text(encoding="utf-8"))
    panel = build_panel(args.input_dir, days=args.days, github_digests=digests)
    args.output.write_bytes(canonical(panel) + b"\n")
    print(panel["status"], panel["all_bars_per_symbol"], panel["panel_sha256"])


if __name__ == "__main__":
    main()
