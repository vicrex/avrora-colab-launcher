"""Approved immutable 12-idea squeeze grid, four independent FULL13 tests per Colab run.

Every entry must be frozen before execution. Uses only the existing 13-period
pinned private dataset, never sealed holdout, maker fills or live orders.
"""
from __future__ import annotations
import base64, hashlib, json, os, pathlib, subprocess, sys, tempfile

try:
    from tools import structural_short as primary
    from tools import vector_squeeze_grid_check2 as checker
    from tools import vector_insight_lab as idea_lab
    from tools import full13_wave_colab as source
except ImportError:
    import structural_short as primary
    import vector_squeeze_grid_check2 as checker
    import vector_insight_lab as idea_lab
    import full13_wave_colab as source

SCHEMA="AVRORA_VECTOR_SQUEEZE_GRID_FULL13_V1"
MARKER="AVRORA_VECTOR_GRID_VERIFIED="
MODE="SQUEEZE_BREAK_SHORT_V1"
BATCH_SIZE=4
MAX_BATCHES=3

def canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def path_for_grid():
    here=pathlib.Path(__file__).resolve()
    a=here.parents[1]/"research/vector_squeeze_grid_prereg_v1.json"
    return a if a.is_file() else here.parent/"vector_squeeze_grid_prereg_v1.json"

def load_grid():
    p=path_for_grid()
    raw=p.read_bytes()
    x=json.loads(raw)
    idea_lab.validated_grid(x)
    return x,sha(raw)

def gate():
    source.gate()
    if os.environ.get("AVRORA_GRID_SHADOW_ENABLED")!="YES":
        raise ValueError("BLOCKED_GRID_NOT_AUTHORIZED")

def params_for(spec,baseline):
    p=dict(baseline)
    p.update(squeeze_max_range_ratio=spec["range_ratio"],
             break_atr=spec["break_atr"],body_atr=spec["body_atr"])
    if spec["window_bars"]!=p["squeeze_lookback_bars"] or spec["previous_window_bars"]!=p["squeeze_previous_window_bars"]:
        raise ValueError("BLOCKED_GRID_LOOKBACK")
    if (spec["ema_fast"]!=p["ema_fast"] or spec["ema_slow"]!=p["ema_slow"]
            or spec["stop_atr"]!=p["stop_atr"] or spec["reward_r"]!=p["reward_r"]
            or spec["time_bars"]!=p["time_bars"]):
        raise ValueError("BLOCKED_GRID_EXIT_OR_TREND_CHANGED")
    return p

def evaluate(panel,meta,grid,grid_sha,batch):
    gate()
    if type(batch) is not int or not 0<=batch<MAX_BATCHES:
        raise ValueError("BLOCKED_GRID_BATCH_INDEX")
    if len(panel)!=78 or sum(map(len,panel.values()))!=69576:
        raise ValueError("BLOCKED_GRID_FULL13_SHAPE")
    manifest,source_sha=primary.load_manifest()
    if manifest.get("schema")!="AVRORA_SHORT_BREAKOUT_FULL13_PREREG_V3":
        raise ValueError("BLOCKED_BASELINE_VERSION")
    chosen=grid["candidates"][batch*BATCH_SIZE:(batch+1)*BATCH_SIZE]
    if len(chosen)!=BATCH_SIZE:
        raise ValueError("BLOCKED_GRID_INCOMPLETE_BATCH")
    periods=sorted({w for w,sym in panel if w!=source.AUX})
    if len(periods)!=12:
        raise ValueError("BLOCKED_GRID_WEEKS")
    results={}
    for entry in chosen:
        params=params_for(entry,manifest["fixed_parameters"])
        customized={"fixed_parameters":params}
        actual_discovery=primary.book(panel,customized,MODE,False)
        checked_discovery=checker.simulate(panel,MODE,False,params)
        checker.assert_equal(actual_discovery,checked_discovery,entry["id"]+"_D_ALL_TRADES")
        actual_aux=primary.book(panel,customized,MODE,True)
        checked_aux=checker.simulate(panel,MODE,True,params)
        checker.assert_equal(actual_aux,checked_aux,entry["id"]+"_M_ALL_TRADES")
        discovery=primary.summarise(actual_discovery,periods,84)
        may=primary.summarise(actual_aux,[source.AUX],7)
        checker.assert_equal(discovery,checker.summarise(checked_discovery,periods,84),
                             entry["id"]+"_D_SUMMARY")
        checker.assert_equal(may,checker.summarise(checked_aux,[source.AUX],7),
                             entry["id"]+"_M_SUMMARY")
        results[entry["id"]]={"spec_sha256":sha(canon(entry).encode()),
             "signal_variant":MODE, "discovery":discovery, "may_aux":may,
             "check2":"PASS_ALL_SIGNALS_FILLS_EQUITY_AND_COSTS"}
    report={"schema":SCHEMA,"status":"PASS_PINNED_FULL13_GRID_CHECK2",
            "prereg_grid_sha256":grid_sha,"prereg_v3_sha256":source_sha,
            "candidate_ids":[e["id"] for e in chosen],"batch_index":batch,
            "candidate_count":len(chosen),"panel_sha256":source.PANEL_GZ_SHA,
            "source_archive_sha256":source.SOURCE_ZIP_SHA,
            "engine_sha256":sha(pathlib.Path(primary.__file__).read_bytes()),
            "checker_sha256":sha(pathlib.Path(checker.__file__).read_bytes()),
            "grid_engine_sha256":sha(pathlib.Path(__file__).read_bytes()),
            "periods":13,"bars":69576,"warmup":220,
            "discovery_days":84,"may_aux_days":7,"real":"OFF","holdout":"SEALED",
            "oos":False,"maker_fill_proven":False,"funding_modeled":False,
            "slippage_modeled":False,"results":results,
            "decision":"EXPLORATORY_MULTIPLE_TESTS_NO_AUTO_PROMOTION",
            "multiplicity":"12_SHARED_DISCOVERY_SET_VARIANTS_NO_UNADJUSTED_BEST_WINNER"}
    report["receipt_sha256"]=sha(canon(report).encode())
    return report

