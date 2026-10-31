"""Fail-closed verification of 100 *actual* Colab double-start MLE trials."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from tools.avrora_hundred_mle_colab import (
    CASE_COUNT, MARKER, PRIVATE_HEAD, SCHEMA, SYMBOLS, canonical, sha,
)


def parse(text):
    hits=[line.split(MARKER,1)[1].strip()
          for line in text.splitlines() if MARKER in line]
    if len(hits)!=1:
        raise ValueError("BLOCKED_MLE_COLAB_RECEIPT_COUNT")
    try:
        obj=json.loads(hits[0])
    except (ValueError,TypeError) as exc:
        raise ValueError("BLOCKED_MLE_COLAB_RECEIPT_JSON") from exc
    if not isinstance(obj,dict):
        raise ValueError("BLOCKED_MLE_COLAB_RECEIPT_SHAPE")
    digest=obj.pop("receipt_sha256",None)
    if not isinstance(digest,str) or sha(canonical(obj))!=digest:
        raise ValueError("BLOCKED_MLE_COLAB_RECEIPT_SHA")
    cases=obj.get("cases")
    status=obj.get("statuses")
    per_symbol=obj.get("cases_by_symbol")
    if (obj.get("schema")!=SCHEMA or
        obj.get("status")!="PASS_100_COMPLETED_MATH_RESEARCH_RUNS" or
        obj.get("private_source_sha")!=PRIVATE_HEAD or
        not isinstance(cases,list) or len(cases)!=CASE_COUNT or
        obj.get("completed_seven_day_mle_runs")!=CASE_COUNT or
        obj.get("total_mle_starts")!=2*CASE_COUNT or
        obj.get("two_frozen_initializations_per_run") is not True or
        obj.get("original_vs_cached_exact_parity_runs")!=CASE_COUNT or
        obj.get("future_time_rejections")!=CASE_COUNT or
        obj.get("actual_colab_cli_sessions")!=1 or
        obj.get("real_market_events_processed")!=0 or
        obj.get("synthetic_event_data") is not True or
        obj.get("provider_completeness_proven") is not False or
        obj.get("historical_first_seen_proven") is not False or
        obj.get("independent_check2") is not False or
        obj.get("prospective_oos_proven") is not False or
        obj.get("maker_fill_proven") is not False or
        obj.get("strategies_proven_profitable")!=0 or
        obj.get("live_trading_authorized") is not False or
        obj.get("real")!="OFF" or obj.get("holdout")!="SEALED" or
        obj.get("scope")!="100_INDEPENDENT_SYNTHETIC_DOUBLE_START_MLE_EXPERIMENTS_ONE_COLAB_CPU_SESSION"):
        raise ValueError("BLOCKED_MLE_COLAB_SCOPE_OR_COUNTS")
    if (type(status)!=dict or set(status)!={"NUMERIC_DOUBLE_START_CONVERGED","BLOCKED_DOUBLE_START"}
            or sum(status.values())!=CASE_COUNT):
        raise ValueError("BLOCKED_MLE_COLAB_STATUS_TOTAL")
    if type(per_symbol)!=dict or set(per_symbol)!=set(SYMBOLS):
        raise ValueError("BLOCKED_MLE_COLAB_SYMBOL_COUNTS")
    signature=__import__("hashlib").sha256()
    for i,case in enumerate(cases):
        if (type(case)!=dict or case.get("case")!=i
                or case.get("symbol")!=SYMBOLS[i%len(SYMBOLS)]
                or case.get("regime")!=("BALANCED_NULL" if i%2==0 else "DIRECTIONAL_BURST")
                or case.get("input_events")!=7*(16+i%16)
                or case.get("math_status") not in status
                or type(case.get("iterations"))!=list
                or len(case["iterations"])!=2
                or any(type(x)!=int or not 1<=x<=400 for x in case["iterations"])
                or type(case.get("loglik"))!=list or len(case["loglik"])!=2
                or type(case.get("grouped_event_times"))!=int
                or not 1<=case["grouped_event_times"]<=case["input_events"]):
            raise ValueError("BLOCKED_MLE_COLAB_CASE_DETAILS")
        signature.update(canonical(case))
    if (signature.hexdigest()!=obj.get("case_signature_sha256")
            or sum(case["math_status"]=="NUMERIC_DOUBLE_START_CONVERGED" for case in cases)!=status["NUMERIC_DOUBLE_START_CONVERGED"]
            or any(sum(case["symbol"]==s for case in cases)!=per_symbol[s] for s in SYMBOLS)):
        raise ValueError("BLOCKED_MLE_COLAB_PER_RUN_SIGNATURE")
    obj["receipt_sha256"]=digest
    return obj


def main():
    if len(sys.argv)==4 and sys.argv[1]=="verify":
        receipt=parse(Path(sys.argv[2]).read_text(encoding="utf-8"))
        out=Path(sys.argv[3])
        if out.exists():raise ValueError("BLOCKED_MLE_RECEIPT_OVERWRITE")
        out.write_bytes(canonical(receipt)+b"\n")
        print("PASS_100_MLE_RECEIPTS",len(receipt["cases"]),receipt["receipt_sha256"])
    elif len(sys.argv)==4 and sys.argv[1]=="compare":
        left=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        right=json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        if left!=right or parse(MARKER+canonical(left).decode("ascii"))!=left:
            raise ValueError("BLOCKED_MLE_COLAB_REMOTE_MATH_PARITY")
        print("PASS_100_ORIGINAL_VS_CACHED_AND_REMOTE_COLAB_SHA_PARITY",left["receipt_sha256"])
    else:
        raise SystemExit("verify LOG receipt.json | compare local.json remote.json")


if __name__=="__main__":main()
