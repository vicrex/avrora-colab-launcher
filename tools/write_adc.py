"""Create temporary runner-side Google ADC file from protected GitHub Actions secret.
Never print its content, base64, filename with tokens or decoded payload.
"""
import base64
import binascii
import json
import os
import pathlib


def main():
    payload = os.getenv("AVRORA_COLAB_ADC_JSON_B64", "")
    if not payload:
        raise SystemExit("BLOCKED_NO_ADC_SECRET")
    try:
        content = base64.b64decode(payload, validate=True)
        data = json.loads(content)
    except (ValueError, json.JSONDecodeError, binascii.Error) as e:
        raise SystemExit("BLOCKED_MALFORMED_ADC_SECRET") from e
    if not isinstance(data, dict) or data.get("type") != "authorized_user":
        raise SystemExit("BLOCKED_ADC_WRONG_TYPE")
    if not all(isinstance(data.get(k), str) and data[k] for k in ("client_id", "client_secret", "refresh_token")):
        raise SystemExit("BLOCKED_ADC_MISSING_FIELDS")
    path = pathlib.Path(os.environ["RUNNER_TEMP"]) / "avrora_colab_adc.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as handle:
        handle.write("GOOGLE_APPLICATION_CREDENTIALS=" + str(path) + "\n")
    print("GOOGLE_ADC_READY")


if __name__ == "__main__":
    main()