def verify_receipt(receipt,expected_batch):
    gate()
    grid,grid_sha=load_grid()
    if receipt.get("receipt_sha256")!=sha(canon({k:v for k,v in receipt.items() if k!="receipt_sha256"}).encode()):
        raise ValueError("BLOCKED_GRID_RECEIPT_SHA")
    manifest,manifest_sha=primary.load_manifest()
    expected={ "schema":SCHEMA,"status":"PASS_PINNED_FULL13_GRID_CHECK2",
       "prereg_grid_sha256":grid_sha,"prereg_v3_sha256":manifest_sha,
       "panel_sha256":source.PANEL_GZ_SHA,"source_archive_sha256":source.SOURCE_ZIP_SHA,
       "engine_sha256":sha(pathlib.Path(primary.__file__).read_bytes()),
       "checker_sha256":sha(pathlib.Path(checker.__file__).read_bytes()),
       "grid_engine_sha256":sha(pathlib.Path(__file__).read_bytes()),
       "batch_index":expected_batch,"candidate_count":4,"periods":13,"bars":69576,
       "warmup":220,"discovery_days":84,"may_aux_days":7,"real":"OFF",
       "holdout":"SEALED","oos":False,"maker_fill_proven":False,
       "funding_modeled":False,"slippage_modeled":False,
       "decision":"EXPLORATORY_MULTIPLE_TESTS_NO_AUTO_PROMOTION"}
    if any(receipt.get(k)!=v or type(receipt.get(k)) is not type(v) for k,v in expected.items()):
        raise ValueError("BLOCKED_GRID_RECEIPT_PIN")
    selected=grid["candidates"][expected_batch*4:expected_batch*4+4]
    if receipt.get("candidate_ids")!=[c["id"] for c in selected] or set(receipt.get("results",{}))!={c["id"] for c in selected}:
        raise ValueError("BLOCKED_GRID_CANDIDATES")
    for candidate in selected:
        out=receipt["results"][candidate["id"]]
        if out.get("spec_sha256")!=sha(canon(candidate).encode()) or out.get("signal_variant")!=MODE or out.get("check2")!="PASS_ALL_SIGNALS_FILLS_EQUITY_AND_COSTS":
            raise ValueError("BLOCKED_GRID_STRATEGY_PROVENANCE")
        d=out.get("discovery",{})
        a=out.get("may_aux",{})
        if len(d.get("by_week",{}))!=12 or set(d.get("by_symbol",{}))!=set(source.SYMBOLS):
            raise ValueError("BLOCKED_GRID_COVERAGE")
        for result in (d,a):
            vals=result.get("net_by_cost_bps_usdt",{})
            if set(vals)!={"16","20","25","40"} or not all(
                    type(vals[k]) in (int,float) and __import__("math").isfinite(vals[k]) for k in vals):
                raise ValueError("BLOCKED_GRID_FEES")
            if not(vals["16"]>=vals["20"]>=vals["25"]>=vals["40"]):
                raise ValueError("BLOCKED_GRID_FEES")
    return receipt

