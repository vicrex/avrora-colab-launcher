"""AVRORA per-hour private 48-dimensional vector evidence gate (stdlib only).

This executable runs only after the existing private report has been generated.
It NEVER posts private vectors to GitHub, prints private values, or requires
additional clocks, tokens, external APIs, trading, or new data sources.
Full private report already goes to Drive via the existing owner GAS route.
"""
from __future__ import annotations
import argparse,hashlib,json,math,os
from pathlib import Path
from tools.multifamily_batch_contract import expected_batch_count

FAMILIES=('TREND_BREAK','SQUEEZE_BREAK','RETEST_CONTINUATION','FALSE_BREAK_FADE','MOMENTUM_BAR','EMA_REVERSION')
DIMENSIONS=(
 *('family_'+f for f in FAMILIES),'is_LONG','is_SHORT',
 'window_bars','break_atr','body_atr','stop_atr','reward_r','holding_bars',
 'signal_timeframe_minutes','symbol_count','start_equity_usdt','notional_cap_usdt',
 'leverage_cap','risk_cap_usdt','max_positions',
 'train_net20_usdt_per_trade','validation_net20_usdt_per_trade',
 'train_gross_usdt_per_trade','validation_gross_usdt_per_trade',
 'train_avg_notional_usdt','validation_avg_notional_usdt',
 'train_trades_per_day','validation_trades_per_day',
 'train_positive_week_fraction','validation_positive_week_fraction',
 'train_week_net20_std','validation_week_net20_std',
 'train_worst_week_net20','validation_worst_week_net20',
 'train_minus_validation_net20_per_trade',
 'validation_net16_usdt_per_trade','validation_net25_usdt_per_trade','validation_net40_usdt_per_trade',
 'validation_cost_slope_per_bps_usdt',
 'receipt_verified','graph_attested','independent_ledger_check',
 'prospective_oos_verified','maker_fill_verified',
 'posthoc_subset_selection','funding_verified','l2_queue_verified')
assert len(DIMENSIONS)==48

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def check_report(data, research_hour=None):
 expected=expected_batch_count(research_hour) if research_hour is not None else 64
 if (not isinstance(data,dict) or data.get('schema')!='AVRORA_MULTIFAMILY_SHADOW_SWEEP_V1' or
   data.get('count')!=expected or data.get('real')!='OFF' or data.get('holdout')!='SEALED' or
   data.get('fill_proven') is not False or data.get('oos_proven') is not False):raise ValueError('BLOCKED_VECTOR_UNTRUSTED_REPORT')
 receipt=data.get('receipt_sha256')
 if receipt!=sha(canonical({k:v for k,v in data.items() if k!='receipt_sha256'})):raise ValueError('BLOCKED_VECTOR_REPORT_HASH')
 if (not isinstance(data.get('models'),list) or not isinstance(data.get('candidate_ids'),list) or
   len(data['models'])!=expected or len(data['candidate_ids'])!=expected or
   len(set(data['candidate_ids']))!=expected or
   [m.get('candidate_id') for m in data['models']]!=data['candidate_ids']):raise ValueError('BLOCKED_VECTOR_MODEL_ID_PARITY')
 return receipt

def stdev(nums):
 av=sum(nums)/len(nums);return (sum((n-av)**2 for n in nums)/len(nums))**.5

