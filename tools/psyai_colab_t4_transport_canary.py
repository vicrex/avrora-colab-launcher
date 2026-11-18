#!/usr/bin/env python3
"""Transport-only T4 check: zero private source, no patient data, no models."""
import json, subprocess
try:
    r=subprocess.run(["nvidia-smi","--query-gpu=name","--format=csv,noheader"],
                     capture_output=True,timeout=15,text=True)
    ok=r.returncode==0 and "T4" in r.stdout
except Exception:
    ok=False
print("PSYAI_T4_TRANSPORT_CHECK="+("PASS" if ok else "FAIL"),flush=True)
raise SystemExit(0 if ok else 2)
