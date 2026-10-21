"""ResCP-inspired causal H4 confidence gate: NOT official ResCP or DLinear.

Pure-Python read-only shadow research on SHA-pinned P816 FULL13.
No real execution, no OOS, no maker fill claim, no code from Issues executed.
"""
from __future__ import annotations
import base64,hashlib,json,math,os,pathlib,random,subprocess,sys,tempfile

try:
    from tools import full13_wave_colab as full13
    from tools import rescp_check2 as independent
except ImportError:
    import full13_wave_colab as full13
    import rescp_check2 as independent

SCHEMA='AVRORA_RESCP_LITE_DISCOVERY_SHADOW_V1'
CANDIDATE='RESCP_LITE_H4_RIDGE_V1'
ISSUE=15
PREREG_SHA='5352bbbaddd4ee4e050df945d368a24e9559aa2139722e0a3553b01ebe9c9cb8'
MARKER='AVRORA_RESCP_SHADOW_VERIFIED='
H=4
L=16
MIN_CAL=96
WIN=128
N=12
ALPHA=0.1
NOTIONAL=500.
COSTS=(16,20,25,40)

def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(v):return hashlib.sha256(v).hexdigest()

def gate():
    full13.gate()
    if os.getenv('AVRORA_ALLOW_RESCP_SHADOW','')!='YES':
        raise ValueError('BLOCKED_RESCP_SHADOW_NOT_APPROVED')

def features(bars,t):
    if t<L:raise ValueError('BLOCKED_FEATURE_PREFIX')
    return [1.]+[10000*math.log(bars[t-k+1][4]/bars[t-k][4]) for k in range(1,L+1)]

def frozen_forecaster(bars):
    """Train a fixed linear H4 proxy ONLY on true preweek prefix."""
    rows=[];ys=[]
    for t in range(L,full13.WARMUP-H):
        rows.append(features(bars,t))
        ys.append(10000*math.log(bars[t+H][4]/bars[t][4]))
    n=L+1
    mat=[[0.]*(n+1) for _ in range(n)]
    for x,y in zip(rows,ys):
        for i in range(n):
            mat[i][-1]+=x[i]*y
            for j in range(n):mat[i][j]+=x[i]*x[j]
    for i in range(n):mat[i][i]+=(0.01 if i==0 else 50.)
    for i in range(n):
        k=max(range(i,n),key=lambda p:abs(mat[p][i]))
        mat[k],mat[i]=mat[i],mat[k]
        if abs(mat[i][i])<1e-10:raise ValueError('BLOCKED_RIDGE_SINGULAR')
        pivot=mat[i][i]
        for j in range(i,n+1):mat[i][j]/=pivot
        for k in range(n):
            if k!=i:
                f=mat[k][i]
                for j in range(i,n+1):mat[k][j]-=f*mat[i][j]
    return [mat[i][-1] for i in range(n)]

def reservoir_weights():
    rng=random.Random(15543)
    return [rng.uniform(-.18,.18) for _ in range(N)],[rng.uniform(-.035,.035) for _ in range(N)]

def evolve(state,error,inp,bias):
    x=max(-6.,min(6.,error/100.))
    return [.35*state[i]+.65*math.tanh(inp[i]*x+.58*state[(i-1)%N]+bias[i]) for i in range(N)]

def cosine(a,b):
    num=sum(x*y for x,y in zip(a,b))
    den=math.sqrt(sum(x*x for x in a)*sum(y*y for y in b))
    return num/den if den>1e-12 else 0.

def wquant(values,weights,q=.9):
    threshold=q*sum(weights);s=0.
    for value,weight in sorted(zip(values,weights)):
        s+=weight
        if s>=threshold:return value
    return max(values)

def ordinary_quantile(values):
    count=len(values)
    return sorted(values)[min(count,math.ceil((count+1)*.9))-1]

