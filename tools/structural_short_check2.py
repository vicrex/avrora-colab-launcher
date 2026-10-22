"""Independent recomputation of every structural SHORT event, fill and equity book.

Does NOT import/call the primary short strategy. Uses only read-only bar tuples.
"""
from __future__ import annotations
import math
try:
    from tools import full13_wave_colab as pinned
except ImportError:
    import full13_wave_colab as pinned

SYMS=("BTCUSDT","ETHUSDT","LINKUSDT","NEARUSDT","SOLUSDT","XRPUSDT")
IDS=("TREND_BREAK_SHORT_V1","BREAK_ONLY_SHORT_CONTROL_V1","TREND_RETEST_SHORT_V1","SQUEEZE_BREAK_SHORT_V1")

def derive(bars,week,symbol):
    a20=2/21
    a60=2/61
    fast=bars[0][4];slow=bars[0][4]
    fasts=[];slows=[]
    for bar in bars:
        fast=fast*(1-a20)+bar[4]*a20
        slow=slow*(1-a60)+bar[4]*a60
        fasts.append(fast);slows.append(slow)
    result=[];last=-999
    for i in range(220,len(bars)-13):
        if i-last<8:continue
        op,hi,lo,cl=bars[i][1:]
        tr=0.
        for k in range(i-13,i+1):
            prev=bars[k-1][4]
            h=bars[k][2];l=bars[k][3]
            tr+=max(h-l,abs(h-prev),abs(l-prev))
        atr=tr/14
        if atr<=0:continue
        recent=min(bars[k][3] for k in range(i-12,i))
        if cl >= recent-.1*atr or op-cl < .35*atr or hi-lo>2.5*atr or cl>=op:
            continue
        trend=fasts[i]<slows[i] and slows[i]<slows[i-8] and cl<fasts[i]
        result.append({"period":week,"symbol":symbol,"signal_t":bars[i][0],
            "signal_i":i,"entry_t":bars[i+1][0],"signal_high":hi,"atr":atr,
            "trend":trend,"bars":bars})
        last=i
    return result

def derive_retests(bars,week,symbol):
    """Independent complete-bar confirmation, not calling primary events."""
    result=[]
    for old in derive(bars,week,symbol):
        if not old["trend"]:
            continue
        t=old["signal_i"]
        broken=min(bars[j][3] for j in range(t-12,t))
        old_atr=old["atr"]
        # Retest is known only at the end of its own candle.
        for k in range(t+1,min(t+5,len(bars)-13)):
            open_k,high_k,low_k,close_k=bars[k][1:]
            if (high_k>=broken-0.15*old_atr
                    and close_k<broken and open_k-close_k>=0.15*old_atr
                    and close_k<open_k):
                tr_sum=0.0
                for q in range(k-13,k+1):
                    prev=bars[q-1][4]
                    hh,ll=bars[q][2],bars[q][3]
                    tr_sum+=max(hh-ll,abs(hh-prev),abs(ll-prev))
                result.append(dict(old,signal_t=bars[k][0],signal_i=k,
                                   entry_t=bars[k+1][0],signal_high=high_k,
                                   atr=tr_sum/14.0))
                break
    return result

def derive_squeezes(bars,week,symbol):
    """Independent OHLC contraction-break reconstruction with no primary imports."""
    a20=2/21
    a60=2/61
    f=bars[0][4]
    s=bars[0][4]
    e20=[]
    e60=[]
    for bar in bars:
        f=bar[4]*a20+f*(1-a20)
        s=bar[4]*a60+s*(1-a60)
        e20.append(f)
        e60.append(s)
    found=[]
    previous_event=-1000
    for i in range(220,len(bars)-13):
        if i-previous_event<8:
            continue
        recent=bars[i-8:i]
        old=bars[i-16:i-8]
        width=max(c[2] for c in recent)-min(c[3] for c in recent)
        oldwidth=max(c[2] for c in old)-min(c[3] for c in old)
        pre_tr=0.0
        for k in range(i-14,i):
            hh,ll=bars[k][2],bars[k][3]
            prevclose=bars[k-1][4]
            pre_tr+=max(hh-ll,abs(hh-prevclose),abs(ll-prevclose))
        pre_atr=pre_tr/14.0
        if not(oldwidth>0 and pre_atr>0 and width<=0.70*oldwidth
               and width<=3.0*pre_atr):
            continue
        vol=0.0
        for k in range(i-13,i+1):
            hh,ll=bars[k][2],bars[k][3]
            prevclose=bars[k-1][4]
            vol+=max(hh-ll,abs(hh-prevclose),abs(ll-prevclose))
        atr=vol/14.0
        op,hi,lo,cl=bars[i][1:]
        if (atr<=0 or cl>=min(c[3] for c in recent)-0.10*atr
                or op-cl<0.35*atr or cl>=op or hi-lo>2.5*atr):
            continue
        if not(e20[i]<e60[i] and e60[i]<e60[i-8] and cl<e20[i]):
            continue
        previous_event=i
        found.append({"period":week,"symbol":symbol,"signal_t":bars[i][0],
                      "signal_i":i,"entry_t":bars[i+1][0],
                      "atr":atr,"signal_high":hi,"trend":True,"bars":bars})
    return found


