"""Parse only SHA-valid synthetic Colab receipts; never echo remote logs."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from tools.avrora_thousand_colab import N, SCHEMA, canonical, sha

MARKER="AVRORA_COLAB_THOUSAND_RECEIPT="


def parse(text):
    lines=[x.split(MARKER,1)[1] for x in text.splitlines() if MARKER in x]
    if len(lines)!=1:
        raise ValueError("BLOCKED_COLAB_THOUSAND_MISSING_OR_DUPLICATE")
    obj=json.loads(lines[0])
    digest=obj.pop("receipt_sha256","")
    if sha(canonical(obj))!=digest:
        raise ValueError("BLOCKED_COLAB_THOUSAND_RECEIPT_SHA")
    if (obj.get("schema")!=SCHEMA or
        obj.get("status")!="PASS_SYNTHETIC_MATH_ONLY" or
        obj.get("completed_synthetic_scenarios")!=N or
        obj.get("future_invariance_checks")!=N or
        obj.get("invalid_event_rejections")!=N or
        obj.get("null_balanced_scenarios")!=500 or
        obj.get("directional_burst_scenarios")!=500 or
        obj.get("real_data_runs")!=0 or
        obj.get("new_verified_strategies")!=0 or
        obj.get("independent_check2") is not False or
        obj.get("maker_fill_proven") is not False or
        obj.get("oos_proven") is not False or
        obj.get("live_trading_authorized") is not False or
        obj.get("real")!="OFF" or obj.get("holdout")!="SEALED" or
        obj.get("scope")!="SYNTHETIC_RESEARCH_ONLY_NO_PROFIT_CLAIM"):
        raise ValueError("BLOCKED_COLAB_THOUSAND_FALSE_PROOF")
    obj["receipt_sha256"]=digest
    return obj


def main():
    if len(sys.argv)==4 and sys.argv[1]=="verify":
        result=parse(Path(sys.argv[2]).read_text("utf8"))
        dest=Path(sys.argv[3])
        if dest.exists():
            raise ValueError("BLOCKED_COLAB_THOUSAND_OVERWRITE")
        dest.write_bytes(canonical(result)+b"\n")
        print("PASS_THOUSAND_SYNTHETIC_RECEIPT",result["completed_synthetic_scenarios"],result["receipt_sha256"])
    elif len(sys.argv)==4 and sys.argv[1]=="compare":
        a=json.loads(Path(sys.argv[2]).read_text("utf8"))
        b=json.loads(Path(sys.argv[3]).read_text("utf8"))
        if a!=b or parse(MARKER+canonical(a).decode())!=a:
            raise ValueError("BLOCKED_LOCAL_REMOTE_NUMERIC_DIVERGENCE")
        print("PASS_THOUSAND_LOCAL_COLAB_SHA_PARITY",a["receipt_sha256"])
    else:
        raise SystemExit("usage: verify LOG RECEIPT.json | compare LOCAL.json REMOTE.json")


if __name__=="__main__":
    main()
