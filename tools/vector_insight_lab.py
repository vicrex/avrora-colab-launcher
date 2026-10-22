"""AVRORA vector insight forge: immutable, aggregate-only FULL13 experiment learning.

Creates descriptive comparison vectors and an honest idea-only exploration queue.
Does NOT run unreviewed proposals, claim OOS, trade, or access private candles.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys

try:
    from tools import structural_short as engine
    from tools import full13_wave_colab as pin
except ImportError:
    import structural_short as engine
    import full13_wave_colab as pin

SCHEMA = "AVRORA_VECTOR_INSIGHT_DELTA_V1"
GRID_SCHEMA = "AVRORA_VECTOR_IDEA_GRID_PREREG_V1"
COSTS = ("16", "20", "25", "40")
SOURCE = pin.PANEL_GZ_SHA

def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(x):
    return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()

def finite(v):
    return type(v) in (int, float) and math.isfinite(v)

def feature_vector(candidate, params):
    """Dimensions are explicit and versioned, not prose-similarity hallucinations."""
    if candidate not in engine.CANDIDATES:
        raise ValueError("BLOCKED_UNKNOWN_CANDIDATE")
    return {
        "side_short": 1.0,
        "ema_trend_required": float(candidate != "BREAK_ONLY_SHORT_CONTROL_V1"),
        "confirm_retest": float(candidate == "TREND_RETEST_SHORT_V1"),
        "pre_break_squeeze": float(candidate == "SQUEEZE_BREAK_SHORT_V1"),
        "break_atr_scaled": params["break_atr"],
        "body_atr_scaled": params["body_atr"],
        "support_lookback_scaled": params["support_lookback"] / 20.0,
        "exit_time_scaled": params["time_bars"] / 48.0,
        "stop_atr_scaled": params["stop_atr"] / 3.0,
        "reward_r_scaled": params["reward_r"] / 4.0,
        "retest_window_scaled": (
            params["retest_window_bars"] / 16.0 if candidate == "TREND_RETEST_SHORT_V1" else 0.0
        ),
        "squeeze_ratio": (
            params["squeeze_max_range_ratio"] if candidate == "SQUEEZE_BREAK_SHORT_V1" else 0.0
        ),
        "squeeze_window_scaled": (
            params["squeeze_lookback_bars"] / 24.0
            if candidate == "SQUEEZE_BREAK_SHORT_V1" else 0.0
        ),
    }

def distance(a, b):
    if set(a) != set(b) or not a:
        raise ValueError("BLOCKED_VECTOR_DIMENSIONS")
    if any(not finite(x) for x in (*a.values(), *b.values())):
        raise ValueError("BLOCKED_VECTOR_NONFINITE")
    return round(math.sqrt(sum((a[k] - b[k]) ** 2 for k in a)), 9)

def validated_grid(grid):
    if not isinstance(grid, dict) or grid.get("schema") != GRID_SCHEMA:
        raise ValueError("BLOCKED_IDEA_SCHEMA")
    fixed = {"source_panel_sha256": SOURCE, "real": "OFF", "holdout": "SEALED",
             "oos": False, "verification": "PROPOSAL_ONLY_UNEVALUATED",
             "maker_fill_proven": False}
    if any(grid.get(k) != v or type(grid.get(k)) is not type(v) for k, v in fixed.items()):
        raise ValueError("BLOCKED_IDEA_SAFETY")
    candidates = grid.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 12:
        raise ValueError("BLOCKED_IDEA_BUDGET")
    if [c.get("id") for c in candidates] != [f"SQ{i:02d}" for i in range(1, 13)]:
        raise ValueError("BLOCKED_IDEA_IDS")
    unique = set()
    for c in candidates:
        expected = {"id", "range_ratio", "break_atr", "body_atr", "window_bars",
                    "previous_window_bars", "ema_fast", "ema_slow", "stop_atr",
                    "reward_r", "time_bars"}
        if not isinstance(c, dict) or set(c) != expected:
            raise ValueError("BLOCKED_IDEA_FIELDS")
        for field, allowed in {
            "range_ratio": (0.55, 0.70, 0.85),
            "break_atr": (0.05, 0.10),
            "body_atr": (0.25, 0.35),
            "window_bars": (8,), "previous_window_bars": (8,),
            "ema_fast": (20,), "ema_slow": (60,),
            "stop_atr": (1.25,), "reward_r": (1.8,), "time_bars": (12,),
        }.items():
            if not finite(c[field]) or c[field] not in allowed:
                raise ValueError("BLOCKED_IDEA_UNAPPROVED_PARAMETER")
        spec = digest({k: v for k, v in c.items() if k != "id"})
        if spec in unique:
            raise ValueError("BLOCKED_IDEA_DUPLICATE")
        unique.add(spec)
    budget = grid.get("compute_budget", {})
    if budget != {"max_candidates_per_colab_job": 4,
                   "max_candidate_count": 12, "total_candidates": 12,
                   "no_extra_timer": True}:
        raise ValueError("BLOCKED_IDEA_BUDGET")
    return candidates

def summary(c):
    d, aux = c["discovery"], c["may_aux"]
    if not isinstance(d, dict) or not isinstance(aux, dict):
        raise ValueError("BLOCKED_ECONOMICS")
    if len(d.get("by_week", {})) != 12 or set(d.get("by_symbol", {})) != set(pin.SYMBOLS):
        raise ValueError("BLOCKED_INCOMPLETE_COVERAGE")
    cost = d.get("net_by_cost_bps_usdt")
    if not isinstance(cost, dict) or set(cost) != set(COSTS) or any(not finite(cost[k]) for k in COSTS):
        raise ValueError("BLOCKED_COST_STRESS")
    if not (cost["16"] >= cost["20"] >= cost["25"] >= cost["40"]):
        raise ValueError("BLOCKED_COST_MONOTONIC")
    n = d.get("trades")
    if type(n) is not int or n < 0:
        raise ValueError("BLOCKED_TRADE_COUNT")
    rate = n / (84 * 6)
    if abs(rate - d.get("trades_per_symbol_day", -1)) > 0.000002:
        raise ValueError("BLOCKED_FREQUENCY")
    by_week = d["by_week"]
    if any(not finite(x.get("net20_usdt")) for x in by_week.values()):
        raise ValueError("BLOCKED_WEEKS")
    if abs(sum(x["net20_usdt"] for x in by_week.values()) - cost["20"]) > 0.00003:
        raise ValueError("BLOCKED_WEEK_COST_RECONCILIATION")
    splits = d.get("splits")
    if not isinstance(splits, dict) or set(splits) != {"early6", "late6"}:
        raise ValueError("BLOCKED_SPLIT_COVERAGE")
    early, late = splits["early6"], splits["late6"]
    if not finite(early.get("net20_usdt")) or not finite(late.get("net20_usdt")):
        raise ValueError("BLOCKED_SPLIT_ECONOMICS")
    if abs(early["net20_usdt"] + late["net20_usdt"] - cost["20"]) > 0.00003:
        raise ValueError("BLOCKED_SPLIT_MISMATCH")
    ac = aux.get("net_by_cost_bps_usdt", {})
    if not isinstance(ac, dict) or set(ac) != set(COSTS):
        raise ValueError("BLOCKED_AUX_COSTS")
    if any(not finite(ac[k]) for k in COSTS):
        raise ValueError("BLOCKED_AUX_ECONOMICS")
    weeks_positive = sum(x["net20_usdt"] > 0 for x in by_week.values())
    flags = []
    if cost["20"] <= 0: flags.append("NEGATIVE_AFTER_20BPS")
    if cost["25"] <= 0: flags.append("NEGATIVE_AFTER_25BPS")
    if cost["40"] <= 0: flags.append("NEGATIVE_AFTER_40BPS")
    if late["net20_usdt"] <= 0: flags.append("LATE_DISCOVERY_LOSS")
    if ac["20"] <= 0: flags.append("MAY_AUX_LOSS")
    if weeks_positive < 7: flags.append("FEWER_THAN_SEVEN_POSITIVE_DISCOVERY_WEEKS")
    if rate < 4: flags.append("BELOW_FOUR_TRADES_PER_SYMBOL_DAY")
    if early["net20_usdt"] > 0 and late["net20_usdt"] < 0:
        flags.append("EARLY_TO_LATE_DECAY")
    return {
        "trades": n,
        "trades_per_symbol_day": round(rate, 6),
        "net_by_cost_bps_usdt": {k: cost[k] for k in COSTS},
        "net20_usdt_day": round(cost["20"] / 84, 6),
        "positive_discovery_weeks": weeks_positive,
        "early6_net20_usdt": early["net20_usdt"],
        "late6_net20_usdt": late["net20_usdt"],
        "may_aux_net20_usdt": ac["20"],
        "flags": flags,
        "evidence_status": "RETROSPECTIVE_NOT_OOS_NOT_INDEPENDENT_REPLICATION",
    }

def build(receipt, grid):
    # Validate original SHA-pinned model, checker, manifest and full independent
    # ledger receipt before treating any economics as an observed vector.
    engine.verify_receipt(receipt)
    engine_manifest, manifest_sha = engine.load_manifest()
    if receipt.get("manifest_sha256") != manifest_sha:
        raise ValueError("BLOCKED_MANIFEST_MISMATCH")
    validated_grid(grid)
    if receipt.get("independent_check2") != "PASS_ALL_SHORT_SIGNALS_FILLS_AND_EQUITY":
        raise ValueError("BLOCKED_NO_CHECK2")
    if receipt.get("bars") != 69576 or receipt.get("periods") != 13:
        raise ValueError("BLOCKED_FULL13_SCOPE")
    seen = set()
    records = []
    for candidate in engine.CANDIDATES:
        results = receipt.get("results", {})
        if candidate not in results or candidate in seen:
            raise ValueError("BLOCKED_CANDIDATE_SET")
        seen.add(candidate)
        v = feature_vector(candidate, engine_manifest["fixed_parameters"])
        records.append({
            "candidate": candidate,
            "experiment_id": digest({"candidate": candidate,
                                    "manifest_sha256": manifest_sha,
                                    "receipt_sha256": receipt["receipt_sha256"]}),
            "vector": v,
            "outcome": summary(results[candidate]),
            "model_sha256": receipt["primary_sha256"],
            "checker_sha256": receipt["checker_sha256"],
        })
    if set(receipt.get("results", {})) != set(engine.CANDIDATES):
        raise ValueError("BLOCKED_UNDECLARED_CANDIDATE")
    neighbors = []
    for i, a in enumerate(records):
        for b in records[i+1:]:
            neighbors.append({"a": a["candidate"], "b": b["candidate"],
                              "distance": distance(a["vector"], b["vector"]),
                              "delta_net20_usdt": round(
                                  a["outcome"]["net_by_cost_bps_usdt"]["20"]
                                  - b["outcome"]["net_by_cost_bps_usdt"]["20"], 6),
                              "inference": "SAME_USED_DATA_MATCHED_DESCRIPTION_ONLY"})
    neighbors.sort(key=lambda r: (r["distance"], r["a"], r["b"]))
    # No earnings-based choice: all grid ideas are preregistered and pending
    # independent review, no candidate is executable from this JSON.
    ideas = []
    for spec in grid["candidates"]:
        entry = {"idea_id": spec["id"],
                 "identity_sha256": digest(spec),
                 "spec": spec,
                 "state": "PREREG_ONLY_NEEDS_REVIEWED_ADAPTER_AND_CHECK2",
                 "economic_result": None,
                 "oos": False}
        ideas.append(entry)
    output = {
        "schema": SCHEMA,
        "source_panel_sha256": SOURCE,
        "receipt_sha256": receipt["receipt_sha256"],
        "prereg_sha256": manifest_sha,
        "grid_sha256": digest(grid),
        "independent_check2": receipt["independent_check2"],
        "real": "OFF", "holdout": "SEALED", "oos": False,
        "sample": "84_ALREADY_USED_DISCOVERY_DAYS_MAY_AUX_SEPARATE",
        "features_version": "STRUCTURAL_SIGNAL_ATTRIBUTES_V1",
        "records": records, "nearest_pairs": neighbors,
        "ideas": ideas,
        "guardrails": {
            "selection": "DESCRIPTIVE_ONLY_NO_AUTO_WINNER",
            "multiple_testing": "12_GRID_PROPOSALS_NOT_EVALUATED_NO_P_VALUES",
            "same_data_warning": "Candidate comparisons share same consumed data; NOT independent replication",
            "true_oos": "SEALED_DO_NOT_TOUCH",
            "execution": "NO_ORDERS_NO_MAKER_FILL_ASSERTION",
            "next_step": "REVIEW_ADAPTER_AND_CHECK2_BEFORE_RUNNING_GRID",
        },
    }
    output["content_sha256"] = digest(output)
    return output

def main(argv):
    if len(argv) != 1:
        raise ValueError("BLOCKED_USAGE")
    source = Path(argv[0])
    if not source.is_file() or source.stat().st_size > 150000:
        raise ValueError("BLOCKED_RECEIPT_SIZE")
    path = Path(__file__).resolve().parents[1] / "research/vector_squeeze_grid_prereg_v1.json"
    receipt = json.loads(source.read_text(encoding="utf-8"))
    grid = json.loads(path.read_text(encoding="utf-8"))
    report = build(receipt, grid)
    Path("vector_insight_delta.json").write_text(canon(report)+"\n", encoding="utf-8")
    print("AVRORA_VECTOR_INSIGHT_VERIFIED", report["content_sha256"],
          "outcomes", len(report["records"]), "unevaluated_ideas", len(report["ideas"]))

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
        print("BLOCKED_VECTOR_INSIGHT_EVIDENCE", file=sys.stderr)
        raise SystemExit(1) from None