def radii(cal,state,t):
    if len(cal)<MIN_CAL:raise ValueError('BLOCKED_CAL_SHORT')
    if any(origin+H>t for origin,*_ in cal):raise ValueError('BLOCKED_UNMATURED_CALIBRATION')
    allq=ordinary_quantile([row[1] for row in cal])
    last=cal[-WIN:];scores=[x[1] for x in last]
    roll=ordinary_quantile(scores)
    expo=wquant(scores,[.98**(len(last)-1-i) for i in range(len(last))])
    logw=[cosine(row[2],state)/.35-math.log1p((t-row[0])/64.) for row in last]
    top=max(logw);weights=[math.exp(x-top) for x in logw]
    neff=sum(weights)**2/sum(x*x for x in weights)
    local=wquant(scores,weights) if neff>=32 else roll
    return {'global':allq,'rolling':roll,'exponential':expo,'reservoir':local},neff

def group_compute(bars,period,symbol):
    fit=frozen_forecaster(bars);inp,bias=reservoir_weights()
    preds={};states={};cal=[];state=[0.]*N
    scores={k:[] for k in ('global','rolling','exponential','reservoir')}
    signals=[];fallback=0
    for t in range(full13.WARMUP,len(bars)-H):
        u=t-H
        if u in preds:
            observed=10000*math.log(bars[t][4]/bars[u][4])
            resid=observed-preds[u]
            cal.append((u,abs(resid),states[u]))
            state=evolve(state,resid,inp,bias)
        pred=sum(x*y for x,y in zip(fit,features(bars,t)))
        states[t]=tuple(state);preds[t]=pred
        if len(cal)<MIN_CAL:continue
        width,neff=radii(cal,states[t],t)
        if neff<32:fallback+=1
        actual=10000*math.log(bars[t+H][4]/bars[t][4])
        past=[10000*math.log(bars[z][4]/bars[z-1][4]) for z in range(t-23,t+1)]
        mean=sum(past)/24
        vol=math.sqrt(sum((v-mean)**2 for v in past)/24)
        for method,q in width.items():
            err=abs(actual-pred)
            scores[method].append((err<=q,q,2*q+20*max(0.,err-q),vol))
        q=width['reservoir']
        if abs(pred)>q and q<120:
            side=1 if pred>0 else -1
            entry=bars[t+1][1];exit_price=bars[t+H][4]
            signals.append(dict(period=period,symbol=symbol,
                signal_t=bars[t][0],entry_t=bars[t+1][0],exit_t=bars[t+H][0],
                side=side,entry=entry,exit=exit_price,
                gross=side*(exit_price/entry-1)*NOTIONAL,notional=NOTIONAL,
                q_bps=q,pred_bps=pred))
    return scores,signals,fallback

def metric(values):
    n=len(values)
    if not n:return dict(n=0,coverage=None,width_bps=None,winkler_bps=None)
    return dict(n=n,coverage=round(sum(int(z[0]) for z in values)/n,6),
                width_bps=round(2*sum(z[1] for z in values)/n,6),
                winkler_bps=round(sum(z[2] for z in values)/n,6))

