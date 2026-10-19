"""AVRORA bounded hourly five-wave discovery. No orders, holdout, Drive, or network.
Experiments are frozen in research/hourly_wave_prereg.json BEFORE execution.
All results are discovery on previously consumed P900 May/July M15 data.
"""
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE_SHA = "0a1a913c2ca93951df7ad65b40f3c75b587983f85d1beb818df8787361bc9015"
MARKER = "AVRORA_HOURLY_WAVE_RESULT="
ROOT = Path(__file__).resolve().parents[1]


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def gate():
    if os.getenv("REAL", "OFF") != "OFF" or os.getenv("HOLDOUT", "SEALED") != "SEALED":
        raise ValueError("BLOCKED_UNSAFE_ENVIRONMENT")


def manifest_file():
    return ROOT / "research" / "hourly_wave_prereg.json"


def validate_manifest(m):
    if m.get("schema") != "AVRORA_FIVE_WAVE_DISCOVERY_PREREG_V1":
        raise ValueError("BLOCKED_PREREG_SCHEMA")
    if m.get("source_sha256") != SOURCE_SHA or m.get("oos") is not False:
        raise ValueError("BLOCKED_PREREG_DATA_SCOPE")
    if m.get("real") != "OFF" or m.get("holdout") != "SEALED":
        raise ValueError("BLOCKED_PREREG_SAFETY")
    variants = m.get("candidates")
    if not isinstance(variants, list) or len(variants) != 12:
        raise ValueError("BLOCKED_UNBOUNDED_CATALOG")
    seen = set()
    for row in variants:
        if set(row) != {"id", "wing", "buffer_atr", "wave3_min_ratio", "reward_r", "max_bars"}:
            raise ValueError("BLOCKED_CANDIDATE_FIELDS")
        if not isinstance(row["id"], str) or not row["id"].startswith("FIVE_WAVE_"):
            raise ValueError("BLOCKED_CANDIDATE_ID")
        if row["id"] in seen:
            raise ValueError("BLOCKED_DUPLICATE_CANDIDATE")
        seen.add(row["id"])
        if row["wing"] not in (2, 3) or row["buffer_atr"] not in (0.0, 0.15, 0.3):
            raise ValueError("BLOCKED_UNAPPROVED_PARAMETERS")
        if row["wave3_min_ratio"] not in (0.8, 1.0) or row["reward_r"] not in (1.5, 2.0):
            raise ValueError("BLOCKED_UNAPPROVED_PARAMETERS")
        if row["max_bars"] not in (16, 24):
            raise ValueError("BLOCKED_UNAPPROVED_PARAMETERS")
    return m


def load_manifest(path=None):
    return validate_manifest(json.loads(Path(path or manifest_file()).read_text("utf-8")))


def select(m, hour=None):
    from datetime import datetime, timezone
    if hour is None:
        hour = datetime.now(timezone.utc).hour
    return m["candidates"][int(hour) % len(m["candidates"])]["id"]


def read_data(raw):
    if sha(raw) != SOURCE_SHA:
        raise ValueError("BLOCKED_SOURCE_SHA256")
    series = {}
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        key = (row["period"], row["symbol"])
        series.setdefault(key, []).append((
            int(row["timestamp_ms"]), float(row["open"]), float(row["high"]),
            float(row["low"]), float(row["close"])
        ))
    if sum(map(len, series.values())) != 8064 or len(series) != 12:
        raise ValueError("BLOCKED_DATASET_SHAPE")
    for key, bars in series.items():
        if len(bars) != 672:
            raise ValueError("BLOCKED_PERIOD_ROWS")
        for i, b in enumerate(bars):
            if not (0 < b[3] <= min(b[1], b[4]) <= max(b[1], b[4]) <= b[2]):
                raise ValueError("BLOCKED_BAD_OHLC")
            if i and b[0] - bars[i-1][0] != 900000:
                raise ValueError("BLOCKED_NONCAUSAL_TIME_GRID")
    return series


