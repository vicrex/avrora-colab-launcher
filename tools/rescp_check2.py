"""Independent CHECK2: recompute frozen fit, ESN weights, quantiles, shadow ledger.

Never calls primary signals or primary metric functions; private candles stay private.
"""
import math,random
H=4;L=16;MIN=96;WIN=128;N=12;WARMUP=220;NOTIONAL=500.
AUX='2026-05-01'

def feat(bars,t):
    return [1.]+[1e4*math.log(bars[t+1-k][4]/bars[t-k][4]) for k in range(1,L+1)]

def train(bars):
    pairs=[(feat(bars,t),1e4*math.log(bars[t+H][4]/bars[t][4])) for t in range(L,WARMUP-H)]
    size=L+1
    a=[[sum(item[0][i]*item[0][j] for item in pairs)
       +(.01 if i==j==0 else (50. if i==j else 0.)) for j in range(size)]
       for i in range(size)]
    rhs=[sum(item[0][i]*item[1] for item in pairs) for i in range(size)]
    # Independent triangular elimination, rather than primary Gauss-Jordan.
    for i in range(size):
        pivot=max(range(i,size),key=lambda p:abs(a[p][i]))
        a[pivot],a[i]=a[i],a[pivot];rhs[pivot],rhs[i]=rhs[i],rhs[pivot]
        if abs(a[i][i])<1e-10:raise ValueError('BLOCKED_CHECK2_RIDGE_SINGULAR')
        for row in range(i+1,size):
            factor=a[row][i]/a[i][i]
            for col in range(i,size):a[row][col]-=factor*a[i][col]
            rhs[row]-=factor*rhs[i]
    x=[0.]*size
    for i in range(size-1,-1,-1):
        x[i]=(rhs[i]-sum(a[i][j]*x[j] for j in range(i+1,size)))/a[i][i]
    return x

def quant(values):
    n=len(values)
    return sorted(values)[min(n,math.ceil((n+1)*.9))-1]

def wquant(values,weights):
    needed=sum(weights)*.9;s=0.
    for v,w in sorted(zip(values,weights)):
        s+=w
        if s>=needed:return v
    return max(values)

def group(bars,period,symbol):
    coef=train(bars)
    rng=random.Random(15543)
    inp=[rng.uniform(-.18,.18) for _ in range(N)]
    bias=[rng.uniform(-.035,.035) for _ in range(N)]
    state=[0.]*N;preds={};states={};cal=[]
    values={k:[] for k in ('global','rolling','exponential','reservoir')}
    trades=[];fallback=0
    for t in range(WARMUP,len(bars)-H):
        u=t-H
        if u in preds:
            actual=1e4*math.log(bars[t][4]/bars[u][4])
            resid=actual-preds[u]
            cal.append((u,abs(resid),states[u]))
            x=max(-6.,min(6.,resid/100.))
            state=[.35*state[i]+.65*math.tanh(inp[i]*x+.58*state[(i-1)%N]+bias[i]) for i in range(N)]
        current=tuple(state)
        forecast=sum(a*b for a,b in zip(feat(bars,t),coef))
        preds[t]=forecast;states[t]=current
        if len(cal)<MIN:continue
        if any(origin+H>t for origin,*_ in cal):raise ValueError('BLOCKED_CHECK2_LABEL_MATURITY')
        recent=cal[-WIN:]
        glob=quant([score for _,score,_ in cal])
        rolling=quant([score for _,score,_ in recent])
        exp=wquant([score for _,score,_ in recent],[.98**(len(recent)-1-i) for i in range(len(recent))])
        logw=[]
        for origin,score,old in recent:
            dot=sum(a*b for a,b in zip(old,current))
            norm=sum(a*a for a in old)*sum(b*b for b in current)
            cs=dot/math.sqrt(norm) if norm>1e-24 else 0.
            logw.append(cs/.35-math.log1p((t-origin)/64.))
        top=max(logw)
        weights=[math.exp(x-top) for x in logw]
        effective=sum(weights)**2/sum(w*w for w in weights)
        if effective<32:fallback+=1
        local=wquant([z[1] for z in recent],weights) if effective>=32 else rolling
        error=abs(1e4*math.log(bars[t+H][4]/bars[t][4])-forecast)
        returns=[1e4*math.log(bars[i][4]/bars[i-1][4]) for i in range(t-23,t+1)]
        avg=sum(returns)/24
        vola=math.sqrt(sum((v-avg)**2 for v in returns)/24)
        for key,radius in zip(values.keys(),(glob,rolling,exp,local)):
            values[key].append((error<=radius,radius,2*radius+20*max(0.,error-radius),vola))
        if abs(forecast)>local and local<120:
            side=1 if forecast>0 else -1
            entry=bars[t+1][1];exit_price=bars[t+H][4]
            trades.append(dict(period=period,symbol=symbol,
                signal_t=bars[t][0],entry_t=bars[t+1][0],exit_t=bars[t+H][0],
                side=side,entry=entry,exit=exit_price,
                gross=side*(exit_price/entry-1)*NOTIONAL,notional=NOTIONAL,
                q_bps=local,pred_bps=forecast))
    return values,trades,fallback

