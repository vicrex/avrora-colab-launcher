"""Offline smoke tests for aggregate vector insight ledger; no Colab or private candles."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import vector_insight_lab as lab
from tools import structural_short as engine
from tools import full13_wave_colab as pin

ROOT = Path(__file__).resolve().parents[1]

def fake_scope(net20=-4.0, late=-3.0):
    early = round(net20 - late, 6)
    labels = [f"week-{i:02d}" for i in range(12)]
    byweek = {}
    for i, label in enumerate(labels):
        byweek[label] = {"trades": 4, "net20_usdt": round((early if i<6 else late)/6,6)}
    # correct last individual week to avoid 1e-6 accumulations
    byweek[labels[5]]["net20_usdt"] = round(early - sum(byweek[x]["net20_usdt"] for x in labels[:5]),6)
    byweek[labels[11]]["net20_usdt"] = round(late - sum(byweek[x]["net20_usdt"] for x in labels[6:11]),6)
    return {
        "mode": "FAKE", "trades": 48,
        "trades_per_symbol_day": round(48/(84*6),6),
        "net_by_cost_bps_usdt": {"16": net20+4, "20": net20, "25": net20-5, "40": net20-10},
        "by_week": byweek, "by_symbol": {symbol:{"trades":8,"net20_usdt":net20/6} for symbol in pin.SYMBOLS},
        "splits": {"early6":{"trades":24,"net20_usdt":early},"late6":{"trades":24,"net20_usdt":late}},
    }

def fake_receipt():
    results = {}
    for i, c in enumerate(engine.CANDIDATES):
        results[c] = {"discovery": fake_scope(-4-i, -3-i),
                      "may_aux": {"net_by_cost_bps_usdt":{"16":2,"20":-1,"25":-2,"40":-4}}}
    return {
        "receipt_sha256": "ab"*32,
        "independent_check2": "PASS_ALL_SHORT_SIGNALS_FILLS_AND_EQUITY",
        "manifest_sha256": "cd"*32,
        "results": results, "bars": 69576, "periods": 13,
        "primary_sha256":"de"*32, "checker_sha256":"ef"*32,
    }

class VectorInsightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid=json.loads((ROOT/"research/vector_squeeze_grid_prereg_v1.json").read_text())
        cls.m,cls.sha=engine.load_manifest()

    def build(self,receipt=None,grid=None):
        with patch.object(lab.engine,"verify_receipt",return_value=None),patch.object(
                lab.engine,"load_manifest",return_value=(self.m,"cd"*32)):
            return lab.build(receipt or fake_receipt(), grid or self.grid)

    def test_preregistered_grid_is_bounded_unique_and_not_executable(self):
        self.assertEqual(len(lab.validated_grid(self.grid)),12)
        x=self.build()
        self.assertEqual(x["real"],"OFF")
        self.assertEqual(x["holdout"],"SEALED")
        self.assertEqual(len(x["ideas"]),12)
        self.assertTrue(all(r["economic_result"] is None and
                            "PREREG_ONLY" in r["state"] for r in x["ideas"]))
        self.assertEqual(x["content_sha256"],lab.digest({k:v for k,v in x.items()
                                                       if k!="content_sha256"}))

    def test_features_all_candidates_and_nearest_are_deterministic(self):
        a=self.build();b=self.build()
        self.assertEqual(a,b)
        self.assertEqual(len(a["records"]),4)
        self.assertEqual(len(a["nearest_pairs"]),6)
        dims={tuple(v["vector"]) for v in a["records"]}
        self.assertEqual(len(dims),1)
        self.assertNotEqual(a["records"][2]["vector"],a["records"][3]["vector"])
        self.assertIn("NEGATIVE_AFTER_20BPS",a["records"][0]["outcome"]["flags"])

    def test_block_incomplete_or_tampered_result(self):
        x=fake_receipt()
        x["results"][engine.CANDIDATES[0]]["discovery"]["net_by_cost_bps_usdt"]["25"]=9.0
        with self.assertRaisesRegex(ValueError,"BLOCKED_COST_MONOTONIC"):
            self.build(receipt=x)
        y=fake_receipt()
        del y["results"][engine.CANDIDATES[0]]["discovery"]["by_symbol"][pin.SYMBOLS[0]]
        with self.assertRaisesRegex(ValueError,"BLOCKED_INCOMPLETE_COVERAGE"):
            self.build(receipt=y)

    def test_block_wrong_safety_or_duplicate_future_spec(self):
        bad=copy.deepcopy(self.grid);bad["holdout"]="OPEN"
        with self.assertRaisesRegex(ValueError,"BLOCKED_IDEA_SAFETY"):
            self.build(grid=bad)
        duplicate=copy.deepcopy(self.grid)
        duplicate["candidates"][1].update({k:v for k,v in duplicate["candidates"][0].items() if k!="id"})
        with self.assertRaisesRegex(ValueError,"BLOCKED_IDEA_DUPLICATE"):
            self.build(grid=duplicate)

    def test_block_missing_check2_and_wrong_receipt_scope(self):
        x=fake_receipt();x["independent_check2"]="PENDING"
        with self.assertRaisesRegex(ValueError,"BLOCKED_NO_CHECK2"):
            self.build(receipt=x)
        y=fake_receipt();y["bars"]=8064
        with self.assertRaisesRegex(ValueError,"BLOCKED_FULL13_SCOPE"):
            self.build(receipt=y)

if __name__=="__main__":
    unittest.main()
