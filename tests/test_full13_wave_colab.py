"""Offline tests for all-weeks-in-ONE-Colab-job pipeline. No raw private candles or credentials."""
import copy,csv,gzip,hashlib,io,json,math,os,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from tools import hourly_wave_research as engine
from tools import full13_wave_colab as f

WEEKS=['2021-11-29','2022-01-17','2022-05-09','2022-06-06','2022-08-15','2022-11-07',
       '2023-08-14','2024-04-08','2024-07-01','2024-07-29','2024-12-16','2025-01-27']

def synthetic():
    buffer=io.StringIO(newline='');o=csv.writer(buffer,lineterminator='\n')
    o.writerow(['period','symbol','timestamp_ms','open','high','low','close'])
    for w in WEEKS+[f.AUX]:
        start=int(datetime.fromisoformat(w).replace(tzinfo=timezone.utc).timestamp()*1000)
        for symbol in f.SYMBOLS:
            for i in range(-220,672):
                p=100+math.sin(i/23)*3
                o.writerow([w,symbol,start+i*900000,p,p+0.3,p-0.3,p+0.05])
    raw=buffer.getvalue().encode()
    z=gzip.compress(raw,mtime=0)
    metadata={'schema':f.DATA_SCHEMA,'source_archive_sha256':f.SOURCE_ZIP_SHA,
            'full_panel_gzip_sha256':hashlib.sha256(z).hexdigest(),
            'full_panel_csv_sha256':hashlib.sha256(raw).hexdigest(),
            'full_panel_gzip_bytes':len(z),'full_panel_csv_bytes':len(raw),
            'periods':13,'total_rows':f.TOTAL_ROWS,'warmup_bars':220,'trade_bars':672,
            'discovery_week_starts':WEEKS,'aux_may_week_start':f.AUX,'symbols':list(f.SYMBOLS),
            'source_original_P900_parquet_sha256':{s:'1'*64 for s in f.SYMBOLS},
            'real':'OFF','holdout':'SEALED','oos':False}
    return z,metadata


class Full13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.compressed,cls.meta=synthetic()

    def test_single_pass_scope_exact_13_complete_weeks(self):
        with patch.object(f,'PANEL_GZ_SHA',hashlib.sha256(self.compressed).hexdigest()):
            data=f.parse_full(self.compressed,self.meta)
        self.assertEqual(len(data),78)
        self.assertEqual(sum(map(len,data.values())),69576)
        self.assertEqual(len(data['2022-01-17','BTCUSDT']),892)

    def test_tampered_or_truncated_source_fails_closed(self):
        z=bytearray(self.compressed);z[-8]^=1
        with self.assertRaisesRegex(ValueError,'PANEL_SHA'):
            f.parse_full(bytes(z),self.meta)
        with self.assertRaisesRegex(ValueError,'PANEL_SHA'):
            f.parse_full(self.compressed,self.meta)

    def test_no_holdout_or_live_mode(self):
        with patch.dict(os.environ,{'REAL':'ON'}):
            with self.assertRaisesRegex(ValueError,'REAL_OR_HOLDOUT'):
                f.load_private('/never-existent')
        with patch.dict(os.environ,{'HOLDOUT':'OPEN'}):
            with self.assertRaisesRegex(ValueError,'REAL_OR_HOLDOUT'):
                f.load_private('/never-existent')

    def test_immutable_manifest_and_incomplete_source_fail(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/f.PRIVATE_DIR;root.mkdir(parents=True)
            meta=copy.deepcopy(self.meta);(root/'data_manifest.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'DATA_PIN'):
                f.load_private(t)
            meta['full_panel_gzip_sha256']=f.PANEL_GZ_SHA
            meta['full_panel_csv_sha256']=f.PANEL_CSV_SHA
            (root/'data_manifest.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'PANEL_PART'):
                f.load_private(t)

    def test_remote_single_job_contains_entire_payload_not_one_week(self):
        m=engine.load_manifest()
        remote=f.build_colab_script(b'only-test-not-production',self.meta,m,'FIVE_WAVE_01')
        compile(remote,'remote.py','exec')
        self.assertEqual(remote.count('full13_wave_colab.py'),2)
        for text in ('drive.google.com','api.bybit.com','api.github.com','refresh_token','private_key'):
            self.assertNotIn(text,remote)
        self.assertIn('BLOCKED_FULL13_EXECUTION',remote)

    def test_status_cannot_be_forged_with_old_receipt(self):
        with self.assertRaisesRegex(ValueError,'RECEIPT_SCHEMA'):
            f.verify_receipt({'schema':'AVRORA_FIVE_WAVE_DISCOVERY_RESULT_V1'},engine.load_manifest(),'FIVE_WAVE_01')


if __name__=='__main__':unittest.main()