def atr(bars, i):
    if i < 15:
        return None
    total = 0.0
    for k in range(i-13, i+1):
        _, _, hi, lo, _ = bars[k]
        previous = bars[k-1][4]
        total += max(hi-lo, abs(hi-previous), abs(lo-previous))
    return total/14.0


def signals(bars, p):
    wing = p["wing"]
    pivots = []
    signaled = set()
    found = []
    for i in range(2*wing, len(bars)-1):
        k = i-wing
        hi, lo = bars[k][2], bars[k][3]
        high_p = all(hi > bars[j][2] for j in range(k-wing, k+wing+1) if j != k)
        low_p = all(lo < bars[j][3] for j in range(k-wing, k+wing+1) if j != k)
        if high_p != low_p:
            typ, price = ("H", hi) if high_p else ("L", lo)
            item = (typ, k, price, i)
            if pivots and pivots[-1][0] == typ:
                old = pivots[-1]
                if (typ == "H" and price > old[2]) or (typ == "L" and price < old[2]):
                    pivots[-1] = item
            else:
                pivots.append(item)
                if len(pivots) > 6:
                    pivots.pop(0)
        if len(pivots) != 6:
            continue
        a = atr(bars, i)
        if not a or a <= 0:
            continue
        for side, types in ((1, ("L","H","L","H","L","H")),
                            (-1, ("H","L","H","L","H","L"))):
            if tuple(q[0] for q in pivots) != types:
                continue
            key = (side, pivots[-1][1])
            if key in signaled or i > pivots[-1][3]+8:
                continue
            v = [q[2] for q in pivots]
            w1, w3, w5 = side*(v[1]-v[0]), side*(v[3]-v[2]), side*(v[5]-v[4])
            if min(w1, w3, w5) <= 0 or w3 < p["wave3_min_ratio"]*w1:
                continue
            if w3 + 1e-12 < min(w1, w5):
                continue
            if not (side*(v[2]-v[0]) > 0 and side*(v[4]-v[1]) > 0):
                continue
            if side*(bars[i][4]-v[5]) <= p["buffer_atr"]*a:
                continue
            found.append({"signal_i": i, "entry_i": i+1, "side": side,
                          "p4": v[4], "pivot5_confirm_i": pivots[-1][3],
                          "signal_t": bars[i][0], "atr": a})
            signaled.add(key)
    return found


def simulate_one(bars, s, p):
    j = s["entry_i"]
    entry = bars[j][1]
    side = s["side"]
    stop = s["p4"]
    distance = side*(entry-stop)
    if not 0 < distance < entry*0.12:
        return None
    notional = min(500.0, 5.0*entry/distance)
    if notional < 1.0:
        return None
    target = entry + side*p["reward_r"]*distance
    end = min(len(bars)-1, j+p["max_bars"])
    exit_price, exit_i, reason = bars[end][4], end, "TIME"
    for k in range(j, end+1):
        _, op, hi, lo, _ = bars[k]
        # Gap through stop is filled at the worse open, not ideal stop.
        if side*(op-stop) <= 0:
            exit_price, exit_i, reason = op, k, "GAP_STOP"
            break
        if (lo <= stop if side == 1 else hi >= stop):
            exit_price, exit_i, reason = stop, k, "STOP_FIRST"
            break
        if (hi >= target if side == 1 else lo <= target):
            exit_price, exit_i, reason = target, k, "TARGET"
            break
    gross = notional*side*(exit_price-entry)/entry
    return {
        "entry_t": bars[j][0], "exit_t": bars[exit_i][0],
        "entry": entry, "exit": exit_price, "side": side, "reason": reason,
        "signal_t": s["signal_t"], "p5_confirm_t": bars[s["pivot5_confirm_i"]][0],
        "stop_risk": notional*distance/entry, "notional": notional,
        "gross": gross, "net20": gross-0.0020*notional,
        "net25": gross-0.0025*notional
    }


