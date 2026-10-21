"""Predeclared causal H4 forecast-edge audit on pinned 13-period discovery data.

Frozen before reading market outcomes; offline and aggregate-only.
The 12 discovery weeks are ALREADY USED, not independent OOS.
No trade execution or maker fills.
"""
from __future__ import annotations

import base64, hashlib, json, math, os, pathlib, subprocess, sys, tempfile
try:
    from tools import full13_wave_colab as data_source
    from tools import rescp_shadow as ridge
    from tools import h4_directional_check2 as checker
except ImportError:
    import full13_wave_colab as data_source
    import rescp_shadow as ridge
    import h4_directional_check2 as checker

SCHEMA = "AVRORA_H4_DIRECTIONAL_EDGE_AUDIT_V1"
CANDIDATE = "FROZEN_RIDGE16_H4_DIRECTIONAL_AUDIT_01"
MARKER = "AVRORA_H4_AUDIT_VERIFIED="
MODES = ("RIDGE_SIGN_0", "RIDGE_SIGN_10", "RIDGE_SIGN_20", "MOM4_SIGN", "REVERSE_MOM4")
STRESS_BPS = (16, 20, 25, 40)
H = 4
NOTIONAL = 500.0

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False)

def hashbytes(x):
    return hashlib.sha256(x).hexdigest()

def guard():
    data_source.gate()
    if os.getenv("AVRORA_H4_AUDIT_ALLOWED", "") != "YES":
        raise ValueError("BLOCKED_H4_AUDIT_NOT_AUTHORIZED")

def sign(x):
    return (x>0)-(x<0)

def group_events(bars,period,symbol):
    coeff=ridge.frozen_forecaster(bars)
    events=[]
    for t in range(data_source.WARMUP,len(bars)-H):
        prediction=sum(a*b for a,b in zip(coeff,ridge.features(bars,t)))
        actual=1e4*math.log(bars[t+H][4]/bars[t][4])
        momentum=1e4*math.log(bars[t][4]/bars[t-H][4])
        row={"period":period,"symbol":symbol,"t":bars[t][0],
             "entry_t":bars[t+1][0],"exit_t":bars[t+H][0],
             "pred":prediction,"actual":actual,"momentum":momentum,
             "entry":bars[t+1][1],"exit":bars[t+H][4]}
        events.append(row)
    return events

def side_for(event,mode):
    pred=event["pred"]
    if mode=="RIDGE_SIGN_0":return sign(pred)
    if mode=="RIDGE_SIGN_10":return sign(pred) if abs(pred)>=10 else 0
    if mode=="RIDGE_SIGN_20":return sign(pred) if abs(pred)>=20 else 0
    if mode=="MOM4_SIGN":return sign(event["momentum"])
    if mode=="REVERSE_MOM4":return -sign(event["momentum"])
    raise ValueError("BLOCKED_UNREVIEWED_GATE")

def portfolio(events,mode):
    proposals=[]
    for row in events:
        side=side_for(row,mode)
        if not side:continue
        proposals.append({**row,"side":side,"gross":NOTIONAL*side*(row["exit"]/row["entry"]-1)})
    proposals.sort(key=lambda x:(x["entry_t"],x["symbol"],x["period"]))
    retained=[]
    for x in proposals:
        active=[p for p in retained if p["period"]==x["period"] and p["entry_t"]<=x["entry_t"]<=p["exit_t"]]
        if len(active)<2 and not any(p["symbol"]==x["symbol"] for p in active):
            retained.append(x)
    return len(proposals),retained

def summarize(events,days):
    n=len(events)
    forecasting={
        "predictions":n,
        "ridge_sign_accuracy":round(sum(sign(e["pred"])==sign(e["actual"]) for e in events)/n,6) if n else None,
        "momentum_sign_accuracy":round(sum(sign(e["momentum"])==sign(e["actual"]) for e in events)/n,6) if n else None,
        "positive_label_rate":round(sum(e["actual"]>0 for e in events)/n,6) if n else None,
        "ridge_mae_bps":round(sum(abs(e["pred"]-e["actual"]) for e in events)/n,6) if n else None,
        "zero_mae_bps":round(sum(abs(e["actual"]) for e in events)/n,6) if n else None,
    }
    methods={}
    for mode in MODES:
        proposed,trades=portfolio(events,mode)
        gross=sum(x["gross"] for x in trades)
        count=len(trades)
        costs={str(k):round(gross-NOTIONAL*k/10000*count,6) for k in STRESS_BPS}
        methods[mode]={
            "signals_proposed":proposed,"trades":count,
            "trades_per_symbol_day":round(count/(days*6),6),
            "gross_usdt":round(gross,6),
            "net_by_cost_bps_usdt":costs,
            "net20_usdt_day":round(costs["20"]/days,6),
            "hit_rate_after_entry":round(sum(sign(x["side"]*(x["exit"]/x["entry"]-1))>0 for x in trades)/count,6) if count else None,
        }
    return {"forecasting":forecasting,"methods":methods}

