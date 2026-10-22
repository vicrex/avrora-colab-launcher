"""Public market-data transport only, NO strategy, model, trading or signals.

Read-only snapshots of Bybit public M15 kline; archive HTTP bytes + receipt time.
Stored orderbook/maker-fill evidence is NOT implied. This code never calls
private endpoints and does not authenticate to any exchange account.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import pathlib
import time
import urllib.parse
import urllib.request
from decimal import Decimal

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT","NEARUSDT","LINKUSDT","XRPUSDT")
API="https://api.bybit.com/v5/market/kline"
BAR_MS=900000
START_UTC_MS=1792713600000
MAX_BYTES=1800000

def jbytes(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def parse(raw,symbol,recv_ms):
    if len(raw)>MAX_BYTES:
        raise ValueError("BLOCKED_HTTP_TOO_LARGE")
    j=json.loads(raw)
    result=j.get("result") or {}
    if (j.get("retCode")!=0 or result.get("category")!="linear"
            or result.get("symbol")!=symbol):
        raise ValueError("BLOCKED_WRONG_PUBLIC_MARKET_SOURCE")
    if abs(int(j.get("time",0))-recv_ms)>300000:
        raise ValueError("BLOCKED_SOURCE_TIMESTAMP_DRIFT")
    rows=result.get("list")
    if not isinstance(rows,list) or not 220<=len(rows)<=1000:
        raise ValueError("BLOCKED_INCOMPLETE_MARKET_WINDOW")
    accepted=[]
    for row in rows:
        if not isinstance(row,list) or len(row)<7:
            raise ValueError("BLOCKED_BAD_KLINE_ROW")
        ts=int(row[0])
        op,hi,lo,cl=(Decimal(v) for v in row[1:5])
        if (ts%BAR_MS or min(op,hi,lo,cl)<=0
            or not all(x.is_finite() for x in (op,hi,lo,cl))
            or hi<max(op,cl) or lo>min(op,cl)):
            raise ValueError("BLOCKED_INVALID_KLINE_OHLC")
        # An unfinished kline is returned by Bybit. Never admit that bar.
        if ts+BAR_MS+60000<=min(int(j["time"]),recv_ms):
            accepted.append((ts,row))
    accepted.sort(key=lambda x:x[0])
    if len(accepted)<219 or any(y[0]-x[0]!=BAR_MS for x,y in zip(accepted,accepted[1:])):
        raise ValueError("BLOCKED_CLOSED_BARS_GAP")
    buffer=io.StringIO(newline="")
    w=csv.writer(buffer,lineterminator="\n")
    w.writerow(("start_ms","open","high","low","close","observed_at_ms"))
    for ts,row in accepted:
        w.writerow((ts,*row[1:5],recv_ms))
    normalized=buffer.getvalue().encode()
    manifest={"symbol":symbol,"interval":"15","category":"linear",
        "first_start_ms":accepted[0][0],"last_start_ms":accepted[-1][0],
        "bar_count":len(accepted),
        "first_prospective_close_utc_ms":START_UTC_MS,
        "forward_closed_bars":sum(ts+BAR_MS>=START_UTC_MS for ts,row in accepted),
        "request_received_at_ms":recv_ms,"server_time_ms":int(j["time"]),
        "source_body_sha256":digest(raw),"normalized_csv_sha256":digest(normalized)}
    return normalized,manifest

def capture(out):
    folder=pathlib.Path(out)
    if folder.exists():
        raise ValueError("BLOCKED_OVERWRITE_MARKET_SNAPSHOT")
    folder.mkdir(parents=True)
    m={"schema":"AVRORA_PUBLIC_M15_TRANSPORT_V1","status":"READ_ONLY_SOURCE_DATA_NO_MAKER_FILL",
       "source_url":API,"real":"OFF","holdout":"SEALED",
       "research_results":False,"records":[]}
    for sym in SYMBOLS:
        params=urllib.parse.urlencode({"category":"linear","symbol":sym,"interval":"15","limit":1000})
        req=urllib.request.Request(API+"?"+params,headers={"User-Agent":"AVRORA-readonly-market-transport/1.0"})
        with urllib.request.urlopen(req,timeout=20) as resp:
            if resp.status!=200:
                raise ValueError("BLOCKED_HTTP_SOURCE")
            raw=resp.read(MAX_BYTES+1)
        received=int(time.time()*1000)
        normalized,record=parse(raw,sym,received)
        (folder/(sym+".response.json")).write_bytes(raw)
        (folder/(sym+".csv")).write_bytes(normalized)
        m["records"].append(record)
    m["manifest_sha256"]=digest(jbytes(m))
    (folder/"manifest.json").write_bytes(jbytes(m)+b"\n")
    return m

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    x=p.parse_args()
    m=capture(x.output)
    print("PASS_PUBLIC_READONLY_MARKET_TRANSPORT",m["manifest_sha256"])