def check_trades(trades):
    # Separate arithmetic and portfolio consistency check, not a second signal engine.
    for idx, t in enumerate(trades):
        if not (t["p5_confirm_t"] <= t["signal_t"] < t["entry_t"] <= t["exit_t"]):
            raise ValueError("BLOCKED_FUTURE_BAR_LEAKAGE")
        if t["notional"] > 500.000001 or t["stop_risk"] > 5.000001:
            raise ValueError("BLOCKED_RISK_LIMIT")
        gross = t["notional"]*t["side"]*(t["exit"]/t["entry"]-1)
        if abs(gross-t["gross"]) > 1e-7:
            raise ValueError("BLOCKED_GROSS_PARITY")
        if abs(t["net20"]-(gross-t["notional"]*0.0020)) > 1e-7:
            raise ValueError("BLOCKED_FEE20_PARITY")
        if abs(t["net25"]-(gross-t["notional"]*0.0025)) > 1e-7:
            raise ValueError("BLOCKED_FEE25_PARITY")
        overlapping = [x for x in trades[:idx] if x["entry_t"] <= t["entry_t"] <= x["exit_t"]]
        if len(overlapping) >= 2:
            raise ValueError("BLOCKED_PORTFOLIO_OVERLAP")
        if any(x["symbol"] == t["symbol"] for x in overlapping):
            raise ValueError("BLOCKED_DUPLICATE_SYMBOL")


def evaluate(raw, m, candidate_id):
    gate()
    series = read_data(raw)
    candidate = next((p for p in m["candidates"] if p["id"] == candidate_id), None)
    if candidate is None:
        raise ValueError("BLOCKED_UNREGISTERED_CANDIDATE")
    proposals = []
    for (period, symbol), bars in sorted(series.items()):
        for s in signals(bars, candidate):
            proposals.append((s["signal_t"], symbol, period, bars, s))
    # Deterministic global 2-slot portfolio, exit releases at M15 candle close.
    proposals.sort(key=lambda x:(x[0],x[1],x[2]))
    ledger = []
    for _, symbol, period, bars, signal in proposals:
        trade = simulate_one(bars, signal, candidate)
        if trade is None:
            continue
        live = [x for x in ledger if x["entry_t"] <= trade["entry_t"] <= x["exit_t"]]
        if len(live) >= 2 or any(x["symbol"] == symbol for x in live):
            continue
        trade.update(symbol=symbol, period=period)
        ledger.append(trade)
    check_trades(ledger)
    # Independent signal AND complete global portfolio parity; fail closed.
    if __package__:
        from . import hourly_wave_check2 as check2
    else:
        import hourly_wave_check2 as check2
    parity = check2.verify_all(series, candidate, proposals, ledger)
    if parity["check2"] != "PASS_FULL_SIGNAL_AND_LEDGER_PARITY":
        raise ValueError("BLOCKED_CHECK2_PARITY")
    positives = sum(t["net20"] for t in ledger if t["net20"]>0)
    negatives = -sum(t["net20"] for t in ledger if t["net20"]<0)
    net20 = sum(t["net20"] for t in ledger)
    net25 = sum(t["net25"] for t in ledger)
    pf = positives/negatives if negatives else None
    rate = len(ledger)/(6*14)
    passed = len(ledger)>=30 and net20>0 and net25>0 and pf is not None and pf>1.2 and rate>=4
    receipt = {
        "schema":"AVRORA_FIVE_WAVE_DISCOVERY_RESULT_V1",
        "engine_sha256":sha(Path(__file__).read_bytes()),
        "checker_sha256":sha((Path(__file__).parent/"hourly_wave_check2.py").read_bytes()),
        "status":"PASS_REPRODUCIBLE_DISCOVERY" if ledger else "PASS_NO_TRADES",
        "promotion":"RESEARCH_ONLY_NEVER_LIVE", "candidate":candidate_id,
        "candidate_sha256":sha(canonical(candidate).encode()),
        "manifest_sha256":sha(canonical(m).encode()), "source_sha256":SOURCE_SHA,
        "source_rows":8064, "real":"OFF", "holdout":"SEALED", "oos":False,
        "independent_signal_parity":True, "check2":parity["check2"], "maker_fill_proven":False,
        "funding_modeled":False, "slippage_modeled":False,
        "proposals":len(proposals), "closed_trades":len(ledger),
        "trades_per_symbol_day":round(rate,6),
        "net20_usdt":round(net20,6), "net25_usdt":round(net25,6),
        "pf20":round(pf,6) if pf is not None else None,
        "decision":"RESEARCH_REVIEW_REQUIRED" if passed else "REJECT_DISCOVERY",
    }
    receipt["receipt_sha256"] = sha(canonical(receipt).encode())
    return receipt


