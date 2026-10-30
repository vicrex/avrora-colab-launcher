"""Exact 12,000-candidate/64-per-hour frozen shadow sweep batch contract.

No private strategy parameters, source data, credentials or external I/O.
"""
EPOCH_HOUR = 497940
SPACE_SIZE = 12000
PER_BATCH = 64
BATCHES = (SPACE_SIZE + PER_BATCH - 1) // PER_BATCH

def expected_batch_count(hour: int) -> int:
    if type(hour) is not int or hour < EPOCH_HOUR:
        raise ValueError("BLOCKED_SWEEP_INVALID_RESEARCH_HOUR")
    offset = (hour - EPOCH_HOUR) % BATCHES
    return min(PER_BATCH, SPACE_SIZE - offset * PER_BATCH)
