"""Independent strict receipt inspection for 1,000 real-history week resamples.

No claim to independent OOS, market fill priority, fee-tier eligibility,
or real profits may be inferred from a successful historical bootstrap.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
from tools.avrora_profit1000_full13 import (
    SCHEMA, MARKER, N, COSTS, CANDIDATE, SEED, canonical, sha,
)
from tools.full13_wave_colab import (
    PANEL_GZ_SHA, SOURCE_ZIP_SHA, TOTAL_ROWS, SYMBOLS,
)


def parse(log):
    lines=[line.split(MARKER,1)[1].strip()
           for line in log.splitlines() if MARKER in line]
    if len(lines)!=1:
        raise ValueError("BLOCKED_PROFIT1000_MARKER_COUNT")
    try:
        obj=json.loads(lines[0])
    except ValueError as exc:
        raise ValueError("BLOCKED_PROFIT1000_RECEIPT_JSON") from exc
    if not isinstance(obj,dict):
        raise ValueError("BLOCKED_PROFIT1000_RECEIPT_OBJECT")
    original=obj.pop("receipt_sha256",None)
    if not isinstance(original,str) or sha(canonical(obj))!=original:
        raise ValueError("BLOCKED_PROFIT1000_RECEIPT_SHA")
    if (obj.get("schema")!=SCHEMA or
        obj.get("status")!="PASS_1000_RETROSPECTIVE_WEEK_BOOTSTRAP" or
        obj.get("candidate_id")!=CANDIDATE or
        obj.get("candidate_selection")!="FIRST_FROZEN_BY_ID_NOT_WINNER" or
        obj.get("private_source_zip_sha256")!=SOURCE_ZIP_SHA or
        obj.get("private_M15_panel_gzip_sha256")!=PANEL_GZ_SHA or
        obj.get("source_m15_rows")!=TOTAL_ROWS or
        obj.get("market_source")!="REAL_HISTORICAL_13_PERIOD_M15_P816" or
        obj.get("reused_discovery_weeks")!=12 or
        obj.get("new_prospective_weeks")!=0 or
        obj.get("may_aux_excluded_from_bootstrap") is not True or
        obj.get("six_symbols")!=list(SYMBOLS) or
        obj.get("seed")!=SEED or
        obj.get("bootstrap_trials_requested")!=N or
        obj.get("bootstrap_trials_completed")!=N or
        obj.get("weeks_drawn")!=N*12 or
        obj.get("independent_price_path_check2") is not True or
        obj.get("estimated_maker_fill_proven") is not False or
        obj.get("source_first_seen_event_receipts_present") is not False or
        obj.get("fee_tier_confirmed") is not False or
        obj.get("actual_net_profit_proven") is not False or
        obj.get("independent_prospective_oos_proven") is not False or
        obj.get("statistical_power_for_strategy_promotion_proven") is not False or
        obj.get("live_trading_authorized") is not False or
        obj.get("null_benchmark")!="NO_TRADE_ZERO_PNL" or
        obj.get("real")!="OFF" or obj.get("holdout")!="SEALED" or
        obj.get("scope")!="ONE_FROZEN_PARENT_ONE_THOUSAND_WEEK_RESAMPLES_NOT_NEW_STRATEGY_OR_OOS"):
        raise ValueError("BLOCKED_PROFIT1000_FALSE_PROOF_OR_SCOPE")
    sections=obj.get("cost_stress_bps")
    if not isinstance(sections,dict) or set(sections)!={str(v) for v in COSTS}:
        raise ValueError("BLOCKED_PROFIT1000_COST_MATRIX")
    for cost in COSTS:
        row=sections[str(cost)]
        if (type(row)!=dict or
                row.get("bootstrap_positive_net_trials",0)+
                row.get("bootstrap_nonpositive_net_trials",0)!=N or
                row.get("no_trade_net_usdt")!=0 or
                row.get("trading_dominates_no_trade_proven") is not False):
            raise ValueError("BLOCKED_PROFIT1000_COST_BIN")
        for key in ("observed_12w_model_net_usdt","bootstrap_min_net_usdt",
                    "bootstrap_p05_net_usdt","bootstrap_median_net_usdt",
                    "bootstrap_p95_net_usdt","bootstrap_max_net_usdt"):
            if type(row.get(key)) not in (int,float):
                raise ValueError("BLOCKED_PROFIT1000_VALUE_SHAPE")
        if not (row["bootstrap_min_net_usdt"]<=row["bootstrap_p05_net_usdt"]<=
                row["bootstrap_median_net_usdt"]<=row["bootstrap_p95_net_usdt"]<=
                row["bootstrap_max_net_usdt"]):
            raise ValueError("BLOCKED_PROFIT1000_QUANTILE_MONOTONE")
    observed=[sections[str(c)]["observed_12w_model_net_usdt"] for c in COSTS]
    if any(a<b-0.000002 for a,b in zip(observed,observed[1:])):
        raise ValueError("BLOCKED_PROFIT1000_FEE_MONOTONE")
    obj["receipt_sha256"]=original
    return obj


def main():
    if len(sys.argv)==4 and sys.argv[1]=="verify":
        result=parse(Path(sys.argv[2]).read_text("utf-8"))
        dst=Path(sys.argv[3])
        if dst.exists():raise ValueError("BLOCKED_PROFIT1000_OVERWRITE")
        dst.write_bytes(canonical(result)+b"\n")
        print("PASS_PROFIT1000_COST_STRESS_RESEARCH_ONLY",N,
              result["receipt_sha256"],flush=True)
    elif len(sys.argv)==4 and sys.argv[1]=="compare":
        local=json.loads(Path(sys.argv[2]).read_text("utf-8"))
        remote=json.loads(Path(sys.argv[3]).read_text("utf-8"))
        if local!=remote or parse(MARKER+canonical(local).decode("utf-8"))!=local:
            raise ValueError("BLOCKED_PROFIT1000_LOCAL_COLAB_NUMERIC_DIVERGENCE")
        print("PASS_PROFIT1000_REAL_HISTORY_LOCAL_COLAB_BYTE_PARITY",
              local["receipt_sha256"],flush=True)
    else:
        raise SystemExit("verify LOG REPORT | compare LOCAL REPORT")


if __name__=="__main__":main()