def split_features(split,label):
 t=split['trades'];w=list(split['by_week'].values())
 if len(w)!=6 or sum(z['trades'] for z in w)!=t or abs(sum(z['net20_usdt'] for z in w)-split['net20_usdt'])>2e-4:raise ValueError('BLOCKED_VECTOR_WEEK_PARITY')
 gross=split['gross_usdt'];notional=split['notional_sum'];net=split['net20_usdt']
 if abs((gross-0.002*notional)-net)>3e-5:raise ValueError('BLOCKED_VECTOR_COST_PARITY')
 f={}
 for name,amount in [('net20',net),('gross',gross),('avg_notional',notional)]:
  key='avg_notional_usdt' if name=='avg_notional' else name+'_usdt_per_trade'
  f[label+'_'+key]=amount/t if t else None
 f[label+'_trades_per_day']=t/42
 f[label+'_positive_week_fraction']=sum(x['net20_usdt']>0 for x in w)/len(w)
 vals=[x['net20_usdt'] for x in w]
 f[label+'_week_net20_std']=stdev(vals)
 f[label+'_worst_week_net20']=min(vals)
 if label=='validation':
  for bp in (16,25,40):f['validation_net'+str(bp)+'_usdt_per_trade']=(gross-bp/10000*notional)/t if t else None
  f['validation_cost_slope_per_bps_usdt']=(-.0024*notional/24/t) if t else None
 return f

def vector_for(model):
 if model.get('family') not in FAMILIES or model.get('side') not in ('LONG','SHORT'):raise ValueError('BLOCKED_VECTOR_UNKNOWN_MECHANISM')
 f={k:None for k in DIMENSIONS}
 for family in FAMILIES:f['family_'+family]=int(model['family']==family)
 for side in ('LONG','SHORT'):f['is_'+side]=int(model['side']==side)
 # Private report does NOT contain full candidate parameters. These dimensions
 # remain NULL until resolved from private frozen specification by the Drive indexer.
 f['symbol_count']=6;f['notional_cap_usdt']=500;f['risk_cap_usdt']=5;f['signal_timeframe_minutes']=15;f['holding_bars']=12
 tr=split_features(model['train'],'train');vl=split_features(model['validation'],'validation')
 f.update(tr);f.update(vl)
 if tr['train_net20_usdt_per_trade'] is not None and vl['validation_net20_usdt_per_trade'] is not None:f['train_minus_validation_net20_per_trade']=tr['train_net20_usdt_per_trade']-vl['validation_net20_usdt_per_trade']
 for k in ('receipt_verified','prospective_oos_verified','maker_fill_verified','posthoc_subset_selection','funding_verified','l2_queue_verified'):
  f[k]=int(k=='receipt_verified')
 f['graph_attested']=None # must not fabricate future private graph append
 f['independent_ledger_check']=0
 values=[f[k] for k in DIMENSIONS]
 if any(x is not None and (type(x) not in (int,float) or not math.isfinite(x)) for x in values):raise ValueError('BLOCKED_VECTOR_NUMERIC_INVALID')
 return {'candidate_id':model['candidate_id'],'raw48':values,'observed_mask48':[int(x is not None) for x in values],
         'prospective_oos_verified':False,'maker_fill_verified':False}

def stage(report_bytes, research_hour=None):
 report=json.loads(report_bytes);receipt=check_report(report, research_hour)
 rows=[vector_for(m) for m in report['models']]
 payload={'schema':'AVRORA_PRIVATE_VECTOR_DELTA48_V1','dimension_names':DIMENSIONS,'count':report['count'],
   'source_report_sha256':sha(report_bytes),'source_receipt_sha256':receipt,
   'strategies':rows,'graph_attested':False,'holdout':'SEALED','real':'OFF',
   'oos_verified':False,'maker_fill_verified':False,'private_only':True,
   'cost_economics_only_modelled':True}
 payload['stage_sha256']=sha(canonical(payload))
 return payload

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 output=Path(a.output)
 if output.exists():raise SystemExit('BLOCKED_VECTOR_OVERWRITE')
 hour=os.environ.get('RESEARCH_UTC_HOUR')
 d=stage(Path(a.input).read_bytes(), int(hour) if hour is not None else None)
 output.write_bytes(canonical(d)+b'\n')
 # No candidate IDs, PnLs or vectors in public job stdout.
 print('PASS_PRIVATE_VECTOR48_STAGE_ONLY',d['count'],d['stage_sha256'])
if __name__=='__main__':main()
