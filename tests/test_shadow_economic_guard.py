"""Synthetic-only checks for the aggregate research guard (no private strategy data)."""
import copy
import json
import unittest

from tools.shadow_economic_guard import audit_report, MIN_TOTAL_VALIDATION_TRADES
from tools.strategy_vector48 import canonical, sha


def split(good, trades):
    net20 = 3.0 if good else -1.0
    return {
        "trades": trades,
        "gross_usdt": net20 + 2.0,
        "net20_usdt": net20,
        "notional_sum": 1000.0,
        "by_week": {f"w{i}": {"trades": trades // 6,
                              "net20_usdt": net20 / 6} for i in range(6)},
    }


def sample(count=64, winners=0, trades=1200):
    models = []
    for i in range(count):
        good = i < winners
        models.append({
            "candidate_id": f"{i:064x}",
            "family": "MOMENTUM_BAR",
            "side": "SHORT" if i % 2 else "LONG",
            "train": split(good, trades),
            "validation": split(good, trades),
        })
    report = {
        "schema": "AVRORA_MULTIFAMILY_SHADOW_SWEEP_V1",
        "count": count, "real": "OFF", "holdout": "SEALED",
        "fill_proven": False, "oos_proven": False,
        "candidate_ids": [m["candidate_id"] for m in models],
        "models": models,
        "summaries": {"train_and_validation_positive": winners},
    }
    report["receipt_sha256"] = sha(canonical(report))
    return report


def resign(report):
    report["receipt_sha256"] = sha(canonical({
        k: v for k, v in report.items() if k != "receipt_sha256"
    }))


class ShadowEconomicGuardTests(unittest.TestCase):
    def test_32_terminal_cost_and_frequency_are_aggregated(self):
        result = audit_report(sample(32, winners=8), 32)
        self.assertEqual(result["dual_positive_both_reused_splits_by_bps"],
                         {"16": 8, "20": 8, "25": 8, "40": 8})
        self.assertEqual(result["models_reaching_necessary_total_frequency"], 32)
        self.assertEqual(result["models_reaching_40bps_and_frequency"], 8)
        self.assertFalse(result["live_trading_authorized"])
        self.assertEqual(result["decision"], "RESEARCH_ONLY_NO_PROMOTION")
        self.assertEqual(result["holdout"], "SEALED")
        self.assertEqual(MIN_TOTAL_VALIDATION_TRADES, 1008)
        raw = json.dumps(result)
        self.assertNotIn("candidate_id", raw)
        self.assertNotIn("gross_usdt", raw)

    def test_64_profitable_but_too_infrequent_stays_blocked(self):
        result = audit_report(sample(64, winners=64, trades=120))
        self.assertEqual(result["dual_positive_both_reused_splits_by_bps"]["40"], 64)
        self.assertEqual(result["models_reaching_necessary_total_frequency"], 0)
        self.assertEqual(result["models_reaching_40bps_and_frequency"], 0)
        self.assertFalse(result["live_trading_authorized"])

    def test_zero_survivors_stays_research_only(self):
        result = audit_report(sample(64, winners=0))
        self.assertEqual(result["dual_positive_both_reused_splits_by_bps"]["40"], 0)
        self.assertEqual(result["models_reaching_40bps_and_frequency"], 0)

    def test_terminal_must_be_explicit(self):
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_REPORT"):
            audit_report(sample(32))

    def test_summary_mismatch_is_blocked(self):
        obj = sample(32, winners=8)
        obj["summaries"]["train_and_validation_positive"] = 7
        resign(obj)
        with self.assertRaisesRegex(ValueError, "AGGREGATE_PARITY"):
            audit_report(obj, 32)

    def test_receipt_sha_is_required(self):
        obj = sample(32, winners=8)
        obj["models"][0]["train"]["net20_usdt"] = 500
        with self.assertRaisesRegex(ValueError, "REPORT_HASH"):
            audit_report(obj, 32)

    def test_weekly_trade_mismatch_is_blocked(self):
        obj = sample()
        obj["models"][0]["validation"]["by_week"]["w0"]["trades"] += 1
        resign(obj)
        with self.assertRaisesRegex(ValueError, "WEEK_PARITY"):
            audit_report(obj)

    def test_cost_inconsistency_is_blocked(self):
        obj = sample()
        obj["models"][0]["validation"]["gross_usdt"] += 2
        resign(obj)
        with self.assertRaisesRegex(ValueError, "COST_PARITY"):
            audit_report(obj)

    def test_negative_notional_is_blocked(self):
        obj = sample()
        obj["models"][0]["validation"]["notional_sum"] = -1000
        obj["models"][0]["validation"]["gross_usdt"] = -3
        resign(obj)
        with self.assertRaisesRegex(ValueError, "NEGATIVE_NOTIONAL"):
            audit_report(obj)

    def test_reject_fake_execution_proof(self):
        obj = sample(32)
        obj["oos_proven"] = True
        resign(obj)
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_REPORT"):
            audit_report(obj, 32)


if __name__ == "__main__":
    unittest.main()
