"""1,000 preregistered cost/weekly robustness resamples of REAL frozen P816 M15 bars.

This is retrospective bootstrap of one ALREADY-FROZEN FIVE_WAVE_01 strategy,
not 1,000 new trading strategies, market fills, independent OOS or revenue.
No candidate selection after reading the dataset; the prereg and original
independent CHECK2 must pass before any resampling.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys
import tempfile

try:
    from tools import full13_wave_colab as panel
    from tools import hourly_wave_research as primary
except ImportError:
    import full13_wave_colab as panel
    import hourly_wave_research as primary

SCHEMA = "AVRORA_1000_REAL_M15_WEEK_BOOTSTRAP_ECONOMICS_V1"
MARKER = "AVRORA_PROFIT1000_REAL_HISTORY_RECEIPT="
N = 1000
SEED = 20261101
CANDIDATE = "FIVE_WAVE_01"  # first preregistered candidate, NOT a fitted winner
COSTS = (16,20,25,40)
ALLOWED_STATUSES = ("NO_TRADE_BETTER","RESEARCH_ONLY_POSITIVE")
PUBLIC_SOURCE_FILES = (
    "full13_wave_colab.py","hourly_wave_research.py",
    "hourly_wave_check2.py","avrora_profit1000_full13.py",
)


def canonical(x):
    return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),
                      allow_nan=False).encode("utf-8")


def sha(x):
    return hashlib.sha256(x).hexdigest()


def quantile(sorted_values,p):
    if not sorted_values or not 0<=p<=1:
        raise ValueError("BLOCKED_PROFIT1000_QUANTILE")
    j=(len(sorted_values)-1)*p
    lo=int(j);hi=min(len(sorted_values)-1,lo+1)
    return sorted_values[lo]+(j-lo)*(sorted_values[hi]-sorted_values[lo])


def sample_weeks(first_six,last_six,*,count=N,seed=SEED):
    """Two chronological six-week strata; bootstrap only within stratum."""
    if (len(first_six)!=6 or len(last_six)!=6 or
            set(first_six)&set(last_six) or
            len(set(first_six+last_six))!=12 or
            type(count) is not int or not 1<=count<=N or
            type(seed) is not int):
        raise ValueError("BLOCKED_PROFIT1000_STRATA")
    r=random.Random(seed)
    for _ in range(count):
        yield ([first_six[r.randrange(6)] for _ in range(6)] +
               [last_six[r.randrange(6)] for _ in range(6)])


def summarize(weekly,first_six,last_six,*,count=N,seed=SEED):
    """Pure, offline exact sum of gross minus fixed per-notional cost.

    Unknown slippage/funding/maker outcomes are NOT magically filled by bps:
    bps stress is a modeling assumption, not an authenticated fill.
    """
    weeks=first_six+last_six
    if (set(weekly)!=set(weeks) or len(weekly)!=12 or
            any(set(x)!={"gross","notional","trades"} or
                any(type(x[k]) not in (int,float) or not __import__("math").isfinite(x[k])
                    for k in ("gross","notional")) or
                x["notional"]<0 or type(x["trades"]) is not int or x["trades"]<0
                for x in weekly.values())):
        raise ValueError("BLOCKED_PROFIT1000_INVALID_WEEK_LEDGER")
    outputs={cost:[] for cost in COSTS}
    trades=[]; sig=hashlib.sha256()
    first_phase_positive={cost:0 for cost in COSTS}
    second_phase_positive={cost:0 for cost in COSTS}
    for run,selected in enumerate(sample_weeks(first_six,last_six,count=count,seed=seed)):
        if len(selected)!=12:raise ValueError("BLOCKED_PROFIT1000_DRAW_COUNT")
        gross=sum(weekly[w]["gross"] for w in selected)
        notional=sum(weekly[w]["notional"] for w in selected)
        num=sum(weekly[w]["trades"] for w in selected)
        trades.append(num)
        encoded=[]
        for cost in COSTS:
            net=gross-notional*cost/10000.0
            outputs[cost].append(net)
            encoded.append(round(net,8))
            if sum(weekly[w]["gross"]-weekly[w]["notional"]*cost/10000.0
                   for w in selected[:6])>0:first_phase_positive[cost]+=1
            if sum(weekly[w]["gross"]-weekly[w]["notional"]*cost/10000.0
                   for w in selected[6:])>0:second_phase_positive[cost]+=1
        if any(encoded[i]<encoded[i+1]-1e-7 for i in range(len(COSTS)-1)):
            raise ValueError("BLOCKED_PROFIT1000_COST_ORDER")
        sig.update(canonical({"trial":run,"week_sample":selected,
                              "trades":num,"net_by_cost_bps":encoded}))
    if len(trades)!=count or any(len(v)!=count for v in outputs.values()):
        raise ValueError("BLOCKED_PROFIT1000_TRIAL_COUNT")
    summary={}
    for cost,values in outputs.items():
        xs=sorted(values)
        observed=sum(weekly[w]["gross"]-weekly[w]["notional"]*cost/10000.0
                     for w in weeks)
        summary[str(cost)]={
            "observed_12w_model_net_usdt":round(observed,6),
            "bootstrap_min_net_usdt":round(xs[0],6),
            "bootstrap_p05_net_usdt":round(quantile(xs,0.05),6),
            "bootstrap_median_net_usdt":round(quantile(xs,0.5),6),
            "bootstrap_p95_net_usdt":round(quantile(xs,0.95),6),
            "bootstrap_max_net_usdt":round(xs[-1],6),
            "bootstrap_positive_net_trials":sum(v>0 for v in values),
            "bootstrap_nonpositive_net_trials":sum(v<=0 for v in values),
            "train_stratum_positive_trials":first_phase_positive[cost],
            "reused_validation_stratum_positive_trials":second_phase_positive[cost],
            "no_trade_net_usdt":0,
            "trading_dominates_no_trade_proven":False,
        }
        if summary[str(cost)]["bootstrap_positive_net_trials"]+summary[str(cost)]["bootstrap_nonpositive_net_trials"]!=count:
            raise ValueError("BLOCKED_PROFIT1000_BIN_TOTAL")
    return {"samples":count,
            "week_draws":12*count,
            "bootstrap_signature_sha256":sig.hexdigest(),
            "historical_closed_trade_count":sum(weekly[w]["trades"] for w in weeks),
            "original_12w_gross_usdt":round(sum(weekly[w]["gross"] for w in weeks),6),
            "original_12w_notional_sum_usdt":round(sum(weekly[w]["notional"] for w in weeks),6),
            "draw_min_trades":min(trades),
            "draw_median_trades":quantile(sorted(trades),0.5),
            "draw_max_trades":max(trades),
            "cost_stress_bps":summary,
           }


def run_real_history(compressed,meta,manifest):
    panel.gate()
    data=panel.parse_full(compressed,meta)
    frozen=primary.validate_manifest(manifest)
    candidate=next((p for p in frozen["candidates"] if p["id"]==CANDIDATE),None)
    if not candidate:
        raise ValueError("BLOCKED_PROFIT1000_PARENT_MISSING")
    # Independently reconstruct the complete original signal and fill ledger.
    reference=panel.run_complete(data,meta,frozen,CANDIDATE,candidate)
    if reference.get("check2")!="PASS_FULL_SIGNALS_AND_LEDGER":
        raise ValueError("BLOCKED_PROFIT1000_CHECK2")
    _proposals,ledger=panel.build_portfolio(data,candidate,
                                         primary.signals,primary.simulate_one)
    # Price-path executions are a model, never authenticated exchange orders.
    weeks=list(meta["discovery_week_starts"])
    if len(weeks)!=12 or weeks!=sorted(weeks):
        raise ValueError("BLOCKED_PROFIT1000_WEEK_ORDER")
    weekly={}
    for w in weeks:
        xs=[t for t in ledger if t["period"]==w]
        weekly[w]={"gross":sum(t["gross"] for t in xs),
                   "notional":sum(t["notional"] for t in xs),
                   "trades":len(xs)}
        actual20=sum(t["gross"]-t["notional"]*.0020 for t in xs)
        if (abs(actual20-reference["by_week"][w]["net20_usdt"])>2e-4
                or len(xs)!=reference["by_week"][w]["trades"]):
            raise ValueError("BLOCKED_PROFIT1000_WEEK_RECONCILIATION")
    ret=summarize(weekly,weeks[:6],weeks[6:])
    report={
        "schema":SCHEMA,"status":"PASS_1000_RETROSPECTIVE_WEEK_BOOTSTRAP",
        "candidate_id":CANDIDATE,"candidate_selection":"FIRST_FROZEN_BY_ID_NOT_WINNER",
        "prereg_sha256":sha(canonical(frozen)),
        "private_source_zip_sha256":panel.SOURCE_ZIP_SHA,
        "private_M15_panel_gzip_sha256":panel.PANEL_GZ_SHA,
        "source_m15_rows":panel.TOTAL_ROWS,
        "market_source":"REAL_HISTORICAL_13_PERIOD_M15_P816",
        "candidate_source_model_sha256":reference["model_sha256"],
        "independent_checker_sha256":reference["checker_sha256"],
        "independent_price_path_check2":True,
        "reused_discovery_weeks":12,
        "new_prospective_weeks":0,
        "may_aux_excluded_from_bootstrap":True,
        "six_symbols":list(panel.SYMBOLS),
        "seed":SEED,"bootstrap_trials_requested":N,
        "bootstrap_trials_completed":ret["samples"],
        "weeks_drawn":ret["week_draws"],
        "original_12w_gross_usdt":ret["original_12w_gross_usdt"],
        "original_12w_notional_sum_usdt":ret["original_12w_notional_sum_usdt"],
        "original_12w_model_closed_trades":ret["historical_closed_trade_count"],
        "bootstrap_min_trades":ret["draw_min_trades"],
        "bootstrap_median_trades":ret["draw_median_trades"],
        "bootstrap_max_trades":ret["draw_max_trades"],
        "bootstrap_signature_sha256":ret["bootstrap_signature_sha256"],
        "cost_stress_bps":ret["cost_stress_bps"],
        "null_benchmark":"NO_TRADE_ZERO_PNL",
        "estimated_maker_fill_proven":False,
        "source_first_seen_event_receipts_present":False,
        "fee_tier_confirmed":False,
        "actual_net_profit_proven":False,
        "independent_prospective_oos_proven":False,
        "statistical_power_for_strategy_promotion_proven":False,
        "live_trading_authorized":False,
        "real":"OFF","holdout":"SEALED",
        "scope":"ONE_FROZEN_PARENT_ONE_THOUSAND_WEEK_RESAMPLES_NOT_NEW_STRATEGY_OR_OOS",
    }
    report["receipt_sha256"]=sha(canonical(report))
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("local","remote"))
    p.add_argument("--private-checkout")
    p.add_argument("--source-gz")
    p.add_argument("--source-manifest")
    p.add_argument("--prereg")
    a=p.parse_args()
    if a.mode=="local":
        if not a.private_checkout:raise ValueError("BLOCKED_PROFIT1000_CHECKOUT_ARG")
        compressed,meta=panel.load_private(a.private_checkout)
        manifest=primary.load_manifest()
    else:
        if not all((a.source_gz,a.source_manifest,a.prereg)):
            raise ValueError("BLOCKED_PROFIT1000_REMOTE_RESOURCE_ARGS")
        compressed=Path(a.source_gz).read_bytes()
        meta=json.loads(Path(a.source_manifest).read_bytes())
        manifest=json.loads(Path(a.prereg).read_bytes())
    report=run_real_history(compressed,meta,manifest)
    print(MARKER+canonical(report).decode("utf-8"),flush=True)


if __name__=="__main__":
    main()
