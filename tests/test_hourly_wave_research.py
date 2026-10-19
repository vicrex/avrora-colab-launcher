"""Offline adversarial gates for hourly private five-wave research."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
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
        bars[20]=(20*900000,87.0,100.0,85.0,91.0)
        gap=m.simulate_one(bars,s,p)
        self.assertEqual(gap["reason"],"GAP_STOP")
        self.assertEqual(gap["exit"],87.0)
        # Separate arithmetic gate validates every expected bps deduction.
        m.check_trades([{**t,"symbol":"BTCUSDT"}])
        altered={**t,"symbol":"BTCUSDT","net20":t["net20"]+1.0}
        with self.assertRaisesRegex(ValueError,"FEE20_PARITY"):
            m.check_trades([altered])

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
            independent_signal_parity=False,decision="REJECT_DISCOVERY",
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
        with unittest.mock.patch.dict("os.environ",{"REAL":"ON"},clear=False):
            with self.assertRaisesRegex(ValueError,"UNSAFE_ENVIRONMENT"):
                m.gate()


if __name__=="__main__":
    unittest.main()
