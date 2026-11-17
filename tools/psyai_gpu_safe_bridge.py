#!/usr/bin/env python3
"""One-shot private PsyAI GPU validation through existing Colab ADC (synthetic data only).
Never export private source, model output, clinical text, credentials or remote logs.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from psyai_private_colab_runner import source_archive, sha, canon

MARKER = "PSYAI_GPU_SAFE_RECEIPT="
SCHEMA = "PSYAI_GPU_SAFE_V1"
OUTPUT = Path("psyai-gpu-safe-proof.json")

def blocked(reason):
    proof = {"schema":SCHEMA,"status":"BLOCKED","reason":reason,"model_generation":False,
             "targeted_tests":False,"gpu":"NOT_VERIFIED","source_private":True,
             "windows_e2e":False,"clinical_quality":"NOT_VERIFIED"}
    proof["receipt_sha256"] = sha(canon(proof).encode("ascii"))
    return proof

def remote(rev, packed):
    template = r'''import base64,hashlib,io,json,os,pathlib,re,subprocess,sys,tarfile,tempfile,time,threading
SCHEMA="PSYAI_GPU_SAFE_V1"
MARKER="PSYAI_GPU_SAFE_RECEIPT="
REV="__REV__"
PACK_HASH="__HASH__"
PACK="__PACK__"
MODEL_REPO="google/gemma-4-12B-it-qat-q4_0-gguf"
MODEL_REV="ef7b15515d7ed7f34305a08edb5717e7989d6dc9"
MODEL_FILE="gemma-4-12b-it-qat-q4_0.gguf"
MODEL_SHA="93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b"
def canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def digest(raw):return hashlib.sha256(raw).hexdigest()
p={"schema":SCHEMA,"status":"BLOCKED","source_sha":REV,"source_private":True,
   "archive_sha256":PACK_HASH,"model_sha256_expected":MODEL_SHA,"model_sha256_verified":False,
   "model_generation":False,"targeted_tests":False,"clinical_quality":"NOT_VERIFIED",
   "windows_e2e":False,"gpu":"NOT_VERIFIED","steps":[]}
def stage(name,ok,reason=""):p["steps"].append({"name":name,"ok":bool(ok),"reason_code":reason})
def cmd(args,cwd=None,timeout=600,capture=False):
    return subprocess.run(args,cwd=cwd,check=False,timeout=timeout,stdin=subprocess.DEVNULL,
      stdout=subprocess.PIPE if capture else subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def mem():
    import subprocess
    q=cmd(["nvidia-smi","--query-gpu=memory.total,memory.free","--format=csv,noheader,nounits"],timeout=15,capture=True)
    if q.returncode:raise ValueError("NVIDIA_SMI_UNAVAILABLE")
    line=q.stdout.decode("ascii","ignore").splitlines()[0]
    total,free=[int(x.strip()) for x in line.split(",")[:2]]
    return total,free
def model_canary(data):
    if not isinstance(data,bytes) or len(data)>262144:return False
    try:s=data.decode("utf-8").casefold()
    except UnicodeError:return False
    return "маяк" in s
try:
  total,free=mem()
  p["gpu"]="T4_REQUESTED"
  p["gpu_total_mib"]=total
  p["gpu_free_mib_start"]=free
  p["vram_budget_mib"]=max(0,min(8192,int(total*0.50),free-2048))
  if p["vram_budget_mib"]<4000:raise ValueError("VRAM_HEADROOM_INSUFFICIENT")
  stage("gpu_preflight",True)
  with tempfile.TemporaryDirectory(prefix="psyai-gpu-safe-") as d:
    root=pathlib.Path(d);app=root/"app";app.mkdir();logs=root/"logs";logs.mkdir()
    compressed=base64.b64decode(PACK,validate=True)
    if digest(compressed)!=PACK_HASH:raise ValueError("SOURCE_ARCHIVE_HASH_MISMATCH")
    with tarfile.open(fileobj=io.BytesIO(__import__("gzip").decompress(compressed))) as tar:
      for item in tar.getmembers():
        parts=pathlib.PurePosixPath(item.name)
        if parts.is_absolute() or ".." in parts.parts or not (item.isfile() or item.isdir()):
          raise ValueError("UNSAFE_SOURCE_ARCHIVE")
      tar.extractall(app,filter="data")
    stage("private_source_sha256",True)
    deps=cmd([sys.executable,"-m","pip","install","-q","-r","requirements.txt","-r","requirements-dev.txt"],cwd=app,timeout=900)
    stage("targeted_test_dependencies",deps.returncode==0,"" if deps.returncode==0 else "DEPENDENCIES_UNAVAILABLE")
    if deps.returncode==0:
      tests=[
        "tests/test_analysis_bundle_premises.py",
        "tests/test_analysis_bundle_entailment.py",
        "tests/test_analysis_bundle_quality.py",
        "tests/test_v_shared_schema.py",
        "tests/test_deep_analysis_cache.py",
      ]
      if all((app/t).is_file() for t in tests):
        with (logs/"targeted-pytest.log").open("wb") as f:
          try:
            result=subprocess.run([sys.executable,"-m","pytest","-q",*tests],cwd=app,
                stdout=f,stderr=subprocess.STDOUT,timeout=900,check=False)
            p["targeted_tests"]=result.returncode==0
            stage("targeted_regressions",p["targeted_tests"],"" if p["targeted_tests"] else "TESTS_FAILED")
          except subprocess.TimeoutExpired:stage("targeted_regressions",False,"TIMEOUT")
      else:stage("targeted_regressions",False,"MISSING_TEST_FILE")
    hfdeps=cmd([sys.executable,"-m","pip","install","-q","huggingface_hub"],timeout=300)
    if hfdeps.returncode:raise ValueError("HUGGING_FACE_DEPENDENCY_FAILED")
    from huggingface_hub import hf_hub_download
    model=pathlib.Path(hf_hub_download(repo_id=MODEL_REPO,revision=MODEL_REV,filename=MODEL_FILE,
        local_dir=str(root/"model"),token=False,etag_timeout=30))
    h=hashlib.sha256()
    with model.open("rb") as f:
      for chunk in iter(lambda:f.read(8*1024*1024),b""):h.update(chunk)
    if h.hexdigest()!=MODEL_SHA:raise ValueError("MODEL_SHA256_MISMATCH")
    p["model_sha256_verified"]=True;stage("pinned_model_integrity",True)
    llama=root/"llama.cpp"
    if cmd(["git","clone","--quiet","--depth","1","https://github.com/ggml-org/llama.cpp.git",str(llama)],timeout=450).returncode:
      raise ValueError("LLAMA_CLONE_FAILED")
    p["llama_sha"]=cmd(["git","-C",str(llama),"rev-parse","HEAD"],timeout=15,capture=True).stdout.decode().strip()
    if cmd(["cmake","-S",str(llama),"-B",str(llama/"build"),"-DGGML_CUDA=ON",
            "-DGGML_NATIVE=OFF","-DLLAMA_CURL=OFF"],timeout=300).returncode:
      raise ValueError("LLAMA_CUDA_CMAKE_FAILED")
    if cmd(["cmake","--build",str(llama/"build"),"--target","llama-cli","-j","4"],timeout=1800).returncode:
      raise ValueError("LLAMA_CUDA_BUILD_FAILED")
    stage("llama_cuda_build",True)
    binary=next((x for x in (llama/"build").rglob("llama-cli") if x.is_file() and os.access(x,os.X_OK)),None)
    if binary is None:raise ValueError("LLAMA_BINARY_MISSING")
    # Model may partially offload to CPU. 8192 MiB is a software ceiling, NOT a
    # hardware-enforced allocation quota; watch our own incremental VRAM usage.
    # Start conservatively: avoid loading too many layers before the monitor reacts.
    ngl=16
    def watch(process,peak):
      while process.poll() is None:
        try:
          _,free_now=mem();used=max(0,free-free_now);peak[0]=max(peak[0],used)
          if used>p["vram_budget_mib"]:
            peak[1]=True
            process.terminate()
            return
        except Exception:pass
        time.sleep(0.25)
    p["gpu_layers_attempted"]=ngl
    p["context_tokens"]=1024
    p["batch_tokens"]=128
    p["microbatch_tokens"]=128
    p["vram_limit_type"]="SOFTWARE_WATCHDOG_NOT_HARD_HARDWARE_QUOTA"
    argv=[str(binary),"-m",str(model),"-ngl",str(ngl),"-c","1024","-b","128","-ub","128","-t","4",
      "-n","48","--no-display-prompt","-p",
      "Как называется башня с огнём, помогающая кораблям найти берег? Ответь одним русским словом."]
    process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    peak=[0,False];thread=threading.Thread(target=watch,args=(process,peak),daemon=True);thread.start()
    try:stdout,_=process.communicate(timeout=900)
    except subprocess.TimeoutExpired:
      process.terminate()
      try:stdout,_=process.communicate(timeout=15)
      except subprocess.TimeoutExpired:
        process.kill();stdout,_=process.communicate()
      p["inference_timeout"]=True
    thread.join(timeout=3)
    p["peak_extra_vram_mib"]=peak[0]
    p["vram_limit_tripped"]=peak[1]
    p["model_generation"]=process.returncode==0 and not peak[1] and model_canary(stdout)
    stage("native_gemma_cuda_smoke",p["model_generation"],
          "" if p["model_generation"] else ("VRAM_LIMIT" if peak[1] else "GENERATION_NOT_VERIFIED"))
  p["status"]="GPU_SMOKE_AND_TESTS_PASS" if p["model_generation"] and p["targeted_tests"] else "PARTIAL_OR_FAIL"
except Exception as e:
  kind=str(e)
  allow={"VRAM_HEADROOM_INSUFFICIENT","NVIDIA_SMI_UNAVAILABLE","SOURCE_ARCHIVE_HASH_MISMATCH",
         "UNSAFE_SOURCE_ARCHIVE","HUGGING_FACE_DEPENDENCY_FAILED","MODEL_SHA256_MISMATCH",
         "LLAMA_CLONE_FAILED","LLAMA_CUDA_CMAKE_FAILED","LLAMA_CUDA_BUILD_FAILED","LLAMA_BINARY_MISSING"}
  p["reason"]=kind if kind in allow else type(e).__name__
p["receipt_sha256"]=digest(canon(p).encode("ascii"))
print(MARKER+canon(p),flush=True)
'''
    return template.replace("__REV__",rev).replace("__HASH__",sha(packed)).replace("__PACK__",base64.b64encode(packed).decode("ascii"))

def main():
    proof=blocked("NOT_STARTED")
    try:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("EXISTING_COLAB_ADC_MISSING")
        if not Path("private_psyai").is_dir():
            raise ValueError("PRIVATE_SOURCE_CHECKOUT_MISSING")
        rev,packed=source_archive()
        with tempfile.TemporaryDirectory(prefix="psyai-gpu-bridge-") as d:
            script=Path(d)/"run_private.py"
            output=Path(d)/"remote.log"
            script.write_text(remote(rev,packed),encoding="utf-8")
            script.chmod(0o600)
            with output.open("wb") as log:
                result=subprocess.run(["colab","--auth=adc","run","--gpu","T4",str(script)],
                    stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
                    timeout=5800,check=False)
            matches=[line.split(MARKER,1)[1] for line in
                     output.read_text(encoding="utf-8",errors="replace").splitlines()
                     if MARKER in line]
            if len(matches)!=1:
                raise ValueError("REMOTE_RECEIPT_MISSING")
            received=json.loads(matches[0])
            digest_value=received.pop("receipt_sha256","")
            if digest_value!=sha(canon(received).encode("ascii")):
                raise ValueError("REMOTE_RECEIPT_HASH_MISMATCH")
            if received.get("schema")!=SCHEMA or received.get("source_sha")!=rev or not received.get("source_private"):
                raise ValueError("REMOTE_RECEIPT_SOURCE_MISMATCH")
            accepted={"schema","status","source_sha","source_private","archive_sha256",
              "model_sha256_expected","model_sha256_verified","model_generation",
              "targeted_tests","clinical_quality","windows_e2e","gpu",
              "gpu_total_mib","gpu_free_mib_start","vram_budget_mib","peak_extra_vram_mib",
              "vram_limit_tripped","gpu_layers_attempted","context_tokens","batch_tokens","microbatch_tokens",
              "vram_limit_type","llama_sha","steps","reason",
              "inference_timeout"}
            proof={k:v for k,v in received.items() if k in accepted}
            proof["receipt_sha256"]=sha(canon(proof).encode("ascii"))
    except (ValueError,OSError,subprocess.TimeoutExpired,subprocess.CalledProcessError) as e:
        allow={"EXISTING_COLAB_ADC_MISSING","PRIVATE_SOURCE_CHECKOUT_MISSING",
          "REMOTE_RECEIPT_MISSING","REMOTE_RECEIPT_HASH_MISMATCH",
          "REMOTE_RECEIPT_SOURCE_MISMATCH"}
        proof=blocked(str(e) if str(e) in allow else type(e).__name__)
    OUTPUT.write_text(json.dumps(proof,ensure_ascii=True,indent=2)+"\n",encoding="utf-8")
    print("PSYAI_GPU_SAFE_STATUS",proof["status"],proof.get("reason",""))
    return 0 if proof["status"]=="GPU_SMOKE_AND_TESTS_PASS" else 2

if __name__=="__main__":
    sys.exit(main())