def remote_run(compressed,meta,batch):
    resources={
       "vector_squeeze_grid.py":pathlib.Path(__file__).read_bytes(),
       "vector_squeeze_grid_check2.py":pathlib.Path(checker.__file__).read_bytes(),
       "vector_insight_lab.py":pathlib.Path(idea_lab.__file__).read_bytes(),
       "structural_short.py":pathlib.Path(primary.__file__).read_bytes(),
       "structural_short_check2.py":pathlib.Path(primary.independent.__file__).read_bytes(),
       "full13_wave_colab.py":pathlib.Path(source.__file__).read_bytes(),
       "hourly_wave_research.py":pathlib.Path(source.primary.__file__).read_bytes(),
       "hourly_wave_check2.py":pathlib.Path(source.independent.__file__).read_bytes(),
       "structural_short_prereg_v3.json":primary.manifest_path().read_bytes(),
       "vector_squeeze_grid_prereg_v1.json":path_for_grid().read_bytes(),
       "panel.gz":compressed,"meta.json":canon(meta).encode()
    }
    b64={k:base64.b64encode(v).decode() for k,v in resources.items()}
    script=("import base64,os,pathlib,subprocess,sys,tempfile\n"
      "with tempfile.TemporaryDirectory(prefix='avrora-grid-') as d:\n"
      " p=pathlib.Path(d)\n"
      f" files={repr(b64)}\n"
      " for name,v in files.items():(p/name).write_bytes(base64.b64decode(v))\n"
      " env=os.environ.copy();env['AVRORA_GRID_SHADOW_ENABLED']='YES';env['REAL']='OFF';env['HOLDOUT']='SEALED'\n"
      f" run=subprocess.run([sys.executable,'vector_squeeze_grid.py','evaluate',str(p/'panel.gz'),str(p/'meta.json'),'{batch}'],cwd=p,env=env,capture_output=True,text=True,timeout=1200)\n"
      " if run.returncode:raise SystemExit('BLOCKED_GRID_REMOTE_EXECUTION')\n"
      f" if run.stdout.count({MARKER!r})!=1:raise SystemExit('BLOCKED_GRID_REMOTE_RECEIPT_MARKER')\n"
      " print(run.stdout.strip(),flush=True)\n"
    )
    with tempfile.TemporaryDirectory(prefix="avrora-grid-colab-") as temp:
        py=pathlib.Path(temp)/"grid_study.py"
        py.write_text(script)
        log=pathlib.Path(temp)/"colab.log"
        with log.open("wb") as output:
            completed=subprocess.run(["colab","--auth=adc","run",str(py)],
                                     stdout=output,stderr=subprocess.STDOUT,
                                     timeout=1800,env={**os.environ,"REAL":"OFF","HOLDOUT":"SEALED"})
        if completed.returncode:
            raise ValueError("BLOCKED_GRID_COLAB_RUN")
        matches=[row.split(MARKER,1)[1] for row in log.read_text("utf-8").splitlines() if MARKER in row]
        if len(matches)!=1:
            raise ValueError("BLOCKED_GRID_COLAB_MARKER")
        return json.loads(matches[0])

def main(args):
    gate()
    if len(args)==2 and args[0]=="run":
        batch=int(args[1])
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("BLOCKED_GRID_NO_ADC")
        checkout=os.environ.get("AVRORA_PRIVATE_CHECKOUT")
        if not checkout:
            raise ValueError("BLOCKED_GRID_NO_PINNED_DATA")
        compressed,meta=source.load_private(checkout)
        result=remote_run(compressed,meta,batch)
        verify_receipt(result,batch)
        pathlib.Path(f"vector_squeeze_grid_batch{batch}.json").write_text(canon(result)+"\n")
        print("AVRORA_GRID_CHECK2_VERIFIED",batch,sha(canon(result).encode()))
    elif len(args)==4 and args[0]=="evaluate":
        batch=int(args[3])
        compressed=pathlib.Path(args[1]).read_bytes()
        meta=json.loads(pathlib.Path(args[2]).read_text())
        panel=source.parse_full(compressed,meta)
        grid,pin_sha=load_grid()
        result=evaluate(panel,meta,grid,pin_sha,batch)
        verify_receipt(result,batch)
        print(MARKER+canon(result))
    elif len(args)==3 and args[0]=="verify":
        verify_receipt(json.loads(pathlib.Path(args[1]).read_text()),int(args[2]))
        print("AVRORA_GRID_RECEIPT_SHA_CHECK2_PASS")
    else:
        raise ValueError("BLOCKED_GRID_MODE")

if __name__=="__main__":
    try: main(sys.argv[1:])
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError):
        print("BLOCKED_VECTOR_GRID_NOT_VERIFIED",file=sys.stderr)
        raise SystemExit(1) from None