def execute(data,meta):
    guard()
    if len(data)!=data_source.TOTAL_GROUPS or sum(map(len,data.values()))!=data_source.TOTAL_ROWS:
        raise ValueError("BLOCKED_H4_INCOMPLETE_PANEL")
    weeks=meta["discovery_week_starts"]
    if len(weeks)!=12 or weeks!=sorted(weeks) or meta["aux_may_week_start"]!=data_source.AUX:
        raise ValueError("BLOCKED_H4_DISCOVERY_SPLIT")
    all_events=[]
    for (period,symbol),bars in sorted(data.items()):
        all_events.extend(group_events(bars,period,symbol))
    splits={
      "early6_discovery":set(weeks[:6]),
      "late6_discovery":set(weeks[6:]),
      "full12_discovery":set(weeks),
      "may_aux_only":{data_source.AUX},
    }
    output={name:summarize([r for r in all_events if r["period"] in periods],
                           7*len(periods))
            for name,periods in splits.items()}
    return {
        "schema":SCHEMA,"candidate":CANDIDATE,
        "status":"DISCOVERY_AUDIT_NOT_OOS",
        "source":"PINNED_P816_FULL13",
        "panel_gzip_sha256":data_source.PANEL_GZ_SHA,
        "bars_total":data_source.TOTAL_ROWS,
        "periods_total":len(data),"discovery_week_count":12,
        "early_weeks":weeks[:6],"late_weeks":weeks[6:],
        "horizon_bars":H,"warmup":data_source.WARMUP,
        "baselines":list(MODES),"stress_bps":list(STRESS_BPS),
        "split_results":output,
        "costs_proxy":"NEXT_BAR_OPEN_CLOSE_AT_H4_16_20_25_40_BPS",
        "maker_fills_proven":False,"slippage_modelled":False,"funding_modelled":False,
        "real":"OFF","holdout":"SEALED","oos":False,
        "independent_check2":"PENDING",
        "decision":"DIAGNOSTICS_ONLY_NO_PROMOTION",
    }

def compute(compressed,meta):
    panel=data_source.parse_full(compressed,meta)
    receipt=execute(panel,meta)
    receipt["independent_check2"]=checker.verify(panel,meta,receipt)
    receipt["model_sha256"]=hashbytes(pathlib.Path(__file__).read_bytes())
    receipt["checker_sha256"]=hashbytes(pathlib.Path(checker.__file__).read_bytes())
    receipt["receipt_sha256"]=hashbytes(canonical(receipt).encode())
    return receipt

def verify_receipt(o):
    guard()
    pins={"schema":SCHEMA,"candidate":CANDIDATE,"panel_gzip_sha256":data_source.PANEL_GZ_SHA,
          "bars_total":data_source.TOTAL_ROWS,
          "real":"OFF","holdout":"SEALED","oos":False,
          "independent_check2":"PASS_INDEPENDENT_DIRECTION_AND_LEDGER_CHECK2",
          "decision":"DIAGNOSTICS_ONLY_NO_PROMOTION"}
    for k,v in pins.items():
        if type(o.get(k))!=type(v) or o[k]!=v:raise ValueError("BLOCKED_H4_RECEIPT_"+k)
    for k,path in (("model_sha256",__file__),("checker_sha256",checker.__file__)):
        if o.get(k)!=hashbytes(pathlib.Path(path).read_bytes()):
            raise ValueError("BLOCKED_H4_CODE_HASH_"+k)
    plain=dict(o);current=plain.pop("receipt_sha256",None)
    if current!=hashbytes(canonical(plain).encode()):
        raise ValueError("BLOCKED_H4_RECEIPT_DIGEST")
    return o

