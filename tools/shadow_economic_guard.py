"""Aggregate-only historical shadow cost/frequency guard. Never a trade selector.

The 12,000-variant P816 discovery grid reuses six validation weeks. A batch
must never be labeled executable based on training/validation profit alone.
No candidate IDs, private configuration or PnL values leave this module.
"""
from __future__ import annotations

import math

from .strategy_vector48 import check_report, split_features

COST_BPS = (16, 20, 25, 40)
VALIDATION_WEEKS = 6
DAYS_PER_WEEK = 7
SYMBOL_COUNT = 6
MIN_TRADES_PER_SYMBOL_DAY = 4
MIN_TOTAL_VALIDATION_TRADES = (
    VALIDATION_WEEKS * DAYS_PER_WEEK * SYMBOL_COUNT
    * MIN_TRADES_PER_SYMBOL_DAY
)


def _split(model, field):
    split = model.get(field)
    if not isinstance(split, dict):
        raise ValueError("BLOCKED_SHADOW_SPLIT")
    split_features(split, field)  # Check independent gross/net20 and week-count parity.
    for key in ("gross_usdt", "notional_sum", "net20_usdt"):
        value = split.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("BLOCKED_SHADOW_COST_NONFINITE")
    if split["notional_sum"] < 0:
        raise ValueError("BLOCKED_SHADOW_NEGATIVE_NOTIONAL")
    return split


def _net(split, bps):
    return split["gross_usdt"] - bps * 0.0001 * split["notional_sum"]


def audit_report(report, expected_count=64):
    """Publicly releasable aggregated guard only; requires verified private receipt."""
    check_report(report, expected_count)
    results = {str(bps): 0 for bps in COST_BPS}
    freq = 0
    jointly_eligible = 0
    for model in report["models"]:
        train = _split(model, "train")
        validation = _split(model, "validation")
        is_frequency_possible = validation["trades"] >= MIN_TOTAL_VALIDATION_TRADES
        freq += int(is_frequency_possible)
        for bps in COST_BPS:
            results[str(bps)] += int(_net(train, bps) > 0 and _net(validation, bps) > 0)
        jointly_eligible += int(
            is_frequency_possible
            and _net(train, 40) > 0 and _net(validation, 40) > 0
        )
    summary = report.get("summaries")
    if (not isinstance(summary, dict)
            or type(summary.get("train_and_validation_positive")) is not int
            or summary["train_and_validation_positive"] != results["20"]):
        raise ValueError("BLOCKED_SHADOW_AGGREGATE_PARITY")
    if not (results["16"] >= results["20"] >= results["25"] >= results["40"]):
        raise ValueError("BLOCKED_SHADOW_COST_MONOTONIC")
    return {
        "schema": "AVRORA_SHADOW_ECONOMIC_GUARD_V1",
        "count": expected_count,
        "dual_positive_both_reused_splits_by_bps": results,
        "minimum_aggregate_validation_trades_for_4_per_symbol_day": MIN_TOTAL_VALIDATION_TRADES,
        "models_reaching_necessary_total_frequency": freq,
        "models_reaching_40bps_and_frequency": jointly_eligible,
        "frequency_condition_is_necessary_not_sufficient": True,
        "scope": "HISTORICAL_REUSED_VALIDATION_NOT_FIRST_SEEN_OOS",
        "decision": "RESEARCH_ONLY_NO_PROMOTION",
        "reason": "NO_INDEPENDENT_CHECK2_NO_PROVEN_OOS_OR_MAKER_EXECUTION",
        "real": "OFF",
        "holdout": "SEALED",
        "live_trading_authorized": False,
    }
