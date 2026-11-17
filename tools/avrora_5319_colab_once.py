"""AVRORA #5319: one-shot actual Colab signal/check2 audit on pinned FULL13 data.
This helper only prepares an ephemeral Colab program with existing read-only private source.
No market orders, no sealed holdout, no schedules, no branch-to-main changes.
"""
from __future__ import annotations
import base64, hashlib, json, os, pathlib, re, subprocess, tempfile
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT/'private_source'/'research'/'P816_FULL13_PREWEEK220'
CODE_DIR = ROOT/'private_code'/'research'/'strategy_search'
CANDIDATE = '7c1fc2dedbd3814b830bcc61e7adb2bed571c69b2b31c7fe35457f59dde8a724'
SOURCE = '7e1bed08982de6e5ff1ec60cbd8afef68067298adcffd590149b43a099dbb297'
MARKER = 'AVRORA_5319_COLAB_ACTUAL_RESULT='

REMOTE = '''import collections, datetime, hashlib, json, os
from research.strategy_search import sweep_v1 as legacy
from research.strategy_search import retest_short_full13_audit as audit
assert os.getenv('REAL','OFF')=='OFF' and os.getenv('HOLDOUT','SEALED')=='SEALED'
p=audit.pinned_parameters()
assert p['candidate_id']=='7c1fc2dedbd3814b830bcc61e7adb2bed571c69b2b31c7fe35457f59dde8a724'
data,meta=audit.load_full13(root)
assert len(data)==72 and sum(len(x) for x in data.values())==64224
checked=0; mismatches=0; raw_signals=0; accepted=[]
by_symbol=collections.Counter(); by_week=collections.Counter(); by_day=collections.Counter()
reasons=collections.Counter()
for (week,sym),bars in sorted(data.items()):
    f=legacy.make_features(bars)
    last=-1000
    for i in range(220,len(bars)-legacy.EXIT_BARS-1):
        a=legacy.eligible(f,i,p)
        b=audit.independent_retest(f,i,p)
        checked+=1
        if a!=b:
            mismatches+=1
            continue
        if not a:continue
        raw_signals+=1
        entry_ms=bars[i+1][0]
        day=(entry_ms//86400000)*86400000
        start=day+12*3600000; stop=day+18*3600000
        if not (start<=entry_ms<stop):
            reasons['offline']+=1;continue
        if entry_ms<start+900000:
            reasons['first_bar_after_start']+=1;continue
        if i-last<8:
            reasons['cooldown']+=1;continue
        if bars[i+12][0]+900000>stop:
            reasons['full_180m_exit_after_window']+=1;continue
        trade=audit.independent_exit(f,i,p,'exact12')
        if trade is None:
            reasons['invalid_stop']+=1;continue
        if trade['entry_t']!=entry_ms:
            raise RuntimeError('BLOCKED_ENTRY_TIME_MISMATCH')
        last=i
        t=datetime.datetime.fromtimestamp(entry_ms/1000,datetime.timezone.utc)
        accepted.append({'week':week,'symbol':sym,'utc':t.isoformat()})
        by_symbol[sym]+=1;by_week[week]+=1;by_day[t.date().isoformat()]+=1
weeks=sorted(set(w for w,s in data))
assert len(weeks)==12
all_days=[(datetime.date.fromisoformat(w)+datetime.timedelta(days=d)).isoformat() for w in weeks for d in range(7)]
zero=sum(by_day[d]==0 for d in all_days)
receipt={
 'schema':'AVRORA_5319_COLAB_FULL13_SIGNALS_V1',
 'execution':'GOOGLE_COLAB_CLI_REAL_ONE_SHOT_NOT_CACHE',
 'candidate_sha256':p['candidate_id'],'source_sha256':'7e1bed08982de6e5ff1ec60cbd8afef68067298adcffd590149b43a099dbb297',
 'check2_checked':checked,'check2_mismatches':mismatches,
 'full13_rows':69576,'discovery_rows':64224,'discovery_weeks':12,
 'raw_signals_all_hours':raw_signals,
 'session_signal_proposals':len(accepted),
 'zero_signal_days':zero,'total_days':len(all_days),
 'by_symbol':dict(by_symbol),'by_week':dict(by_week),'by_day':dict(by_day),
 'rejection_reasons':dict(reasons),
 'real':'OFF','holdout':'SEALED','orders_sent':0,
 'forward_execution_verified':False,'profit_proven':False,
 'one_slot_canary_trade_count_verified':False,
 'note':'already studied discovery weeks, 2-slot historical source only; no new OOS or live BBO'
}
receipt['receipt_sha256']=hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
if mismatches:raise RuntimeError('BLOCKED_CHECK2_MISMATCH')
print('AVRORA_5319_COLAB_ACTUAL_RESULT='+json.dumps(receipt,sort_keys=True,separators=(',',':'),ensure_ascii=False),flush=True)
'''

