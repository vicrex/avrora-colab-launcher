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
import tarfile
import urllib.request
import re
import unicodedata
import tempfile
import time

MARKER="PSYAI_GPU8_COLAB_RECEIPT="
MODEL_REPO="google/gemma-4-12B-it-qat-q4_0-gguf"
MODEL_REV="ef7b15515d7ed7f34305a08edb5717e7989d6dc9"
MODEL_FILE="gemma-4-12b-it-qat-q4_0.gguf"
MODEL_SHA="93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b"
CAP_MIB=8192
# Official GitHub release b11774, not mutable llama.cpp/main.
CUDA_TAG="b11774"
CUDA_ASSETS=(
    ("llama-b11774-bin-ubuntu-cuda-12.8-x64.tar.gz",
     "7d03c8482b62c9533d47e777c0d3ca2edce6e57916b51f587a4576d332757fbb",
     "cuda_binary_download"),
    ("cudart-llama-b11774-bin-ubuntu-cuda-12.8-x64.tar.gz",
     "d4fe9a68a521add2001396fdc324dcc613104a2e7a175b68823448793bf8eb9f",
     "cuda_runtime_download"),
)

MIB=1024*1024

def canon(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True)

STAGE_MARKER="PSYAI_GPU8_STAGE="

def progress(name, status, elapsed_seconds=None, exit_code=None, reason_code=None):
    event={"schema":"PSYAI_GPU8_STAGE_V1","name":name,"status":status}
    if elapsed_seconds is not None:event["elapsed_seconds"]=round(elapsed_seconds,2)
    if exit_code is not None:event["exit_code"]=int(exit_code)
    if reason_code:event["reason_code"]=reason_code
    print(STAGE_MARKER+canon(event),flush=True)

def command(cmd, timeout=1200, label="external_command"):
    started=time.monotonic()
    progress(label,"START")
    # Keep subprocess output in ephemeral storage, not /dev/null.
    # Never print potentially sensitive dependency-manager or CLI logs.
    with tempfile.TemporaryFile(mode="w+b") as diagnostic:
        try:
            p=subprocess.run(cmd,timeout=timeout,stdout=diagnostic,
                             stderr=subprocess.STDOUT,check=False)
            rc=p.returncode
        except subprocess.TimeoutExpired:
            progress(label,"TIMEOUT",time.monotonic()-started,
                     exit_code=124,reason_code="COMMAND_TIMEOUT")
            return 124
        diagnostic.seek(0)
        tail=diagnostic.read()[-8192:].decode("utf-8",errors="replace").lower()
        reason=None
        if rc:
            if "out of memory" in tail or "cuda error: out of memory" in tail:reason="CUDA_OOM"
            elif "no space left on device" in tail:reason="DISK_FULL"
            elif "permission denied" in tail:reason="PERMISSION_DENIED"
            elif "network" in tail or "timed out" in tail:reason="NETWORK_ERROR"
            elif "cmake error" in tail:reason="CMAKE_ERROR"
            else:reason="COMMAND_NONZERO_EXIT"
        progress(label,"PASS" if rc==0 else "FAIL",time.monotonic()-started,
                 exit_code=rc,reason_code=reason)
        return rc


def download_pinned_asset(root:Path,filename:str,expected_sha:str,label:str)->Path:
    """Stream an official pinned release, enforce size and SHA before extraction."""
    url=("https://github.com/ggml-org/llama.cpp/releases/download/"
         +CUDA_TAG+"/"+filename)
    path=root/filename
    partial=root/(filename+".partial")
    limit_bytes=800_000_000
    started=time.monotonic()
    progress(label,"START")
    try:
        digest=hashlib.sha256()
        total=0
        with urllib.request.urlopen(url,timeout=60) as response,partial.open("wb") as dst:
            while True:
                block=response.read(8*1024*1024)
                if not block:break
                total+=len(block)
                if total>limit_bytes:raise RuntimeError("CUDA_ASSET_SIZE_EXCEEDED")
                digest.update(block)
                dst.write(block)
        if digest.hexdigest()!=expected_sha:
            raise RuntimeError("PINNED_CUDA_ASSET_SHA_MISMATCH")
        os.replace(partial,path)
        progress(label,"PASS",time.monotonic()-started)
        return path
    except Exception:
        partial.unlink(missing_ok=True)
        progress(label,"FAIL",time.monotonic()-started,reason_code="CUDA_ASSET_VERIFICATION_FAILED")
        raise RuntimeError("CUDA_ASSET_VERIFICATION_FAILED") from None