def metric(rows):
    n=len(rows)
    return dict(n=n,
        coverage=round(sum(int(row[0]) for row in rows)/n,6) if n else None,
        width_bps=round(2*sum(row[1] for row in rows)/n,6) if n else None,
        winkler_bps=round(sum(row[2] for row in rows)/n,6) if n else None)

def deciles(rows):
    if not rows:return {'worst_decile_coverage':None,'coverage_by_decile':[]}
    ordered=sorted(rows,key=lambda z:z[3])
    groups=[[] for _ in range(10)];n=len(rows)
    for i,z in enumerate(ordered):groups[min(9,10*i//n)].append(z)
    cover=[round(sum(int(z[0]) for z in grp)/len(grp),6) if grp else None for grp in groups]
    return {'worst_decile_coverage':min(v for v in cover if v is not None),
            'coverage_by_decile':cover}

def portfolio(trades):
    out=[]
    for row in sorted(trades,key=lambda r:(r['entry_t'],r['symbol'],r['period'])):
        concurrent=[x for x in out if x['period']==row['period'] and x['entry_t']<=row['entry_t']<=x['exit_t']]
        if len(concurrent)<2 and not any(x['symbol']==row['symbol'] for x in concurrent):out.append(row)
    return out

def economics(rows,days):
    return dict(trades=len(rows),trades_per_symbol_day=round(len(rows)/(days*6),6),
        net_by_cost_bps_usdt={str(b):round(sum(x['gross']-x['notional']*b/10000 for x in rows),6)
                              for b in (16,20,25,40)},
        net20_usdt_day=round(sum(x['gross']-x['notional']*.002 for x in rows)/days,6))

def compare(a,b,path='receipt'):
    if isinstance(a,dict):
        if not isinstance(b,dict) or a.keys()!=b.keys():raise ValueError('BLOCKED_CHECK2_KEYS_'+path)
        for key,v in a.items():compare(v,b[key],path+'.'+str(key))
    elif isinstance(a,(list,tuple)):
        if not isinstance(b,(list,tuple)) or len(a)!=len(b):raise ValueError('BLOCKED_CHECK2_LENGTH_'+path)
        for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'.'+str(i))
    elif isinstance(a,(float,int)) and not isinstance(a,bool):
        if not isinstance(b,(float,int)) or abs(a-b)>1e-4*max(1.,abs(a),abs(b)):
            raise ValueError('BLOCKED_CHECK2_VALUE_'+path)
    elif a!=b:raise ValueError('BLOCKED_CHECK2_VALUE_'+path)

def verify_result(data,receipt):
    allscores={k:[] for k in ('global','rolling','exponential','reservoir')}
    by_symbol={};by_period={};signals=[];fallback=0
    for (period,symbol),bars in sorted(data.items()):
        samples,tt,count=group(bars,period,symbol)
        signals.extend(tt);fallback+=count
        by_symbol.setdefault(symbol,{k:[] for k in allscores})
        by_period.setdefault(period,{k:[] for k in allscores})
        for k in allscores:
            allscores[k].extend(samples[k])
            by_symbol[symbol][k].extend(samples[k])
            by_period[period][k].extend(samples[k])
    accepted=portfolio(signals)
    expected={
        'forecast_count':len(allscores['reservoir']),
        'fallback_low_effective_n':fallback,
        'conformal':{k:metric(v) for k,v in allscores.items()},
        'volatility_deciles':{k:deciles(v) for k,v in allscores.items()},
        'by_symbol':{s:{k:metric(v) for k,v in d.items()} for s,d in by_symbol.items()},
        'by_period':{p:{k:metric(v) for k,v in d.items()} for p,d in by_period.items()},
        'economics_discovery_shadow':economics([z for z in accepted if z['period']!=AUX],84),
        'economics_may_aux_shadow':economics([z for z in accepted if z['period']==AUX],7)}
    for key,val in expected.items():compare(val,receipt.get(key),key)
    return 'PASS_RECOMPUTED_ALL_INTERVALS_AND_ECONOMICS'
