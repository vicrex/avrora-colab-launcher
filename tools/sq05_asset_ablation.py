"""Retrospective SQ05 asset×mechanism portfolio ablation, independent CHECK2.

Six scenarios PRE-REGISTERED after seeing asset PnL in old research. They are
exploratory only, never evidence of live or truly unseen profitable alpha.
"""
from __future__ import annotations
import base64, hashlib, json, os, pathlib, subprocess, sys, tempfile

try:
    from tools import structural_short as primary
    from tools import vector_squeeze_grid_check2 as independent
    from tools import vector_squeeze_grid as grid
    from tools import vector_insight_lab as insight
    from tools import full13_wave_colab as source
except ImportError:
    import structural_short as primary
    import vector_squeeze_grid_check2 as independent
    import vector_squeeze_grid as grid
    import vector_insight_lab as insight
    import full13_wave_colab as source

SCHEMA = "AVRORA_SQ05_ASSET_ABLATION_FULL13_V1"
MARKER = "AVRORA_SQ05_ASSET_CHECK2_VERIFIED="
MODE = "SQUEEZE_BREAK_SHORT_V1"
EXPECTED = (
    ("ALL6_CONTROL", ("BTCUSDT","ETHUSDT","LINKUSDT","NEARUSDT","SOLUSDT","XRPUSDT")),
    ("SOL_ONLY", ("SOLUSDT",)),
    ("XRP_ONLY", ("XRPUSDT",)),
    ("SOL_XRP", ("SOLUSDT","XRPUSDT")),
    ("SOL_XRP_LINK", ("LINKUSDT","SOLUSDT","XRPUSDT")),
    ("BTC_ETH_NEAR_NEG_CONTROL", ("BTCUSDT","ETHUSDT","NEARUSDT")),
)
CONTROL = {"trades":380,"net20":32.896420,"net25":-47.183751}

def canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def path_prereg():
    f=pathlib.Path(__file__).resolve()
    a=f.parents[1]/"research/sq05_asset_mechanism_ablation_prereg_v1.json"
    return a if a.is_file() else f.parent/"sq05_asset_mechanism_ablation_prereg_v1.json"

def gate():
    source.gate()
    if os.environ.get("AVRORA_ASSET_ABLATION_ENABLED")!="YES":
        raise ValueError("BLOCKED_ASSET_ABLATION_NOT_AUTHORIZED")
    if os.environ.get("AVRORA_GRID_SHADOW_ENABLED")!="YES":
        raise ValueError("BLOCKED_GRID_FAMILY_NOT_AUTHORIZED")

def prereg():
    raw=path_prereg().read_bytes()
    j=json.loads(raw)
    required=("schema","date_utc","preexisting_chosen_signal",
              "exact_ordered_scenarios","permissions","data","costs_bps")
    if not isinstance(j,dict) or any(k not in j for k in required):
        raise ValueError("BLOCKED_ASSET_PREREG_SCHEMA")
    if j["schema"]!="AVRORA_SQ05_ASSET_MECHANISM_ABLATION_PREREG_V1":
        raise ValueError("BLOCKED_ASSET_PREREG_VERSION")
    actual=tuple((q["id"],tuple(q["symbols"])) for q in j["exact_ordered_scenarios"])
    if actual!=EXPECTED:
        raise ValueError("BLOCKED_ASSET_PREREG_SCOPES")
    if j["permissions"]!={"real":"OFF","holdout":"SEALED",
                           "new_cron":False,"ChatGPT_Work":False}:
        raise ValueError("BLOCKED_ASSET_PREREG_PERMISSIONS")
    if j["data"].get("source_panel_sha256")!=source.PANEL_GZ_SHA:
        raise ValueError("BLOCKED_ASSET_PREREG_SOURCE")
    if j["data"].get("bars")!=69576 or j["costs_bps"]!=[16,20,25,40]:
        raise ValueError("BLOCKED_ASSET_PREREG_SCOPE")
    s=j["preexisting_chosen_signal"]
    if s.get("id")!="SQ05" or s.get("family")!=MODE or (
            s.get("range_ratio"),s.get("break_atr"),s.get("body_atr")
        )!=(0.70,0.05,0.25):
        raise ValueError("BLOCKED_ASSET_PREREG_SPEC")
    return j,sha(raw)

def parameter_pin():
    manifest,manifest_sha=primary.load_manifest()
    g,gsha=grid.load_grid()
    sq=[c for c in g["candidates"] if c["id"]=="SQ05"]
    if len(sq)!=1:
        raise ValueError("BLOCKED_SQ05_MISSING")
    params=grid.params_for(sq[0],manifest["fixed_parameters"])
    if (params["squeeze_max_range_ratio"],params["break_atr"],
        params["body_atr"])!=(0.7,0.05,0.25):
        raise ValueError("BLOCKED_SQ05_PARAM_DRIFT")
    return params,manifest_sha,gsha,sha(canon(sq[0]).encode())

