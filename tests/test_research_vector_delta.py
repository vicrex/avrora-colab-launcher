import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import research_vector_delta as d
from tools import hourly_wave_research as wave

class DeltaTests(unittest.TestCase):
 def test_missing_receipt_is_blocked_not_pass(self):
  m=wave.load_manifest();candidate=m['candidates'][0]['id']
  with tempfile.TemporaryDirectory() as p:
   card=d.make_card(candidate,str(Path(p)/'absent.json'),'987123','1',False)
  self.assertEqual(card['decision'],'BLOCKED')
  self.assertEqual(card['status'],'BLOCKED_NO_VERIFIED_RECEIPT')
  self.assertIsNone(card['metrics'])
 def test_candidate_injection_blocked(self):
  with self.assertRaisesRegex(ValueError,'BLOCKED_CANDIDATE'):
   d.make_card('BAD_ENV_INJECT', 'no.json','123','1',False)
 def test_no_run_context(self):
  with self.assertRaisesRegex(ValueError,'BLOCKED_RUN_ID'):
   d.make_card('FIVE_WAVE_01','x.json','not-a-run','1',False)
 def test_holdout_status(self):
  with patch.dict(os.environ,{'HOLDOUT':'OPEN'}):
   with self.assertRaisesRegex(ValueError,'BLOCKED_SAFETY'):
    d.make_card('FIVE_WAVE_01','x.json','77','1',False)
 def test_stable_cache_receipt_identity(self):
  a=d.make_card('FIVE_WAVE_01','absent','987','1',True)
  b=d.make_card('FIVE_WAVE_01','absent','987','1',True)
  self.assertEqual(a,b)
 def test_vector_nonempty(self):
  self.assertTrue(d.vec('Wave5 Elliott Fibonacci SHORT AO'))

if __name__=='__main__':unittest.main()