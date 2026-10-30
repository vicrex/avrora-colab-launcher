"""Offline synthetic unit tests for public neutral engine; no private data."""
import copy,hashlib,json,unittest
from tools import strategy_vector48 as v

def mock_report(count=64):
 a={'by_week':{f'2021-01-{j:02d}':{'net20_usdt':1.,'trades':2} for j in range(1,7)},'trades':12,'gross_usdt':7.2,'notional_sum':600.,'net20_usdt':6.}
 b={'by_week':{f'2023-01-{j:02d}':{'net20_usdt':-1.,'trades':2} for j in range(1,7)},'trades':12,'gross_usdt':-4.8,'notional_sum':600.,'net20_usdt':-6.}
 models=[{'candidate_id':f'{i:064x}','family':v.FAMILIES[i%6],'side':('LONG','SHORT')[i%2],'train':copy.deepcopy(a),'validation':copy.deepcopy(b)} for i in range(count)]
 r={'schema':'AVRORA_MULTIFAMILY_SHADOW_SWEEP_V1','real':'OFF','holdout':'SEALED','fill_proven':False,'oos_proven':False,'count':count,'models':models,'candidate_ids':[x['candidate_id'] for x in models]};r['receipt_sha256']=v.sha(v.canonical(r));return r

class VectorStageTest(unittest.TestCase):
 def test_48_exact(self):self.assertEqual(len(v.DIMENSIONS),48)
 def test_all_models_preserved(self):
  s=v.stage(v.canonical(mock_report()));self.assertEqual(len(s['strategies']),64)
  self.assertEqual(len({x['candidate_id'] for x in s['strategies']}),64)
 def test_terminal_partial_batch_preserved(self):
  r=mock_report(32);s=v.stage(v.canonical(r),32);self.assertEqual(s['count'],32)
  self.assertEqual(len(s['strategies']),32)
 def test_terminal_partial_requires_explicit_expected_count(self):
  with self.assertRaisesRegex(ValueError,'BLOCKED_VECTOR_UNTRUSTED_REPORT'):v.stage(v.canonical(mock_report(32)))
 def test_unexpected_count_fails_closed(self):
  with self.assertRaisesRegex(ValueError,'BLOCKED_VECTOR_EXPECTED_COUNT'):v.stage(v.canonical(mock_report(32)),31)
 def test_masks_null_not_zero(self):
  p=v.stage(v.canonical(mock_report()))['strategies'][0];i=v.DIMENSIONS.index('window_bars');self.assertIsNone(p['raw48'][i]);self.assertEqual(p['observed_mask48'][i],0)
 def test_refuse_future_proof(self):
  s=v.stage(v.canonical(mock_report()));self.assertFalse(s['maker_fill_verified']);self.assertFalse(s['oos_verified']);self.assertFalse(s['graph_attested'])
 def test_hash_tamper_fail_closed(self):
  r=mock_report();r['models'][0]['train']['net20_usdt']=30
  with self.assertRaisesRegex(ValueError,'BLOCKED_VECTOR_REPORT_HASH'):v.stage(v.canonical(r))
 def test_bad_week_total_fail_closed(self):
  r=mock_report();r['models'][0]['train']['by_week']['2021-01-01']['net20_usdt']=2.;r['receipt_sha256']=v.sha(v.canonical({k:x for k,x in r.items() if k!='receipt_sha256'}))
  with self.assertRaisesRegex(ValueError,'BLOCKED_VECTOR_WEEK_PARITY'):v.stage(v.canonical(r))
 def test_wrong_side_fail_closed(self):
  r=mock_report();r['models'][0]['side']='SIDEWAYS';r['receipt_sha256']=v.sha(v.canonical({k:x for k,x in r.items() if k!='receipt_sha256'}))
  with self.assertRaisesRegex(ValueError,'BLOCKED_VECTOR_UNKNOWN_MECHANISM'):v.stage(v.canonical(r))
 def test_duplicate_candidate_fails(self):
  r=mock_report();r['candidate_ids'][1]=r['candidate_ids'][0];r['models'][1]['candidate_id']=r['candidate_ids'][0];r['receipt_sha256']=v.sha(v.canonical({k:x for k,x in r.items() if k!='receipt_sha256'}))
  with self.assertRaisesRegex(ValueError,'BLOCKED_VECTOR_MODEL_ID_PARITY'):v.stage(v.canonical(r))
 def test_cost_stress_decreases(self):
  row=v.stage(v.canonical(mock_report()))['strategies'][0];i=v.DIMENSIONS.index('validation_net16_usdt_per_trade');j=v.DIMENSIONS.index('validation_net40_usdt_per_trade')
  self.assertGreater(row['raw48'][i],row['raw48'][j])
 def test_reproducible(self):
  b=v.canonical(mock_report());self.assertEqual(v.stage(b)['stage_sha256'],v.stage(b)['stage_sha256'])
if __name__=='__main__':unittest.main()
