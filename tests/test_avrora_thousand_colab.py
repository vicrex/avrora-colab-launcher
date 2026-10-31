"""Offline adversarial checks before a single actual Colab 1000-scenario run."""
import json
import unittest
from tools import avrora_thousand_colab as lab
from tools.verify_thousand_colab import parse, MARKER


class ThousandColabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=lab.simulate()
        cls.report["receipt_sha256"]=lab.sha(lab.canonical(cls.report))

    def test_1000_completed_and_six_symbols(self):
        r=self.report
        self.assertEqual(r["completed_synthetic_scenarios"],1000)
        self.assertEqual(r["null_balanced_scenarios"],500)
        self.assertEqual(r["directional_burst_scenarios"],500)
        self.assertEqual(len(r["cases_by_symbol"]),6)
        self.assertEqual(sum(r["cases_by_symbol"].values()),1000)
        self.assertEqual(r["future_invariance_checks"],1000)
        self.assertEqual(r["invalid_event_rejections"],1000)

    def test_brute_and_recursive_are_invariant(self):
        self.assertLess(self.report["recurrence_vs_direct_sum_max_error"],1e-12)
        self.assertEqual(self.report["real_data_runs"],0)
        self.assertFalse(self.report["oos_proven"])
        self.assertFalse(self.report["live_trading_authorized"])

    def test_deterministic_repeat(self):
        self.assertEqual(lab.simulate(),lab.simulate())

    def test_receipt_sha_and_duplicate_detection(self):
        txt=MARKER+lab.canonical(self.report).decode()
        self.assertEqual(parse(txt),self.report)
        with self.assertRaisesRegex(ValueError,"MISSING_OR_DUPLICATE"):
            parse(txt+"\n"+txt)

    def test_false_economic_evidence_rejected(self):
        copy=dict(self.report)
        copy["maker_fill_proven"]=True
        copy["receipt_sha256"]=lab.sha(lab.canonical({
            k:v for k,v in copy.items() if k!="receipt_sha256"}))
        with self.assertRaisesRegex(ValueError,"FALSE_PROOF"):
            parse(MARKER+lab.canonical(copy).decode())

    def test_tampered_receipt_is_rejected(self):
        copy=dict(self.report)
        copy["completed_synthetic_scenarios"]=999
        with self.assertRaisesRegex(ValueError,"RECEIPT_SHA"):
            parse(MARKER+lab.canonical(copy).decode())

    def test_bad_event_receipt_raises(self):
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_EVENT_ORDER"):
            lab.intensity_brute([(100,99,0)],lab.DECISION_MS)

    def test_frozen_kernel_is_stable(self):
        self.assertLess(sum(lab.ALPHA[0])/lab.BETA,0.95)
        self.assertLess(sum(lab.ALPHA[1])/lab.BETA,0.95)

if __name__=="__main__":
    unittest.main()
