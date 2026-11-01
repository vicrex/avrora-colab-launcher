"""Stream-check original Bybit gzip trade CSV against its claimed UTC source day.

This is independent of SHA/CRC: an intact gzip with a re-labelled filename
can still contain events from the wrong date. No trading, no API or credentials.
Only the declared row count, in-day timestamps and symbol are validated here;
provider completeness and historical first-seen remain unproven.
"""
from __future__ import annotations
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
from pathlib import Path

COLUMNS = ("timestamp", "symbol", "side", "size", "price",
           "tickDirection", "trdMatchID", "grossValue",
           "homeNotional", "foreignNotional", "RPI")
MAX_ROWS = 20_000_000


def as_microseconds(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("BLOCKED_ARCHIVE_EVENT_TIMESTAMP")
    try:
        number = Decimal(value) * 1_000_000
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("BLOCKED_ARCHIVE_EVENT_TIMESTAMP") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError("BLOCKED_ARCHIVE_EVENT_TIMESTAMP")
    return int(number)


def verify_day(path, symbol, day, expected_lines):
    if (type(day) is not date or not isinstance(symbol, str)
            or not symbol.endswith("USDT")
            or type(expected_lines) is not int
            or expected_lines < 2 or expected_lines > MAX_ROWS + 1):
        raise ValueError("BLOCKED_ARCHIVE_EVENT_SCOPE_ARGUMENTS")
    begin = int(datetime.combine(day, datetime.min.time(),
                                 tzinfo=timezone.utc).timestamp()) * 1_000_000
    end = int(datetime.combine(day + timedelta(days=1), datetime.min.time(),
                               tzinfo=timezone.utc).timestamp()) * 1_000_000
    rows = 0
    earliest = latest = None
    hours = [0] * 24
    try:
        with gzip.open(Path(path), "rt", encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            if tuple(next(reader, ())) != COLUMNS:
                raise ValueError("BLOCKED_ARCHIVE_EVENT_HEADER")
            for fields in reader:
                rows += 1
                if rows >= expected_lines or rows > MAX_ROWS:
                    raise ValueError("BLOCKED_ARCHIVE_EVENT_ROW_COUNT")
                if len(fields) != len(COLUMNS):
                    raise ValueError("BLOCKED_ARCHIVE_EVENT_ROW_STRUCTURE")
                if fields[1] != symbol:
                    raise ValueError("BLOCKED_ARCHIVE_EVENT_WRONG_SYMBOL")
                event = as_microseconds(fields[0])
                if not begin <= event < end:
                    raise ValueError("BLOCKED_ARCHIVE_EVENT_OUTSIDE_UTC_DAY")
                earliest = event if earliest is None else min(earliest, event)
                latest = event if latest is None else max(latest, event)
                hours[(event - begin) // 3_600_000_000] += 1
    except (UnicodeError, csv.Error, EOFError, OSError) as exc:
        raise ValueError("BLOCKED_ARCHIVE_EVENT_CSV_OR_GZIP") from exc
    if rows != expected_lines - 1:
        raise ValueError("BLOCKED_ARCHIVE_EVENT_ROW_COUNT")
    return {
        "event_day_scope_verified": True,
        "event_day_rows": rows,
        "first_source_event_ms": earliest // 1000,
        "last_source_event_ms": latest // 1000,
        "hours_with_observed_events": sum(bool(v) for v in hours),
        "provider_all_events_completeness_proven": False,
        "individual_first_seen_proven": False,
    }
