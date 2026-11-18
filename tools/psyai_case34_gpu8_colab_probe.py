#!/usr/bin/env python3
"""PsyAI Gemma 4 12B T4 GPU / 8 GiB VRAM constrained preflight, not CASE34 E2E.

Runs only on an ephemeral Colab GPU via the existing authorized AVRORA CLI.
Returns SHA-bound summary; never calls Bybit, AVRORA trading code, or any EXE.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

MARKER="PSYAI_GPU8_COLAB_RECEIPT="
MODEL_REPO="google/gemma-4-12B-it-qat-q4_0-gguf"
MODEL_REV="ef7b15515d7ed7f34305a08edb5717e7989d6dc9"
MODEL_FILE="gemma-4-12b-it-qat-q4_0.gguf"
MODEL_SHA="93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b"
CAP_MIB=8192
MIB=1024*1024

def canon(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True)

def command(cmd, timeout=1200):
    return subprocess.run(cmd,timeout=timeout,stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,check=False).returncode

def gpu_memory():
    p=subprocess.run(["nvidia-smi","--query-gpu=memory.total,memory.used,memory.free",
                       "--format=csv,noheader,nounits"],capture_output=True,
                     text=True,timeout=20,check=True)
    line=p.stdout.strip().splitlines()[0]
    return tuple(int(x.strip()) for x in line.split(",")[:3])

def proc_gpu_mib(pid):
    p=subprocess.run(["nvidia-smi","--query-compute-apps=pid,used_gpu_memory",
                      "--format=csv,noheader,nounits"],capture_output=True,
                     text=True,timeout=15,check=False)
    for line in p.stdout.splitlines():
        fields=[x.strip() for x in line.split(",")]
        if len(fields)==2 and fields[0].isdigit() and int(fields[0])==pid and fields[1].isdigit():
            return int(fields[1])
    return None

def main():
    started=time.monotonic()
    receipt={"schema":"PSYAI_GPU8_COLAB_PREFLIGHT_V1","status":"BLOCKED",
             "gpu_requested":"T4","vram_cap_mib":CAP_MIB,
             "memory_cap_method":"reserve_excess_gpu_memory_plus_pid_watchdog",
             "model_sha256_verified":False,"generation_verified":False,
             "case34_full_e2e":False,"case34_seconds":None,"steps":[]}
    def stage(name,status,reason=None):
        row={"name":name,"status":status}
        if reason:row["reason_code"]=reason
        receipt["steps"].append(row)
    try:
        total,used,free=gpu_memory()
        receipt["physical_gpu_total_mib"]=total
        receipt["physical_gpu_free_before_mib"]=free
        stage("t4_gpu","PASS")
        if total<CAP_MIB+1024:raise RuntimeError("GPU_TOTAL_BELOW_8G")
        import torch
        if not torch.cuda.is_available():raise RuntimeError("CUDA_UNAVAILABLE")
        name=torch.cuda.get_device_name(0)
        receipt["gpu_name"]=name
        if "T4" not in name:raise RuntimeError("EXPECTED_T4_GPU")
        # Allocate the excess VRAM in a live CUDA process. This reduces actual
        # free GPU memory to the capacity available on an 8 GiB card. The
        # external llama.cpp CUDA allocator is NOT governed by torch fraction.
        reserve_mib=max(0,free-CAP_MIB)
        if reserve_mib<256:raise RuntimeError("FREE_GPU_MEMORY_BELOW_REALISTIC_CAP")
        # Keep a 256-MiB CUDA overhead margin under the 8-GiB usable budget.
        guard_bytes=(reserve_mib+256)*MIB
        guard=torch.empty(guard_bytes,dtype=torch.uint8,device="cuda")
        guard.fill_(0)
        torch.cuda.synchronize()
        total,now_used,now_free=gpu_memory()
        receipt["gpu_free_after_reserve_mib"]=now_free
        receipt["gpu_guard_memory_mib"]=reserve_mib+256
        if now_free>CAP_MIB or now_free<512:raise RuntimeError("VRAM_RESERVATION_INVALID")
        stage("eight_gib_vram_partition","PASS")
        with tempfile.TemporaryDirectory(prefix="psyai-gpu8-colab-") as temporary:
            root=Path(temporary)
            if command([sys.executable,"-m","pip","install","-q","huggingface_hub"],600):
                raise RuntimeError("HF_INSTALL_FAILED")
            from huggingface_hub import hf_hub_download
            try:
                model=Path(hf_hub_download(repo_id=MODEL_REPO,revision=MODEL_REV,
                    filename=MODEL_FILE,local_dir=str(root/"model"),token=False,etag_timeout=30))
            except Exception as exc:
                raise RuntimeError("PINNED_MODEL_DOWNLOAD_FAILED") from None
            h=hashlib.sha256()
            with model.open("rb") as f:
                for block in iter(lambda:f.read(8*MIB),b""):h.update(block)
            if h.hexdigest()!=MODEL_SHA:raise RuntimeError("PINNED_MODEL_SHA_MISMATCH")
            receipt["model_sha256_verified"]=True
            stage("pinned_model","PASS")
            src=root/"llama.cpp"
            if command(["git","clone","--quiet","--depth","1",
                        "https://github.com/ggml-org/llama.cpp.git",str(src)],600):
                raise RuntimeError("LLAMA_CPP_CLONE_FAILED")
            build=src/"build"
            if command(["cmake","-S",str(src),"-B",str(build),"-DGGML_CUDA=ON",
                        "-DLLAMA_CURL=OFF","-DGGML_NATIVE=OFF"],600):
                raise RuntimeError("LLAMA_CUDA_CONFIG_FAILED")
            if command(["cmake","--build",str(build),"--target","llama-cli","-j","4"],1500):
                raise RuntimeError("LLAMA_CUDA_BUILD_FAILED")
            cli=next((p for p in build.rglob("llama-cli") if p.is_file() and os.access(p,os.X_OK)),None)
            if not cli:raise RuntimeError("LLAMA_CLI_MISSING")
            stage("cuda_llama_binary","PASS")
            # Small GPU layer count is intentional: CPU offload allowed, full
            # CUDA load is not evidence of an 8-GiB device simulation.
            args=[str(cli),"-m",str(model),"-ngl","20","-c","2048",
                  "-b","256","-ub","128","-n","32","--no-display-prompt",
                  "-p","Как называется башня с огнём, помогающая кораблям найти берег? Ответь одним русским словом."]
            with subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as proc:
                peak=0
                over=False
                until=time.monotonic()+480
                while proc.poll() is None and time.monotonic()<until:
                    pid_mib=proc_gpu_mib(proc.pid)
                    if pid_mib is not None:peak=max(peak,pid_mib)
                    # Both the GPU process estimate and the real free-memory
                    # floor are enforced. Never allow model to spill beyond its
                    # 8 GiB effective partition.
                    if peak>CAP_MIB or gpu_memory()[2]<128:
                        over=True
                        proc.kill()
                        break
                    time.sleep(0.3)
                if proc.poll() is None:proc.kill()
                output=proc.communicate(timeout=15)[0]
                receipt["model_gpu_peak_mib"]=peak
                receipt["gpu_free_after_inference_mib"]=gpu_memory()[2]
                if over:raise RuntimeError("GPU8_WATCHDOG_LIMIT_EXCEEDED")
                if proc.returncode:raise RuntimeError("LLAMA_GENERATION_NONZERO_EXIT")
                if b""==output or "маяк" not in output.decode("utf8",errors="replace").lower():
                    raise RuntimeError("NO_GENERATED_CANARY")
                if peak==0:raise RuntimeError("GPU_ALLOCATIONS_NOT_CONFIRMED")
                receipt["generation_verified"]=True
                stage("gpu8_inference","PASS")
        receipt["status"]="GPU8_MODEL_PREFLIGHT_PASS"
    except Exception as exc:
        reason=str(exc)
        if not reason or not reason.isupper():reason=type(exc).__name__.upper()
        stage("stopped","BLOCKED",reason[:70])
        receipt["status"]="BLOCKED_OR_FAILED"
    receipt["elapsed_seconds"]=round(time.monotonic()-started,2)
    receipt["receipt_sha256"]=hashlib.sha256(canon(receipt).encode("ascii")).hexdigest()
    print(MARKER+canon(receipt),flush=True)
    return 0 if receipt["status"]=="GPU8_MODEL_PREFLIGHT_PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
