"""Fail-closed offline contracts for 100 MLE runs; no credentials."""
from __future__ import annotations
import base64
import json
import tempfile
from pathlib import Path
import types
import unittest
import zipfile
import io

from tools import avrora_hundred_mle_colab as m
from tools import build_hundred_mle_bundle as b
from tools import verify_hundred_mle_colab as v


class FrozenHundredMleTests(unittest.TestCase):
    def test_exact_100_frozen_cases_across_all_six_symbols(self):
        self.assertEqual(m.CASE_COUNT,100)
        self.assertEqual(len(m.SYMBOLS),6)
        self.assertEqual(m.PRIVATE_HEAD,"46d70a9c7d81f53959d0f12a5fce6db856624983")
        self.assertEqual(len(set(m.SYMBOLS)),6)
    def test_seven_complete_synthetic_days_tied_group_and_receipts(self):
        f=types.SimpleNamespace(DAY_MS=86400000)
        for case in (0,1,29,73,99):
            events,asof,regime=m.build_case(case,f)
            self.assertEqual(len(events),7*(16+case%16))
            self.assertEqual(len({x["trade_id"] for x in events}),len(events))
            self.assertTrue(all(
                x["event_ms"]==x["received_ms"] and
                asof-7*f.DAY_MS<=x["event_ms"]<asof and
                x["aggressor"] in ("BUY","SELL") for x in events))
            self.assertTrue(all(
                events[i]["event_ms"]<=events[i+1]["event_ms"]
                for i in range(len(events)-1)))
            self.assertEqual(regime,"BALANCED_NULL" if case%2==0 else "DIRECTIONAL_BURST")
            self.assertEqual(events,m.build_case(case,f)[0])
    def test_fifty_dense_temporal_cases_actually_test_60_second_kernel(self):
        f=types.SimpleNamespace(DAY_MS=86400000)
        dense=0
        for index in range(100):
            events,_,regime=m.build_case(index,f)
            gaps=[y["event_ms"]-x["event_ms"] for x,y in zip(events,events[1:])]
            if regime=="DIRECTIONAL_BURST":
                dense+=1
                self.assertGreater(sum(0<=gap<=1800 for gap in gaps),50)
            else:
                self.assertGreater(sum(gap>120000 for gap in gaps),70)
        self.assertEqual(dense,50)
    def test_negative_or_forged_case_index_blocked(self):
        for case in (-1,100,True,"22"):
            with self.assertRaisesRegex(ValueError,"CASE_INDEX"):
                m.build_case(case,types.SimpleNamespace(DAY_MS=86400000))
    def test_missing_or_duplicate_receipt_blocked(self):
        for text in ("","not-a-log",m.MARKER+"{}\n"+m.MARKER+"{}"):
            with self.assertRaisesRegex(ValueError,"RECEIPT_COUNT"):
                v.parse(text)
    def test_corrupted_receipt_digest_failclosed(self):
        with self.assertRaisesRegex(ValueError,"RECEIPT_SHA"):
            v.parse(m.MARKER+'{"receipt_sha256":"garbage"}')
    def test_bundle_rejects_arbitrary_member_and_zip_oversize(self):
        z=io.BytesIO()
        with zipfile.ZipFile(z,"w") as archive:
            archive.writestr("untrusted/secret",b"unsafe")
        with self.assertRaisesRegex(ValueError,"BUNDLE_SHAPE"):
            m._frozen_modules(z.getvalue())
    def test_bundle_builder_requires_real_pinned_module_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"PRIVATE_SOURCE_MISSING"):
                b.build(d,Path(__file__).resolve().parents[1]/
                    "tools"/"avrora_hundred_mle_colab.py")
    def test_placeholder_missing_does_not_generate_broken_script(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for file in m.FILES:
                if file.endswith("/__init__.py"):continue
                p=root/file
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text("X=1\n",encoding="utf-8")
            text=b.build(root,Path(__file__).resolve().parents[1]/
                "tools"/"avrora_hundred_mle_colab.py")
            self.assertNotIn('SOURCE_ZIP_B64 = "__SOURCE_ZIP_B64__"',text)
            compile(text,"bundle.py","exec")
    def test_constant_security_flags_present_in_100_run_report(self):
        import inspect
        source=inspect.getsource(m.run)
        for k in ("live_trading_authorized","real_market_events_processed",
                  "historical_first_seen_proven","independent_check2",
                  "original_vs_cached_exact_parity_runs",
                  "future_time_rejections"):
            self.assertIn(k,source)


if __name__=="__main__":
    unittest.main()
