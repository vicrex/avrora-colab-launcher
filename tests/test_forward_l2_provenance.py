import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import avrora_forward_l2_provenance as p

BASE_MS=1793000000000

def book(sym,kind="snapshot",u=100,seq=300):
    bids=[["100","5"],["99","3"]] if kind=="snapshot" else [["100","4"]]
    asks=[["101","6"],["102","2"]] if kind=="snapshot" else [["101","7"]]
    return {"topic":f"orderbook.50.{sym}","type":kind,"ts":BASE_MS,
            "cts":BASE_MS-2,"data":{"s":sym,"b":bids,"a":asks,"u":u,"seq":seq}}

def trade(sym):
    return {"topic":f"publicTrade.{sym}","type":"snapshot","ts":BASE_MS,
            "data":[{"s":sym,"S":"Sell","T":BASE_MS-1,"v":"0.5","p":"100.00",
                     "i":sym+"-unique-id","seq":400}]}

def sample(path, *, mutate=None, omit=None):
    chain=p.AppendChain(path)
    try:
        counter=0
        for sym in p.SYMBOLS:
            for typ in ("snapshot","delta","trade"):
                if (sym,typ)==omit:continue
                frame=trade(sym) if typ=="trade" else book(sym,typ,100 if typ=="snapshot" else 101,300 if typ=="snapshot" else 301)
                if mutate and mutate[0]==sym and mutate[1]==typ: mutate[2](frame)
                counter+=1
                chain.add(frame,(BASE_MS+counter)*1000000,(1000000000000000+counter))
    finally:chain.close()

class Prove(unittest.TestCase):
    def test_full_six_stream_records_and_hash_chain(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f)
            r=p.verify_file(f)
            self.assertEqual(r["record_count"],18)
            self.assertEqual(r["status"],"PASS_RECORDED_PUBLIC_FEED_COVERAGE_ONLY")
            self.assertFalse(r["maker_fill_verified"])
            self.assertFalse(r["actual_order_receipts_verified"])
            self.assertFalse(r["oos_verified"])
            self.assertTrue(all(r["counts"]["trades"][s]==1 for s in p.SYMBOLS))
    def test_missing_delta_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,omit=("BTCUSDT","delta"))
            self.assertEqual(p.verify_file(f)["status"],"BLOCKED_INCOMPLETE_L2_AND_TRADES")
    def test_tamper_fails_sha_chain(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f)
            x=f.read_bytes().replace(b'"v":"0.5"',b'"v":"0.6"',1)
            f.write_bytes(x)
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_HASH_CHAIN"):
                p.verify_file(f)
    def test_illegal_symbol_blocks(self):
        def wrong(x):x["topic"]="orderbook.50.DOGEUSDT"
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,mutate=("BTCUSDT","snapshot",wrong))
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_TOPIC"):
                p.verify_file(f)
    def test_delta_without_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,omit=("BTCUSDT","snapshot"))
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_DELTA_WITHOUT_VALID_SNAPSHOT"):
                p.verify_file(f)
    def test_trade_side_must_be_aggressor(self):
        def wrong(x):x["data"][0]["S"]="Unknown"
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,mutate=("BTCUSDT","trade",wrong))
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_TRADE_SOURCE"):
                p.verify_file(f)
    def test_crossed_book_fails(self):
        def wrong(x):x["data"]["a"]=[["99","5"]]
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,mutate=("BTCUSDT","snapshot",wrong))
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_CROSSED_BOOK"):
                p.verify_file(f)
    def test_replay_sequence_fails(self):
        def wrong(x):x["data"]["u"]=100
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,mutate=("BTCUSDT","delta",wrong))
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_BOOK_SEQUENCE_REPLAY"):
                p.verify_file(f)
    def test_clock_far_from_provider_fails(self):
        def wrong(x):x["ts"]=BASE_MS-600000
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,mutate=("BTCUSDT","trade",wrong))
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_PROVIDER_RECEIPT_CLOCK_DRIFT"):
                p.verify_file(f)
    def test_max_seconds_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_DURATION"):
                import asyncio
                asyncio.run(p.capture(Path(d)/"test",p.MAX_DURATION_SECONDS+1))
    def test_bad_nonfinite_price(self):
        def wrong(x):x["data"]["a"]=[["NaN","4"]]
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,mutate=("BTCUSDT","snapshot",wrong))
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_INVALID_PRICE_SIZE"):
                p.verify_file(f)
    def test_duplicate_level(self):
        def wrong(x):x["data"]["b"]=[["100","4"],["100","5"]]
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"events.jsonl";sample(f,mutate=("BTCUSDT","snapshot",wrong))
            with self.assertRaisesRegex(p.Blocked,"BLOCKED_DUPLICATE_LEVEL"):
                p.verify_file(f)

if __name__=="__main__":unittest.main()
