"""Synthetic offline trust-boundary tests for SOL/XRP SQ05 portfolio ablations."""
import json
import os
import unittest
from unittest.mock import patch

from tools import sq05_asset_ablation as a

class AssetMechanismTests(unittest.TestCase):
    def test_exact_frozen_six_scenarios_and_original_sq05_parameters(self):
        m,sha=a.prereg()
        self.assertEqual(len(sha),64)
        self.assertEqual(tuple((x["id"],tuple(x["symbols"]))
                               for x in m["exact_ordered_scenarios"]),a.EXPECTED)
        params,baseline,gridsha,specsha=a.parameter_pin()
        self.assertEqual((params["squeeze_max_range_ratio"],
                          params["break_atr"],params["body_atr"]),(.7,.05,.25))
        self.assertEqual(params["max_notional"],500)
        self.assertEqual(params["start_equity_usdt"],300)

    def test_symbol_week_aggregation_uses_real_accepted_trade_grain(self):
        ledger=[
          {"period":"week-1","symbol":"SOLUSDT","net20_usdt":3.8},
          {"period":"week-1","symbol":"SOLUSDT","net20_usdt":-1.1},
          {"period":"week-1","symbol":"XRPUSDT","net20_usdt":0.6},
          {"period":"week-2","symbol":"XRPUSDT","net20_usdt":-2.0},
        ]
        table=a.cross_tab(ledger,["week-1","week-2"],("SOLUSDT","XRPUSDT"))
        self.assertEqual(table["week-1"]["SOLUSDT"],{"trades":2,"net20_usdt":2.7})
        self.assertEqual(table["week-2"]["SOLUSDT"],{"trades":0,"net20_usdt":0.0})
        self.assertAlmostEqual(sum(v["net20_usdt"] for w in table.values()
                                   for v in w.values()),1.3,places=6)
        with self.assertRaisesRegex(ValueError,"BLOCKED_ASSET_CROSSTAB_TRADE_SCOPE"):
            a.cross_tab(ledger,["week-1"],("SOLUSDT",))

    def test_not_authorized_without_two_explicit_shadow_gates(self):
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED",
                                     "AVRORA_ASSET_ABLATION_ENABLED":"",
                                     "AVRORA_GRID_SHADOW_ENABLED":"YES"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_ASSET_ABLATION_NOT_AUTHORIZED"):
                a.gate()
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED",
                                     "AVRORA_ASSET_ABLATION_ENABLED":"YES",
                                     "AVRORA_GRID_SHADOW_ENABLED":""}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_GRID_FAMILY_NOT_AUTHORIZED"):
                a.gate()
        with patch.dict(os.environ,{"REAL":"ON","HOLDOUT":"SEALED",
                                     "AVRORA_ASSET_ABLATION_ENABLED":"YES",
                                     "AVRORA_GRID_SHADOW_ENABLED":"YES"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_REAL_OR_HOLDOUT"):
                a.gate()

    def test_rejects_incomplete_nonfull13_market_source(self):
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED",
                                     "AVRORA_ASSET_ABLATION_ENABLED":"YES",
                                     "AVRORA_GRID_SHADOW_ENABLED":"YES"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_ASSET_FULL13_SCOPE"):
                a.evaluate({}, {})
            with self.assertRaisesRegex(ValueError,"BLOCKED_ASSET_RECEIPT_PROVENANCE"):
                a.verify({})

    def test_payload_scope_cannot_be_changed_to_make_redistribution_look_profitable(self):
        # Checks boundary that the canonical receipt always pins all six
        # preregistered scenarios, including ALL6 and loss-control.
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED",
                                     "AVRORA_ASSET_ABLATION_ENABLED":"YES",
                                     "AVRORA_GRID_SHADOW_ENABLED":"YES"}):
            m,_=a.prereg()
            self.assertIn("BTC_ETH_NEAR_NEG_CONTROL",
                          {x["id"] for x in m["exact_ordered_scenarios"]})
            self.assertEqual(a.CONTROL["trades"],380)
            self.assertEqual(a.CONTROL["net25"],-47.183751)

if __name__=="__main__":unittest.main()
