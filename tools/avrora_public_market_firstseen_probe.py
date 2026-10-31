"""Read-only bounded FIRST-OBSERVED public Bybit trade/L2 ingress probe.

This observes *this process's* ingress clock; it does not certify upstream
completeness, continuous seven-day first-seen coverage, maker fills or profit.
No private API, credentials, trading, SIM, replay or background loop.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import time

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","LINKUSDT","NEARUSDT")
TOPICS=tuple(f"publicTrade.{s}" for s in SYMBOLS)+tuple(
    f"orderbook.50.{s}" for s in SYMBOLS)
ENDPOINT="wss://stream.bybit.com/v5/public/linear"
SCHEMA="AVRORA_PUBLIC_FIRST_OBSERVED_TRADE_L2_SHORT_PROBE_V1"
MAX_RAW_MSG=2_000_000
MAX_FRAMES=100_000
MAX_UNCOMPRESSED=160_000_000


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode("utf-8")


class Probe:
    def __init__(self, out_file):
        self.out_file=Path(out_file)
        if self.out_file.exists():raise ValueError("BLOCKED_PROBE_OVERWRITE")
        self.source=self.out_file.open("xb")
        self.gz=gzip.GzipFile(filename="",mode="wb",fileobj=self.source,mtime=0)
        self.frames=0;self.uncompressed=0
        self.trades=Counter();self.books=Counter();self.snapshots=Counter()
        self.duplicates=0;self.skew=0;self.book_gaps=0;self.book_updates={}
        self.ids=set();self.acks=set()
        self.first_utc_ms=None;self.last_utc_ms=None
        self.last_mono_ns=None
        self.raw_digest=hashlib.sha256()
    def close(self):
        self.gz.close();self.source.close()
    def ingest(self,raw,utc_ms,monotonic_ns):
        """Caller stamps *immediately after recv* before JSON parsing."""
        if (type(utc_ms) is not int or type(monotonic_ns) is not int or
                utc_ms<=0 or monotonic_ns<=0):
            raise ValueError("BLOCKED_PROBE_RECEIPT_CLOCK")
        if self.last_mono_ns is not None and monotonic_ns<self.last_mono_ns:
            raise ValueError("BLOCKED_PROBE_MONOTONIC_REVERSED")
        self.last_mono_ns=monotonic_ns
        if not isinstance(raw,str) or len(raw.encode("utf-8"))>MAX_RAW_MSG:
            raise ValueError("BLOCKED_PROBE_RAW_SIZE")
        m=json.loads(raw)
        if not isinstance(m,dict):
            raise ValueError("BLOCKED_PROBE_BAD_MESSAGE")
        if m.get("op")=="subscribe":
            if m.get("success") is not True:
                raise ValueError("BLOCKED_PROBE_SUBSCRIBE_REJECTED")
            self.acks.add(str(m.get("req_id") or "ack"))
            return
        if m.get("op")=="pong" or m.get("ret_msg")=="pong":
            return
        topic=m.get("topic")
        if topic not in TOPICS:raise ValueError("BLOCKED_PROBE_UNEXPECTED_TOPIC")
        data=m.get("data")
        if topic.startswith("publicTrade."):
            symbol=topic.split(".",1)[1]
            if not isinstance(data,list):
                raise ValueError("BLOCKED_PROBE_TRADE_BATCH_SHAPE")
            if len(data)>1024:
                raise ValueError("BLOCKED_PROBE_TRADE_BATCH_CAP")
            for trade in data:
                if (not isinstance(trade,dict) or trade.get("s")!=symbol
                        or trade.get("S") not in ("Buy","Sell")
                        or not isinstance(trade.get("i"),str)
                        or not 1<=len(trade["i"])<=128
                        or type(trade.get("T")) is not int
                        or trade["T"]<=0
                        or not isinstance(trade.get("p"),str)
                        or not isinstance(trade.get("v"),str)
                        or type(trade.get("seq")) is not int):
                    raise ValueError("BLOCKED_PROBE_TRADE_SCHEMA")
                key=(symbol,trade["i"])
                if key in self.ids:
                    self.duplicates+=1
                    # preserve the original duplicate frame but never call it
                    # an additional unique trade.
                else:
                    self.ids.add(key);self.trades[symbol]+=1
                if trade["T"]>utc_ms:self.skew+=1
        else:
            symbol=topic.split(".",2)[2]
            if (not isinstance(data,dict) or data.get("s")!=symbol
                    or m.get("type") not in ("snapshot","delta")
                    or type(data.get("u")) is not int
                    or type(data.get("seq")) is not int
                    or type(m.get("cts")) is not int
                    or any(not isinstance(data.get(side),list) for side in ("a","b"))):
                raise ValueError("BLOCKED_PROBE_BOOK_SCHEMA")
            self.books[symbol]+=1
            u=data["u"];prev=self.book_updates.get(symbol)
            if m["type"]=="snapshot":
                self.snapshots[symbol]+=1
                self.book_updates[symbol]=u
            else:
                if prev is None or u<=prev or u>prev+1:
                    self.book_gaps+=1
                self.book_updates[symbol]=u
        self.frames+=1
        if self.frames>MAX_FRAMES:
            raise ValueError("BLOCKED_PROBE_FRAME_CAP")
        record=canonical({"recv_utc_ms":utc_ms,"recv_monotonic_ns":monotonic_ns,
                          "source_frame_json":raw})+b"\n"
        self.uncompressed+=len(record)
        if self.uncompressed>MAX_UNCOMPRESSED:
            raise ValueError("BLOCKED_PROBE_DISK_CAP")
        self.raw_digest.update(record)
        self.gz.write(record)
        if self.first_utc_ms is None:self.first_utc_ms=utc_ms
        self.last_utc_ms=utc_ms
    def receipt(self):
        self.close()
        compressed=self.out_file.read_bytes()
        report={
            "schema":SCHEMA,"status":"PROSPECTIVE_FIRST_OBSERVED_SHORT_PROBE",
            "source":ENDPOINT,"symbols":list(SYMBOLS),
            "observed_unique_trades":dict(self.trades),
            "observed_l2_frames":dict(self.books),
            "observed_l2_snapshots":dict(self.snapshots),
            "repeated_trade_ids":self.duplicates,
            "clock_skew_trades":self.skew,
            "book_update_uncertainties":self.book_gaps,
            "accepted_market_frames":self.frames,
            "accepted_subscribe_acks":len(self.acks),
            "first_receive_utc_ms":self.first_utc_ms,
            "last_receive_utc_ms":self.last_utc_ms,
            "raw_ingress_jsonl_sha256":self.raw_digest.hexdigest(),
            "compressed_source_sha256":hashlib.sha256(compressed).hexdigest(),
            "compressed_bytes":len(compressed),
            "uncompressed_bytes":self.uncompressed,
            "continuous_seven_day_coverage_proven":False,
            "no_market_feed_gaps_proven":False,
            "any_fills_proven":False,
            "maker_queue_priority_proven":False,
            "independent_check2":False,
            "oos_proven":False,"strategy_net_profit_proven":False,
            "live_trading_authorized":False,
            "real":"OFF","holdout":"SEALED",
        }
        report["receipt_sha256"]=hashlib.sha256(canonical(report)).hexdigest()
        return report


async def collect(seconds, probe):
    if type(seconds) is not int or not 15<=seconds<=90:
        raise ValueError("BLOCKED_PROBE_DURATION")
    from websockets.asyncio.client import connect
    async with connect(ENDPOINT,max_size=MAX_RAW_MSG,
                       ping_interval=20,ping_timeout=10,close_timeout=5) as ws:
        for i,topics in enumerate((TOPICS[:6],TOPICS[6:])):
            await ws.send(json.dumps({"op":"subscribe","req_id":f"research-{i}",
                                      "args":list(topics)}))
        deadline=time.monotonic()+seconds
        while (remain:=deadline-time.monotonic())>0:
            try:
                incoming=await asyncio.wait_for(ws.recv(),timeout=min(remain,12))
            except asyncio.TimeoutError:
                # Timeout when no messages is a possible missing-feed interval;
                # neither silent retry nor fabricated fill is acceptable.
                if time.monotonic()>=deadline:break
                raise ValueError("BLOCKED_PROBE_PUBLIC_FEED_TIMEOUT")
            # Arrival timestamp is obtained IMMEDIATELY on receipt.
            received_wall=time.time_ns()//1_000_000
            received_mono=time.monotonic_ns()
            probe.ingest(incoming,received_wall,received_mono)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seconds",type=int,default=45)
    p.add_argument("--out-dir",required=True)
    a=p.parse_args()
    root=Path(a.out_dir)
    if root.exists():raise ValueError("BLOCKED_PROBE_OUTPUT_EXISTS")
    root.mkdir(parents=True)
    probe=Probe(root/"observed_ws_frames.jsonl.gz")
    try:
        asyncio.run(collect(a.seconds,probe))
        report=probe.receipt()
        (root/"probe_receipt.json").write_bytes(canonical(report)+b"\n")
        sufficient=(report["accepted_subscribe_acks"]>=2
                    and all(report["observed_unique_trades"].get(s,0)>0 for s in SYMBOLS)
                    and all(report["observed_l2_snapshots"].get(s,0)>0 for s in SYMBOLS))
        if not sufficient:
            raise ValueError("BLOCKED_PROBE_SIX_SYMBOL_TRADE_BOOK_COVERAGE")
        print("PASS_PUBLIC_SIX_SYMBOL_FIRST_OBSERVED_SHORT_PROBE",
              report["accepted_market_frames"],report["receipt_sha256"])
    finally:
        if not probe.source.closed:probe.close()


if __name__=="__main__":
    main()
