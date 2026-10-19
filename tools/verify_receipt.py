"""Extract and validate ONLY the harmless smoke marker (no Colab logs in artifacts)."""
import hashlib
import json
import sys
from pathlib import Path

MARKER = "AVRORA_COLAB_SMOKE_RESULT="


def extract(log_text):
    found = []
    for line in log_text.splitlines():
        if MARKER in line:
            raw = line.split(MARKER, 1)[1].strip()
            try:
                found.append(json.loads(raw))
            except json.JSONDecodeError as e:
                raise ValueError("Malformed smoke JSON") from e
    if len(found) != 1:
        raise ValueError(f"Expected exactly one smoke receipt, got {len(found)}")
    data = found[0]
    required = {
        "marker": "AVRORA_COLAB_SMOKE_V1",
        "status": "PASS",
        "mode": "CPU_ONLY_NO_TRADING",
        "orders": 0,
        "source_rows": 0,
        "real": "OFF",
        "holdout": "SEALED",
    }
    if any(data.get(key) != val for key, val in required.items()):
        raise ValueError("Smoke security/format gate failed")
    if data.get("platform") != "Linux":
        raise ValueError("Expected Linux execution on Colab")
    digest = data.get("payload_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("Missing SHA256")
    unhashed = {k: v for k, v in data.items() if k != "payload_sha256"}
    actual = hashlib.sha256(json.dumps(unhashed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if actual != digest:
        raise ValueError("Receipt SHA256 failed")
    return data


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_receipt.py LOG OUTPUT_JSON")
    data = extract(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[2]).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("AVRORA_REMOTE_COLAB_PASS: verified zero orders, zero data rows and receipt SHA256")


if __name__ == "__main__":
    main()
