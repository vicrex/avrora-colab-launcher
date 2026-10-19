"""Run P900 Wave/Fibonacci replay from a dedicated PRIVATE GitHub checkout.

Never reads Google Drive. NEVER prints market data, code, tokens, or Colab output.
Each run verifies original ZIP and CSV SHA256 against frozen historical sources,
patches one known portfolio release-time bug in two independent implementations,
executes on Colab CPU in ephemeral private context, and saves summary-only proof.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import private_wave_colab as engine

SOURCE_PATH = Path("research/WAVE_FIB_01/private_source")
CSV_PARTS = (
    "P900_DISCOVERY_MAY_JUL_2026.csv.b64.part01",
    "P900_DISCOVERY_MAY_JUL_2026.csv.b64.part02",
    "P900_DISCOVERY_MAY_JUL_2026.csv.b64.part03",
)
ZIP_FILE = "AVRORA_WAVE_FIB_20261018.zip.b64"


def read_pinned_inputs(private_dir):
    source = Path(private_dir) / SOURCE_PATH
    encoded_csv = "".join((source / name).read_text(encoding="ascii").strip() for name in CSV_PARTS)
    encoded_zip = (source / ZIP_FILE).read_text(encoding="ascii").strip()
    if len(encoded_csv) != 1005816 or len(encoded_zip) != 80280:
        raise ValueError("BLOCKED_PRIVATE_INPUT_SIZE_MISMATCH")
    csv = base64.b64decode(encoded_csv, validate=True)
    archive = base64.b64decode(encoded_zip, validate=True)
    if len(csv) != 754360 or len(archive) != 60210:
        raise ValueError("BLOCKED_DECODED_SIZE_MISMATCH")
    # This independently checks original SHA256 and all private engine SHA256.
    fixed_source = engine.validate_source(archive, csv)
    return fixed_source, csv


def verify_environment():
    if os.environ.get("REAL", "OFF") != "OFF" or os.environ.get("HOLDOUT", "SEALED") != "SEALED":
        raise ValueError("BLOCKED_REAL_OR_HOLDOUT")
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        raise ValueError("BLOCKED_GOOGLE_COLAB_ADC_ABSENT")


def run_remote(files, csv):
    script = engine.build_remote_script(files, csv)
    with tempfile.TemporaryDirectory(prefix="avrora-private-wave-") as directory:
        home = Path(directory)
        source = home / "private_wave.py"
        log = home / "colab.log"
        source.write_text(script, encoding="utf-8")
        source.chmod(0o600)
        try:
            with log.open("wb") as out:
                result = subprocess.run(
                    ["colab", "--auth=adc", "run", str(source)],
                    stdout=out, stderr=subprocess.STDOUT,
                    timeout=780, check=False,
                    env={**os.environ, "REAL": "OFF", "HOLDOUT": "SEALED"},
                )
        except Exception:
            raise ValueError("BLOCKED_PRIVATE_COLAB_TRANSPORT") from None
        if result.returncode:
            raise ValueError("BLOCKED_PRIVATE_COLAB_RUN_FAILED")
        # Parse only the verified bounded receipt; never expose or upload remote logs.
        return engine.verify_remote_receipt(log.read_text(encoding="utf-8"))


def main():
    try:
        verify_environment()
        checkout = os.environ.get("AVRORA_PRIVATE_CHECKOUT", "")
        if not checkout:
            raise ValueError("BLOCKED_PRIVATE_SOURCE_CHECKOUT_ABSENT")
        files, csv = read_pinned_inputs(checkout)
        report = run_remote(files, csv)
        if not isinstance(report, dict) or report.get("real") != "OFF" or report.get("holdout") != "SEALED":
            raise ValueError("BLOCKED_UNSAFE_REPLAY_REPORT")
        output = Path(os.environ.get("AVRORA_WAVE_SUMMARY_PATH", "wave_research_summary.json"))
        output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print("AVRORA_COLAB_PRIVATE_WAVE_REPLAY_PASS (CHECK2 + SHA256, no orders)")
    except (ValueError, OSError) as exc:
        # Public logs receive only generic status codes, not data/credentials.
        print(str(exc) if str(exc).startswith("BLOCKED_") else "BLOCKED_PRIVATE_WAVE_REPLAY", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
