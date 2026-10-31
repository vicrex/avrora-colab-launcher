"""Synthetic-only delayed Bybit archive event structure controls."""
from datetime import date,datetime,timedelta,timezone
import csv,gzip,io,tempfile,json,unittest
from pathlib import Path
from tools import bybit_trade_event_qc as q
from tools import bybit_official_archive_transport as t

DAY=date(2026,10,30)
SYMBOL="LINKUSDT"
HEADER=list(q.COLUMNS)

def materialize(root,mutate=None):
    root=Path(root)
    base=int(datetime.combine(DAY,datetime.min.time(),timezone.utc).timestamp())
    data=[]
    for hour in range(24):
        data.append([str(base+hour*3600)+".3121",SYMBOL,
            "Buy" if hour%2 else "Sell","19.6","10.607","PlusTick",
            "00000000-0000-0000-0000-"+str(hour).zfill(12),
            "20789720000","19.6","207.8972","0"])
    if mutate is not None:mutate(data)
    output=io.StringIO(newline="")
    writer=csv.writer(output,lineterminator="\n")
    writer.writerow(HEADER);writer.writerows(data)
    raw=output.getvalue().encode()
    compressed=gzip.compress(raw,mtime=0)
    name=t.archive_filename(DAY,SYMBOL)
    (root/name).write_bytes(compressed)
    received="2026-10-31T12:38:46.719619Z"
    manifest={
        "schema":"AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2",
        "kind":"DELAYED_PUBLIC_HISTORICAL_TRADES",
        "source":"public.bybit.com/trading",
        "url":t.archive_url(DAY,SYMBOL),
        "symbol":SYMBOL,"day_utc":DAY.isoformat(),"file_name":name,
        "source_gz_sha256":q.sha(compressed),
        "source_compressed_bytes":len(compressed),
        "source_uncompressed_bytes":len(raw),
        "source_text_lines":raw.count(b"\n"),
        "archive_received_at_utc":received,
        "causally_usable_not_before_utc":received,
        "signal_realtime_available":False,"fill_proven":False,
        "trade_return_proven":False,"new_oos_proven":False,
        "real":"OFF","holdout":"SEALED","note":"synthetic test only",
    }
    manifest["manifest_sha256"]=q.sha(q.canonical(manifest))
    (root/"manifest.json").write_bytes(q.canonical(manifest)+b"\n")
    return root

class BybitEventQCTests(unittest.TestCase):
    def test_24hour_archive_only_structural_not_firstseen(self):
        with tempfile.TemporaryDirectory() as d:
            result=q.audit(materialize(d),SYMBOL,DAY)
            self.assertEqual(result["status"],"PASS_HISTORICAL_EVENT_STRUCTURAL_QC")
            self.assertEqual(result["observed_trade_rows"],24)
            self.assertEqual(result["unique_trade_ids"],24)
            self.assertEqual(result["hours_with_at_least_one_event"],24)
            self.assertEqual(result["buy_aggressor_rows"],12)
            for field in ("provider_all_trades_completeness_proven",
                          "individual_historical_first_seen_receipt_proven",
                          "hawkes_real_time_calibration_authorized",
                          "independent_check2","prospective_oos_proven",
                          "maker_fill_proven","live_trading_authorized"):
                self.assertFalse(result[field])
            self.assertEqual(result["real"],"OFF")
            self.assertEqual(result["holdout"],"SEALED")
            self.assertEqual(result["receipt_sha256"],q.sha(q.canonical(
                {k:v for k,v in result.items() if k!="receipt_sha256"})))
    def test_missing_one_hour_does_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            def missing(data):data[6][0]=data[5][0].replace(".3121",".3122")
            result=q.audit(materialize(d,missing),SYMBOL,DAY)
            self.assertEqual(result["status"],"BLOCKED_TRADE_MISSING_HOURLY_OBSERVATIONS")
    def test_duplicate_trade_id_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            def dupe(data):data[8][6]=data[7][6]
            with self.assertRaisesRegex(ValueError,"ID_DUPLICATE"):
                q.audit(materialize(d,dupe),SYMBOL,DAY)
    def test_clock_reversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            def reverse(data):data[8][0]=data[6][0]
            with self.assertRaisesRegex(ValueError,"EVENT_CLOCK_REVERSAL"):
                q.audit(materialize(d,reverse),SYMBOL,DAY)
    def test_symbol_and_side_rejected(self):
        for column,value in ((1,"DOGEUSDT"),(2,"BUY")):
            with tempfile.TemporaryDirectory() as d:
                def wrong(data):data[8][column]=value
                with self.assertRaisesRegex(ValueError,"SYMBOL_OR_AGGRESSOR"):
                    q.audit(materialize(d,wrong),SYMBOL,DAY)
    def test_time_submicrosecond_and_future_rejected(self):
        for value,reason in (("1793318400.3121001","TIME_PRECISION"),
                             ("1793404800.0000","OUTSIDE_UTC_ARCHIVE_DAY")):
            with tempfile.TemporaryDirectory() as d:
                def wrong(data):data[-1][0]=value
                with self.assertRaisesRegex(ValueError,reason):
                    q.audit(materialize(d,wrong),SYMBOL,DAY)
    def test_invalid_rpi_and_price_rejected(self):
        for col,value,reason in ((10,"YES","TICK_OR_RPI"),(4,"nan","TRADE_NUMERIC")):
            with tempfile.TemporaryDirectory() as d:
                def wrong(data):data[3][col]=value
                with self.assertRaisesRegex(ValueError,reason):
                    q.audit(materialize(d,wrong),SYMBOL,DAY)
    def test_bounded_resource_cap(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"RESOURCE_CAP"):
                q.audit(materialize(d),SYMBOL,DAY,max_rows=23)
    def test_tampered_compressed_bytes_fail(self):
        with tempfile.TemporaryDirectory() as d:
            p=materialize(d)
            f=p/t.archive_filename(DAY,SYMBOL)
            f.write_bytes(f.read_bytes()+b"attack")
            with self.assertRaisesRegex(ValueError,"BYTES_SHA_MISMATCH"):
                q.audit(p,SYMBOL,DAY)
    def test_no_overwrite_exit_contract(self):
        with tempfile.TemporaryDirectory() as d:
            p=materialize(d)
            self.assertEqual(q.audit(p,SYMBOL,DAY),q.audit(p,SYMBOL,DAY))

if __name__=="__main__":unittest.main()
