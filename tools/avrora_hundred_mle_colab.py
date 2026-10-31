"""100 distinct exact private HAWKES01 seven-day double-start MLE fits: real temporal bursts.

Standalone runner executes ONLY source from an immutable, runner-built zip.
One actual remote Colab CPU execution holds 100 separate MLE research cases;
it is NOT 100 separately allocated Colab sessions or real market data.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import zipfile

SCHEMA = "AVRORA_COLAB_100_SEVEN_DAY_DOUBLE_START_MLE_V1"
MARKER = "AVRORA_COLAB_HUNDRED_MLE_RECEIPT="
CASE_COUNT = 100
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "LINKUSDT", "NEARUSDT")
PRIVATE_HEAD = "46d70a9c7d81f53959d0f12a5fce6db856624983"
SOURCE_ZIP_B64 = "__SOURCE_ZIP_B64__"
FILES = (
    "research/__init__.py",
    "research/strategy_search/__init__.py",
    "research/strategy_search/hawkes01.py",
    "research/strategy_search/hawkes01_fit.py",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prng(seed):
    x = seed & 0xFFFFFFFF
    while True:
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        yield x & 0xFFFFFFFF


def build_case(index, f):
    if type(index) is not int or not 0 <= index < CASE_COUNT:
        raise ValueError("BLOCKED_COLAB_MLE_CASE_INDEX")
    asof = 20_000 * f.DAY_MS
    start = asof - 7 * f.DAY_MS
    size = 16 + index % 16
    regime = "BALANCED_NULL" if index % 2 == 0 else "DIRECTIONAL_BURST"
    burst_side = index // 2 % 2
    rng = prng(20261031 ^ ((index + 1) * 2654435761))
    data = []
    for d in range(7):
        for j in range(size):
            if regime == "DIRECTIONAL_BURST":
                # Independent null vs *temporal* burst: genuine 1.8s spacing,
                # two 30s clusters every UTC day, well inside fixed 60s half-life.
                first_count = size // 2
                group = 0 if j < first_count else 1
                within = j if group == 0 else j - first_count
                timestamp = (start + d * f.DAY_MS
                             + (6 if group == 0 else 18) * 3600000
                             + within * 1800)
            else:
                timestamp = start + d * f.DAY_MS + (j + 1) * f.DAY_MS // (size + 2)
                if index % 4 == 0 and j % 5 == 4:
                    timestamp = data[-1]["event_ms"]
            draw = next(rng) % 100
            probability = (50 if regime == "BALANCED_NULL"
                           else (80 if burst_side == 0 else 20))
            data.append({
                "trade_id": f"synthetic-{index}-{d}-{j}",
                "event_ms": timestamp,
                "received_ms": timestamp,
                "aggressor": "BUY" if draw < probability else "SELL",
            })
    return data, asof, regime


def _frozen_modules(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    names = z.namelist()
    if len(names) != len(FILES) or set(names) != set(FILES):
        raise ValueError("BLOCKED_COLAB_MLE_BUNDLE_SHAPE")
    if any(z.getinfo(name).file_size > 16000 for name in names):
        raise ValueError("BLOCKED_COLAB_MLE_BUNDLE_SIZE")
    return z


def run(bundle):
    cases = []
    statuses = {"NUMERIC_DOUBLE_START_CONVERGED": 0, "BLOCKED_DOUBLE_START": 0}
    signature = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix="avrora_hawkes_100_") as tmp:
        root = Path(tmp)
        with _frozen_modules(bundle) as archive:
            for name in FILES:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(archive.read(name))
        sys.path.insert(0, tmp)
        try:
            from research.strategy_search import hawkes01_fit as f
            from research.strategy_search import hawkes01 as h
            if (f.SEVEN_DAYS != 7 or f.PERIOD_SECONDS != 604800
                    or len(f.STARTS) != 2 or f.MAX_ITER != 400
                    or not 0.011 < h.BETA < 0.012
                    or h.PREREG != "HAWKES01_SIGNED_TRADE_INTENSITY_GATE_20261026"):
                raise ValueError("BLOCKED_COLAB_MLE_FROZEN_PREREG")
            for index in range(CASE_COUNT):
                events, asof, regime = build_case(index, f)
                # Original double-start implementation is the independent oracle.
                baseline = f.fit_math(events, asof)
                trace, exposure, counts = f.prepare(events, asof)
                faster = f.fit_prepared(trace, exposure, counts, asof,
                                        reuse_em=True)
                if baseline != faster:
                    raise ValueError("BLOCKED_COLAB_MLE_EM_CACHE_PARITY")
                if (baseline["input_trade_count"] != len(events)
                        or baseline["fixed_initializations"] != 2
                        or baseline["model_eligible_for_signal"] is not False
                        or baseline["model_eligible_for_trade"] is not False
                        or baseline["first_seen_proven"] is not False
                        or baseline["independent_check2"] is not False
                        or baseline["real"] != "OFF"
                        or baseline["holdout"] != "SEALED"):
                    raise ValueError("BLOCKED_COLAB_MLE_FALSE_MARKET_PROOF")
                # Ensure a future-data injection cannot pass the strict asof guard.
                contaminated = dict(events[-1])
                contaminated["trade_id"] = f"future-{index}"
                contaminated["event_ms"] = asof
                contaminated["received_ms"] = asof
                try:
                    f.prepare([*events, contaminated], asof)
                except ValueError as exc:
                    if "SEVEN_DAY_WINDOW" not in str(exc):
                        raise
                else:
                    raise ValueError("BLOCKED_COLAB_MLE_ACCEPTED_FUTURE_TRADE")
                status = baseline["fit_math_status"]
                if status not in statuses:
                    raise ValueError("BLOCKED_COLAB_MLE_UNEXPECTED_STATUS")
                statuses[status] += 1
                c = {
                    "case": index,
                    "symbol": SYMBOLS[index % len(SYMBOLS)],
                    "regime": regime,
                    "input_events": len(events),
                    "grouped_event_times": len(trace),
                    "iterations": baseline["iterations"],
                    "loglik": baseline["loglik"],
                    "math_status": status,
                    "oracle_vs_cached_report_sha": baseline["content_sha256"],
                }
                c["nontrivial_em_iterations"] = any(x > 2 for x in c["iterations"])
                if any(x < 0 or x > f.MAX_ITER for x in c["iterations"]):
                    raise ValueError("BLOCKED_COLAB_MLE_ITERATION_COUNT")
                signature.update(canonical(c))
                cases.append(c)
        finally:
            sys.path.remove(tmp)
            for module in tuple(sys.modules):
                if module == "research" or module.startswith("research."):
                    del sys.modules[module]
    if len(cases) != CASE_COUNT or sum(statuses.values()) != CASE_COUNT:
        raise ValueError("BLOCKED_COLAB_MLE_RUN_COUNT")
    burst_nontrivial = sum(
        c["nontrivial_em_iterations"]
        for c in cases if c["regime"] == "DIRECTIONAL_BURST"
    )
    if burst_nontrivial < 40:
        raise ValueError("BLOCKED_COLAB_MLE_WEAK_TEMPORAL_BURSTS")
    if {case["symbol"] for case in cases} != set(SYMBOLS):
        raise ValueError("BLOCKED_COLAB_MLE_SYMBOL_COVERAGE")
    report = {
        "schema": SCHEMA,
        "status": "PASS_100_COMPLETED_MATH_RESEARCH_RUNS",
        "private_source_sha": PRIVATE_HEAD,
        "private_source_bundle_sha256": sha(bundle),
        "completed_seven_day_mle_runs": CASE_COUNT,
        "two_frozen_initializations_per_run": True,
        "total_mle_starts": CASE_COUNT * 2,
        "original_vs_cached_exact_parity_runs": CASE_COUNT,
        "future_time_rejections": CASE_COUNT,
        "cases_by_symbol": {sym: sum(c["symbol"] == sym for c in cases)
                            for sym in SYMBOLS},
        "temporal_burst_cases": 50,
        "temporal_burst_cases_with_gt2_iterations": burst_nontrivial,
        "statuses": statuses,
        "case_signature_sha256": signature.hexdigest(),
        "cases": cases,
        "actual_colab_cli_sessions": 1,
        "synthetic_event_data": True,
        "real_market_events_processed": 0,
        "provider_completeness_proven": False,
        "historical_first_seen_proven": False,
        "independent_check2": False,
        "prospective_oos_proven": False,
        "maker_fill_proven": False,
        "strategies_proven_profitable": 0,
        "live_trading_authorized": False,
        "real": "OFF", "holdout": "SEALED",
        "scope": "100_INDEPENDENT_SYNTHETIC_DOUBLE_START_MLE_EXPERIMENTS_ONE_COLAB_CPU_SESSION",
    }
    report["receipt_sha256"] = sha(canonical(report))
    return report


def main():
    try:
        blob = base64.b64decode(SOURCE_ZIP_B64, validate=True)
    except Exception as exc:
        raise ValueError("BLOCKED_COLAB_MLE_UNPACK_SOURCE") from exc
    if len(blob) > 45000:
        raise ValueError("BLOCKED_COLAB_MLE_OVERSIZE_PRIVATE_SOURCE")
    r = run(blob)
    print(MARKER + canonical(r).decode("ascii"), flush=True)


if __name__ == "__main__":
    main()
