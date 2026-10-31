"""Offline regression tests for the existing Bybit six-job UTC lookback rotation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from tools.bybit_archive_day_selector import (
    FIRST_ARCHIVE_DAY,
    MAX_BACKFILL_DAYS,
    select_utc_archive_day,
)


class ArchiveDaySelectorTests(unittest.TestCase):
    def pick(self, day: int, hour: int):
        return select_utc_archive_day(
            datetime(2026, 10, day, hour, 23, tzinfo=timezone.utc))

    def test_first_day_not_yet_complete(self):
        self.assertEqual(self.pick(23, 23)["status"],
                         "WAIT_FIRST_COMPLETED_OFFICIAL_ARCHIVE_DAY")
        self.assertEqual(self.pick(23, 23)["day"], "")
        self.assertEqual(self.pick(23, 23)["lag"], 0)

    def test_oct24_first_completed_day(self):
        for hour in (0, 5, 23):
            x = self.pick(24, hour)
            self.assertEqual(x["day"], "2026-10-23")
            self.assertEqual(x["window_days"], 1)
            self.assertEqual(x["status"], "READY_EXISTING_SIX_JOBS")

    def test_oct25_rotation_has_two_days(self):
        self.assertEqual(self.pick(25, 4)["day"], "2026-10-24")
        self.assertEqual(self.pick(25, 5)["day"], "2026-10-23")
        self.assertEqual(self.pick(25, 5)["window_days"], 2)

    def test_oct26_only_three_eligible_days(self):
        selected = self.pick(26, 5)
        self.assertEqual(selected["window_days"], 3)
        self.assertEqual(selected["lag"], 2)
        self.assertEqual(selected["day"], "2026-10-24")
        self.assertEqual(self.pick(26, 6)["day"], "2026-10-25")
        self.assertEqual(self.pick(26, 7)["day"], "2026-10-23")

    def test_yesterday_prioritized_twelve_times_with_existing_hourly_clock(self):
        for hour in range(0, 24, 2):
            with self.subTest(hour=hour):
                x = self.pick(31, hour)
                self.assertEqual(x["window_days"], MAX_BACKFILL_DAYS)
                self.assertEqual(x["lag"], 1)
                self.assertEqual(x["day"], "2026-10-30")

    def test_older_six_covered_fairly_without_starvation(self):
        days = [self.pick(31, hour)["day"] for hour in range(1, 24, 2)]
        self.assertEqual(set(days), {
            "2026-10-24", "2026-10-25", "2026-10-26",
            "2026-10-27", "2026-10-28", "2026-10-29",
        })
        from collections import Counter
        self.assertTrue(all(n == 2 for n in Counter(days).values()))
        x = self.pick(31, 13)
        self.assertEqual(x["window_days"], MAX_BACKFILL_DAYS)
        self.assertEqual(x["lag"], 2)
        self.assertEqual(x["day"], "2026-10-29")
        self.assertGreaterEqual(datetime.fromisoformat(x["day"]).date(),
                                FIRST_ARCHIVE_DAY)

    def test_never_fetches_unfinished_utc_day(self):
        for day in range(24, 32):
            for hour in range(24):
                x = self.pick(day, hour)
                chosen = datetime.fromisoformat(x["day"]).date()
                self.assertLess(chosen, datetime(2026, 10, day).date())
                self.assertGreaterEqual(chosen, FIRST_ARCHIVE_DAY)

    def test_timezone_conversion_is_utc_not_wall_clock(self):
        local = datetime(2026, 10, 26, 8, 0,
                         tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(select_utc_archive_day(local)["day"], "2026-10-25")

    def test_naive_clock_blocked(self):
        with self.assertRaisesRegex(ValueError, "TIMEZONE_AWARE"):
            select_utc_archive_day(datetime(2026, 10, 26, 6))

    def test_workflow_gates_source_and_reuses_existing_job_matrix(self):
        wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" /
              "bybit-official-archive.yml").read_text(encoding="utf-8")
        self.assertIn("python -m tools.bybit_archive_day_selector", wf)
        self.assertIn("matrix.symbol", wf)
        self.assertIn("steps.day.outputs.status == 'READY_EXISTING_SIX_JOBS'", wf)
        self.assertIn("steps.cached.outputs.cache-hit != 'true'", wf)
        self.assertNotIn("lag=\"$((hour % 7 + 1))\"", wf)


if __name__ == "__main__":
    unittest.main()