def sequence(data,mode):
    rows=[]
    for (week,sym),bars in sorted(data.items()):
        if mode==IDS[3]:
            rows.extend(derive_squeezes(bars,week,sym))
        elif mode==IDS[2]:
            rows.extend(derive_retests(bars,week,sym))
        elif mode==IDS[1]:
            rows.extend(derive(bars,week,sym))
        elif mode==IDS[0]:
            rows.extend(e for e in derive(bars,week,sym) if e["trend"])
        else:
            raise ValueError("BLOCKED_SHORT_UNKNOWN_MODE")
    def selector(x):
        slot=(SYMS.index(x["symbol"])-(x["entry_t"]//(4*900000))%6)%6
        return x["entry_t"],slot,x["period"]
    rows.sort(key=selector)
    return rows

def fill(e,amount):
    bars=e["bars"]
    entry_idx=e["signal_i"]+1
    entry=bars[entry_idx][1]
    stop=max(e["signal_high"],entry+1.25*e["atr"])
    goal=entry-1.8*(stop-entry)
    chosen=bars[entry_idx+12][4]
    exit_at=entry_idx+12
    cause="TIME"
    for k in range(entry_idx,entry_idx+13):
        op,high,low=bars[k][1:4]
        if op>=stop:
            chosen=op;exit_at=k;cause="GAP_STOP";break
        if high>=stop:
            chosen=stop;exit_at=k;cause="STOP_FIRST";break
        if low<=goal:
            chosen=goal;exit_at=k;cause="TARGET";break
    profit=amount*(entry-chosen)/entry
    return {"period":e["period"],"symbol":e["symbol"],
        "signal_t":e["signal_t"],"entry_t":bars[entry_idx][0],
        "exit_t":bars[exit_at][0],"entry":entry,"exit":chosen,
        "stop":stop,"target":goal,"reason":cause,"notional":amount,
        "stop_risk_usdt":amount*(stop-entry)/entry,
        "gross_usdt":profit,"net20_usdt":profit-amount*.002}

def simulate(data,mode,aux):
    events=[e for e in sequence(data,mode) if (e["period"]=="2026-05-01")==aux]
    cash=300.;peak=300.;dd=0.;depleted=False
    opened={};ledger=[]
    refused={"concurrent":0,"duplicate_symbol":0,"insufficient_margin":0,
             "notional_too_small":0,"equity_floor":0}
    def closing(now):
        nonlocal cash,peak,dd,depleted,opened
        done=sorted([r for r in opened.values() if r["exit_t"]<now],
                    key=lambda x:(x["exit_t"],x["symbol"]))
        for r in done:
            cash+=r["net20_usdt"]
            peak=max(peak,cash)
            dd=max(dd,peak-cash)
            if cash<=0:depleted=True
        opened={s:r for s,r in opened.items() if r["exit_t"]>=now}
    for e in events:
        closing(e["entry_t"])
        if depleted or cash<=20:
            refused["equity_floor"]+=1;continue
        if len(opened)>=2:
            refused["concurrent"]+=1;continue
        sym=e["symbol"]
        if sym in opened:
            refused["duplicate_symbol"]+=1;continue
        entry=e["bars"][e["signal_i"]+1][1]
        stop=max(e["signal_high"],entry+1.25*e["atr"])
        fraction=(stop-entry)/entry
        if fraction<=0 or fraction>=.1:
            refused["notional_too_small"]+=1;continue
        collateral=cash-sum(x["notional"]/10 for x in opened.values())
        amount=min(500.,5/fraction,max(0,collateral)*10)
        if amount<25:
            if collateral*10<25:refused["insufficient_margin"]+=1
            else:refused["notional_too_small"]+=1
            continue
        r=fill(e,amount)
        ledger.append(r)
        opened[sym]=r
    closing(float("inf"))
    return {"mode":mode,"proposals":len(events),"ledger":ledger,
       "final_equity":cash,"max_drawdown_usdt":dd,
       "equity_depleted":depleted,"rejection_counts":refused}

def summarise(p,periods,days):
    ledger=p["ledger"]
    cost={}
    for bp in (16,20,25,40):
        cost[str(bp)]=round(sum(t["gross_usdt"]-bp*t["notional"]/1e4 for t in ledger),6)
    symstats={}
    for sym in SYMS:
        ts=[t for t in ledger if t["symbol"]==sym]
        symstats[sym]={"trades":len(ts),"trades_per_day":round(len(ts)/days,6),
                        "net20_usdt":round(sum(x["net20_usdt"] for x in ts),6)}
    weekstats={}
    for week in periods:
        rows=[t for t in ledger if t["period"]==week]
        weekstats[week]={"trades":len(rows),
                         "net20_usdt":round(sum(t["net20_usdt"] for t in rows),6)}
    cut={}
    if len(periods)==12:
        for label,scope in (("early6",set(periods[:6])),("late6",set(periods[6:]))):
            rows=[t for t in ledger if t["period"] in scope]
            cut[label]={"trades":len(rows),
                        "net20_usdt":round(sum(t["net20_usdt"] for t in rows),6)}
    return {"mode":p["mode"],"proposals":p["proposals"],"trades":len(ledger),
      "gross_usdt":round(sum(t["gross_usdt"] for t in ledger),6),
      "net_by_cost_bps_usdt":cost,"net20_usdt_day":round(cost["20"]/days,6),
      "trades_per_symbol_day":round(len(ledger)/(days*6),6),
      "final_equity_20bps_usdt":round(p["final_equity"],6),
      "max_realized_drawdown_usdt":round(p["max_drawdown_usdt"],6),
      "equity_depleted_proxy":p["equity_depleted"],
      "by_symbol":symstats,"by_week":weekstats,"splits":cut,
      "rejection_counts":p["rejection_counts"],"loss_gap_risk_possible":True}

def assert_equal(a,b,where=""):
    if isinstance(a,dict):
        if not isinstance(b,dict) or set(a)!=set(b):
            raise ValueError("BLOCKED_SHORT_CHECK2_KEYS_"+where)
        for k,v in a.items():assert_equal(v,b[k],where+"_"+str(k))
    elif isinstance(a,list):
        if not isinstance(b,list) or len(a)!=len(b):
            raise ValueError("BLOCKED_SHORT_CHECK2_LENGTH_"+where)
        for i,(x,y) in enumerate(zip(a,b)):assert_equal(x,y,where+"_"+str(i))
    elif isinstance(a,bool) or isinstance(b,bool):
        if a is not b:raise ValueError("BLOCKED_SHORT_CHECK2_BOOLEAN_"+where)
    elif isinstance(a,(float,int)) and isinstance(b,(float,int)):
        if not (math.isfinite(a) and math.isfinite(b)) or abs(a-b)>1e-6*max(1.,abs(a),abs(b)):
            raise ValueError("BLOCKED_SHORT_CHECK2_VALUE_"+where)
    elif a!=b:
        raise ValueError("BLOCKED_SHORT_CHECK2_MISMATCH_"+where)

def verify(panel,manifest,receipt,primary_books):
    if len(panel)!=78 or set(receipt["candidate_ids"])!=set(IDS):
        raise ValueError("BLOCKED_SHORT_CHECK2_SCOPE")
    weeks=sorted({week for week,sym in panel if week!="2026-05-01"})
    if len(weeks)!=12:raise ValueError("BLOCKED_SHORT_CHECK2_WEEKS")
    for mode in IDS:
        for label,aux,periods,days in (
            ("discovery",False,weeks,84),
            ("may_aux",True,["2026-05-01"],7)):
            ours=simulate(panel,mode,aux)
            theirs=primary_books[mode][label]
            # Compare complete trade ledger in memory, not merely aggregated PnL.
            assert_equal(ours,theirs,mode+"_"+label+"_all_trades")
            expected=summarise(ours,periods,days)
            assert_equal(expected,receipt["results"][mode][label],mode+"_"+label+"_summary")
    return "PASS_ALL_SHORT_SIGNALS_FILLS_AND_EQUITY"