def remote_run(comp,meta):
    files={
        "h4_directional_audit.py":pathlib.Path(__file__).read_bytes(),
        "h4_directional_check2.py":pathlib.Path(checker.__file__).read_bytes(),
        "rescp_shadow.py":pathlib.Path(ridge.__file__).read_bytes(),
        "rescp_check2.py":pathlib.Path(ridge.independent.__file__).read_bytes(),
        "full13_wave_colab.py":pathlib.Path(data_source.__file__).read_bytes(),
        "hourly_wave_research.py":pathlib.Path(data_source.primary.__file__).read_bytes(),
        "hourly_wave_check2.py":pathlib.Path(data_source.independent.__file__).read_bytes(),
        "panel.gz":comp,"meta.json":canonical(meta).encode(),
    }
    bundle={k:base64.b64encode(v).decode() for k,v in files.items()}
    script=("import base64,os,pathlib,subprocess,sys,tempfile\n"
        "with tempfile.TemporaryDirectory(prefix='avrora-h4-edge-') as d:\n"
        " p=pathlib.Path(d)\n"
        f" files={repr(bundle)}\n"
        " for k,v in files.items():(p/k).write_bytes(base64.b64decode(v))\n"
        " env=os.environ.copy();env['REAL']='OFF';env['HOLDOUT']='SEALED';env['AVRORA_H4_AUDIT_ALLOWED']='YES'\n"
        " result=subprocess.run([sys.executable,'h4_directional_audit.py','evaluate',str(p/'panel.gz'),str(p/'meta.json')],cwd=p,env=env,capture_output=True,text=True,timeout=1200)\n"
        " if result.returncode:raise SystemExit('BLOCKED_H4_REMOTE_PROCESS')\n"
        f" if result.stdout.count({MARKER!r})!=1:raise SystemExit('BLOCKED_H4_MARKER')\n"
        " print(result.stdout.strip(),flush=True)\n")
    with tempfile.TemporaryDirectory(prefix="avrora-h4-local-") as d:
        program=pathlib.Path(d)/"one_shot.py"
        program.write_text(script,encoding="utf-8")
        logs=pathlib.Path(d)/"colab.log"
        with logs.open("wb") as f:
            p=subprocess.run(["colab","--auth=adc","run",str(program)],stdout=f,
                             stderr=subprocess.STDOUT,timeout=1500,
                             env={**os.environ,"REAL":"OFF","HOLDOUT":"SEALED"})
        if p.returncode:raise ValueError("BLOCKED_H4_COLAB")
        found=[s.split(MARKER,1)[1] for s in logs.read_text().splitlines() if MARKER in s]
        if len(found)!=1:raise ValueError("BLOCKED_H4_COLAB_RECEIPT")
        return json.loads(found[0])

def main(args):
    guard()
    if args==["run"]:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):raise ValueError("BLOCKED_H4_COLAB_AUTH")
        checkout=os.getenv("AVRORA_PRIVATE_CHECKOUT")
        if not checkout:raise ValueError("BLOCKED_H4_NO_PRIVATE_CHECKOUT")
        comp,meta=data_source.load_private(checkout)
        o=remote_run(comp,meta);verify_receipt(o)
        pathlib.Path("h4_directional_audit_receipt.json").write_text(canonical(o)+"\n")
        print("PASS_H4_DIRECTIONAL_EDGE_AUDIT_CHECK2")
    elif len(args)==3 and args[0]=="evaluate":
        o=compute(pathlib.Path(args[1]).read_bytes(),json.loads(pathlib.Path(args[2]).read_text()))
        verify_receipt(o);print(MARKER+canonical(o))
    elif len(args)==2 and args[0]=="verify":
        verify_receipt(json.loads(pathlib.Path(args[1]).read_text()))
        print("PASS_H4_DIRECTIONAL_EDGE_RECEIPT")
    else:
        raise ValueError("BLOCKED_H4_UNKNOWN_MODE")

if __name__=="__main__":
    try:main(sys.argv[1:])
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as e:
        msg=str(e)
        print(msg if msg.startswith("BLOCKED_") else "BLOCKED_H4_AUDIT",file=sys.stderr)
        raise SystemExit(1) from None
