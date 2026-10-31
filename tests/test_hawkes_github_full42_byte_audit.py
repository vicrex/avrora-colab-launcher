"""Offline adversarial tests; 42 fixture ZIPs only, never trading."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import gzip
import hashlib
import json
import tempfile
import unittest
import zipfile

from tools import hawkes_github_full42_byte_audit as a
from tools import bybit_official_archive_transport as t
from tools.hawkes_seven_day_archive_audit import canonical, required_days

ASOF=date(2026,10,31)


def archive(root,symbol,day,number):
    root=Path(root)
    payload=(b"timestamp,symbol,side,size,price\n"
             +b"123,"+symbol.encode()+b",Buy,1,123\n")
    zipped_gz=gzip.compress(payload,mtime=0)
    when=datetime.combine(day+timedelta(days=1),datetime.min.time(),
                          tzinfo=timezone.utc).replace(hour=12).isoformat().replace("+00:00","Z")
    name=t.archive_filename(day,symbol)
    m={
        "schema":"AVRORA_BYBIT_STATIC_TRADES_TRANSPORT_V2",
        "kind":"DELAYED_PUBLIC_HISTORICAL_TRADES",
        "source":"public.bybit.com/trading",
        "url":t.archive_url(day,symbol),
        "symbol":symbol,"day_utc":day.isoformat(),"file_name":name,
        "source_gz_sha256":hashlib.sha256(zipped_gz).hexdigest(),
        "source_compressed_bytes":len(zipped_gz),
        "source_uncompressed_bytes":len(payload),
        "source_text_lines":payload.count(b"\n"),
        "archive_received_at_utc":when,
        "causally_usable_not_before_utc":when,
        "signal_realtime_available":False, "fill_proven":False,
        "trade_return_proven":False, "new_oos_proven":False,
        "real":"OFF","holdout":"SEALED",
    }
    m["manifest_sha256"]=hashlib.sha256(canonical(m)).hexdigest()
    zip_path=root/(str(number)+".zip")
    with zipfile.ZipFile(zip_path,"w",compression=zipfile.ZIP_STORED) as z:
        z.writestr("manifest.json",canonical(m)+b"\n")
        z.writestr(name,zipped_gz)
    b=zip_path.read_bytes()
    item={
        "name":f"avrora-official-trades-{symbol}-{day.isoformat()}-11111111111",
        "expired":False, "id":number,"digest":"sha256:"+hashlib.sha256(b).hexdigest(),
        "size_in_bytes":len(b)
    }
    return item,zip_path


def fixtures(root):
    items=[];paths={}
    for d in required_days(ASOF):
        for s in a.SYMBOLS:
            n=len(items)+1
            item,loc=archive(root,s,d,n)
            items.append(item);paths[n]=loc
    return items,paths


class RealByteAuditOffline(unittest.TestCase):
    def test_full_42_signed_gzip_crc_lineage_but_never_realtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            items, paths=fixtures(tmp)
            def local_copy(n,dest):
                Path(dest).write_bytes(paths[n].read_bytes())
            r=a.audit([{"artifacts":items}],ASOF,downloader=local_copy)
            self.assertEqual(r["status"],"PASS_ARCHIVED_42_FILES_NOT_REALTIME")
            self.assertEqual(r["source_gzip_sha_crc_verified"],42)
            self.assertEqual(r["github_original_zip_sha_verified"],42)
            self.assertEqual(r["distinct_symbol_day_pairs"],42)
            self.assertEqual(len(r["receipts"]),42)
            self.assertEqual(r["not_available_by_asof_midnight"],6)
            for field in ("provider_trade_count_completeness_proven",
                          "individual_historical_first_seen_proven",
                          "hawkes_real_time_fit_proven","independent_check2",
                          "prospective_oos_proven","maker_fill_proven",
                          "live_trading_authorized"):
                self.assertIs(r[field],False)
            self.assertEqual((r["real"],r["holdout"]),("OFF","SEALED"))
            self.assertEqual(r["receipt_sha256"],a.sha(canonical({
                k:v for k,v in r.items() if k!="receipt_sha256"})))
    def test_missing_day_blocks_before_any_download(self):
        with tempfile.TemporaryDirectory() as d:
            items,_=fixtures(d)
            with self.assertRaisesRegex(ValueError,"42_METADATA"):
                a.select([{"artifacts":items[:-1]}],ASOF)
    def test_duplicate_metadata_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            items,_=fixtures(d)
            bad=dict(items[0],id=900,name=items[0]["name"].replace("11111111111","22222222222"))
            with self.assertRaisesRegex(ValueError,"42_METADATA"):
                a.select([{"artifacts":items+[bad]}],ASOF)
    def test_invalid_artifact_digest_blocks_before_download(self):
        with tempfile.TemporaryDirectory() as d:
            items,_=fixtures(d)
            items[1]["digest"]="sha256:bad"
            with self.assertRaisesRegex(ValueError,"UNTRUSTED_METADATA"):
                a.select([{"artifacts":items}],ASOF)
    def test_transfer_byte_modification_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            items,paths=fixtures(d)
            z=paths[1]
            with z.open("ab") as f:f.write(b"tamper")
            with self.assertRaisesRegex(ValueError,"TRANSFER_DIGEST"):
                a.verify_one(z,a.SYMBOLS[0],required_days(ASOF)[0],ASOF,items[0])
    def test_embedded_extra_path_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            items,paths=fixtures(d)
            z=paths[1]
            with zipfile.ZipFile(z,"a") as f:f.writestr("../escape","bad")
            b=z.read_bytes()
            items[0]["size_in_bytes"]=len(b)
            items[0]["digest"]="sha256:"+hashlib.sha256(b).hexdigest()
            with self.assertRaisesRegex(ValueError,"MEMBER_SHAPE"):
                a.verify_one(z,a.SYMBOLS[0],required_days(ASOF)[0],ASOF,items[0])
    def test_signed_manifest_tamper_fails_after_zip_rehash(self):
        with tempfile.TemporaryDirectory() as d:
            items,paths=fixtures(d)
            z=paths[1]
            with zipfile.ZipFile(z) as f:
                old=json.loads(f.read("manifest.json"))
                gz=f.read(t.archive_filename(required_days(ASOF)[0],a.SYMBOLS[0]))
            old["signal_realtime_available"]=True
            old["manifest_sha256"]=a.sha(canonical({k:v for k,v in old.items() if k!="manifest_sha256"}))
            with zipfile.ZipFile(z,"w") as f:
                f.writestr("manifest.json",canonical(old)+b"\n")
                f.writestr(t.archive_filename(required_days(ASOF)[0],a.SYMBOLS[0]),gz)
            b=z.read_bytes()
            items[0]["size_in_bytes"]=len(b)
            items[0]["digest"]="sha256:"+hashlib.sha256(b).hexdigest()
            with self.assertRaisesRegex(ValueError,"MANIFEST_SCOPE"):
                a.verify_one(z,a.SYMBOLS[0],required_days(ASOF)[0],ASOF,items[0])
    def test_truncated_gzip_member_detected_after_zip_rehash(self):
        with tempfile.TemporaryDirectory() as d:
            items,paths=fixtures(d)
            z=paths[1];s=a.SYMBOLS[0];day=required_days(ASOF)[0]
            with zipfile.ZipFile(z) as f:
                old=f.read("manifest.json")
                gz=f.read(t.archive_filename(day,s))
            with zipfile.ZipFile(z,"w") as f:
                f.writestr("manifest.json",old)
                f.writestr(t.archive_filename(day,s),gz[:-8])
            b=z.read_bytes()
            items[0]["size_in_bytes"]=len(b)
            items[0]["digest"]="sha256:"+hashlib.sha256(b).hexdigest()
            with self.assertRaisesRegex(ValueError,"BYTES_SHA_MISMATCH"):
                a.verify_one(z,s,day,ASOF,items[0])

if __name__=="__main__":
    unittest.main()
