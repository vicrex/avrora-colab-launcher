"""Independent H4 directional CHECK2, no use of primary audit selectors/ledger."""
from __future__ import annotations
import math

try:from tools import rescp_check2 as frozen
except ImportError:import rescp_check2 as frozen

MODES=("RIDGE_SIGN_0","RIDGE_SIGN_10","RIDGE_SIGN_20","MOM4_SIGN","REVERSE_MOM4")
COSTS=(16,20,25,40)
H=4
TRADE_SIZE=500.

def direction(x):
    if x>0:return 1
    if x<0:return -1
    return 0

def group(bars,period,symbol):
    model=frozen.train(bars)
    output=[]
    for i in range(220,len(bars)-H):
        history=frozen.feat(bars,i)
        forecast=sum(model[j]*history[j] for j in range(len(model)))
        realized=10000*math.log(bars[i+H][4]/bars[i][4])
        trend=10000*math.log(bars[i][4]/bars[i-H][4])
        output.append(dict(period=period,symbol=symbol,t=bars[i][0],
            entry_t=bars[i+1][0],exit_t=bars[i+H][0],pred=forecast,
            actual=realized,momentum=trend,entry=bars[i+1][1],exit=bars[i+H][4]))
    return output

def proposals(rows,mode):
    candidates=[]
    for x in rows:
        pred=x["pred"]
        if mode=="RIDGE_SIGN_0":side=direction(pred)
        elif mode=="RIDGE_SIGN_10":side=direction(pred) if abs(pred)>=10 else 0
        elif mode=="RIDGE_SIGN_20":side=direction(pred) if abs(pred)>=20 else 0
        elif mode=="MOM4_SIGN":side=direction(x["momentum"])
        elif mode=="REVERSE_MOM4":side=-direction(x["momentum"])
        else:raise ValueError("BLOCKED_CHECK2_INVALID_METHOD")
        if not side:continue
        candidates.append((x["entry_t"],x["symbol"],x["period"],x["exit_t"],
                           side,TRADE_SIZE*side*(x["exit"]/x["entry"]-1),
                           x["entry"],x["exit"]))
    candidates.sort(key=lambda r:r[:3])
    retained=[]
    for row in candidates:
        active=[old for old in retained if old[2]==row[2] and old[0]<=row[0]<=old[3]]
        if len(active)<2 and all(old[1]!=row[1] for old in active):retained.append(row)
    return len(candidates),retained

def aggregate(rows,days):
    n=len(rows)
    baseline={
        "predictions":n,
        "ridge_sign_accuracy":round(sum(direction(x["pred"])==direction(x["actual"]) for x in rows)/n,6) if n else None,
        "momentum_sign_accuracy":round(sum(direction(x["momentum"])==direction(x["actual"]) for x in rows)/n,6) if n else None,
        "positive_label_rate":round(sum(x["actual"]>0 for x in rows)/n,6) if n else None,
        "ridge_mae_bps":round(sum(abs(x["pred"]-x["actual"]) for x in rows)/n,6) if n else None,
        "zero_mae_bps":round(sum(abs(x["actual"]) for x in rows)/n,6) if n else None}
    perf={}
    for mode in MODES:
        offered,ledger=proposals(rows,mode)
        pnl=sum(z[5] for z in ledger)
        net={str(bp):round(pnl-TRADE_SIZE*bp/10000*len(ledger),6) for bp in COSTS}
        perf[mode]={
            "signals_proposed":offered,
            "trades":len(ledger),
            "trades_per_symbol_day":round(len(ledger)/(days*6),6),
            "gross_usdt":round(pnl,6),
            "net_by_cost_bps_usdt":net,
            "net20_usdt_day":round(net["20"]/days,6),
            "hit_rate_after_entry":round(sum(direction(z[4]*(z[7]/z[6]-1))>0 for z in ledger)/len(ledger),6) if ledger else None}
    return {"forecasting":baseline,"methods":perf}

def assert_near(x,y,path=""):
    if isinstance(x,dict):
        if not isinstance(y,dict) or set(x)!=set(y):
            raise ValueError("BLOCKED_H4_CHECK2_FIELDS_"+path)
        for k,v in x.items():assert_near(v,y[k],path+"_"+k)
    elif isinstance(x,list):
        if not isinstance(y,list) or len(x)!=len(y):
            raise ValueError("BLOCKED_H4_CHECK2_ARRAY_"+path)
        for i,(a,b) in enumerate(zip(x,y)):assert_near(a,b,path+"_"+str(i))
    elif isinstance(x,(float,int)) and not isinstance(x,bool):
        if not isinstance(y,(float,int)) or abs(x-y)>1e-6*max(1.,abs(x),abs(y)):
            raise ValueError("BLOCKED_H4_CHECK2_VALUE_"+path)
    elif x!=y:
        raise ValueError("BLOCKED_H4_CHECK2_MISMATCH_"+path)

def verify(panel,meta,receipt):
    if len(panel)!=78:raise ValueError("BLOCKED_H4_CHECK2_PANEL")
    periods=meta["discovery_week_starts"]
    if len(periods)!=12 or periods!=sorted(periods):
        raise ValueError("BLOCKED_H4_CHECK2_PERIODS")
    observations=[]
    for (period,symbol),bars in sorted(panel.items()):
        observations+=group(bars,period,symbol)
    groups={
        "early6_discovery":set(periods[:6]),
        "late6_discovery":set(periods[6:]),
        "full12_discovery":set(periods),
        "may_aux_only":{meta["aux_may_week_start"]}}
    for key,dates in groups.items():
        rows=[x for x in observations if x["period"] in dates]
        expected=aggregate(rows,days=len(dates)*7)
        assert_near(expected,receipt["split_results"][key],key)
    return "PASS_INDEPENDENT_DIRECTION_AND_LEDGER_CHECK2"
