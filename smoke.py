"""AVRORA public Colab smoke: zero data, zero trading, no credentials."""
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone


def main():
    if os.getenv("REAL", "OFF") != "OFF" or os.getenv("HOLDOUT", "SEALED") != "SEALED":
        raise SystemExit("SAFETY_GATE_FAILED")
    result = {
        "marker": "AVRORA_COLAB_SMOKE_V1",
        "status": "PASS",
        "mode": "CPU_ONLY_NO_TRADING",
        "orders": 0,
        "source_rows": 0,
        "real": "OFF",
        "holdout": "SEALED",
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "utc": datetime.now(timezone.utc).isoformat(),
    }
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    result["payload_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    print("AVRORA_COLAB_SMOKE_RESULT=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