def main():
    if os.getenv('REAL','OFF')!='OFF' or os.getenv('HOLDOUT','SEALED')!='SEALED':
        raise RuntimeError('BLOCKED_ENVIRONMENT')
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        raise RuntimeError('BLOCKED_COLAB_CREDENTIALS')
    files={}
    for file in ('sweep_v1.py','retest_short_full13_audit.py'):
        p=CODE_DIR/file
        if not p.is_file():raise RuntimeError('BLOCKED_MISSING_CODE_'+file)
        files['research/strategy_search/'+file]=base64.b64encode(p.read_bytes()).decode()
    for file in ['data_manifest.json']+[f'P816_PANEL.private.b64.part{i:02}' for i in range(1,11)]:
        p=DATA_DIR/file
        if not p.is_file():raise RuntimeError('BLOCKED_MISSING_DATA_'+file)
        files['research/P816_FULL13_PREWEEK220/'+file]=base64.b64encode(p.read_bytes()).decode()
    bootstrap=(
      'import base64,os,pathlib,sys,tempfile\n'
      'root=pathlib.Path(tempfile.mkdtemp(prefix="avrora5319_colab_"))\n'
      f'FILES={files!r}\n'
      'for rel,encoded in FILES.items():\n'
      ' p=root/rel; p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(encoded))\n'
      'sys.path.insert(0,str(root))\n'
    )
    with tempfile.TemporaryDirectory(prefix='avrora5319_once_') as d:
        script=pathlib.Path(d)/'colab_5319.py'
        script.write_text(bootstrap+REMOTE,encoding='utf8');script.chmod(0o600)
        log=pathlib.Path(d)/'colab.log'
        with log.open('wb') as f:
            p=subprocess.run(['colab','--auth=adc','run',str(script)],stdout=f,stderr=subprocess.STDOUT,
                             env={**os.environ,'REAL':'OFF','HOLDOUT':'SEALED'},timeout=1600)
        if p.returncode:
            print('BLOCKED_AVRORA5319_COLAB_EXECUTION_RETURN_CODE',p.returncode)
            raise SystemExit(2)
        lines=[l.split(MARKER,1)[1] for l in log.read_text('utf8').splitlines() if MARKER in l]
        if len(lines)!=1:raise RuntimeError('BLOCKED_NO_EXACT_RESULT_MARKER')
        x=json.loads(lines[0]); h=x.pop('receipt_sha256')
        canon=json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        if (hashlib.sha256(canon).hexdigest()!=h or x.get('candidate_sha256')!=CANDIDATE
                or x.get('source_sha256')!=SOURCE or x.get('check2_mismatches')!=0
                or x.get('real')!='OFF' or x.get('holdout')!='SEALED'):
            raise RuntimeError('BLOCKED_INVALID_COLAB_RECEIPT')
        x['receipt_sha256']=h
        target=ROOT/'AVRORA_5319_COLAB_ACTUAL_RECEIPT.json'
        if target.exists():raise RuntimeError('BLOCKED_RECEIPT_OVERWRITE')
        target.write_text(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2),encoding='utf8')
        print('PASS_AVRORA5319_ACTUAL_COLAB',len(lines),'signals',x['session_signal_proposals'],
              'zero_days',x['zero_signal_days'],'checked',x['check2_checked'],'sha',h)

if __name__=='__main__':main()