"""AVRORA: 1,000 deterministic CPU research diagnostics in one bounded Colab run.

SYNTHETIC mathematical stress tests only, not 1,000 strategies, maker fills,
real PnL, an authenticated trade stream, CHECK2 or prospective OOS.
Standalone stdlib module so Colab can execute it without a private checkout.
"""
from __future__ import annotations
import hashlib
import json
import math

SCHEMA = "AVRORA_COLAB_THOUSAND_SYNTHETIC_HAWKES_STRESS_V1"
SEED = 20261031
N = 1000
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "LINKUSDT", "NEARUSDT")
DECISION_MS = 1800000
BETA = math.log(2.0) / 60.0
BASE = (0.003, 0.003)
ALPHA = ((0.008, 0.001), (0.001, 0.008))
TOXICITY_THRESHOLD = 0.25


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def pseudorandom(state):
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= state >> 17
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF


def sample(case):
    # Frozen 500 null-balanced and 500 directionally burst-biased paths.
    state = (SEED ^ ((case + 1) * 2654435761)) & 0xFFFFFFFF
    n = 24 + case % 37
    regime = case % 2
    side_bias = (case // 2) % 2
    events = []
    for k in range(n):
        state = pseudorandom(state)
        choice = state % 100
        if not regime:
            aggressive_buy = choice < 50
        else:
            aggressive_buy = choice < (85 if side_bias == 0 else 15)
        state = pseudorandom(state)
        t = 1200000 + k * 6500 + state % 500
        state = pseudorandom(state)
        events.append((t, t + state % 100, 0 if aggressive_buy else 1))
    return events


def _guard(events, decision_ms):
    if type(decision_ms) is not int or decision_ms <= 0:
        raise ValueError("BLOCKED_DECISION_CLOCK")
    prev_event = -1
    prev_recv = -1
    for t, recv, side in events:
        if (type(t) is not int or type(recv) is not int or
                t <= prev_event or recv < t or recv < prev_recv or
                recv >= decision_ms or side not in (0, 1)):
            raise ValueError("BLOCKED_UNVERIFIED_EVENT_ORDER")
        prev_event = t
        prev_recv = recv


def intensity_brute(events, decision_ms):
    _guard(events, decision_ms)
    vals = [BASE[0], BASE[1]]
    for t, _received, side in events:
        decay = math.exp(-BETA * (decision_ms - t) / 1000.0)
        vals[0] += ALPHA[0][side] * decay
        vals[1] += ALPHA[1][side] * decay
    return vals


def intensity_recursive(events, decision_ms):
    _guard(events, decision_ms)
    memory = [0.0, 0.0]
    last = events[0][0] if events else decision_ms
    for t, _received, side in events:
        decay = math.exp(-BETA * (t - last) / 1000.0)
        memory = [v * decay for v in memory]
        memory[side] += 1.0
        last = t
    tail = math.exp(-BETA * (decision_ms - last) / 1000.0)
    return [BASE[i] + tail * sum(ALPHA[i][j] * memory[j]
                                for j in (0, 1)) for i in (0, 1)]


def simulate():
    if (sum(ALPHA[0]) / BETA >= 0.95 or sum(ALPHA[1]) / BETA >= 0.95):
        raise ValueError("BLOCKED_UNSTABLE_FROZEN_PARAMETERS")
    baseline = 0
    burst = 0
    abstain = 0
    by_symbol = {s: 0 for s in SYMBOLS}
    max_difference = 0.0
    future_invariance = 0
    rejected_invalid = 0
    signature = hashlib.sha256()
    for case in range(N):
        symbol = SYMBOLS[case % len(SYMBOLS)]
        events = sample(case)
        normal = intensity_brute(events, DECISION_MS)
        independent_numerical = intensity_recursive(events, DECISION_MS)
        error = max(abs(a-b) for a,b in zip(normal, independent_numerical))
        max_difference = max(max_difference, error)
        if error > 1e-12:
            raise ValueError("BLOCKED_HAWKES_RECURRENCE_MISMATCH")
        # Events received after the decision are unavailable; no contamination.
        future = (DECISION_MS + 1, DECISION_MS + 2, 1)
        known = [e for e in (*events, future) if e[1] < DECISION_MS]
        if known != events or intensity_brute(known, DECISION_MS) != normal:
            raise ValueError("BLOCKED_FUTURE_EVENT_LEAKAGE")
        future_invariance += 1
        # Adversarial clock inversion must be rejected for every case.
        invalid = list(events)
        t, r, side = invalid[0]
        invalid[0] = (t, t-1, side)
        try:
            intensity_brute(invalid, DECISION_MS)
        except ValueError as exc:
            if str(exc) != "BLOCKED_UNVERIFIED_EVENT_ORDER":
                raise
            rejected_invalid += 1
        else:
            raise ValueError("BLOCKED_INVALID_EVENT_ACCEPTED")
        null_path = (case % 2 == 0)
        baseline += int(null_path)
        burst += int(not null_path)
        side = "LONG" if (case // 3) % 2 == 0 else "SHORT"
        signed = (normal[0]-normal[1]) / sum(normal)
        opposing = -signed if side == "LONG" else signed
        abstain += int(opposing >= TOXICITY_THRESHOLD)
        by_symbol[symbol] += 1
        signature.update(canonical([case,symbol,round(signed,12),
                                    int(opposing>=TOXICITY_THRESHOLD)]))
    if (baseline,burst,future_invariance,rejected_invalid)!=(500,500,N,N):
        raise ValueError("BLOCKED_THOUSAND_INCOMPLETE")
    if not all(by_symbol.values()) or sum(by_symbol.values())!=N:
        raise ValueError("BLOCKED_SYMBOL_COVERAGE")
    return {
        "schema": SCHEMA,
        "status": "PASS_SYNTHETIC_MATH_ONLY",
        "requested_synthetic_scenarios": N,
        "completed_synthetic_scenarios": N,
        "null_balanced_scenarios": baseline,
        "directional_burst_scenarios": burst,
        "symbols": list(SYMBOLS),
        "cases_by_symbol": by_symbol,
        "frozen_seed": SEED,
        "recurrence_vs_direct_sum_max_error": round(max_difference, 15),
        "future_invariance_checks": future_invariance,
        "invalid_event_rejections": rejected_invalid,
        "synthetic_abstentions": abstain,
        "scenario_signature_sha256": signature.hexdigest(),
        "real_data_runs": 0,
        "new_verified_strategies": 0,
        "independent_check2": False,
        "oos_proven": False,
        "maker_fill_proven": False,
        "seven_day_model_fit_proven": False,
        "live_trading_authorized": False,
        "real": "OFF", "holdout": "SEALED",
        "scope": "SYNTHETIC_RESEARCH_ONLY_NO_PROFIT_CLAIM",
    }


def main():
    r=simulate()
    r["receipt_sha256"]=sha(canonical(r))
    print("AVRORA_COLAB_THOUSAND_RECEIPT="+canonical(r).decode("ascii"))


if __name__ == "__main__":
    main()
