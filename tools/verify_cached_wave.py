"""Verify immutable aggregate receipt restored from GitHub Actions cache.

Works both as `python tools/verify_cached_wave.py <receipt>` (the exact
workflow invocation) and as `python -m tools.verify_cached_wave <receipt>`.
"""
import json
from pathlib import Path
import sys

if __package__:
    from . import private_wave_colab as protocol
else:
    import private_wave_colab as protocol


def verify(path):
    raw = Path(path).read_text(encoding="utf-8")
    if len(raw) > 10000:
        raise ValueError("BLOCKED_AGGREGATE_RECEIPT_OVERSIZE")
    compact = json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"))
    result = protocol.verify_remote_receipt(protocol.MARKER + compact)
    if result["oos"] is not False or result["status"] != "PASS":
        raise ValueError("BLOCKED_NOT_DISCOVERY_RESULT")
    return result


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("BLOCKED_RECEIPT_PATH_MISSING")
        verify(sys.argv[1])
        print("IDLE_NO_NEW_APPROVED_CANDIDATE")
    except Exception:
        print("BLOCKED_INVALID_CACHED_WAVE_RECEIPT", file=sys.stderr)
        raise SystemExit(1) from None
