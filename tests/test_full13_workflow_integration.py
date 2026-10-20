"""Protect one candidate -> one complete full13 Colab run in existing hourly workflow."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
WF=ROOT/'.github/workflows/avrora-private-wave.yml'
HOURLY=ROOT/'.github/workflows/colab-launcher.yml'

class Full13WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.s=WF.read_text(encoding='utf-8')
    def test_one_existing_hourly_timer(self):
        caller=HOURLY.read_text(encoding='utf-8')
        self.assertEqual(len(re.findall(r'cron: "7 \* \* \* \*"',caller)),1)
        self.assertNotIn('  schedule:',self.s)
        self.assertIn('workflow_call:',self.s)
        self.assertIn('uses: ./.github/workflows/avrora-private-wave.yml',caller)
        self.assertIn('secrets: inherit',caller)
        self.assertIn('cancel-in-progress: false',self.s)
    def test_explicit_full13_dispatch_and_pin(self):
        self.assertIn('          - full13',self.s)
        self.assertIn("inputs.mode == 'full13'",self.s)
        self.assertIn('AVRORA_FULL13_SOURCE_SHA',self.s)
        self.assertIn('BLOCKED_FULL13_SOURCE_SHA_NOT_PINNED',self.s)
        self.assertIn('PASS_PINNED_FULL13_DATASET_69576_M15',self.s)
    def test_one_colab_per_entire_dataset(self):
        self.assertEqual(self.s.count('python tools/full13_wave_colab.py run'),1)
        self.assertIn('12 weeks + May + 220-bar warmup + CHECK2',self.s)
        self.assertIn('python tools/full13_wave_colab.py verify',self.s)
        self.assertIn('avrora-full13-verified-',self.s)
        self.assertIn('avrora-full13-vector-delta-',self.s)
        self.assertIn('BLOCKED_NO_VERIFIED_FULL13_RECEIPT',self.s)
    def test_paid_colab_adc_is_still_narrow(self):
        self.assertIn("env.RUN_FULL13 == 'true' || steps.existing_proof",self.s)
        self.assertIn("'google-colab-cli==0.7.4'",self.s)
        self.assertIn('AVRORA_COLAB_ADC_JSON_B64',self.s)
        self.assertNotIn('AVRORA_DRIVE_SERVICE_ACCOUNT',self.s)
    def test_no_live_or_holdout(self):
        self.assertIn('REAL: "OFF"',self.s)
        self.assertIn('HOLDOUT: "SEALED"',self.s)
        self.assertIn('permissions:\n  contents: read',self.s)

if __name__=='__main__':unittest.main()
