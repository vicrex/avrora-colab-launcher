"""Causal OHLC structural SHORT discovery experiment with bounded $300 equity.

NOT orderbook/liquidity, maker-fill, live, new OOS, or real liquidation evidence.
Private source can only be loaded through the existing SHA-pinned FULL13 loader.
"""
from __future__ import annotations
import base64, hashlib, json, math, os, pathlib, subprocess, sys, tempfile
try:
    from tools import full13_wave_colab as pin
    from tools import structural_short_check2 as independent
except ImportError:
    import full13_wave_colab as pin
    import structural_short_check2 as independent

SCHEMA="AVRORA_STRUCTURAL_SHORT_FULL13_V1"
MARKER="AVRORA_STRUCTURAL_SHORT_VERIFIED="
CANDIDATES=("TREND_BREAK_SHORT_V1","BREAK_ONLY_SHORT_CONTROL_V1")
MANIFEST="research/structural_short_prereg_v1.json"
NOTIONAL_CAP=500.
START_EQUITY=300.
SYMBOLS=pin.SYMBOLS
MAX_DURATION=12

def canon(a):return json.dumps(a,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
def hashbytes(b):return hashlib.sha256(b).hexdigest()

def gate():
    pin.gate()
    if os.getenv("AVRORA_STRUCT_SHORT_ENABLED","")!="YES":
        raise ValueError("BLOCKED_STRUCTURAL_SHORT_NOT_AUTHORIZED")

def manifest_path():
    local=pathlib.Path(__file__).resolve().parent.parent/"research/structural_short_prereg_v1.json"
    if local.is_file():return local
    return pathlib.Path(__file__).resolve().parent/"structural_short_prereg_v1.json"

def load_manifest():
    path=manifest_path()
    raw=path.read_bytes()
    m=json.loads(raw)
    if (m.get("schema")!="AVRORA_SHORT_BREAKOUT_FULL13_PREREG_V1"
        or m.get("candidate_ids")!=list(CANDIDATES)
        or m.get("safety",{}).get("holdout")!="SEALED"
        or m.get("safety",{}).get("real")!="OFF"
        or m.get("safety",{}).get("oos") is not False):
        raise ValueError("BLOCKED_STRUCTURAL_PREREG_SCHEMA")
    expected={"support_lookback":12,"break_atr":0.10,"body_atr":0.35,
        "max_bar_range_atr":2.5,"ema_fast":20,"ema_slow":60,
        "ema_slope_lag":8,"signal_cooldown_bars":8,"atr_period":14,
        "stop_atr":1.25,"reward_r":1.8,"time_bars":12,
        "min_notional":25,"max_notional":500,"max_stop_risk_usdt":5,
        "start_equity_usdt":300,"min_equity_for_entry_usdt":20,
        "max_leverage":10,"max_active":2,"primary_roundtrip_cost_bps":20,
        "stress_roundtrip_cost_bps":[16,20,25,40]}
    if m.get("fixed_parameters")!=expected:
        raise ValueError("BLOCKED_STRUCTURAL_PREREG_PARAMETERS")
    return m,hashbytes(raw)

def true_atr(bars,t):
    values=[]
    for i in range(t-13,t+1):
        high,low=bars[i][2],bars[i][3]
        prev=bars[i-1][4]
        values.append(max(high-low,abs(high-prev),abs(low-prev)))
    return sum(values)/14.

def ema_series(bars,period):
    factor=2./(period+1)
    v=bars[0][4]
    out=[]
    for bar in bars:
        v=factor*bar[4]+(1-factor)*v
        out.append(v)
    return out

def find_events(bars,week,sym,params):
    fast=ema_series(bars,20);slow=ema_series(bars,60)
    last=-1000;events=[]
    for t in range(pin.WARMUP,len(bars)-MAX_DURATION-1):
        if t-last<8:continue
        op,high,low,close=bars[t][1:]
        atr=true_atr(bars,t)
        if atr<=0:continue
        support=min(row[3] for row in bars[t-12:t])
        if not (close<support-.10*atr and op-close>=.35*atr and
                high-low<=2.5*atr and close<op):
            continue
        trend=(fast[t]<slow[t] and slow[t]<slow[t-8] and close<fast[t])
        last=t
        events.append({"period":week,"symbol":sym,"signal_t":bars[t][0],
                       "signal_i":t,"entry_t":bars[t+1][0],
                       "atr":atr,"signal_high":high,"trend":trend,
                       "bars":bars})
    return events

def predict_fill(event,notional,params):
    b=event["bars"];t=event["signal_i"];entry_idx=t+1
    entry=b[entry_idx][1];stop=max(event["signal_high"],entry+1.25*event["atr"])
    risk_frac=(stop-entry)/entry
    if not 0<risk_frac<.1:raise ValueError("BLOCKED_STRUCTURAL_RISK_DISTANCE")
    target=entry-1.8*(stop-entry)
    end=entry_idx+12
    if end>=len(b):raise ValueError("BLOCKED_STRUCTURAL_INCOMPLETE_HORIZON")
    price=b[end][4];exit_i=end;why="TIME"
    for j in range(entry_idx,end+1):
        op,high,low=b[j][1:4]
        if op>=stop:
            price=op;exit_i=j;why="GAP_STOP";break
        if high>=stop:
            price=stop;exit_i=j;why="STOP_FIRST";break
        if low<=target:
            price=target;exit_i=j;why="TARGET";break
    gross=notional*(entry-price)/entry
    return {"period":event["period"],"symbol":event["symbol"],
       "signal_t":event["signal_t"],"entry_t":b[entry_idx][0],
       "exit_t":b[exit_i][0],"entry":entry,"exit":price,"stop":stop,
       "target":target,"reason":why,"notional":notional,
       "stop_risk_usdt":notional*risk_frac,
       "gross_usdt":gross,"net20_usdt":gross-notional*.002}

def proposals(data,m,mode):
    incoming=[]
    for (period,symbol),bars in sorted(data.items()):
        if mode=="TREND_BREAK_SHORT_V1":
            found=[x for x in find_events(bars,period,symbol,m["fixed_parameters"]) if x["trend"]]
        else:found=find_events(bars,period,symbol,m["fixed_parameters"])
        incoming.extend(found)
    def rank(x):
        ordinal=SYMBOLS.index(x["symbol"])
        rotated=(ordinal-(x["entry_t"]//900000//4)%len(SYMBOLS))%len(SYMBOLS)
        return x["entry_t"],rotated,x["period"]
    return sorted(incoming,key=rank)

def book(data,m,mode,aux=False):
    candidates=[x for x in proposals(data,m,mode) if (x["period"]==pin.AUX)==aux]
    equity=300.;highwater=300.;maxdd=0.;active=[];ledger=[]
    rejected={"concurrent":0,"duplicate_symbol":0,"insufficient_margin":0,
              "notional_too_small":0,"equity_floor":0}
    stopped=False
    def settle(bound):
        nonlocal equity,highwater,maxdd,active,stopped
        done=sorted((r for r in active if r["exit_t"]<bound),key=lambda x:(x["exit_t"],x["symbol"]))
        active=[r for r in active if r["exit_t"]>=bound]
        for r in done:
            equity+=r["net20_usdt"]
            highwater=max(highwater,equity)
            maxdd=max(maxdd,highwater-equity)
            if equity<=0:stopped=True
    for x in candidates:
        settle(x["entry_t"])
        if stopped or equity<=20:
            rejected["equity_floor"]+=1
            continue
        if len(active)>=2:
            rejected["concurrent"]+=1;continue
        if any(r["symbol"]==x["symbol"] for r in active):
            rejected["duplicate_symbol"]+=1;continue
        entry=x["bars"][x["signal_i"]+1][1]
        stop=max(x["signal_high"],entry+1.25*x["atr"])
        risk_fraction=(stop-entry)/entry
        if not 0<risk_fraction<.1:
            rejected["notional_too_small"]+=1;continue
        reserved=sum(r["notional"]/10. for r in active)
        available=max(0.,equity-reserved)
        notional=min(500.,5./risk_fraction,available*10.)
        if notional<25.:
            rejected["insufficient_margin" if available*10<25 else "notional_too_small"]+=1
            continue
        executed=predict_fill(x,notional,m["fixed_parameters"])
        ledger.append(executed);active.append(executed)
    settle(float("inf"))
    return {"mode":mode,"proposals":len(candidates),
            "ledger":ledger,"final_equity":equity,"max_drawdown_usdt":maxdd,
            "equity_depleted":stopped,"rejection_counts":rejected}

def summarise(portfolio,week_names,days):
    rows=portfolio["ledger"]
    gross=sum(t["gross_usdt"] for t in rows)
    net={str(c):round(sum(t["gross_usdt"]-t["notional"]*c/10000 for t in rows),6)
         for c in (16,20,25,40)}
    bysym={}
    for sym in SYMBOLS:
        subset=[t for t in rows if t["symbol"]==sym]
        bysym[sym]={"trades":len(subset),"trades_per_day":round(len(subset)/days,6),
            "net20_usdt":round(sum(r["net20_usdt"] for r in subset),6)}
    byweek={}
    for week in week_names:
        w=[t for t in rows if t["period"]==week]
        byweek[week]={"trades":len(w),"net20_usdt":round(sum(x["net20_usdt"] for x in w),6)}
    early=set(week_names[:6]) if len(week_names)==12 else set()
    late=set(week_names[6:]) if len(week_names)==12 else set()
    splits={}
    for label,subset in (("early6",early),("late6",late)):
        if subset:
            observed=[t for t in rows if t["period"] in subset]
            splits[label]={"trades":len(observed),
              "net20_usdt":round(sum(t["net20_usdt"] for t in observed),6)}
    return {"mode":portfolio["mode"],"proposals":portfolio["proposals"],
       "trades":len(rows),"gross_usdt":round(gross,6),"net_by_cost_bps_usdt":net,
       "net20_usdt_day":round(net["20"]/days,6),
       "trades_per_symbol_day":round(len(rows)/(days*6),6),
       "final_equity_20bps_usdt":round(portfolio["final_equity"],6),
       "max_realized_drawdown_usdt":round(portfolio["max_drawdown_usdt"],6),
       "equity_depleted_proxy":portfolio["equity_depleted"],
       "by_symbol":bysym,"by_week":byweek,"splits":splits,
       "rejection_counts":portfolio["rejection_counts"],
       "loss_gap_risk_possible":True}

def run_evaluation(data,m,manifest_sha):
    gate()
    if len(data)!=78 or sum(len(v) for v in data.values())!=69576:
        raise ValueError("BLOCKED_STRUCTURAL_FULL13_SHAPE")
    periods=sorted({w for w,sym in data if w!=pin.AUX})
    if len(periods)!=12:raise ValueError("BLOCKED_STRUCTURAL_WEEKS")
    result={}
    original_books={}
    for mode in CANDIDATES:
        allweeks=book(data,m,mode,False)
        may=book(data,m,mode,True)
        original_books[mode]={"discovery":allweeks,"may_aux":may}
        result[mode]={"discovery":summarise(allweeks,periods,84),
                      "may_aux":summarise(may,[pin.AUX],7)}
    receipt={"schema":SCHEMA,"status":"SHADOW_DISCOVERY_CHECK2",
        "manifest_sha256":manifest_sha,"candidate_ids":list(CANDIDATES),
        "source_panel_sha256":pin.PANEL_GZ_SHA,"periods":13,"bars":69576,
        "discovery_days":84,"may_aux_days":7,"results":result,
        "assumptions":{"equity_initial":300,"leverage_margin_proxy":10,
                       "stop_risk_cap_usdt":5,"trade_cost_bps_primary":20,
                       "stress_cost_bps":[16,20,25,40],
                       "market_entry_proxy":"NEXT_OPEN_NO_MAKER_FILL",
                       "exit_proxy":"STOP_FIRST_GAP_WORST_OPEN",
                       "liquidation_modeled":False,"unrealized_pnl_margin_modeled":False,
                       "slippage_modeled":False,"funding_modeled":False,
                       "orderbook_confirmed":False},
        "independent_check2":"PENDING","real":"OFF","holdout":"SEALED",
        "oos":False,"decision":"DIAGNOSTICS_ONLY_NEVER_LIVE"}
    return receipt,original_books

def verified(comp,meta):
    data=pin.parse_full(comp,meta)
    m,manifest_sha=load_manifest()
    obj,original_books=run_evaluation(data,m,manifest_sha)
    obj["independent_check2"]=independent.verify(data,m,obj,original_books)
    obj["primary_sha256"]=hashbytes(pathlib.Path(__file__).read_bytes())
    obj["checker_sha256"]=hashbytes(pathlib.Path(independent.__file__).read_bytes())
    obj["receipt_sha256"]=hashbytes(canon(obj).encode())
    return obj

def verify_receipt(obj):
    gate()
    m,sha=load_manifest()
    checks={"schema":SCHEMA,"manifest_sha256":sha,"source_panel_sha256":pin.PANEL_GZ_SHA,
            "periods":13,"bars":69576,"real":"OFF","holdout":"SEALED",
            "oos":False,"candidate_ids":list(CANDIDATES),
            "independent_check2":"PASS_ALL_SHORT_SIGNALS_FILLS_AND_EQUITY",
            "decision":"DIAGNOSTICS_ONLY_NEVER_LIVE"}
    for k,v in checks.items():
        if obj.get(k)!=v:raise ValueError("BLOCKED_STRUCTURAL_RECEIPT_"+k)
    for k,path in (("primary_sha256",__file__),("checker_sha256",independent.__file__)):
        if obj.get(k)!=hashbytes(pathlib.Path(path).read_bytes()):
            raise ValueError("BLOCKED_STRUCTURAL_CODE_SHA_"+k)
    receipt=dict(obj);digest=receipt.pop("receipt_sha256",None)
    if digest!=hashbytes(canon(receipt).encode()):raise ValueError("BLOCKED_STRUCTURAL_RECEIPT_SHA")
    return obj

def remote_run(compressed,meta):
    files={"structural_short.py":pathlib.Path(__file__).read_bytes(),
        "structural_short_check2.py":pathlib.Path(independent.__file__).read_bytes(),
        "full13_wave_colab.py":pathlib.Path(pin.__file__).read_bytes(),
        "hourly_wave_research.py":pathlib.Path(pin.primary.__file__).read_bytes(),
        "hourly_wave_check2.py":pathlib.Path(pin.independent.__file__).read_bytes(),
        "structural_short_prereg_v1.json":manifest_path().read_bytes(),
        "panel.gz":compressed,"meta.json":canon(meta).encode()}
    b={k:base64.b64encode(v).decode() for k,v in files.items()}
    script=("import base64,os,pathlib,subprocess,sys,tempfile\n"
       "with tempfile.TemporaryDirectory(prefix='avrora-short-') as d:\n"
       " p=pathlib.Path(d)\n"
       f" files={repr(b)}\n"
       " for name,v in files.items():(p/name).write_bytes(base64.b64decode(v))\n"
       " env=os.environ.copy();env['AVRORA_STRUCT_SHORT_ENABLED']='YES';env['REAL']='OFF';env['HOLDOUT']='SEALED'\n"
       " result=subprocess.run([sys.executable,'structural_short.py','evaluate',str(p/'panel.gz'),str(p/'meta.json')],cwd=p,env=env,capture_output=True,text=True,timeout=1200)\n"
       " if result.returncode:raise SystemExit('BLOCKED_STRUCTURAL_REMOTE_PROCESS')\n"
       f" if result.stdout.count({MARKER!r})!=1:raise SystemExit('BLOCKED_STRUCTURAL_REMOTE_MARKER')\n"
       " print(result.stdout.strip(),flush=True)\n")
    with tempfile.TemporaryDirectory(prefix="avrora-short-job-") as d:
        source=pathlib.Path(d)/"study.py";source.write_text(script)
        logfile=pathlib.Path(d)/"colab.log"
        with logfile.open("wb") as out:
            proc=subprocess.run(["colab","--auth=adc","run",str(source)],
                stdout=out,stderr=subprocess.STDOUT,timeout=1500,
                env={**os.environ,"REAL":"OFF","HOLDOUT":"SEALED"})
        if proc.returncode:raise ValueError("BLOCKED_STRUCTURAL_COLAB")
        hits=[line.split(MARKER,1)[1] for line in logfile.read_text("utf-8").splitlines() if MARKER in line]
        if len(hits)!=1:raise ValueError("BLOCKED_STRUCTURAL_COLAB_RECEIPT")
        return json.loads(hits[0])

def main(args):
    gate()
    if args==["run"]:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("BLOCKED_STRUCTURAL_COLAB_AUTH")
        where=os.getenv("AVRORA_PRIVATE_CHECKOUT")
        if not where:raise ValueError("BLOCKED_STRUCTURAL_MISSING_SOURCE")
        comp,meta=pin.load_private(where)
        obj=remote_run(comp,meta)
        verify_receipt(obj)
        pathlib.Path("structural_short_receipt.json").write_text(canon(obj)+"\n")
        print("PASS_STRUCTURAL_SHORT_FULL13_CHECK2")
    elif len(args)==3 and args[0]=="evaluate":
        obj=verified(pathlib.Path(args[1]).read_bytes(),json.loads(pathlib.Path(args[2]).read_text()))
        verify_receipt(obj);print(MARKER+canon(obj))
    elif len(args)==2 and args[0]=="verify":
        obj=json.loads(pathlib.Path(args[1]).read_text())
        verify_receipt(obj);print("PASS_STRUCTURAL_SHORT_RECEIPT_SHA")
    else:raise ValueError("BLOCKED_STRUCTURAL_MODE")

if __name__=="__main__":
    try:main(sys.argv[1:])
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:
        msg=str(error)
        print(msg if msg.startswith("BLOCKED_") else "BLOCKED_STRUCTURAL_SHORT",file=sys.stderr)
        raise SystemExit(1) from None
