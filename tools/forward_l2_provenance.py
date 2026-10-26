#!/usr/bin/env python3
"""AVRORA independent public-data evidence recorder and verifier.

No keys, no private endpoints, no order entry and never proof of maker fill.
Requires real supported network access to Bybit WebSocket public linear feed.
Offline verifier validates exact append-only hash-chain, snapshots, deltas,
receipt timestamps, provider timestamps, aggressor trade checks, and 6-symbol
channel coverage. A recorded market event does not prove hypothetical fill.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import sys
import time

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "LINKUSDT", "XRPUSDT")
SOURCE = "wss://stream.bybit.com/v5/public/linear"
SCHEMA = "AVRORA_PUBLIC_LINEAR_L50_TRADE_RECEIPT_V1"
ZERO = "0" * 64
MAX_FRAME_BYTES = 1_000_000
MAX_TOTAL_BYTES = 80_000_000
MAX_DURATION_SECONDS = 300

class Blocked(ValueError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def integer(value, key):
    if type(value) not in (int, str) or str(value).strip().startswith("-"):
        raise Blocked("BLOCKED_" + key)
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise Blocked("BLOCKED_" + key) from None
    if n < 1:
        raise Blocked("BLOCKED_" + key)
    return n

def positive_decimal(value, *, allow_zero=False):
    if not isinstance(value, str):
        raise Blocked("BLOCKED_PRICE_SIZE_TYPE")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError):
        raise Blocked("BLOCKED_INVALID_PRICE_SIZE") from None
    if not d.is_finite() or d < 0 or (d == 0 and not allow_zero):
        raise Blocked("BLOCKED_INVALID_PRICE_SIZE")
    return d

def pair_map(pairs, *, allow_zero=False):
    if not isinstance(pairs, list):
        raise Blocked("BLOCKED_LEVEL_STRUCTURE")
    out = {}
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise Blocked("BLOCKED_LEVEL_STRUCTURE")
        px, sz = positive_decimal(pair[0]), positive_decimal(pair[1],allow_zero=allow_zero)
        if px in out:
            raise Blocked("BLOCKED_DUPLICATE_LEVEL")
        out[px] = sz
    return out

def allowed_topic(topic):
    if not isinstance(topic, str):
        raise Blocked("BLOCKED_TOPIC")
    items=topic.split(".")
    if len(items) == 3 and items[:2] == ["orderbook", "50"] and items[2] in SYMBOLS:
        return "orderbook", items[2]
    if len(items) == 2 and items[0] == "publicTrade" and items[1] in SYMBOLS:
        return "trade", items[1]
    raise Blocked("BLOCKED_TOPIC")

class MarketValidator:
    """Per-symbol orderbook epochs and coarse public-trade provenance."""
    def __init__(self):
        self.books={}
        self.snapshots=defaultdict(int)
        self.deltas=defaultdict(int)
        self.trades=defaultdict(int)
        self.crossed=0
        self.prev_recv_ns=0
        self.prev_mono_ns=0
        self.last_trade_ts={}
        self.last_seq={}
        self.first_recv_ns=None
        self.last_recv_ns=None
        self.message_count=0

    def observe(self, frame, received_ns, monotonic_ns):
        if not isinstance(frame,dict):
            raise Blocked("BLOCKED_FRAME_TYPE")
        kind,sym=allowed_topic(frame.get("topic"))
        if received_ns < self.prev_recv_ns or monotonic_ns <= self.prev_mono_ns:
            raise Blocked("BLOCKED_RECEIPT_ORDER")
        self.prev_recv_ns=received_ns
        self.prev_mono_ns=monotonic_ns
        if self.first_recv_ns is None:self.first_recv_ns=received_ns
        self.last_recv_ns=received_ns
        self.message_count += 1
        provider_ts=integer(frame.get("ts"), "PROVIDER_TS")
        # Public Bybit data is not retroactively first-seen simply because we
        # replayed it now: live session receipt must occur near event time.
        if abs(received_ns // 1_000_000 - provider_ts) > 300_000:
            raise Blocked("BLOCKED_PROVIDER_RECEIPT_CLOCK_DRIFT")
        if kind=="orderbook":
            data=frame.get("data")
            if not isinstance(data,dict) or data.get("s")!=sym:
                raise Blocked("BLOCKED_BOOK_SOURCE")
            u=integer(data.get("u"), "ORDERBOOK_UPDATE_ID")
            seq=integer(data.get("seq"), "ORDERBOOK_SEQUENCE")
            cts=integer(frame.get("cts"), "MATCHING_ENGINE_TIMESTAMP")
            if cts > provider_ts + 5000 or abs(received_ns//1_000_000-cts)>300_000:
                raise Blocked("BLOCKED_MATCHING_ENGINE_CLOCK")
            bids=pair_map(data.get("b"),allow_zero=True)
            asks=pair_map(data.get("a"),allow_zero=True)
            typ=frame.get("type")
            if typ == "snapshot":
                bids={k:v for k,v in bids.items() if v>0}
                asks={k:v for k,v in asks.items() if v>0}
                if not bids or not asks:raise Blocked("BLOCKED_EMPTY_SNAPSHOT")
                self.books[sym]={"b":bids,"a":asks,"u":u,"seq":seq}
                self.snapshots[sym]+=1
                self.last_seq[sym]=seq
            elif typ=="delta":
                b=self.books.get(sym)
                if b is None or u==1:
                    raise Blocked("BLOCKED_DELTA_WITHOUT_VALID_SNAPSHOT")
                # L50 is a filtered book, so 'u' is not forced to advance by 1.
                if u<=b["u"] or seq<=b["seq"]:
                    raise Blocked("BLOCKED_BOOK_SEQUENCE_REPLAY")
                for side,items in (("b",bids),("a",asks)):
                    for px,qty in items.items():
                        if qty == 0:
                            b[side].pop(px,None)
                        else:
                            b[side][px]=qty
                b["u"]=u
                b["seq"]=seq
                self.deltas[sym]+=1
            else:
                raise Blocked("BLOCKED_BOOK_MESSAGE_TYPE")
            b=self.books[sym]
            if b["a"] and b["b"] and max(b["b"])>=min(b["a"]):
                self.crossed+=1
                raise Blocked("BLOCKED_CROSSED_BOOK")
        elif kind=="trade":
            data=frame.get("data")
            if frame.get("type")!="snapshot" or not isinstance(data,list) or not data:
                raise Blocked("BLOCKED_TRADE_STRUCTURE")
            for event in data:
                if not isinstance(event,dict) or event.get("s")!=sym or event.get("S") not in ("Buy","Sell"):
                    raise Blocked("BLOCKED_TRADE_SOURCE")
                positive_decimal(event.get("v"))
                positive_decimal(event.get("p"))
                event_ts=integer(event.get("T"), "TRADE_MATCH_TIME")
                if event_ts>provider_ts+5000 or abs(event_ts-provider_ts)>300_000:
                    raise Blocked("BLOCKED_TRADE_TIMESTAMP")
                if event_ts<self.last_trade_ts.get(sym,0):
                    raise Blocked("BLOCKED_TRADE_CLOCK_REGRESSION")
                if not isinstance(event.get("i"),str) or not event["i"]:
                    raise Blocked("BLOCKED_TRADE_ID")
                integer(event.get("seq"), "TRADE_SEQ")
                self.last_trade_ts[sym]=event_ts
                self.trades[sym]+=1

    def summary(self):
        all_six=all(self.snapshots[s]>=1 and self.deltas[s]>=1 and self.trades[s]>=1 for s in SYMBOLS)
        return {
            "schema":SCHEMA,
            "source":SOURCE,
            "counts":{"snapshots":dict(self.snapshots),"deltas":dict(self.deltas),"trades":dict(self.trades)},
            "message_count":self.message_count,
            "first_receipt_ns":self.first_recv_ns,"last_receipt_ns":self.last_recv_ns,
            "complete_topics_6_of_6":all_six,
            "status":"PASS_RECORDED_PUBLIC_FEED_COVERAGE_ONLY" if all_six else "BLOCKED_INCOMPLETE_L2_AND_TRADES",
            "maker_fill_verified":False,"actual_order_receipts_verified":False,
            "queue_position_verified":False,"oos_verified":False,"independent_economic_check2":False,
            "real":"OFF","holdout":"SEALED",
            "note":"A public L50 book and opposite taker trades cannot prove fills for an unsubmitted PostOnly order; RPI/hidden liquidity and private queue position unavailable.",
        }

class AppendChain:
    def __init__(self,path):
        self.path=Path(path)
        self.file=self.path.open("xb")
        self.prev=ZERO
        self.total=0
        self.count=0
        self.closed=False
    def add(self,frame,recv_ns,mono_ns):
        base={"received_unix_ns":recv_ns,"received_monotonic_ns":mono_ns,"frame":frame}
        new=sha((self.prev+":").encode()+canonical(base))
        row={**base,"prev_sha256":self.prev,"chain_sha256":new}
        encoded=canonical(row)+b"\n"
        self.total+=len(encoded)
        if self.total>MAX_TOTAL_BYTES:
            raise Blocked("BLOCKED_RECORDING_LIMIT")
        self.file.write(encoded)
        self.prev=new
        self.count+=1
    def close(self):
        if not self.closed:
            self.file.close()
            self.closed=True

def verify_file(path):
    path=Path(path)
    if path.stat().st_size>MAX_TOTAL_BYTES:
        raise Blocked("BLOCKED_RECORDING_LIMIT")
    validator=MarketValidator()
    prev=ZERO
    count=0
    with path.open("rb") as f:
        for raw in f:
            if len(raw)>MAX_FRAME_BYTES:
                raise Blocked("BLOCKED_FRAME_TOO_LARGE")
            try:row=json.loads(raw)
            except (ValueError,UnicodeDecodeError):raise Blocked("BLOCKED_JSONL") from None
            if set(row)!={"received_unix_ns","received_monotonic_ns","frame","prev_sha256","chain_sha256"}:
                raise Blocked("BLOCKED_RECEIPT_SCHEMA")
            base={k:row[k] for k in ("received_unix_ns","received_monotonic_ns","frame")}
            digest=sha((prev+":").encode()+canonical(base))
            if row["prev_sha256"]!=prev or row["chain_sha256"]!=digest:
                raise Blocked("BLOCKED_HASH_CHAIN")
            recv=integer(base["received_unix_ns"],"RECEIPT_TS")
            mono=integer(base["received_monotonic_ns"],"MONOTONIC_TS")
            validator.observe(base["frame"],recv,mono)
            prev=digest
            count+=1
    result=validator.summary()
    result["events_file_sha256"]=sha(path.read_bytes())
    result["final_chain_sha256"]=prev
    result["events_file_bytes"]=path.stat().st_size
    result["record_count"]=count
    result["diagnostic_only_not_execution"] = True
    return result

async def capture(folder,duration):
    if not 1<=duration<=MAX_DURATION_SECONDS:
        raise Blocked("BLOCKED_DURATION")
    root=Path(folder)
    if root.exists():raise Blocked("BLOCKED_OUTPUT_EXISTS")
    root.mkdir(parents=True,exist_ok=False)
    record=root/"events.jsonl"
    writer=AppendChain(record)
    validator=MarketValidator()
    result=None
    try:
        try:import websockets
        except ImportError:raise Blocked("BLOCKED_WEBSOCKETS_DEPENDENCY") from None
        topics=[f"orderbook.50.{s}" for s in SYMBOLS]+[f"publicTrade.{s}" for s in SYMBOLS]
        # This is PUBLIC market data, not private order activity.
        async with websockets.connect(SOURCE,open_timeout=15,close_timeout=4,max_size=MAX_FRAME_BYTES,
                                      ping_interval=15,ping_timeout=15) as connection:
            await connection.send(json.dumps({"op":"subscribe","args":topics},separators=(",",":")))
            end=time.monotonic()+duration
            while time.monotonic()<end:
                try:
                    frame_raw=await asyncio.wait_for(connection.recv(),timeout=min(10,max(.01,end-time.monotonic())))
                except asyncio.TimeoutError:
                    continue
                recv_ns=time.time_ns();mono_ns=time.monotonic_ns()
                if isinstance(frame_raw,bytes) or len(frame_raw.encode())>MAX_FRAME_BYTES:
                    raise Blocked("BLOCKED_PUBLIC_FRAME_LIMIT")
                obj=json.loads(frame_raw)
                if isinstance(obj,dict) and obj.get("op")=="subscribe":
                    if obj.get("success") is not True:raise Blocked("BLOCKED_SUBSCRIPTION_REJECTED")
                    continue
                if not isinstance(obj,dict) or "topic" not in obj:continue
                validator.observe(obj,recv_ns,mono_ns)
                writer.add(obj,recv_ns,mono_ns)
    except Exception as exc:
        result={"schema":SCHEMA,"status":"BLOCKED_CAPTURE","reason":str(exc)[:300],"real":"OFF","holdout":"SEALED",
                "maker_fill_verified":False,"oos_verified":False,"completed":False}
    finally:
        writer.close()
    if result is None:
        try:result=verify_file(record)
        except Exception as exc:result={"schema":SCHEMA,"status":"BLOCKED_VERIFY","reason":str(exc)[:300],"real":"OFF","holdout":"SEALED"}
    result["captured_duration_requested_seconds"]=duration
    result["proof_claim"]="PUBLIC_RECEIPT_DATA_ONLY_NOT_MAKER_FILL"
    manifest={**result}
    manifest["manifest_sha256"]=sha(canonical(manifest))
    (root/"manifest.json").write_bytes(canonical(manifest)+b"\n")
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    c=sub.add_parser("capture")
    c.add_argument("--output",required=True)
    c.add_argument("--seconds",type=int,default=60)
    v=sub.add_parser("verify")
    v.add_argument("--events",required=True)
    v.add_argument("--output",default=None)
    a=p.parse_args(argv)
    if a.mode=="capture":result=asyncio.run(capture(a.output,a.seconds))
    else:
        result=verify_file(a.events)
        if a.output:
            dest=Path(a.output)
            if dest.exists():raise Blocked("BLOCKED_OVERWRITE_AUDIT")
            dest.write_bytes(canonical(result)+b"\n")
    print(result["status"],"events",result.get("record_count",0),"maker_fill_verified",False)
    return 0 if result["status"]=="PASS_RECORDED_PUBLIC_FEED_COVERAGE_ONLY" else 3

if __name__=="__main__":
    sys.exit(main())