def cross_tab(ledger,periods,symbols):
    # Provenance: aggregation from each ACTUAL accepted portfolio trade, not
    # from independent marginals by symbol and week.
    index={}
    for period in periods:
        index[period]={sym:{"trades":0,"net20_usdt":0.0} for sym in symbols}
    for trade in ledger:
        p=trade["period"];sym=trade["symbol"]
        if p not in index or sym not in index[p]:
            raise ValueError("BLOCKED_ASSET_CROSSTAB_TRADE_SCOPE")
        cell=index[p][sym]
        cell["trades"]+=1
        cell["net20_usdt"]+=trade["net20_usdt"]
    for cells in index.values():
        for cell in cells.values():
            cell["net20_usdt"]=round(cell["net20_usdt"],6)
    return index

def evaluate(panel,meta):
    gate()
    prereg_data,prereg_sha=prereg()
    params,model_sha,grid_sha,spec_sha=parameter_pin()
    if len(panel)!=78 or sum(map(len,panel.values()))!=69576:
        raise ValueError("BLOCKED_ASSET_FULL13_SCOPE")
    if set(sym for week,sym in panel)!=set(source.SYMBOLS):
        raise ValueError("BLOCKED_ASSET_SYMBOLS")
    periods=sorted({w for w,s in panel if w!=source.AUX})
    if len(periods)!=12 or source.AUX in periods:
        raise ValueError("BLOCKED_ASSET_DISCOVERY_WEEKS")
    results={}
    for scenario,symbols in EXPECTED:
        sub={key:bars for key,bars in panel.items() if key[1] in symbols}
        if len(sub)!=13*len(symbols):
            raise ValueError("BLOCKED_ASSET_GROUP_COVERAGE")
        outcomes={}
        for label,aux,window,days in (
            ("discovery",False,periods,84),
            ("may_aux",True,[source.AUX],7)):
            own=primary.book(sub,{"fixed_parameters":params},MODE,aux)
            check=independent.simulate(sub,MODE,aux,params)
            # Independent ledger includes all fills, risk rejections, capital
            # constraints and timings, not just net PnL.
            independent.assert_equal(own,check,scenario+"_"+label+"_LEDGER")
            p=primary.summarise(own,window,days)
            q=independent.summarise(check,window,days)
            independent.assert_equal(p,q,scenario+"_"+label+"_AGG")
            cross=cross_tab(own["ledger"],window,symbols)
            second=cross_tab(check["ledger"],window,symbols)
            independent.assert_equal(cross,second,scenario+"_"+label+"_CROSSTAB")
            if abs(sum(x["net20_usdt"] for cells in cross.values()
                       for x in cells.values())-p["net_by_cost_bps_usdt"]["20"])>0.0001:
                raise ValueError("BLOCKED_ASSET_CROSSTAB_COST_SUM")
            if sum(x["trades"] for cells in cross.values()
                   for x in cells.values())!=p["trades"]:
                raise ValueError("BLOCKED_ASSET_CROSSTAB_TRADE_SUM")
            outcomes[label]={"summary":p,"symbol_week":cross,
                "trades_per_selected_symbol_day":round(p["trades"]/(days*len(symbols)),6)}
        results[scenario]={"symbols":list(symbols),"results":outcomes,
                           "check2":"PASS_FULL_LEDGER_TIMELINE_EQUITY_AND_SYMBOL_WEEK"}
    all6=results["ALL6_CONTROL"]["results"]["discovery"]["summary"]
    if (all6["trades"]!=CONTROL["trades"] or
        abs(all6["net_by_cost_bps_usdt"]["20"]-CONTROL["net20"])>0.00002 or
        abs(all6["net_by_cost_bps_usdt"]["25"]-CONTROL["net25"])>0.00002):
        raise ValueError("BLOCKED_ASSET_OLD_SQ05_CONTROL_DRIFT")
    payload={"schema":SCHEMA,"status":"PASS_PINNED_FULL13_ASSET_CHECK2",
             "data_source_sha256":source.SOURCE_ZIP_SHA,
             "panel_sha256":source.PANEL_GZ_SHA,
             "prereg_sha256":prereg_sha,"grid_prereg_sha256":grid_sha,
             "baseline_manifest_sha256":model_sha,"SQ05_spec_sha256":spec_sha,
             "asset_replay_sha256":sha(pathlib.Path(__file__).read_bytes()),
             "signal_engine_sha256":sha(pathlib.Path(primary.__file__).read_bytes()),
             "independent_checker_sha256":sha(pathlib.Path(independent.__file__).read_bytes()),
             "bars":69576,"periods":13,"warmup":220,
             "discovery_days":84,"may_aux_days":7,
             "real":"OFF","holdout":"SEALED","oos":False,
             "maker_fill_proven":False,"funding_modeled":False,
             "slippage_modeled":False,
             "research_limit":"ASSET_SCOPES_SELECTED_AFTER_VIEWING_DISCOVERY_PNL_NO_ALPHA",
             "cost_bps":[16,20,25,40],"results":results,
             "independent_check2":"PASS_FULL_LEDGER_TIMELINE_EQUITY_AND_SYMBOL_WEEK",
             "decision":"RESEARCH_ONLY_NO_AUTO_PROMOTION"}
    payload["receipt_sha256"]=sha(canon(payload).encode())
    return payload

