#!/usr/bin/env python3
"""Offline synthetic-only proof of full CASE34 Colab packaging.

Requires a temporary read-only checkout at private_psyai; does not need
CASE34 secret, private dialogue, Google login, GPU, Gemma, E5 or NLI. Validates
remote Python syntax and immutable source archive before any cold run.
"""
from __future__ import annotations
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile

RUNNER=Path("tools/psyai_case34_full_colab_bridge.py")
REMOTE=Path("tools/psyai_case34_colab_full_remote.py")
HELPER=Path("tools/psyai_case34_gpu8_colab_probe.py")

for f in (RUNNER,REMOTE,HELPER):
    compile(f.read_bytes(),str(f),"exec")

spec=importlib.util.spec_from_file_location("bridge",RUNNER)
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

def fake_original():
    return "\n".join(
        ("Клиент: " if i%2==0 else "Психолог: ")
        +"synthetic_fixture_only_34_turns_"+str(i)
        for i in range(34)).encode("utf-8")

def main():
    original=fake_original()
    assert len(original)<3000
    bridge.ORIGINAL_SHA=hashlib.sha256(original).hexdigest()
    rev,packed,count=bridge.private_source_archive()
    assert len(rev)==40 and count>100
    with tarfile.open(fileobj=io.BytesIO(__import__("gzip").decompress(packed)),mode="r:") as tar:
        names=[m.name for m in tar.getmembers()]
    assert "app.py" in names
    assert "tools/e2e_full_gemma.py" in names
    assert "tools/run_case34_hybrid_acceptance.py" in names
    assert not any(n.startswith("docs/") or n.startswith("reports/")
                   or n.startswith("tests/") for n in names)
    helper=HELPER.read_bytes()
    script=bridge.build_ephemeral_script(rev,packed,original,helper)
    assert "__PSYAI_" not in script
    assert "synthetic_fixture_only_34_turns" not in script  # base64 only
    compile(script,"ephemeral_synthetic_colab.py","exec")
    # Controlled allocation fallback must not accidentally rerun a completed
    # model analysis. Validate only synthetic logs, never a private transcript.
    assert 'for variant in ("T4","L4")' in RUNNER.read_text("utf-8")
    assert '"T4" in detected or "L4" in detected' in REMOTE.read_text("utf-8")
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        logfile=Path(directory)/"cli.log"
        logfile.write_text("Failed to assign accelerator: HTTP 412",encoding="utf-8")
        assert bridge.safe_gpu_allocation_reason(logfile)=="COLAB_GPU_ASSIGNMENT_REJECTED"
        logfile.write_text("Internal remote Python error",encoding="utf-8")
        assert bridge.safe_gpu_allocation_reason(logfile)=="OTHER_FAILURE"
    # Verify a bounded failure code reaches the public receipt without
    # accidentally exposing arbitrary human text from the private runtime.
    import types
    remote_spec=importlib.util.spec_from_file_location("case34_remote_template",REMOTE)
    # The templated module is syntax checked above; inspect source because its
    # mandatory secret placeholders are deliberately unavailable in offline CI.
    remote_text=REMOTE.read_text("utf-8")
    assert 'output["reason_code"]=code' in remote_text
    assert 're.fullmatch(r"[A-Z][A-Z0-9_]{2,80}",code)' in remote_text
    assert '"reason_code"' in RUNNER.read_text("utf-8")
    # Never print the injected source, helper or synthetic payload to CI logs.
    print("PASS_CASE34_COLAB_FULL_ARCHIVE_SHA_SYNTHETIC_REMOTE_SYNTAX")
    print("PASS_CASE34_COLAB_PRIVATE_FILES_FILTERED_COUNT_GT_100")
    print("PASS_CASE34_ONE_USE_REMOTE_HAS_NO_CLEAR_TEXT_SOURCE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
