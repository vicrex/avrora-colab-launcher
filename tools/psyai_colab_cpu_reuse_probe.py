#!/usr/bin/env python3
"""PsyAI one-shot public model smoke on existing AVRORA Colab ADC.

No PsyAI source, private credentials, or real consultations are transferred.
Gemma CPU verification is independent of the application's full E2E gate.
Only a sanitized cryptographic receipt is printed.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

MODEL_REPO="google/gemma-4-12B-it-qat-q4_0-gguf"
MODEL_REV="ef7b15515d7ed7f34305a08edb5717e7989d6dc9"
MODEL_FILE="gemma-4-12b-it-qat-q4_0.gguf"
MODEL_SHA="93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b"
MARKER="PSYAI_COLAB_CPU_RECEIPT="
STAGES=[]


def canon(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True)


def stage(label, status, reason=""):
    STAGES.append({"name":label,"status":status,"reason_code":reason})


def run(cmd,*,cwd=None,timeout=1200,capture_stdout=False):
    # The final inference smoke must inspect real generated tokens, whereas
    # dependency/build commands must never copy raw output into a receipt.
    return subprocess.run(
        cmd,cwd=cwd,check=False,timeout=timeout,
        stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def verifies_generated_answer(stdout):
    """Conservative synthetic canary. No raw model output leaves Colab.

    The answer word is deliberately absent from the prompt, so an echoed
    prompt or a zero-token successful exit cannot be counted as generation.
    """
    if not isinstance(stdout, bytes) or not 1 <= len(stdout) <= 262144:
        return False
    try:
        sample = stdout.decode('utf-8',errors='strict').lower()
    except UnicodeDecodeError:
        return False
    import re
    sample = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', sample)
    return 'маяк' in sample


def get_memory_gib():
    try:
        with open("/proc/meminfo",encoding="ascii") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1])/1024/1024,2)
    except OSError:
        pass
    return None


def main():
    t0=time.monotonic()
    receipt={"schema":"PSYAI_COLAB_CPU_REUSE_V1","status":"BLOCKED",
             "source_repository":"vicrex/PSYAI_PROFESSIONAL","source_loaded":False,
             "model_repository":MODEL_REPO,"model_revision":MODEL_REV,
             "model_sha256_expected":MODEL_SHA,"model_sha256_verified":False,
             "actual_generation":False,"application_e2e":False,
             "windows_e2e":False,"full_tz_accepted":False,
             "cpu_count":os.cpu_count(),"ram_gib":get_memory_gib(),
             "python":platform.python_version(),"steps":STAGES}
    try:
        stage("colab_cpu_remote","PASS" if os.cpu_count() else "FAIL")
        # Fail-closed on insufficient RAM, before downloading 7 GB.
        if (receipt["ram_gib"] or 0)<11.0:
            stage("model_memory_gate","BLOCKED","RAM_BELOW_11_GIB")
        else:
            stage("model_memory_gate","PASS")
            with tempfile.TemporaryDirectory(prefix="psyai-colab-cpu-") as temp:
                root=Path(temp)
                pip=run([sys.executable,"-m","pip","-q","install","huggingface_hub"],timeout=600)
                if pip.returncode:
                    stage("download_dependencies","BLOCKED","PIP_INSTALL_FAILED")
                else:
                    from huggingface_hub import hf_hub_download
                    try:
                        p=Path(hf_hub_download(repo_id=MODEL_REPO,revision=MODEL_REV,filename=MODEL_FILE,
                           local_dir=str(root/"model"),token=False,etag_timeout=30))
                    except Exception:
                        stage("model_download","BLOCKED","OFFICIAL_GGUF_UNAVAILABLE_OR_RESTRICTED")
                    else:
                        stage("model_download","PASS")
                        h=hashlib.sha256()
                        with p.open("rb") as stream:
                            for chunk in iter(lambda:stream.read(8*1024*1024),b""):
                                h.update(chunk)
                        if h.hexdigest()!=MODEL_SHA:
                            stage("model_integrity","FAIL","PINNED_SHA256_MISMATCH")
                        else:
                            receipt["model_sha256_verified"]=True
                            stage("model_integrity","PASS")
                            ll=root/"llama.cpp"
                            g=run(["git","clone","--depth","1","--quiet","https://github.com/ggml-org/llama.cpp.git",str(ll)],timeout=600)
                            if g.returncode:
                                stage("llama_cpp_clone","BLOCKED","GIT_CLONE_FAILED")
                            else:
                                conf=run(["cmake","-S",str(ll),"-B",str(ll/"build"),
                                    "-DGGML_CUDA=OFF","-DGGML_VULKAN=OFF","-DLLAMA_CURL=OFF",
                                    "-DGGML_NATIVE=OFF"],timeout=300)
                                built=conf.returncode==0 and run(["cmake","--build",str(ll/"build"),
                                    "--target","llama-cli","-j","4"],timeout=1500).returncode==0
                                if not built:
                                    stage("llama_cpu_build","FAIL","LLAMA_BUILD_FAILED")
                                else:
                                    stage("llama_cpu_build","PASS")
                                    binary=next((x for x in (ll/"build").rglob("llama-cli")
                                                 if x.is_file() and os.access(x,os.X_OK)),None)
                                    if not binary:
                                        stage("inference","FAIL","BINARY_MISSING")
                                    else:
                                        try:
                                            result=run([str(binary),"-m",str(p),"-ngl","0",
                                                "-c","1024","-t","4","-p",
                                                "Как называется башня с огнём, помогающая кораблям найти берег? Ответь одним русским словом.",
                                                "-n","32","--no-display-prompt"],
                                                timeout=900,capture_stdout=True)
                                            verified = (result.returncode==0
                                                        and verifies_generated_answer(result.stdout))
                                            receipt["actual_generation"]=verified
                                            stage("inference","PASS" if verified else "FAIL",
                                                "" if verified else (
                                                    "LLAMA_RETURN_CODE_NONZERO"
                                                    if result.returncode else
                                                    "NO_VERIFIED_GENERATED_CANARY"))
                                        except subprocess.TimeoutExpired:
                                            stage("inference","FAIL","LLAMA_CPU_TIMEOUT")
    except Exception:
        stage("unexpected","BLOCKED","UNEXPECTED_EXCEPTION")
    receipt["elapsed_seconds"]=round(time.monotonic()-t0,1)
    receipt["status"]="MODEL_CPU_PASS" if receipt["actual_generation"] and receipt["model_sha256_verified"] else "BLOCKED_OR_FAIL"
    receipt["next_gate"]="BLOCKED_PRIVATE_PSYAI_SOURCE_NOT_IN_AVRORA_DEPLOY_KEY_SCOPE"
    receipt["receipt_sha256"]=hashlib.sha256(canon(receipt).encode()).hexdigest()
    print(MARKER+canon(receipt),flush=True)
    return 0 if receipt["status"]=="MODEL_CPU_PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