def recognize_generated_canary(raw:bytes)->tuple[bool,dict]:
    """Recognize legitimate RU or EN lighthouse answers, not exit code alone.

    No model stdout, prompts, or answer text are returned or logged. A valid
    CLI exit code with only performance logs is NOT evidence of generation.
    """
    decoded=raw.decode("utf-8",errors="replace")
    normalized=unicodedata.normalize("NFKD",decoded).casefold()
    normalized="".join(c for c in normalized if unicodedata.category(c)!="Mn")
    normalized=re.sub(r"\\x1b\\[[0-9;]*[A-Za-z]","",normalized)
    ru=bool(re.search(r"(?<![а-яё])маяк(?:а|у|ом|е|и|ов|ам|ами|ах)?(?![а-яё])",normalized))
    en=bool(re.search(r"(?<![a-z])(?:lighthouses?|beacons?)(?![a-z])",normalized))
    metadata={
        "stdout_bytes":len(raw),
        "stdout_nonspace_chars":sum(not c.isspace() for c in decoded),
        "output_sha256_prefix":hashlib.sha256(raw).hexdigest()[:20],
        "has_llama_timing":bool(re.search(r"(?:llama_perf|eval time|prompt eval time)",normalized)),
        "canary_ru":ru,
        "canary_en":en,
    }
    return bool(raw.strip()) and (ru or en),metadata


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
        row={"name":name,"status":status,
             "elapsed_seconds":round(time.monotonic()-started,2)}
        if reason:row["reason_code"]=reason
        receipt["steps"].append(row)
        progress(name,status,row["elapsed_seconds"],reason_code=reason)
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
        # Re-read free VRAM AFTER creating the PyTorch CUDA context; its
        # overhead must not be double-counted during reservation.
        free=gpu_memory()[2]
        reserve_mib=max(0,free-CAP_MIB+128)
        if reserve_mib<256:raise RuntimeError("FREE_GPU_MEMORY_BELOW_REALISTIC_CAP")
        guard_bytes=reserve_mib*MIB
        guard=torch.empty(guard_bytes,dtype=torch.uint8,device="cuda")
        guard.fill_(0)
        torch.cuda.synchronize()
        total,now_used,now_free=gpu_memory()
        receipt["gpu_free_after_reserve_mib"]=now_free
        receipt["gpu_guard_memory_mib"]=reserve_mib
        if now_free>CAP_MIB or now_free<512:raise RuntimeError("VRAM_RESERVATION_INVALID")
        stage("eight_gib_vram_partition","PASS")
        with tempfile.TemporaryDirectory(prefix="psyai-gpu8-colab-") as temporary:
            root=Path(temporary)
            if command([sys.executable,"-m","pip","install","-q","huggingface_hub"],600,label="install_hf_client"):
                raise RuntimeError("HF_INSTALL_FAILED")
            from huggingface_hub import hf_hub_download
            progress("model_download","START")
            download_started=time.monotonic()
            try:
                model=Path(hf_hub_download(repo_id=MODEL_REPO,revision=MODEL_REV,
                    filename=MODEL_FILE,local_dir=str(root/"model"),token=False,etag_timeout=30))
            except Exception as exc:
                raise RuntimeError("PINNED_MODEL_DOWNLOAD_FAILED") from None
            progress("model_download","PASS",time.monotonic()-download_started)
            progress("model_sha256","START")
            sha_started=time.monotonic()
            h=hashlib.sha256()
            with model.open("rb") as f:
                for block in iter(lambda:f.read(8*MIB),b""):h.update(block)
            if h.hexdigest()!=MODEL_SHA:raise RuntimeError("PINNED_MODEL_SHA_MISMATCH")
            progress("model_sha256","PASS",time.monotonic()-sha_started)
            receipt["model_sha256_verified"]=True
            stage("pinned_model","PASS")
            # Reuse a VERIFIED official CUDA build; compiling llama.cpp from
            # upstream main previously consumed 1500 seconds and timed out.
            # Pin both immutable release tag and the official asset digests.
            bundle=root/"llama_official_cuda"
            bundle.mkdir()
            for name,digest,label in CUDA_ASSETS:
                artifact=download_pinned_asset(root,name,digest,label)
                with tarfile.open(artifact,"r:gz") as archive:
                    # Python 3.12 data filter rejects path traversal and
                    # links outside the extraction root.
                    archive.extractall(bundle,filter="data")
            cli=next((p for p in bundle.rglob("llama-cli") if p.is_file()
                and not p.is_symlink()),None)
            if not cli:raise RuntimeError("PINNED_LLAMA_CLI_MISSING")
            cli.chmod(cli.stat().st_mode|0o111)
            stage("cuda_llama_binary","PASS")
            # Prebuilt libraries may be in a nested bin/lib directory.
            runtime_env=os.environ.copy()
            libs={str(cli.parent),str(bundle)}
            for pattern in ("libggml*.so*","libcudart.so*","libcublas.so*"):
                for f in bundle.rglob(pattern):
                    libs.add(str(f.parent))
            runtime_env["LD_LIBRARY_PATH"]=os.pathsep.join(
                sorted(libs)+[runtime_env.get("LD_LIBRARY_PATH","")])
            # Small GPU layer count is intentional: CPU offload allowed, full
            # CUDA load is not evidence of an 8-GiB device simulation.
            args=[str(cli),"-m",str(model),"-ngl","20","-c","2048",
                  "-b","256","-ub","128","-n","32","--no-display-prompt",
                  "-p","Как называется башня с огнём, помогающая кораблям найти берег? Ответь одним русским словом."]
            progress("model_inference","START")
            inference_started=time.monotonic()
            with subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=runtime_env) as proc:
                peak=0
                over=False
                timed_out=False
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
                if proc.poll() is None:
                    timed_out=True
                    proc.kill()
                output=proc.communicate(timeout=15)[0]
                receipt["model_gpu_peak_mib"]=peak
                receipt["gpu_free_after_inference_mib"]=gpu_memory()[2]
                if over:raise RuntimeError("GPU8_WATCHDOG_LIMIT_EXCEEDED")
                if timed_out:raise RuntimeError("LLAMA_INFERENCE_TIMEOUT")
                if proc.returncode:raise RuntimeError("LLAMA_GENERATION_NONZERO_EXIT")
                canary,summary=recognize_generated_canary(output)
                receipt["inference_output_probe"]=summary
                if not canary:
                    raise RuntimeError("NO_RECOGNIZED_GENERATED_CANARY")
                if peak==0:raise RuntimeError("GPU_ALLOCATIONS_NOT_CONFIRMED")
                receipt["generation_verified"]=True
                receipt["inference_seconds"]=round(time.monotonic()-inference_started,2)
                progress("model_inference","PASS",receipt["inference_seconds"])
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
