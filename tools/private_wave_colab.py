"""Pure WAV-FIB/01 source SHA256 gate and Colab payload/receipt verification.

NO Google Drive API; NO GitHub API; NO credentials. Called only after a dedicated
private repository is checked out via an encrypted, read-only GitHub deploy key.
"""
import base64
import hashlib
import io
import json
import zipfile

CSV_SHA = "0a1a913c2ca93951df7ad65b40f3c75b587983f85d1beb818df8787361bc9015"
ZIP_SHA = "e1e4e9ed00e4a22fd81b498e6f5ef9dd899014ffda1560fedb038e01e5bc96be"
SOURCE_HASHES = {
    "engine.py": "8bcdda7077b52675510adfd55327d9ea808b21c30c655dc6b5e7b3f6058f99c2",
    "check2_independent.py": "1f9a2a25f0e72f90760e7f284ad03bf0e49db81e84123cf52b7b25b3da7d3be6",
    "tests.py": "ad8ade66876222f41af5f5d3ca5798a0b0bc6d126808c6fbfde81d14665f0417",
}
PATCHES = {
    "engine.py": ("q['exit_t']>x['entry_t']", "(q['exit_t']+900000)>x['entry_t']"),
    "check2_independent.py": ("a['exit_t']>p['entry_t']", "(a['exit_t']+900000)>p['entry_t']"),
}
MARKER = "AVRORA_PRIVATE_WAVE_RESULT="
EXPECTED = {
    "WAVE_123_CONFIRM": {"accepted": 32, "net20_usdt": -26.458036},
    "FIB_618_RETRACE": {"accepted": 106, "net20_usdt": -88.815211},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_source(raw_zip, raw_csv):
    if sha(raw_zip) != ZIP_SHA or sha(raw_csv) != CSV_SHA:
        raise ValueError("BLOCKED_PRIVATE_SOURCE_HASH_MISMATCH")
    files = {}
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        for name, expected in SOURCE_HASHES.items():
            data = archive.read(name)
            if sha(data) != expected:
                raise ValueError("BLOCKED_PRIVATE_ENGINE_HASH_MISMATCH")
            files[name] = data.decode("utf-8")
    for name, (before, after) in PATCHES.items():
        if files[name].count(before) != 1:
            raise ValueError("BLOCKED_PORTFOLIO_PATCH_MISMATCH")
        files[name] = files[name].replace(before, after)
    return files


def build_remote_script(files, raw_csv):
    """Creates a script entirely on transient runner; not checked into Git."""
    raw_zip = io.BytesIO()
    with zipfile.ZipFile(raw_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items():
            z.writestr(name, body)
        z.writestr("input.csv", raw_csv)
    b64 = base64.b64encode(raw_zip.getvalue()).decode("ascii")
    expected = json.dumps(EXPECTED, sort_keys=True)
    payload = StringTemplate.replace("__BUNDLE__", b64).replace("__EXPECTED__", expected)
    return payload


StringTemplate = r'''# AUTO-GENERATED IN EPHEMERAL RUNNER — PRIVATE WAVES & DATA; NEVER COMMIT.
import base64,hashlib,io,json,os,pathlib,subprocess,sys,tempfile,zipfile
if os.getenv("REAL","OFF")!="OFF" or os.getenv("HOLDOUT","SEALED")!="SEALED":
    raise SystemExit("BLOCKED_SAFETY_GATE")
bundle=base64.b64decode("__BUNDLE__")
with tempfile.TemporaryDirectory(prefix="avrora-wave-") as d:
    root=pathlib.Path(d)
    with zipfile.ZipFile(io.BytesIO(bundle)) as z:
        for n in ("engine.py","check2_independent.py","tests.py","input.csv"):
            (root/n).write_bytes(z.read(n))
    if hashlib.sha256((root/"input.csv").read_bytes()).hexdigest()!="__CSV_SHA__":
        raise SystemExit("BLOCKED_SOURCE_HASH")
    def verified_run(args):
        process=subprocess.run([sys.executable,*args],cwd=root,text=True,capture_output=True,timeout=200)
        if process.returncode:
            raise SystemExit("BLOCKED_PRIVATE_REPLAY_OR_CHECK2_FAILED")
    verified_run(["tests.py","input.csv"])
    verified_run(["engine.py","input.csv","out"])
    verified_run(["check2_independent.py","input.csv","out"])
    result=json.loads((root/"out"/"results.json").read_text())
    checker=json.loads((root/"out"/"check2_independent.json").read_text())
    if checker.get("status")!="PASS" or checker.get("holdout")!="SEALED":
        raise SystemExit("BLOCKED_CHECK2")
    expected=__EXPECTED__
    summary={"schema":"AVRORA_WAVE_COLAB_DISCOVERY_V1",
             "status":"PASS","real":"OFF","holdout":"SEALED",
             "oos":False,"source_rows":8064,"fee_bps_roundtrip":20,
             "models":{}}
    for name,v in expected.items():
        model=result["models"][name]
        check=checker["models"][name]
        total=model["aggregate"]["net20_usdt"]
        if model["accepted"]!=v["accepted"] or abs(total-v["net20_usdt"])>0.00001:
            raise SystemExit("BLOCKED_ECONOMIC_REPRODUCIBILITY")
        if not check["matched_all_fields"] or check["trades"]!=v["accepted"]:
            raise SystemExit("BLOCKED_CHECK2_DIVERGENCE")
        summary["models"][name]={"trades":v["accepted"],
              "net20_usdt":total,
              "net20_per_day":model["aggregate"]["net20_per_day"],
              "profit_factor":model["aggregate"]["profit_factor_net20"]}
    h=hashlib.sha256(json.dumps(summary,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    summary["receipt_sha256"]=h
    print("AVRORA_PRIVATE_WAVE_RESULT="+json.dumps(summary,sort_keys=True),flush=True)
'''.replace("__CSV_SHA__", CSV_SHA)


def verify_remote_receipt(text):
    lines = [line.split(MARKER, 1)[1] for line in text.splitlines() if MARKER in line]
    if len(lines) != 1:
        raise ValueError("BLOCKED_REMOTE_WAVE_RECEIPT_MISSING")
    obj = json.loads(lines[0])
    digest = obj.pop("receipt_sha256", "")
    if digest != sha(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()):
        raise ValueError("BLOCKED_REMOTE_WAVE_RECEIPT_HASH")
    if obj.get("status") != "PASS" or obj.get("source_rows") != 8064 or obj.get("real") != "OFF" or obj.get("holdout") != "SEALED":
        raise ValueError("BLOCKED_REMOTE_WAVE_SAFETY")
    for name, v in EXPECTED.items():
        row = obj["models"][name]
        if row["trades"] != v["accepted"] or abs(row["net20_usdt"] - v["net20_usdt"]) > .00001:
            raise ValueError("BLOCKED_REMOTE_WAVE_METRICS")
    obj["receipt_sha256"] = digest
    return obj


