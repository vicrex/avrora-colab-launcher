"""Fail-closed contract for FULL13 decision-card economics scope."""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/avrora-private-wave.yml"


class Full13EconomicsScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_modelled_cost_stress_is_not_execution_economics(self):
        self.assertIn("economics_proven=False,execution_economics_proven=False", self.text)
        self.assertNotIn("reason_code=None,economics_proven=True", self.text)
        self.assertIn("modelled_stress_economics_verified=True", self.text)
        self.assertIn(
            "economics_scope='MODELLED_20_25_40BPS_NO_FUNDING_SLIPPAGE_FILLS'",
            self.text,
        )

    def test_missing_owner_16bps_and_execution_fields_are_explicit(self):
        self.assertIn(
            "owner_required_16bps_present='net16_usdt' in r['discovery']",
            self.text,
        )
        self.assertIn("funding_modeled=bool(r.get('funding_modeled',False))", self.text)
        self.assertIn("slippage_modeled=bool(r.get('slippage_modeled',False))", self.text)
        self.assertIn(
            "maker_fill_proven=bool(r.get('maker_fills_proven',False))",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
