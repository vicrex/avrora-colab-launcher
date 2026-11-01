"""Independent read-only replay of short publicTrade/L50 first-observed capture.

This module does not call Probe.ingest, collect(), live market endpoints, or
strategy code. It reconstructs counters from the stored raw JSONL frames and
checks two SHA-256 chains-of-custody (compressed source + raw JSONL receipt).
It does NOT prove upstream continuity, private order ACKs, maker queue/fills,
six prospective weeks, market profitability or full strategy CHECK2.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","LINKUSDT","NEARUSDT")
TOPICS={*(f"publicTrade.{s}" for s in SYMBOLS),
        *(f"orderbook.50.{s}" for s in SYMBOLS)}
MAX_COMPRESSED=160_000_000
MAX_UNCOMPRESSED=160_000_000
MAX_FRAMES=100_000
MAX_LINE=2_100_000
SCHEMA="AVRORA_PUBLIC_FIRST_OBSERVED_RAW_CHECK2_V1"


def canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(raw_path,receipt_path):
    source=Path(raw_path)
    if not source.is_file() or not 0<source.stat().st_size<=MAX_COMPRESSED:
        raise ValueError("BLOCKED_CHECK2_SOURCE_SIZE")
    receipt=json.loads(Path(receipt_path).read_bytes())
    h=receipt.get("receipt_sha256")
    if not isinstance(h,str) or sha(canon({k:v for k,v in receipt.items()
                                            if k!="receipt_sha256"}))!=h:
        raise ValueError("BLOCKED_CHECK2_RECEIPT_SHA")
    if (receipt.get("schema")!="AVRORA_PUBLIC_FIRST_OBSERVED_TRADE_L2_SHORT_PROBE_V1"
            or receipt.get("status")!="PROSPECTIVE_FIRST_OBSERVED_SHORT_PROBE"
            or receipt.get("symbols")!=list(SYMBOLS)
            or receipt.get("real")!="OFF" or receipt.get("holdout")!="SEALED"
            or receipt.get("independent_check2") is not False
            or any(receipt.get(k) is not False for k in (
                "oos_proven","any_fills_proven","maker_queue_priority_proven",
                "live_trading_authorized","strategy_net_profit_proven",
                "no_market_feed_gaps_proven","continuous_seven_day_coverage_proven"))):
        raise ValueError("BLOCKED_CHECK2_RESEARCH_SCOPE")
    digest=hashlib.sha256()
    with source.open("rb") as compressed:
        while buf:=compressed.read(1024*1024):
            digest.update(buf)
    if digest.hexdigest()!=receipt.get("compressed_source_sha256"):
        raise ValueError("BLOCKED_CHECK2_COMPRESSED_SHA")
    if source.stat().st_size!=receipt.get("compressed_bytes"):
        raise ValueError("BLOCKED_CHECK2_COMPRESSED_SIZE")
    line_sha=hashlib.sha256()
    trades=Counter();books=Counter();snaps=Counter()
    seen=set();ids={};seqs={}
    duplicates=skew=gaps=skips=frames=bytes_total=0
    first=last=None;previous_mono=None;previous_wall=None
    try:
        with gzip.open(source,"rb") as stream:
            for line in stream:
                frames+=1;bytes_total+=len(line)
                if (frames>MAX_FRAMES or bytes_total>MAX_UNCOMPRESSED
                        or len(line)>MAX_LINE or not line.endswith(b"\n")):
                    raise ValueError("BLOCKED_CHECK2_RAW_FRAME_CAP")
                obj=json.loads(line)
                if not isinstance(obj,dict) or set(obj)!={
                        "recv_utc_ms","recv_monotonic_ns","source_frame_json"}:
                    raise ValueError("BLOCKED_CHECK2_RAW_FRAME_SCHEMA")
                if canon(obj)+b"\n"!=line:
                    raise ValueError("BLOCKED_CHECK2_RAW_CANONICAL")
                wall=obj["recv_utc_ms"];mono=obj["recv_monotonic_ns"]
                if (type(wall) is not int or type(mono) is not int
                        or wall<=0 or mono<=0
                        or previous_mono is not None and mono<previous_mono
                        or previous_wall is not None and wall<previous_wall):
                    raise ValueError("BLOCKED_CHECK2_RECEIVE_CLOCK")
                previous_mono=mono;previous_wall=wall
                if first is None:first=wall
                last=wall
                if not isinstance(obj["source_frame_json"],str):
                    raise ValueError("BLOCKED_CHECK2_FRAME_STRING")
                frame=json.loads(obj["source_frame_json"])
                topic=frame.get("topic")
                if topic not in TOPICS:
                    raise ValueError("BLOCKED_CHECK2_UNEXPECTED_TOPIC")
                sym=topic.rsplit(".",1)[-1]
                data=frame.get("data")
                if topic.startswith("publicTrade."):
                    if not isinstance(data,list) or len(data)>1024:
                        raise ValueError("BLOCKED_CHECK2_TRADE_BATCH")
                    for trade in data:
                        if (not isinstance(trade,dict) or trade.get("s")!=sym
                                or trade.get("S") not in ("Buy","Sell")
                                or type(trade.get("T")) is not int
                                or trade["T"]<=0
                                or not isinstance(trade.get("i"),str)
                                or not 1<=len(trade["i"])<=128
                                or not isinstance(trade.get("p"),str)
                                or not isinstance(trade.get("v"),str)
                                or type(trade.get("seq")) is not int):
                            raise ValueError("BLOCKED_CHECK2_TRADE_SCHEMA")
                        key=(sym,trade["i"])
                        if key in seen:duplicates+=1
                        else:seen.add(key);trades[sym]+=1
                        if trade["T"]>wall:skew+=1
                else:
                    if (not isinstance(data,dict) or data.get("s")!=sym
                            or frame.get("type") not in ("snapshot","delta")
                            or type(data.get("u")) is not int
                            or type(data.get("seq")) is not int
                            or type(frame.get("cts")) is not int
                            or not isinstance(data.get("a"),list)
                            or not isinstance(data.get("b"),list)):
                        raise ValueError("BLOCKED_CHECK2_L50_SCHEMA")
                    u=data["u"];seq=data["seq"];books[sym]+=1
                    if frame["type"]=="snapshot":
                        snaps[sym]+=1
                    else:
                        old=ids.get(sym);oldseq=seqs.get(sym)
                        if old is None or oldseq is None or u<=old or seq<=oldseq or u==1:
                            gaps+=1
                        elif u>old+1:
                            skips+=1
                    ids[sym]=u;seqs[sym]=seq
                line_sha.update(line)
    except (OSError,EOFError,UnicodeError) as exc:
        raise ValueError("BLOCKED_CHECK2_GZIP_OR_TEXT") from exc
    if (bytes_total!=receipt.get("uncompressed_bytes")
            or line_sha.hexdigest()!=receipt.get("raw_ingress_jsonl_sha256")
            or frames!=receipt.get("accepted_market_frames")
            or trades!=receipt.get("observed_unique_trades")
            or books!=receipt.get("observed_l2_frames")
            or snaps!=receipt.get("observed_l2_snapshots")
            or duplicates!=receipt.get("repeated_trade_ids")
            or skew!=receipt.get("clock_skew_trades")
            or gaps!=receipt.get("book_update_uncertainties")
            or skips!=receipt.get("book_update_id_jumps_not_gaps")
            or first!=receipt.get("first_receive_utc_ms")
            or last!=receipt.get("last_receive_utc_ms")):
        raise ValueError("BLOCKED_CHECK2_SOURCE_RECEIPT_PARITY")
    if (not all(trades[s]>0 and snaps[s]>0 for s in SYMBOLS)
            or receipt.get("accepted_subscribe_acks",0)<2):
        raise ValueError("BLOCKED_CHECK2_SIX_SYMBOL_COVERAGE")
    report={"schema":SCHEMA,"status":"PASS_RECORDED_PUBLIC_RAW_REPLAY_PARITY_ONLY",
            "source_compressed_sha256":digest.hexdigest(),
            "source_jsonl_sha256":line_sha.hexdigest(),
            "captured_market_frames":frames,"distinct_trades":sum(trades.values()),
            "book_update_uncertainties":gaps,
            "book_update_id_jumps_not_gaps":skips,
            "six_symbol_trade_and_l50_snapshot_verified":True,
            "subscription_acks_independently_replayed":False,
            "all_feed_packets_proven":False,
            "strategy_signal_check2":False,
            "economic_net_profit_proven":False,
            "maker_fills_proven":False,
            "six_prospective_weeks_proven":False,
            "live_trading_authorized":False,
            "real":"OFF","holdout":"SEALED"}
    report["report_sha256"]=sha(canon(report))
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--raw",required=True)
    p.add_argument("--receipt",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    out=Path(args.out)
    if out.exists():raise ValueError("BLOCKED_CHECK2_REPORT_OVERWRITE")
    report=check(args.raw,args.receipt)
    out.write_bytes(canon(report)+b"\n")
    print("PASS_FIRSTSEEN_INDEPENDENT_RAW_RECEIPT_PARITY_NOT_PROFIT",
          report["captured_market_frames"],report["report_sha256"])


if __name__=="__main__":
    main()