def verify(receipt):
    gate()
    _,prereg_sha=prereg()
    params,model_sha,grid_sha,spec_sha=parameter_pin()
    expected={
       "schema":SCHEMA,"status":"PASS_PINNED_FULL13_ASSET_CHECK2",
       "panel_sha256":source.PANEL_GZ_SHA,
       "data_source_sha256":source.SOURCE_ZIP_SHA,
       "prereg_sha256":prereg_sha,"grid_prereg_sha256":grid_sha,
       "baseline_manifest_sha256":model_sha,"SQ05_spec_sha256":spec_sha,
       "asset_replay_sha256":sha(pathlib.Path(__file__).read_bytes()),
       "signal_engine_sha256":sha(pathlib.Path(primary.__file__).read_bytes()),
       "independent_checker_sha256":sha(pathlib.Path(independent.__file__).read_bytes()),
       "real":"OFF","holdout":"SEALED","oos":False,
       "bars":69576,"periods":13,"warmup":220,
       "maker_fill_proven":False,"funding_modeled":False,"slippage_modeled":False,
       "cost_bps":[16,20,25,40],
       "independent_check2":"PASS_FULL_LEDGER_TIMELINE_EQUITY_AND_SYMBOL_WEEK",
       "decision":"RESEARCH_ONLY_NO_AUTO_PROMOTION"}
    if any(receipt.get(k)!=v or type(receipt.get(k)) is not type(v)
           for k,v in expected.items()):
        raise ValueError("BLOCKED_ASSET_RECEIPT_PROVENANCE")
    if receipt.get("receipt_sha256")!=sha(canon({
            k:v for k,v in receipt.items() if k!="receipt_sha256"}).encode()):
        raise ValueError("BLOCKED_ASSET_RECEIPT_SHA")
    if set(receipt.get("results",{}))!={id for id,_ in EXPECTED}:
        raise ValueError("BLOCKED_ASSET_RECEIPT_SCENARIOS")
    for scenario,symbols in EXPECTED:
        r=receipt["results"][scenario]
        if r.get("symbols")!=list(symbols) or r.get("check2")!=expected["independent_check2"]:
            raise ValueError("BLOCKED_ASSET_RECEIPT_CHECK2_SCOPE")
        for label,days,nweeks in (("discovery",84,12),("may_aux",7,1)):
            scoped=r.get("results",{}).get(label,{})
            s=scoped.get("summary",{})
            tabs=scoped.get("symbol_week",{})
            if len(tabs)!=nweeks or any(set(cells)!=set(symbols) for cells in tabs.values()):
                raise ValueError("BLOCKED_ASSET_RECEIPT_WEEK_SYMBOLS")
            fees=s.get("net_by_cost_bps_usdt",{})
            if set(fees)!={"16","20","25","40"} or not(
                    fees["16"]>=fees["20"]>=fees["25"]>=fees["40"]):
                raise ValueError("BLOCKED_ASSET_RECEIPT_COSTS")
            if abs(sum(c["net20_usdt"] for cells in tabs.values()
                       for c in cells.values())-fees["20"])>0.0001:
                raise ValueError("BLOCKED_ASSET_RECEIPT_CROSSTAB")
            if sum(c["trades"] for cells in tabs.values()
                   for c in cells.values())!=s.get("trades"):
                raise ValueError("BLOCKED_ASSET_RECEIPT_TRADE_COUNTS")
            if abs(scoped.get("trades_per_selected_symbol_day",-1)-
                    round(s["trades"]/(days*len(symbols)),6))>1e-7:
                raise ValueError("BLOCKED_ASSET_RECEIPT_TRADE_RATE")
    return receipt