def deciles(rows):
    if not rows:return {'worst_decile_coverage':None,'coverage_by_decile':[]}
    ordered=sorted(rows,key=lambda z:z[3]);n=len(rows)
    groups=[[] for _ in range(10)]
    for i,z in enumerate(ordered):groups[min(9,10*i//n)].append(z)
    coverage=[round(sum(int(z[0]) for z in group)/len(group),6) if group else None
              for group in groups]
    return {'worst_decile_coverage':min(v for v in coverage if v is not None),
            'coverage_by_decile':coverage}

def portfolio(trades):
    result=[]
    for z in sorted(trades,key=lambda x:(x['entry_t'],x['symbol'],x['period'])):
        active=[x for x in result if x['period']==z['period'] and x['entry_t']<=z['entry_t']<=x['exit_t']]
        if len(active)<2 and not any(x['symbol']==z['symbol'] for x in active):result.append(z)
    return result

def economics(trades,days):
    return dict(trades=len(trades),trades_per_symbol_day=round(len(trades)/(days*6),6),
        net_by_cost_bps_usdt={str(b):round(sum(x['gross']-x['notional']*b/10000 for x in trades),6)
                              for b in COSTS},
        net20_usdt_day=round(sum(x['gross']-x['notional']*.002 for x in trades)/days,6))

def evaluate(data):
    gate()
    if len(data)!=full13.TOTAL_GROUPS or sum(map(len,data.values()))!=full13.TOTAL_ROWS:
        raise ValueError('BLOCKED_FULL13_SHAPE')
    metrics={k:[] for k in ('global','rolling','exponential','reservoir')}
    by_symbol={};by_period={};raw_signals=[];fallback=0
    for (period,symbol),bars in sorted(data.items()):
        samples,signals,count=group_compute(bars,period,symbol)
        fallback+=count;raw_signals.extend(signals)
        by_symbol.setdefault(symbol,{k:[] for k in metrics})
        by_period.setdefault(period,{k:[] for k in metrics})
        for k in metrics:
            metrics[k].extend(samples[k]);by_symbol[symbol][k].extend(samples[k])
            by_period[period][k].extend(samples[k])
    trades=portfolio(raw_signals)
    receipt={
       'schema':SCHEMA,'candidate':CANDIDATE,'issue':ISSUE,
       'prereg_sha256':PREREG_SHA,'status':'RESEARCH_ONLY_NOT_AUTHOR_IMPLEMENTATION',
       'engine':'FROZEN_RIDGE16_CAUSAL_H4_RETURN_PROXY',
       'method':'RESCP_INSPIRED_FIXED_RING_ESN_WEIGHTED_CONFORMAL',
       'horizon_bars':H,'warmup_bars':full13.WARMUP,
       'discovery_week_count':12,'aux_may_count':1,'bars_total':full13.TOTAL_ROWS,
       'calibration_min':MIN_CAL,'calibration_window':WIN,
       'forecast_count':len(metrics['reservoir']),
       'conformal':{k:metric(v) for k,v in metrics.items()},
       'volatility_deciles':{k:deciles(v) for k,v in metrics.items()},
       'by_symbol':{s:{k:metric(v) for k,v in d.items()} for s,d in by_symbol.items()},
       'by_period':{p:{k:metric(v) for k,v in d.items()} for p,d in by_period.items()},
       'fallback_low_effective_n':fallback,
       'economics_discovery_shadow':economics([z for z in trades if z['period']!=full13.AUX],84),
       'economics_may_aux_shadow':economics([z for z in trades if z['period']==full13.AUX],7),
       'execution_proxy':'NEXT_BAR_OPEN_H4_CLOSE_NO_MAKER_FILL','fees_modeled':True,
       'slippage_modeled':False,'funding_modeled':False,
       'independent_check2':'PENDING','real':'OFF','holdout':'SEALED','oos':False,
       'decision':'REJECT_FOR_LIVE_DISCOVERY_ONLY'}
    return receipt

def run_local(compressed,meta):
    data=full13.parse_full(compressed,meta)
    out=evaluate(data)
    out['independent_check2']=independent.verify_result(data,out)
    out['model_sha256']=sha(pathlib.Path(__file__).read_bytes())
    out['checker_sha256']=sha(pathlib.Path(independent.__file__).read_bytes())
    out['panel_gzip_sha256']=full13.PANEL_GZ_SHA
    out['receipt_sha256']=sha(canonical(out).encode())
    return out

def verify_receipt(o):
    if o.get('schema')!=SCHEMA or o.get('candidate')!=CANDIDATE or o.get('prereg_sha256')!=PREREG_SHA:
        raise ValueError('BLOCKED_RESCP_RECEIPT_IDENTITY')
    if o.get('real')!='OFF' or o.get('holdout')!='SEALED' or o.get('oos') is not False:
        raise ValueError('BLOCKED_RESCP_SAFETY')
    if o.get('independent_check2')!='PASS_RECOMPUTED_ALL_INTERVALS_AND_ECONOMICS':
        raise ValueError('BLOCKED_RESCP_CHECK2')
    if o.get('panel_gzip_sha256')!=full13.PANEL_GZ_SHA or o.get('bars_total')!=full13.TOTAL_ROWS:
        raise ValueError('BLOCKED_RESCP_DATA_PIN')
    for field,path in [('model_sha256',__file__),('checker_sha256',independent.__file__)]:
        if o.get(field)!=sha(pathlib.Path(path).read_bytes()):raise ValueError('BLOCKED_RESCP_CODE_PIN')
    core=dict(o);receipt=core.pop('receipt_sha256',None)
    if receipt!=sha(canonical(core).encode()):raise ValueError('BLOCKED_RESCP_RECEIPT_SHA')
    if o.get('decision')!='REJECT_FOR_LIVE_DISCOVERY_ONLY':raise ValueError('BLOCKED_RESCP_DECISION')
    return o

def run_remote(comp,meta):
    files={
        'rescp_shadow.py':pathlib.Path(__file__).read_bytes(),
        'rescp_check2.py':pathlib.Path(independent.__file__).read_bytes(),
        'full13_wave_colab.py':pathlib.Path(full13.__file__).read_bytes(),
        'hourly_wave_research.py':pathlib.Path(full13.primary.__file__).read_bytes(),
        'hourly_wave_check2.py':pathlib.Path(full13.independent.__file__).read_bytes(),
        'P816_panel.gz':comp,'manifest.json':canonical(meta).encode()}
    encoded={k:base64.b64encode(v).decode() for k,v in files.items()}
    script=("import base64,os,pathlib,subprocess,sys,tempfile\n"
       "if os.getenv('REAL','OFF')!='OFF' or os.getenv('HOLDOUT','SEALED')!='SEALED':raise SystemExit('BLOCKED_MODE')\n"
       "with tempfile.TemporaryDirectory(prefix='avrora-rescp-') as d:\n"
       " p=pathlib.Path(d)\n"
       f" files={repr(encoded)}\n"
       " for name,value in files.items():(p/name).write_bytes(base64.b64decode(value))\n"
       " env=os.environ.copy();env['AVRORA_ALLOW_RESCP_SHADOW']='YES'\n"
       " r=subprocess.run([sys.executable,'rescp_shadow.py','evaluate',str(p/'P816_panel.gz'),str(p/'manifest.json')],cwd=p,env=env,capture_output=True,text=True,timeout=1200)\n"
       " if r.returncode:raise SystemExit('BLOCKED_RESCP_REMOTE_EXEC')\n"
       f" if r.stdout.count({MARKER!r})!=1:raise SystemExit('BLOCKED_RESCP_REMOTE_MARKER')\n"
       " print(r.stdout.strip(),flush=True)\n")
    with tempfile.TemporaryDirectory(prefix='avrora-rescp-job-') as root:
        program=pathlib.Path(root)/'remote.py';program.write_text(script)
        logfile=pathlib.Path(root)/'remote.log'
        with logfile.open('wb') as f:
            proc=subprocess.run(['colab','--auth=adc','run',str(program)],stdout=f,
                stderr=subprocess.STDOUT,timeout=1500,
                env={**os.environ,'REAL':'OFF','HOLDOUT':'SEALED'})
        if proc.returncode:raise ValueError('BLOCKED_RESCP_COLAB_FAILED')
        rows=[line.split(MARKER,1)[1] for line in logfile.read_text('utf-8').splitlines() if MARKER in line]
        if len(rows)!=1:raise ValueError('BLOCKED_RESCP_REMOTE_RECEIPT')
        return json.loads(rows[0])

def main(args):
    gate()
    if len(args)==1 and args[0]=='run':
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):raise ValueError('BLOCKED_COLAB_AUTH_ABSENT')
        d=os.getenv('AVRORA_PRIVATE_CHECKOUT')
        if not d:raise ValueError('BLOCKED_PRIVATE_SOURCE_NOT_CHECKED_OUT')
        compressed,meta=full13.load_private(d)
        result=run_remote(compressed,meta)
        verify_receipt(result)
        pathlib.Path('rescp_shadow_receipt.json').write_text(canonical(result)+'\n')
        print('PASS_RESCP_LITE_SHADOW_CHECK2')
    elif len(args)==3 and args[0]=='evaluate':
        compressed=pathlib.Path(args[1]).read_bytes()
        meta=json.loads(pathlib.Path(args[2]).read_text('utf-8'))
        result=run_local(compressed,meta)
        verify_receipt(result)
        print(MARKER+canonical(result))
    elif len(args)==2 and args[0]=='verify':
        result=json.loads(pathlib.Path(args[1]).read_text('utf-8'))
        verify_receipt(result)
        print('PASS_RESCP_LITE_RECEIPT_SHA')
    else:raise ValueError('BLOCKED_RESCP_UNKNOWN_MODE')

if __name__=='__main__':
    try:main(sys.argv[1:])
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:
        message=str(error)
        print(message if message.startswith('BLOCKED_') else 'BLOCKED_RESCP_SHADOW',file=sys.stderr)
        raise SystemExit(1) from None