def verify_receipt(text, m, candidate_id):
    matched = [line.split(MARKER,1)[1] for line in text.splitlines() if MARKER in line]
    if len(matched) != 1:
        raise ValueError("BLOCKED_MISSING_OR_DUPLICATE_RECEIPT")
    receipt = json.loads(matched[0])
    digest = receipt.pop("receipt_sha256", "")
    if sha(canonical(receipt).encode()) != digest:
        raise ValueError("BLOCKED_RECEIPT_INTEGRITY")
    candidate = next((p for p in m["candidates"] if p["id"] == candidate_id), None)
    if candidate is None or receipt.get("candidate_sha256") != sha(canonical(candidate).encode()):
        raise ValueError("BLOCKED_CANDIDATE_MISMATCH")
    if receipt.get("manifest_sha256") != sha(canonical(m).encode()):
        raise ValueError("BLOCKED_PREREG_MISMATCH")
    for key,value in (("engine_sha256",sha(Path(__file__).read_bytes())),
                      ("checker_sha256",sha((Path(__file__).parent/"hourly_wave_check2.py").read_bytes())),
                      ("candidate",candidate_id),("source_sha256",SOURCE_SHA),
                      ("source_rows",8064),("real","OFF"),("holdout","SEALED"),
                      ("oos",False),("promotion","RESEARCH_ONLY_NEVER_LIVE"),
                      ("independent_signal_parity",True),
                      ("check2","PASS_FULL_SIGNAL_AND_LEDGER_PARITY")):
        if receipt.get(key)!=value:
            raise ValueError("BLOCKED_RECEIPT_SCOPE_"+key)
    if receipt.get("decision") not in ("REJECT_DISCOVERY","RESEARCH_REVIEW_REQUIRED"):
        raise ValueError("BLOCKED_UNAPPROVED_DECISION")
    if receipt.get("status") not in ("PASS_REPRODUCIBLE_DISCOVERY","PASS_NO_TRADES"):
        raise ValueError("BLOCKED_UNAPPROVED_STATUS")
    for field in ("closed_trades","proposals"):
        if not isinstance(receipt.get(field),int) or receipt[field]<0:
            raise ValueError("BLOCKED_INVALID_METRIC")
    receipt["receipt_sha256"]=digest
    return receipt


def build_remote_script(raw, m, candidate_id):
    # Script/data exists only in runner temporary filesystem and the private Colab VM.
    self_code = Path(__file__).read_bytes()
    checker_code = (Path(__file__).parent/"hourly_wave_check2.py").read_bytes()
    manifest_raw = canonical(m).encode()
    return (
        "import base64,os,pathlib,subprocess,sys,tempfile\n"
        "if os.getenv('REAL','OFF')!='OFF' or os.getenv('HOLDOUT','SEALED')!='SEALED':\n"
        " raise SystemExit('BLOCKED_SAFETY_GATE')\n"
        "with tempfile.TemporaryDirectory(prefix='avrora-wave-study-') as d:\n"
        " p=pathlib.Path(d)\n"
        + " (p/'model.py').write_bytes(base64.b64decode("+repr(base64.b64encode(self_code).decode())+"))\n"
        + " (p/'hourly_wave_check2.py').write_bytes(base64.b64decode("+repr(base64.b64encode(checker_code).decode())+"))\n"
        + " (p/'data.csv').write_bytes(base64.b64decode("+repr(base64.b64encode(raw).decode())+"))\n"
        + " (p/'manifest.json').write_bytes(base64.b64decode("+repr(base64.b64encode(manifest_raw).decode())+"))\n"
        + " r=subprocess.run([sys.executable,'model.py','evaluate','data.csv','manifest.json',"+repr(candidate_id)+"],cwd=p,capture_output=True,text=True,timeout=210)\n"
        + " if r.returncode: raise SystemExit('BLOCKED_CAUSAL_EVALUATION')\n"
        + " if r.stdout.count('"+MARKER+"')!=1: raise SystemExit('BLOCKED_RESULT_SHAPE')\n"
        + " print(r.stdout.strip(),flush=True)\n"
    )


