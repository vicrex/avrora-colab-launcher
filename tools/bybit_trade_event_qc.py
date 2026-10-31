"""Read-only completed-day Bybit event QC. Never first-seen or maker proof.

Requires original signed V2 manifest + gzip CRC/SHA check from existing
transport.verify. Streams CSV, rejects clock inversion, duplicate trade IDs,
missing UTC hourly observations and invalid side/tick/RPI/price.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json
from . import bybit_official_archive_transport as transport

SCHEMA="AVRORA_BYBIT_HISTORICAL_EVENT_QC_V1"
COLUMNS=("timestamp","symbol","side","size","price","tickDirection",
         "trdMatchID","grossValue","homeNotional","foreignNotional","RPI")
TICK=frozenset(("PlusTick","MinusTick","ZeroPlusTick","ZeroMinusTick"))
MAX_ROWS=750000

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode()

def sha(b):
    return hashlib.sha256(b).hexdigest()

def positive(value):
    try: v=Decimal(value)
    except (TypeError,ValueError,InvalidOperation) as exc:
        raise ValueError("BLOCKED_TRADE_NUMERIC") from exc
    if not v.is_finite() or v<=0:
        raise ValueError("BLOCKED_TRADE_NUMERIC")

def microseconds(value):
    try: micros=Decimal(value)*1_000_000
    except (TypeError,ValueError,InvalidOperation) as exc:
        raise ValueError("BLOCKED_TRADE_TIME_PRECISION") from exc
    if not micros.is_finite() or micros!=micros.to_integral_value():
        raise ValueError("BLOCKED_TRADE_TIME_PRECISION")
    return int(micros)

def audit(root,symbol,day,*,max_rows=MAX_ROWS):
    if (not isinstance(root,(str,Path)) or type(day) is not date
            or type(max_rows) is not int or not 1<=max_rows<=MAX_ROWS):
        raise ValueError("BLOCKED_TRADE_SOURCE_ARGUMENTS")
    root=Path(root)
    proof=transport.verify(root,symbol)
    m=json.loads((root/"manifest.json").read_bytes())
    if m["manifest_sha256"]!=proof or m["day_utc"]!=day.isoformat():
        raise ValueError("BLOCKED_TRADE_ORIGINAL_MANIFEST")
    begin=int(datetime.combine(day,datetime.min.time(),timezone.utc).timestamp()*1e6)
    finish=int(datetime.combine(day+timedelta(days=1),
                                datetime.min.time(),timezone.utc).timestamp()*1e6)
    rows=buys=sells=rpi_count=0
    hour_counts=[0]*24
    prev=None;first=None;last=None;largest_gap=0;seen=set()
    filename=root/transport.archive_filename(day,symbol)
    with gzip.open(filename,"rt",encoding="utf8",newline="") as stream:
        reader=csv.DictReader(stream)
        if tuple(reader.fieldnames or ())!=COLUMNS:
            raise ValueError("BLOCKED_TRADE_HEADER")
        for rec in reader:
            rows+=1
            if rows>max_rows:
                raise ValueError("BLOCKED_TRADE_RESOURCE_CAP")
            if None in rec or any(v is None for v in rec.values()):
                raise ValueError("BLOCKED_TRADE_ROW_SHAPE")
            if rec["symbol"]!=symbol or rec["side"] not in ("Buy","Sell"):
                raise ValueError("BLOCKED_TRADE_SYMBOL_OR_AGGRESSOR")
            if rec["tickDirection"] not in TICK or rec["RPI"] not in ("0","1"):
                raise ValueError("BLOCKED_TRADE_TICK_OR_RPI")
            for field in ("size","price","grossValue","homeNotional","foreignNotional"):
                positive(rec[field])
            micros=microseconds(rec["timestamp"])
            if not begin<=micros<finish:
                raise ValueError("BLOCKED_TRADE_OUTSIDE_UTC_ARCHIVE_DAY")
            if prev is not None:
                if micros<prev:
                    raise ValueError("BLOCKED_TRADE_EVENT_CLOCK_REVERSAL")
                largest_gap=max(largest_gap,micros-prev)
            prev=micros
            if first is None:first=micros
            last=micros
            trade_id=rec["trdMatchID"]
            if not isinstance(trade_id,str) or not 1<=len(trade_id)<=128:
                raise ValueError("BLOCKED_TRADE_ID_INVALID")
            if trade_id in seen:
                raise ValueError("BLOCKED_TRADE_ID_DUPLICATE")
            seen.add(trade_id)
            hour_counts[(micros-begin)//3_600_000_000]+=1
            buys+=int(rec["side"]=="Buy")
            sells+=int(rec["side"]=="Sell")
            rpi_count+=int(rec["RPI"]=="1")
    if rows<24 or len(seen)!=rows or sum(hour_counts)!=rows:
        raise ValueError("BLOCKED_TRADE_INCOMPLETE_OBSERVED_ROWS")
    status=("PASS_HISTORICAL_EVENT_STRUCTURAL_QC" if all(hour_counts)
            else "BLOCKED_TRADE_MISSING_HOURLY_OBSERVATIONS")
    report={
        "schema":SCHEMA,"status":status,"symbol":symbol,"day_utc":day.isoformat(),
        "source_gz_sha256":m["source_gz_sha256"],
        "source_manifest_sha256":proof,
        "original_archive_available_not_before_utc":m["causally_usable_not_before_utc"],
        "observed_trade_rows":rows,"unique_trade_ids":len(seen),
        "buy_aggressor_rows":buys,"sell_aggressor_rows":sells,
        "rpi_rows":rpi_count,"hours_with_at_least_one_event":sum(bool(x) for x in hour_counts),
        "min_hour_rows":min(hour_counts),"max_hour_rows":max(hour_counts),
        "max_intertrade_gap_ms":largest_gap//1000,
        "first_source_event_ms":first//1000,"last_source_event_ms":last//1000,
        "historical_archive_byte_crc_verified":True,
        "historical_archive_content_structure_verified":status.startswith("PASS_"),
        "provider_all_trades_completeness_proven":False,
        "individual_historical_first_seen_receipt_proven":False,
        "hawkes_real_time_calibration_authorized":False,
        "independent_check2":False,"prospective_oos_proven":False,
        "maker_fill_proven":False,"live_trading_authorized":False,
        "real":"OFF","holdout":"SEALED",
        "scope":"DELAYED_HISTORICAL_TRADE_EVENTS_NOT_FIRST_SEEN",
    }
    report["receipt_sha256"]=sha(canonical(report))
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--symbol",required=True,choices=transport.SYMBOLS)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    destination=Path(args.out)
    if destination.exists():raise ValueError("BLOCKED_EVENT_QC_REPORT_OVERWRITE")
    report=audit(args.root,args.symbol,date.fromisoformat(args.day))
    destination.write_bytes(canonical(report)+b"\n")
    print(report["status"],args.symbol,args.day,report["observed_trade_rows"],
          report["unique_trade_ids"],report["receipt_sha256"])
    print("HISTORICAL_EVENT_QC_NOT_FIRST_SEEN_OR_CHECK2")
    return 0 if report["status"]=="PASS_HISTORICAL_EVENT_STRUCTURAL_QC" else 3

if __name__=="__main__":
    raise SystemExit(main())
