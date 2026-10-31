"""Offline safety, schema and receipt tests: NEVER connect to Bybit."""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools import avrora_public_market_firstseen_probe as p


def frame(topic,data,**fields):
    return json.dumps({"topic":topic,"data":data,**fields},
                      separators=(",",":"))


class PublicIngressProbeTests(unittest.TestCase):
    def test_six_symbol_trade_and_book_utc_monotonic_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            x=p.Probe(Path(d)/"raw.gz")
            x.ingest('{"op":"subscribe","success":true,"req_id":"research-0"}',1000,10)
            x.ingest('{"op":"subscribe","success":true,"req_id":"research-1"}',1001,11)
            t=1002
            for sym in p.SYMBOLS:
                x.ingest(frame("publicTrade."+sym,[{
                    "T":t-1,"s":sym,"S":"Sell","v":"1.0","p":"10.2",
                    "i":"trade-"+sym,"seq":1
                }]),t,t)
                t+=1
                x.ingest(frame("orderbook.50."+sym,{
                    "s":sym,"b":[["10.1","1"]],"a":[["10.2","2"]],
                    "u":8,"seq":33
                },type="snapshot",cts=t-1),t,t)
                t+=1
            receipt=x.receipt()
            self.assertEqual(receipt["accepted_market_frames"],12)
            self.assertEqual(sum(receipt["observed_unique_trades"].values()),6)
            self.assertEqual(sum(receipt["observed_l2_snapshots"].values()),6)
            self.assertEqual(receipt["accepted_subscribe_acks"],2)
            self.assertEqual(receipt["book_update_uncertainties"],0)
            self.assertEqual(receipt["raw_ingress_jsonl_sha256"],hashlib.sha256(
                gzip.decompress((Path(d)/"raw.gz").read_bytes())).hexdigest())
            self.assertEqual(receipt["compressed_source_sha256"],hashlib.sha256(
                (Path(d)/"raw.gz").read_bytes()).hexdigest())
            self.assertIs(receipt["live_trading_authorized"],False)
            self.assertIs(receipt["strategy_net_profit_proven"],False)
            self.assertIs(receipt["no_market_feed_gaps_proven"],False)
            self.assertEqual((receipt["real"],receipt["holdout"]),("OFF","SEALED"))
            self.assertEqual(receipt["receipt_sha256"],hashlib.sha256(p.canonical(
                {k:v for k,v in receipt.items() if k!="receipt_sha256"})).hexdigest())
            contents=gzip.decompress((Path(d)/"raw.gz").read_bytes())
            self.assertEqual(len(contents.splitlines()),12)
            self.assertEqual(json.loads(contents.splitlines()[0])["recv_utc_ms"],1002)
    def test_duplicate_trade_is_not_new_unique_trade(self):
        with tempfile.TemporaryDirectory() as d:
            x=p.Probe(Path(d)/"raw.gz")
            f=frame("publicTrade.BTCUSDT",[{
                "T":1000,"s":"BTCUSDT","S":"Buy","v":"1","p":"10",
                "i":"dup","seq":9}])
            x.ingest(f,1001,2000);x.ingest(f,1002,2001)
            self.assertEqual(x.trades["BTCUSDT"],1)
            self.assertEqual(x.duplicates,1)
            self.assertEqual(x.receipt()["accepted_market_frames"],2)
    def test_book_unknown_prior_and_missing_update_marked_uncertain(self):
        with tempfile.TemporaryDirectory() as d:
            x=p.Probe(Path(d)/"raw.gz")
            topic="orderbook.50.LINKUSDT"
            data={"s":"LINKUSDT","b":[],"a":[],"u":100,"seq":999}
            x.ingest(frame(topic,data,type="delta",cts=1000),1000,1000)
            x.ingest(frame(topic,dict(data,u=103),type="delta",cts=1001),1001,1001)
            self.assertEqual(x.book_gaps,2)
            x.close()
    def test_malformed_message_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            x=p.Probe(Path(d)/"raw.gz")
            for m,reason in [
                ('{"topic":"privateOrder.BTCUSDT","data":[]}',"UNEXPECTED_TOPIC"),
                ('{"topic":"publicTrade.BTCUSDT","data":{}}',"BATCH_SHAPE"),
                ('{"op":"subscribe","success":false}',"SUBSCRIBE_REJECTED"),
            ]:
                with self.assertRaisesRegex(ValueError,reason):
                    x.ingest(m,1000,1000)
            x.close()
    def test_clock_and_trade_schema_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            x=p.Probe(Path(d)/"raw.gz")
            trade=frame("publicTrade.BTCUSDT",[
                {"T":999,"s":"BTCUSDT","S":"Buy","v":"1","p":"1","i":"xx","seq":2}])
            x.ingest(trade,1000,2000)
            with self.assertRaisesRegex(ValueError,"MONOTONIC_REVERSED"):
                x.ingest(trade,1001,1999)
            with self.assertRaisesRegex(ValueError,"TRADE_SCHEMA"):
                x.ingest(frame("publicTrade.BTCUSDT",[
                    {"T":1000,"s":"BTCUSDT","S":"Wrong","v":"1","p":"1","i":"yy","seq":2}]),1002,2001)
            x.close()
    def test_untrusted_output_overwrite_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"raw.gz";path.write_bytes(b"original")
            with self.assertRaisesRegex(ValueError,"OVERWRITE"):
                p.Probe(path)
            self.assertEqual(path.read_bytes(),b"original")
    def test_no_credential_or_order_endpoints(self):
        import inspect
        src=inspect.getsource(p)
        self.assertEqual(p.ENDPOINT,"wss://stream.bybit.com/v5/public/linear")
        self.assertNotIn("/v5/private",src)
        self.assertNotIn("/v5/trade",src)
        self.assertNotIn('"op":"auth"',src)
        self.assertIn('"real":"OFF"',src)
        self.assertIn('"holdout":"SEALED"',src)


if __name__=="__main__":
    unittest.main()