def remote_run(raw, m, candidate_id):
    script = build_remote_script(raw, m, candidate_id)
    with tempfile.TemporaryDirectory(prefix="avrora-hourly-wave-") as d:
        path = Path(d)/"research.py"
        log = Path(d)/"colab.log"
        path.write_text(script, encoding="utf-8")
        path.chmod(0o600)
        with log.open("wb") as sink:
            proc = subprocess.run(["colab","--auth=adc","run",str(path)],
                                  stdout=sink, stderr=subprocess.STDOUT,
                                  timeout=780, env={**os.environ,"REAL":"OFF","HOLDOUT":"SEALED"})
        if proc.returncode:
            raise ValueError("BLOCKED_PRIVATE_COLAB_RESEARCH")
        return verify_receipt(log.read_text("utf-8"),m,candidate_id)


def main():
    gate()
    if len(sys.argv)<2:
        raise ValueError("BLOCKED_MISSING_MODE")
    mode = sys.argv[1]
    if mode=="select":
        print("id="+select(load_manifest()))
        return
    if mode=="evaluate":
        if len(sys.argv)!=5:
            raise ValueError("BLOCKED_EVALUATE_ARGS")
        raw=Path(sys.argv[2]).read_bytes()
        m=load_manifest(sys.argv[3])
        result=evaluate(raw,m,sys.argv[4])
        print(MARKER+canonical(result))
        return
    if mode=="verify":
        if len(sys.argv)!=4:
            raise ValueError("BLOCKED_VERIFY_ARGS")
        m=load_manifest()
        verify_receipt(MARKER+Path(sys.argv[2]).read_text("utf-8").strip(),m,sys.argv[3])
        print("IDLE_NO_NEW_APPROVED_CANDIDATE")
        return
    if mode=="run":
        if len(sys.argv)!=3:
            raise ValueError("BLOCKED_RUN_ARGS")
        candidate_id=sys.argv[2]
        m=load_manifest()
        if not any(x["id"]==candidate_id for x in m["candidates"]):
            raise ValueError("BLOCKED_UNREGISTERED_CANDIDATE")
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("BLOCKED_COLAB_AUTH_ABSENT")
        checkout=os.environ.get("AVRORA_PRIVATE_CHECKOUT")
        if not checkout:
            raise ValueError("BLOCKED_READONLY_SOURCE_ABSENT")
        from run_private_wave_checkout import read_pinned_inputs
        _,raw=read_pinned_inputs(checkout)
        result=remote_run(raw,m,candidate_id)
        out=Path("hourly_research_receipt.json")
        out.write_text(canonical(result)+"\n","utf-8")
        print("AVRORA_HOURLY_DISCOVERY_PASS_AGGREGATE_ONLY")
        return
    raise ValueError("BLOCKED_UNKNOWN_MODE")


if __name__=="__main__":
    try:
        main()
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        # Never print private code, data, Google credentials or remote logs.
        message=str(exc)
        print(message if message.startswith("BLOCKED_") else "BLOCKED_HOURLY_RESEARCH",file=sys.stderr)
        raise SystemExit(1) from None