def remote_run(compressed,meta):
    resources={
       "sq05_asset_ablation.py":pathlib.Path(__file__).read_bytes(),
       "sq05_asset_mechanism_ablation_prereg_v1.json":path_prereg().read_bytes(),
       "vector_squeeze_grid.py":pathlib.Path(grid.__file__).read_bytes(),
       "vector_squeeze_grid_check2.py":pathlib.Path(independent.__file__).read_bytes(),
       "vector_insight_lab.py":pathlib.Path(insight.__file__).read_bytes(),
       "structural_short.py":pathlib.Path(primary.__file__).read_bytes(),
       "structural_short_check2.py":pathlib.Path(primary.independent.__file__).read_bytes(),
       "full13_wave_colab.py":pathlib.Path(source.__file__).read_bytes(),
       "hourly_wave_research.py":pathlib.Path(source.primary.__file__).read_bytes(),
       "hourly_wave_check2.py":pathlib.Path(source.independent.__file__).read_bytes(),
       "structural_short_prereg_v3.json":primary.manifest_path().read_bytes(),
       "vector_squeeze_grid_prereg_v1.json":grid.path_for_grid().read_bytes(),
       "panel.gz":compressed,"meta.json":canon(meta).encode()
    }
    encoded={key:base64.b64encode(v).decode() for key,v in resources.items()}
    script=("import base64,os,pathlib,subprocess,sys,tempfile\n"
      "with tempfile.TemporaryDirectory(prefix='avrora-asset-') as d:\n"
      " p=pathlib.Path(d)\n"
      f" files={repr(encoded)}\n"
      " for name,v in files.items():(p/name).write_bytes(base64.b64decode(v))\n"
      " env=os.environ.copy();env['AVRORA_ASSET_ABLATION_ENABLED']='YES';env['AVRORA_GRID_SHADOW_ENABLED']='YES';env['REAL']='OFF';env['HOLDOUT']='SEALED'\n"
      " run=subprocess.run([sys.executable,'sq05_asset_ablation.py','evaluate',str(p/'panel.gz'),str(p/'meta.json')],cwd=p,env=env,capture_output=True,text=True,timeout=1200)\n"
      " if run.returncode:raise SystemExit('BLOCKED_ASSET_COLAB_EVAL')\n"
      f" if run.stdout.count({MARKER!r})!=1:raise SystemExit('BLOCKED_ASSET_COLAB_MARKER')\n"
      " print(run.stdout.strip(),flush=True)\n")
    with tempfile.TemporaryDirectory(prefix="avrora-sq05-colab-") as temp:
        study=pathlib.Path(temp)/"asset_study.py"
        study.write_text(script,encoding="utf-8")
        log=pathlib.Path(temp)/"remote.log"
        with log.open("wb") as f:
            proc=subprocess.run(["colab","--auth=adc","run",str(study)],
                                stdout=f,stderr=subprocess.STDOUT,
                                timeout=1800,env={**os.environ,"REAL":"OFF","HOLDOUT":"SEALED"})
        if proc.returncode: raise ValueError("BLOCKED_ASSET_COLAB_RUN")
        lines=[ln.split(MARKER,1)[1] for ln in log.read_text("utf-8").splitlines()
               if MARKER in ln]
        if len(lines)!=1:raise ValueError("BLOCKED_ASSET_REMOTE_RECEIPT")
        return json.loads(lines[0])

def main(argv):
    gate()
    if argv==["run"]:
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("BLOCKED_ASSET_NO_ADC")
        checkout=os.environ.get("AVRORA_PRIVATE_CHECKOUT")
        if not checkout:raise ValueError("BLOCKED_ASSET_NO_PRIVATE_CHECKOUT")
        payload,meta=source.load_private(checkout)
        report=remote_run(payload,meta)
        verify(report)
        pathlib.Path("sq05_asset_ablation_receipt.json").write_text(canon(report)+"\n")
        print("PASS_SQ05_ASSET_PORTFOLIO_CHECK2",report["receipt_sha256"])
    elif len(argv)==3 and argv[0]=="evaluate":
        raw=pathlib.Path(argv[1]).read_bytes()
        meta=json.loads(pathlib.Path(argv[2]).read_text("utf-8"))
        report=evaluate(source.parse_full(raw,meta),meta)
        verify(report)
        print(MARKER+canon(report))
    elif len(argv)==2 and argv[0]=="verify":
        verify(json.loads(pathlib.Path(argv[1]).read_text("utf-8")))
        print("PASS_SQ05_ASSET_RECEIPT_PIN")
    else:raise ValueError("BLOCKED_ASSET_ARGS")

if __name__=="__main__":
    try:main(sys.argv[1:])
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError):
        print("BLOCKED_ASSET_ABLATION_UNVERIFIED",file=sys.stderr)
        raise SystemExit(1) from None
