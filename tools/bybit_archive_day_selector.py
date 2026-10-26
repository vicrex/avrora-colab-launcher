"""Select only completed, causally frozen Bybit source days for the existing hourly job.

The official six-symbol archive collector first began at 2026-10-23 UTC.
A rigid modulo-seven clock before 2026-10-30 wastes hours attempting dates
before the supported collection window. This pure selector changes no timer,
network, data, strategy, trading or permissions.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import sys

FIRST_ARCHIVE_DAY = date(2026, 10, 23)
MAX_BACKFILL_DAYS = 7


def select_utc_archive_day(now: datetime) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("BLOCKED_EXPECT_TIMEZONE_AWARE_CLOCK")
    utc_now = now.astimezone(timezone.utc)
    elapsed_completed_days = (utc_now.date() - FIRST_ARCHIVE_DAY).days
    if elapsed_completed_days < 1:
        # Used only if a future workflow is run before the first valid day ends.
        # Never request today's partial file or a date before first provenance.
        return {
            "status": "WAIT_FIRST_COMPLETED_OFFICIAL_ARCHIVE_DAY",
            "day": "",
            "lag": 0,
            "window_days": 0,
        }
    window = min(MAX_BACKFILL_DAYS, elapsed_completed_days)
    lag = (utc_now.hour % window) + 1
    chosen = utc_now.date() - timedelta(days=lag)
    if chosen < FIRST_ARCHIVE_DAY or chosen >= utc_now.date():
        raise ValueError("BLOCKED_SOURCE_DAY_OUT_OF_RANGE")
    return {
        "status": "READY_EXISTING_SIX_JOBS",
        "day": chosen.isoformat(),
        "lag": lag,
        "window_days": window,
    }


def main() -> None:
    selected = select_utc_archive_day(datetime.now(timezone.utc))
    for key in ("day", "lag", "window_days", "status"):
        print(f"{key}={selected[key]}")
    print(
        f"OFFICIAL_ARCHIVE_BACKFILL_LAG_DAYS_{selected['lag']}_"
        f"ELIGIBLE_WINDOW_{selected['window_days']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
