#!/usr/bin/env python3
"""Sanitized, observable Google Colab CLI bridge for PSYAI GPU8 preflight.

No browser, no repeated Google authorization, no raw logs/artifacts.
Runs on GitHub Actions and prints only allowlisted stage records.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from psyai_gpu8_status import GitHubStatusJournal

STAGE="PSYAI_GPU8_STAGE="
RECEIPT="PSYAI_GPU8_COLAB_RECEIPT="
PROOF_PATH=Path("psyai_gpu8_proof.json")
TIMEOUT_SECONDS=40*60
ALLOWED_STATES={"START","PASS","FAIL","TIMEOUT","BLOCKED"}
ALLOWED_STAGES={
    "t4_gpu", "eight_gib_vram_partition", "install_hf_client",
    "model_download", "model_sha256", "pinned_model", "llama_clone",
    "cuda_configure", "cuda_build", "cuda_binary_download",
    "cuda_runtime_download", "cuda_llama_binary",
    "model_inference", "gpu8_inference", "stopped"
}

def canonical(d):
    return json.dumps(d,sort_keys=True,separators=(",",":"),ensure_ascii=True)

def classify_cli(text):
    """Classify the real CLI output without exporting any potentially secret text."""
    tail=text.lower()
    patterns=(
        ("COLAB_CLI_SYNTAX_ERROR",("unrecognized arguments","no such option","unknown option",
            "unexpected extra argument","invalid value for","usage: colab")),
        ("COLAB_T4_NOT_AVAILABLE",("no gpu available","no available gpu",
            "accelerator unavailable","gpu not available","no t4")),
        ("COLAB_QUOTA_OR_ASSIGNMENT_REJECTED",("quota","resource_exhausted",
            "too many assignments","assignment quota","code: 412","status 412",
            "http 412","gpu usage limit")),
        ("COLAB_AUTH_ERROR",("invalid_grant","invalid credentials","unauthenticated",
            "authentication required","refresh token","expired token",
            "application default credentials","permission denied","forbidden","403")),
        ("COLAB_RUNTIME_ALLOCATION_FAILED",("failed to assign","assign failed",
            "could not allocate","runtime allocation","cannot create session")),
        ("COLAB_TRANSPORT_ERROR",("connection refused","failed to connect","unreachable",
            "timed out","timeout","network error","dns")),
        ("COLAB_REMOTE_SCRIPT_ERROR",("filenotfounderror","modulenotfounderror",
            "syntaxerror","traceback (most recent call last)")),
        ("COLAB_COMMAND_OR_FILE_NOT_FOUND",("not found","no such file")),
    )
    for code,needles in patterns:
        if any(needle in tail for needle in needles):
            return code
    return "COLAB_NO_VERIFIED_REMOTE_RECEIPT"

def main():
    started=time.monotonic()
    # Verified against google-colab-cli v0.7.4's run_command signature:
    # default --timeout is only 30 s; remote GGUF download/build requires
    # an explicit 35-minute kernel execution deadline.
    cli=["colab","--auth=adc","run","--gpu","T4","--timeout","2100",
         "tools/psyai_case34_gpu8_colab_probe.py"]
    proof={"schema":"PSYAI_GPU8_COLAB_BRIDGE_V2","status":"BLOCKED_NO_VALID_REMOTE_RECEIPT",
           "gpu_requested":"T4","vram_cap_mib":8192,
           "case34_full_e2e":False,"github_run_id":os.getenv("GITHUB_RUN_ID",""),
           "cli_exit_code":None,"elapsed_seconds":None,"stages":[]}
    collected=[]
    snippets=[]
    timer=None
    timed_out=False
    rc=None
    journal=GitHubStatusJournal()
    phase=["waiting_for_colab_output"]
    heartbeat_stop=threading.Event()
    heartbeat_thread=None
    print("PSYAI_GPU8_BRIDGE_STARTED",flush=True)
    proof["script_revision"]=os.getenv("GITHUB_SHA","")[:12]
    try:
        # Do not launch an expensive cloud job unless independent progress
        # reporting is available. GitHub Actions logs may be inaccessible.
        if not journal.heartbeat(0,phase[0]):
            proof["status"]="STATUS_JOURNAL_UNAVAILABLE"
            raise RuntimeError("STATUS_JOURNAL_UNAVAILABLE")
        print("PSYAI_GPU8_JOURNAL_READY",flush=True)

        def report_heartbeat():
            while not heartbeat_stop.wait(60):
                journal.heartbeat(time.monotonic()-started,phase[0])
        heartbeat_thread=threading.Thread(target=report_heartbeat,daemon=True)
        heartbeat_thread.start()

        # GitHub token is only for the local status journal; never pass it
        # to the Colab CLI subprocess or remote Python job.
        child_env=os.environ.copy()
        child_env.pop("GITHUB_TOKEN",None)
        proc=subprocess.Popen(cli,env=child_env,stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,text=True,
                              errors="replace",bufsize=1)
        def stop_timeout():
            nonlocal timed_out
            if proc.poll() is None:
                timed_out=True
                proc.kill()
        timer=threading.Timer(TIMEOUT_SECONDS,stop_timeout)
        timer.daemon=True
        timer.start()
        assert proc.stdout
        for raw in proc.stdout:
            line=raw.strip()
            snippets.append(line[-200:])
            if len(snippets)>120:snippets.pop(0)
            if STAGE in line:
                try:
                    record=json.loads(line.split(STAGE,1)[1])
                    if record.get("schema")!="PSYAI_GPU8_STAGE_V1":continue
                    name=record.get("name")
                    state=record.get("status")
                    if name not in ALLOWED_STAGES or state not in ALLOWED_STATES:
                        continue
                    sanitized={"name":name,"status":state}
                    for key in ("elapsed_seconds","exit_code"):
                        if isinstance(record.get(key),(int,float)):
                            sanitized[key]=record[key]
                    if isinstance(record.get("reason_code"),str):
                        code=record["reason_code"]
                        if code.replace("_","").isalnum() and code.isupper() and len(code)<90:
                            sanitized["reason_code"]=code
                    proof["stages"].append(sanitized)
                    phase[0]=name
                    journal.stage(name,state,sanitized.get("elapsed_seconds"))
                    print("PSYAI_GPU8_STAGE="+canonical(sanitized),flush=True)
                except (ValueError,TypeError,KeyError):
                    pass
            if RECEIPT in line:
                collected.append(line.split(RECEIPT,1)[1])
        rc=proc.wait()
        if timed_out:
            proof["status"]="COLAB_CLI_TIMEOUT"
        elif len(collected)==1:
            try:
                receipt=json.loads(collected[0])
                digest=receipt.pop("receipt_sha256",None)
                actual=hashlib.sha256(canonical(receipt).encode("ascii")).hexdigest()
                if digest!=actual or receipt.get("schema")!="PSYAI_GPU8_COLAB_PREFLIGHT_V1":
                    raise ValueError("INVALID_RECEIPT")
                receipt["receipt_sha256"]=digest
                proof["remote"]=receipt
                proof["status"]=receipt["status"]
            except (ValueError,KeyError,TypeError,UnicodeError):
                proof["status"]="INVALID_REMOTE_RECEIPT"
        elif len(collected)>1:
            proof["status"]="AMBIGUOUS_REMOTE_RECEIPTS"
        else:
            proof["status"]=classify_cli("\n".join(snippets))
            proof["cli_diagnostics"]={
                "output_lines_seen":sum(1 for x in snippets if x),
                "output_tail_sha256":hashlib.sha256(
                    "\n".join(snippets).encode("utf-8",errors="replace")
                ).hexdigest()[:20],
                "reason_class":proof["status"],
            }
    except (OSError,ValueError,RuntimeError) as exc:
        if proof["status"]!="STATUS_JOURNAL_UNAVAILABLE":
            proof["status"]="COLAB_CLI_LAUNCH_FAILED"
        proof["error_type"]=type(exc).__name__
    finally:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=9)
        if timer is not None:timer.cancel()
        success=rc==0 and proof["status"]=="GPU8_MODEL_PREFLIGHT_PASS"
        terminal_status_ok=journal.finish(success,
            "GPU8_MODEL_PREFLIGHT_PASS" if success else proof["status"])
        proof["journal"]={
            "initial_heartbeat_verified":True if journal.accepted>0 else False,
            "statuses_accepted":journal.accepted,
            "statuses_failed":journal.rejected,
            "final_status_published":terminal_status_ok,
            "last_error_code":journal.last_error
        }
        if not terminal_status_ok and success:
            proof["status"]="STATUS_JOURNAL_TERMINAL_FAILED"
        proof["cli_exit_code"]=rc
        proof["elapsed_seconds"]=round(time.monotonic()-started,2)
        PROOF_PATH.write_text(json.dumps(proof,indent=2,ensure_ascii=True)+"\n",
                              encoding="utf-8")
        print("PSYAI_GPU8_STATUS="+proof["status"],flush=True)
        print("PSYAI_GPU8_WALL_SECONDS="+str(proof["elapsed_seconds"]),flush=True)
    return 0 if rc==0 and proof["status"]=="GPU8_MODEL_PREFLIGHT_PASS" else 2

if __name__=="__main__":
    sys.exit(main())
