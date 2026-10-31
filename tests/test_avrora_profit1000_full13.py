"""Deterministic adversarial offline checks; NO private dataset or network."""
from __future__ import annotations
import hashlib
import json
import tempfile
from pathlib import Path
import unittest

from tools import avrora_profit1000_full13 as p
from tools import verify_profit1000_colab as v


FIRST=[f"train-{i}" for i in range(6)]
LATE=[f"seen-late-{i}" for i in range(6)]


def ledger():
    # Real sign mixtures for testing code only. This is SYNTHETIC test data.
    return {
        w:{"gross":(i%3-1)*1.25,"notional":100+i*10.0,
           "trades":(i%4)}
        for i,w in enumerate(FIRST+LATE)
    }


class Profit1000OfflineContracts(unittest.TestCase):
    def test_preregistered_exact_one_thousand_and_costs(self):
        self.assertEqual((p.N,p.CANDIDATE,p.SEED),
                         (1000,"FIVE_WAVE_01",20261101))
        self.assertEqual(p.COSTS,(16,20,25,40))
    def test_original_bootstrap_exact_reproducibility(self):
        a=p.summarize(ledger(),FIRST,LATE)
        b=p.summarize(ledger(),FIRST,LATE)
        self.assertEqual(a,b)
        self.assertEqual(a["samples"],1000)
        self.assertEqual(a["week_draws"],12000)
        self.assertEqual(len(a["bootstrap_signature_sha256"]),64)
    def test_all_cost_stresses_applied_to_every_week(self):
        a=p.summarize(ledger(),FIRST,LATE)
        rows=a["cost_stress_bps"]
        self.assertEqual(set(rows),{"16","20","25","40"})
        for cost in p.COSTS:
            z=rows[str(cost)]
            self.assertEqual(z["bootstrap_positive_net_trials"]+
                             z["bootstrap_nonpositive_net_trials"],1000)
            self.assertFalse(z["trading_dominates_no_trade_proven"])
            self.assertEqual(z["no_trade_net_usdt"],0)
        self.assertTrue(all(
            rows[str(x)]["observed_12w_model_net_usdt"]>=
            rows[str(y)]["observed_12w_model_net_usdt"]
            for x,y in zip(p.COSTS,p.COSTS[1:])))
    def test_all_zero_baseline_is_no_profit_not_1000_winners(self):
        d={w:{"gross":0.0,"notional":0.0,"trades":0} for w in FIRST+LATE}
        a=p.summarize(d,FIRST,LATE)
        self.assertEqual(a["historical_closed_trade_count"],0)
        for z in a["cost_stress_bps"].values():
            self.assertEqual(z["bootstrap_positive_net_trials"],0)
            self.assertEqual(z["bootstrap_nonpositive_net_trials"],1000)
            self.assertEqual(z["bootstrap_median_net_usdt"],0)
    def test_missing_week_is_blocked(self):
        d=ledger()
        d.pop(FIRST[0])
        with self.assertRaisesRegex(ValueError,"WEEK_LEDGER"):
            p.summarize(d,FIRST,LATE)
    def test_strata_different_and_unique(self):
        with self.assertRaisesRegex(ValueError,"STRATA"):
            list(p.sample_weeks(FIRST,FIRST))
        with self.assertRaisesRegex(ValueError,"STRATA"):
            list(p.sample_weeks(FIRST,LATE[:-1]))
    def test_out_of_range_trial_count_blocked(self):
        with self.assertRaisesRegex(ValueError,"STRATA"):
            list(p.sample_weeks(FIRST,LATE,count=1001))
    def test_quantiles_are_monotone(self):
        a=sorted([-10.,0.,1.,13.,200.])
        self.assertLessEqual(p.quantile(a,.05),p.quantile(a,.5))
        self.assertLessEqual(p.quantile(a,.5),p.quantile(a,.95))
    def test_receipt_without_digest_never_passes(self):
        with self.assertRaisesRegex(ValueError,"RECEIPT_SHA"):
            v.parse(p.MARKER+'{"schema":"'+p.SCHEMA+'"}')
    def test_duplicate_receipt_marker_never_passes(self):
        with self.assertRaisesRegex(ValueError,"MARKER_COUNT"):
            v.parse(p.MARKER+"{}\n"+p.MARKER+"{}")
    def test_source_and_trading_guards_in_report(self):
        import inspect
        code=inspect.getsource(p.run_real_history)
        for attr in ("actual_net_profit_proven",
                     "independent_prospective_oos_proven",
                     "estimated_maker_fill_proven",
                     "source_first_seen_event_receipts_present"):
            self.assertIn(attr,code)
        self.assertIn("run_complete",code)
        self.assertNotIn("place_order",code)


if __name__=="__main__":
    unittest.main()
