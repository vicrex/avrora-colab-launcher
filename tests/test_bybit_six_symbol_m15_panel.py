"""Synthetic offline M15 panel checks: no private code, network, or execution."""
from __future__ import annotations
import csv
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools import bybit_six_symbol_archive_qc as qc
from tools import bybit_six_symbol_m15_panel as p

START = date(2026,10,23)
DAYS = [(START + timedelta(days=i)).isoformat() for i in range(3)]


def make_zip(symbol: str, day: str, *, early_receipt: bool=False,
             skip_slot: int|None=None) -> bytes:
    first = p.utc_timestamp(day)
    header = ["timestamp","symbol","side","size","price","tickDirection",
              "trdMatchID","grossValue","homeNotional","foreignNotional","RPI"]
    rows = [header]
    for slot in range(96):
        if slot == skip_slot:
            continue
        trades = [("Buy","1","10")]
        if slot == 0:
            trades = [("Buy","1","10"), ("Sell","2","11"),
                      ("Buy","3","9"), ("Sell","4","10.5")]
        for i,(side, size, price) in enumerate(trades):
            rows.append([str(first + slot*900 + .1 + i*.1), symbol, side,
                         size,price,"PlusTick",f"{day}-{symbol}-{slot}-{i}",
                         "1","1","1","0"])
    text = io.StringIO(newline="")
    csv.writer(text).writerows(rows)
    source_gz = gzip.compress(text.getvalue().encode("utf-8"),mtime=0)
    receipt = datetime.fromtimestamp(first + (43200 if early_receipt else
                                              86400 + 3600), timezone.utc).isoformat()
    manifest = {
        "schema":"AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2",
        "symbol":symbol, "day_utc":day, "real":"OFF",
        "holdout":"SEALED","kind":"DELAYED_PUBLIC_HISTORICAL_TRADES",
        "new_oos_proven":False,"fill_proven":False,
        "signal_realtime_available":False,
        "source_compressed_bytes":len(source_gz),
        "source_gz_sha256":hashlib.sha256(source_gz).hexdigest(),
        "source_text_lines":len(rows),
        "causally_usable_not_before_utc":receipt,
    }
    manifest["manifest_sha256"]=qc.sha(qc.canon(manifest))
    buf=io.BytesIO()
    with ZipFile(buf,"w") as z:
        z.writestr(f"{symbol}{day}.csv.gz", source_gz)
        z.writestr("manifest.json",qc.canon(manifest))
    return buf.getvalue()


class M15PanelTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.folder = Path(self.root.name)
        self.digests = {}
        for day in DAYS:
            self.digests[day]={}
            for symbol in qc.SYMBOLS:
                raw=make_zip(symbol,day)
                dest=self.folder / f"BYBIT_TRADES_{symbol}_{day}_123456.zip"
                dest.write_bytes(raw)
                self.digests[day][symbol] = "sha256:" + qc.sha(raw)

    def tearDown(self):
        self.root.cleanup()

    def swap(self,symbol,day,raw):
        (self.folder / f"BYBIT_TRADES_{symbol}_{day}_123456.zip").write_bytes(raw)
        self.digests[day][symbol]="sha256:"+qc.sha(raw)

    def test_two_days_contiguous_but_220_warmup_blocked(self):
        out=p.build_panel(self.folder,days=DAYS[:2],
                          github_digests={d:self.digests[d] for d in DAYS[:2]})
        self.assertEqual(out["all_bars_per_symbol"],192)
        self.assertEqual(out["minimum_engine_input_bars"],234)
        self.assertFalse(out["offline_feature_input_sufficient"])
        self.assertTrue(out["status"].startswith("BLOCKED_INSUFFICIENT"))
        self.assertFalse(out["live_or_sim_strategy_executable"])
        self.assertEqual(out["verified_archives"][0]["total_trades"],6*(96+3))
        for sym in qc.SYMBOLS:
            self.assertEqual(len(out["bars"][sym]),192)
            self.assertEqual(out["bars"][sym][95]["timestamp_ms"] + 900000,
                             out["bars"][sym][96]["timestamp_ms"])

    def test_ohlcv_flow_and_time_boundaries_exact(self):
        out=p.build_panel(self.folder,days=DAYS[:1],
                          github_digests={DAYS[0]:self.digests[DAYS[0]]})
        a=out["bars"]["BTCUSDT"][0]
        self.assertEqual(a["open"],"10")
        self.assertEqual(a["high"],"11")
        self.assertEqual(a["low"],"9")
        self.assertEqual(a["close"],"10.5")
        self.assertEqual(a["volume"],"10")
        self.assertEqual(a["buy_volume"],"4")
        self.assertEqual(a["sell_volume"],"6")
        self.assertEqual(a["turnover"],"100.0")
        self.assertEqual(a["trade_count"],4)
        self.assertEqual(a["timestamp_ms"],p.utc_timestamp(DAYS[0])*1000)

    def test_three_days_allow_offline_features_never_realtime(self):
        out=p.build_panel(self.folder,days=DAYS,github_digests=self.digests)
        self.assertEqual(out["all_bars_per_symbol"],288)
        self.assertTrue(out["offline_feature_input_sufficient"])
        self.assertEqual(out["max_retro_model_exit_bars"],55)
        self.assertFalse(out["live_or_sim_strategy_executable"])
        self.assertFalse(out["realtime_signal_proven"])
        self.assertFalse(out["maker_queue_fill_proven"])
        self.assertEqual(out["real"],"OFF")
        self.assertEqual(out["holdout"],"SEALED")

    def test_nonconsecutive_days_block_before_read(self):
        with self.assertRaisesRegex(ValueError,"NONCONSECUTIVE"):
            p.build_panel(self.folder,days=[DAYS[0],DAYS[2]],
                          github_digests={d:self.digests[d] for d in (DAYS[0],DAYS[2])})

    def test_missing_symbol_archive_fails_closed(self):
        self.digests[DAYS[0]].pop("ETHUSDT")
        with self.assertRaisesRegex(ValueError,"EXACT_SIX"):
            p.build_panel(self.folder,days=[DAYS[0]],
                          github_digests={DAYS[0]:self.digests[DAYS[0]]})

    def test_tampered_zip_fails_before_normalization(self):
        f=next(self.folder.glob(f"BYBIT_TRADES_BTCUSDT_{DAYS[0]}_*.zip"))
        f.write_bytes(f.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError,"ZIP_SHA"):
            p.build_panel(self.folder,days=[DAYS[0]],
                          github_digests={DAYS[0]:self.digests[DAYS[0]]})

    def test_missing_m15_bar_fails_closed(self):
        self.swap("BTCUSDT",DAYS[0],
                  make_zip("BTCUSDT",DAYS[0],skip_slot=23))
        with self.assertRaisesRegex(ValueError,"MISSING_M15_BAR"):
            p.build_panel(self.folder,days=[DAYS[0]],
                          github_digests={DAYS[0]:self.digests[DAYS[0]]})

    def test_archive_received_before_day_end_is_blocked(self):
        self.swap("BTCUSDT",DAYS[0],
                  make_zip("BTCUSDT",DAYS[0],early_receipt=True))
        with self.assertRaisesRegex(ValueError,"RECEIVED_BEFORE_UTC_DAY_ENDED"):
            p.build_panel(self.folder,days=[DAYS[0]],
                          github_digests={DAYS[0]:self.digests[DAYS[0]]})


if __name__ == "__main__":
    unittest.main()
