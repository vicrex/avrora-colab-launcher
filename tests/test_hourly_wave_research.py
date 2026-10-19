"""Offline adversarial gates for hourly private five-wave research."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock
from tools import hourly_wave_research as m


class HourlyWaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=m.load_manifest()

    def test_preregistered_catalog_and_cadence(self):
        self.assertEqual(len(self.manifest["candidates"]),12)
        self.assertEqual(m.select(self.manifest,0),"FIVE_WAVE_01")
        self.assertEqual(m.select(self.manifest,11),"FIVE_WAVE_12")
        self.assertEqual(m.select(self.manifest,12),"FIVE_WAVE_01")
        self.assertEqual(m.select(self.manifest,23),"FIVE_WAVE_12")

    def test_rejects_unregistered_and_unsafe_edits(self):
        changed=copy.deepcopy(self.manifest)
        changed["candidates"][0]["python"]="import os"
        with self.assertRaisesRegex(ValueError,"FIELDS"):
            m.validate_manifest(changed)
        changed=copy.deepcopy(self.manifest)
        changed["source_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"DATA_SCOPE"):
            m.validate_manifest(changed)
        changed=copy.deepcopy(self.manifest)
        changed["real"]="ON"
        with self.assertRaisesRegex(ValueError,"SAFETY"):
            m.validate_manifest(changed)
        changed=copy.deepcopy(self.manifest)
        changed["candidates"][0]["id"]=changed["candidates"][1]["id"]
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            m.validate_manifest(changed)

    def test_refuse_unauthenticated_or_tampered_data(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_SHA256"):
            m.read_data(b"symbol,price\nBTCUSDT,1\n")

    def test_stop_first_worse_gap_and_fee_parity(self):
        bars=[(i*900000,100.0,101.0,99.0,100.0) for i in range(40)]
        s=dict(entry_i=20,side=1,p4=90.0,signal_t=19*900000,pivot5_confirm_i=18)
        p=dict(reward_r=1.5,max_bars=16)
        bars[20]=(20*900000,100.0,116.0,88.0,113.0)
        t=m.simulate_one(bars,s,p)
        self.assertEqual(t["reason"],"STOP_FIRST")
        self.assertEqual(t["exit"],90.0)
        self.assertLess(t["net25"],t["net20"])
        # The entry must be on the correct side of the stop; a later bar
        # gaps beyond the stop and receives the worse opening price.
        bars[20]=(20*900000,100.0,101.0,99.0,100.0)
        bars[21]=(21*900000,87.0,89.0,85.0,88.0)
        gap=m.simulate_one(bars,s,p)
        self.assertEqual(gap["reason"],"GAP_STOP")
        self.assertEqual(gap["exit"],87.0)
        # Separate arithmetic gate validates every expected bps deduction.
        m.check_trades([{**t,"symbol":"BTCUSDT"}])
        altered={**t,"symbol":"BTCUSDT","net20":t["net20"]+1.0}
        with self.assertRaisesRegex(ValueError,"FEE20_PARITY"):
            m.check_trades([altered])

    def test_fifth_wave_pivot_is_confirmed_without_future_lookahead(self):
        # Synthetic rising 1-2-3-4-5 pivots followed by a close above wave 5.
        # No real/private market data are used in this regression test.
        knots=[(0,120),(10,100),(20,110),(30,105),(40,125),
               (50,115),(60,135),(61,132),(62,131),(63,138),
               (65,142),(80,142),(90,140)]
        values=[]
        for i in range(95):
            value=140.0
            for left,right in zip(knots,knots[1:]):
                t0,v0=left
                t1,v1=right
                if t0<=i<=t1:
                    value=v0+(v1-v0)*(i-t0)/(t1-t0)
                    break
            values.append(value)
        bars=[(i*900000,v,v+0.2,v-0.2,v) for i,v in enumerate(values)]
        candidate={"wing":2,"buffer_atr":0.15,"wave3_min_ratio":0.8}
        original=m.signals(bars,candidate)
        self.assertTrue(original,"Synthetic five-wave pattern must be detected")
        first=original[0]
        self.assertEqual(first["signal_i"],63)
        self.assertEqual(first["entry_i"],64)
        self.assertEqual(first["pivot5_confirm_i"],62)
        self.assertLess(first["pivot5_confirm_i"],first["signal_i"])
        # Future shock must not change an already confirmed signal.
        changed=list(bars)
        for i in range(68,len(changed)):
            v=5.0 if i%2 else 500.0
            changed[i]=(i*900000,v,v+0.2,v-0.2,v)
        future=m.signals(changed,candidate)
        self.assertEqual([x for x in original if x["signal_i"]<=63],
                         [x for x in future if x["signal_i"]<=63])

    def test_receipt_binding_and_replay_rejection(self):
        m0=self.manifest
        candidate=m0["candidates"][0]
        obj=dict(
            schema="AVRORA_FIVE_WAVE_DISCOVERY_RESULT_V1",
            status="PASS_NO_TRADES",
            promotion="RESEARCH_ONLY_NEVER_LIVE",
            candidate=candidate["id"],
            candidate_sha256=m.sha(m.canonical(candidate).encode()),
            manifest_sha256=m.sha(m.canonical(m0).encode()),
            source_sha256=m.SOURCE_SHA,source_rows=8064,
            real="OFF",holdout="SEALED",oos=False,
            independent_signal_parity=True,check2="PASS_FULL_SIGNAL_AND_LEDGER_PARITY",
            decision="REJECT_DISCOVERY",
            closed_trades=0, proposals=0,
        )
        obj["receipt_sha256"]=m.sha(m.canonical(obj).encode())
        text=m.MARKER+m.canonical(obj)
        self.assertEqual(m.verify_receipt(text,m0,candidate["id"])["closed_trades"],0)
        with self.assertRaisesRegex(ValueError,"DUPLICATE_RECEIPT"):
            m.verify_receipt(text+"\n"+text,m0,candidate["id"])
        tampered=copy.deepcopy(obj)
        tampered["decision"]="RESEARCH_REVIEW_REQUIRED"
        with self.assertRaisesRegex(ValueError,"INTEGRITY"):
            m.verify_receipt(m.MARKER+m.canonical(tampered),m0,candidate["id"])

    def test_remote_payload_compiles_without_network_or_trading(self):
        remote=m.build_remote_script(b"synthetic-only",self.manifest,"FIVE_WAVE_01")
        compile(remote,"remote_study.py","exec")
        self.assertNotIn("api.github.com",remote)
        self.assertNotIn("drive.google.com",remote)
        self.assertNotIn("bybit.com",remote)
        self.assertNotIn("refresh_token",remote)
        self.assertNotIn("import requests",remote)
        self.assertNotIn("private_key",remote)

    def test_fails_closed_without_credentials(self):
        self.assertFalse("REAL" in self.manifest["candidates"][0])
        with mock.patch.dict("os.environ",{"REAL":"ON"},clear=False):
            with self.assertRaisesRegex(ValueError,"UNSAFE_ENVIRONMENT"):
                m.gate()


if __name__=="__main__":
    unittest.main()
