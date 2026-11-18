#!/usr/bin/env python3
"""ONE cold full CASE34 run in existing owner-authorized Colab GPU.

This PUBLIC template contains NO private consultation text, credentials or
source. Bridge fills three private, base64-encoded placeholders ONLY inside an
ephemeral mode-0600 runner file and submits it to the owner's private Colab.
Public GitHub logs/artifacts receive ONLY bounded status codes and metrics.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

PACK="__PSYAI_PRIVATE_GIT_ARCHIVE_B64__"
PACK_SHA="__PSYAI_PRIVATE_GIT_ARCHIVE_SHA256__"
PRIVATE_HEAD="__PSYAI_PRIVATE_GIT_COMMIT_SHA__"
CASE34="__PSYAI_CASE34_PRIVATE_ORIGINAL_B64__"
HELPER="__PSYAI_PINNED_GPU8_HELPER_B64__"

MODEL_SHA="93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b"
CASE34_SHA="3fb91a7a0286389073d0da9099d99081b6d49e913b7d34381e359d744d0720cc"
SCHEMA="PSYAI_CASE34_FULL_COLAB_V1"
MARKER="PSYAI_CASE34_FULL_RECEIPT="
STAGE_MARKER="PSYAI_CASE34_FULL_STAGE="
CAP_MIB=8192
MIB=1024*1024

def canon(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True)

def progress(stage,status,elapsed=None,reason=None):
    event={"schema":"PSYAI_CASE34_FULL_STAGE_V1","stage":stage,"status":status}
    if isinstance(elapsed,(int,float)):event["seconds"]=round(float(elapsed),2)
    if reason and re.fullmatch(r"[A-Z_0-9]{1,70}",reason):
        event["reason_code"]=reason
    print(STAGE_MARKER+canon(event),flush=True)

def digest_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(8*MIB),b""):h.update(block)
    return h.hexdigest()

def safe_extract(blob,destination):
    """Reject symlinks/hardlinks/path traversal, never trust tar metadata."""
    destination.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob),mode="r:") as tar:
        members=tar.getmembers()
        if not 200<=len(members)<=7000:raise RuntimeError("PRIVATE_ARCHIVE_FILE_COUNT")
        for m in members:
            p=Path(m.name)
            if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir()):
                raise RuntimeError("PRIVATE_ARCHIVE_PATH_REJECTED")
            if any(p.name.endswith(ext) for ext in (".gguf",".db",".sqlite",".sqlite3",".pfx",".pem",".key")):
                raise RuntimeError("PRIVATE_ARCHIVE_SECRET_ENTRY")
        tar.extractall(destination,filter="data")

def import_helper(root):
    path=root/"verified_gpu8_helper.py"
    contents=base64.b64decode(HELPER,validate=True)
    if len(contents)>250_000:raise RuntimeError("GPU8_HELPER_SIZE_INVALID")
    path.write_bytes(contents)
    spec=importlib.util.spec_from_file_location("verified_gpu8_helper",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.MODEL_SHA!=MODEL_SHA or module.CAP_MIB!=CAP_MIB or module.CUDA_TAG!="b11774":
        raise RuntimeError("GPU8_HELPER_PIN_MISMATCH")
    module.progress=lambda *a,**k:None
    return module

def command(cmd, cwd=None, env=None, timeout=1000):
    """Never publish pip, stdout, app logs or path data."""
    with tempfile.TemporaryFile(mode="w+b") as out:
        try:
            res=subprocess.run(cmd,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                              stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
            return res.returncode==0
        except (OSError,subprocess.TimeoutExpired):
            return False

def install_deps(source):
    if not command([sys.executable,"-m","pip","-q","install","--disable-pip-version-check",
                    "-r","requirements.txt","-r","requirements-semantic.txt",
                    "psutil>=5.9,<8","transformers==4.57.1","sentencepiece==0.2.1",
                    "huggingface_hub>=0.32,<1"],cwd=source,timeout=950):
        raise RuntimeError("PRODUCTION_DEPENDENCIES_UNAVAILABLE")

def prepare_model(work,gpu):
    from huggingface_hub import hf_hub_download
    model=Path(hf_hub_download(repo_id=gpu.MODEL_REPO,
        revision=gpu.MODEL_REV,filename=gpu.MODEL_FILE,
        local_dir=str(work/"models"),token=False,etag_timeout=30))
    if digest_file(model)!=MODEL_SHA:raise RuntimeError("GEMMA_PINNED_SHA_MISMATCH")
    return model

def install_e5(work,source):
    sys.path.insert(0,str(source))
    import embedding_model
    where=work/"models"/embedding_model.FOLDER
    embedding_model.install(folder=where)
    if not embedding_model.verify(where).get("ok"):
        raise RuntimeError("E5_PINNED_INTEGRITY_FAILED")
    return embedding_model.REVISION

def install_nli(work):
    from huggingface_hub import model_info,snapshot_download
    repo="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
    # Resolve and PIN one immutable commit for this trial. Save the exact SHA
    # to receipt; subsequent trials must use this pinned commit, not "main".
    rev=model_info(repo,revision="main").sha
    if not re.fullmatch(r"[a-f0-9]{40}",rev):
        raise RuntimeError("NLI_REVISION_INVALID")
    folder=work/"models"/"nli_mdeberta"
    snapshot_download(repo_id=repo,revision=rev,local_dir=str(folder),
        allow_patterns=["*.json","*.safetensors","*.model","*.txt"],
        token=False,max_workers=4)
    if not (folder/"config.json").is_file():
        raise RuntimeError("NLI_CONFIG_MISSING")
    if not list(folder.glob("*.safetensors")):
        raise RuntimeError("NLI_WEIGHTS_MISSING")
    return folder,rev

def prepare_cuda(work,gpu):
    source=work/"llama_official_cuda"
    source.mkdir()
    for filename,sha,label in gpu.CUDA_ASSETS:
        path=gpu.download_pinned_asset(work,filename,sha,label)
        with tarfile.open(path,"r:gz") as tar:
            for item in tar.getmembers():
                p=Path(item.name)
                if p.is_absolute() or ".." in p.parts:
                    raise RuntimeError("UNSAFE_CUDA_PACKAGE_ENTRY")
            tar.extractall(source,filter="data")
    binaries=list(source.rglob("llama-server"))
    if len(binaries)!=1:raise RuntimeError("CUDA_LLAMA_SERVER_NOT_UNIQUE")
    server=binaries[0]
    root=work/"offline_payload"
    for name in ("runtime","runtime-cuda"):
        dest=root/name
        dest.mkdir(parents=True)
        for binary in source.rglob("*"):
            if not binary.is_file() or binary.is_symlink():continue
            if binary.name!="llama-server" and ".so" not in binary.name:continue
            target=dest/binary.name
            if target.exists():
                if digest_file(binary)!=digest_file(target):
                    raise RuntimeError("CUDA_DUPLICATE_LIBRARY_CONFLICT")
                continue
            try:os.link(binary,target)
            except OSError:shutil.copy2(binary,target)
        if not (dest/"llama-server").is_file():raise RuntimeError("PINNED_RUNTIME_SERVER_MISSING")
        (dest/"llama-server").chmod((dest/"llama-server").stat().st_mode|0o111)
    if not list((root/"runtime-cuda").glob("libggml-cuda.so*")):
        raise RuntimeError("PINNED_CUDA_SHARED_OBJECT_MISSING")
    libs=sorted({str(p.parent) for p in source.rglob("*") if p.is_file() and ".so" in p.name})
    libs.extend([str(root/"runtime-cuda"),str(root/"runtime")])
    os.environ["LD_LIBRARY_PATH"]=os.pathsep.join(libs+[os.environ.get("LD_LIBRARY_PATH","")])
    return gpu.CUDA_TAG

def summary_only(work,process_rc):
    path=work/"evidence"/"CASE34_HYBRID_LAST_RUN.json"
    if not path.is_file():
        return {"result_receipt":"MISSING","case34_status":"BLOCKED_OR_FAILED"}
    item=json.loads(path.read_text(encoding="utf-8"))
    # Never pass arbitrary model text, source, hypotheses or errors into a
    # PUBLIC GitHub artifact. Restrict strings to small fixed enumerations.
    enums={"IN_PROGRESS","BLOCKED_OR_FAILED","NOT_ACCEPTED",
           "CANDIDATE_FOR_EXPERT_REVIEW","PASS","FAIL",
           "AUTOMATED_PASS_EXPERT_PENDING","NOT_REVIEWED"}
    result=item.get("status","BLOCKED_OR_FAILED")
    if result not in enums:result="BLOCKED_OR_FAILED"
    output={"result_receipt":"PRESENT","case34_status":result,
            "full_analysis_seconds":item.get("full_analysis_seconds"),
            "analysis_seconds":item.get("analysis_seconds"),
            "export_seconds":item.get("export_seconds"),
            "wall_total_seconds":item.get("wall_total_seconds"),
            "real_gemma":item.get("real_gemma") is True,
            "performance":item.get("performance") if item.get("performance") in enums else "UNVERIFIED",
            "quality":item.get("quality") if item.get("quality") in enums else "UNVERIFIED"}
    checks=item.get("verification") or {}
    if isinstance(checks,dict):
        output["automated_checks_pass"]=checks.get("automated_checks_pass") is True
        for field in ("model_claims","graph_edges","graph_edge_candidates",
                      "hypothesis_count","hybrid_shadow_seconds"):
            number=checks.get(field)
            if type(number) in (int,float) and 0<=number<100000:
                output[field]=number
        # Failure identifiers are constant and must be enumerated, not
        # unrestricted model or exception messages.
        problems=checks.get("automated_failures") or []
        safe=re.compile(r"[A-Z][A-Z0-9_]{2,80}")
        output["failure_codes"]=[x for x in problems[:30]
                                  if isinstance(x,str) and safe.fullmatch(x)]
    for ext in ("pdf","docx"):
        path=work/"evidence"/("CASE34_HYBRID_report."+ext)
        if path.is_file():
            output[ext+"_bytes"]=path.stat().st_size
            output[ext+"_sha256"]=digest_file(path)
    return output

def main():
    started=time.monotonic()
    proof={"schema":SCHEMA,"status":"BLOCKED_OR_FAILED",
           "case34_original_sha256_verified":False,
           "source_private":True,"source_published":False,
           "model_started":False,"generation_verified":False,
           "full_case34":False,"target_seconds":900,
           "vram_cap_mib":CAP_MIB,"stages":[]}
    def stage(name,status,detail=None):
        elapsed=round(time.monotonic()-started,2)
        row={"name":name,"status":status,"elapsed_seconds":elapsed}
        if detail and re.fullmatch(r"[A-Z0-9_]{2,70}",detail):
            row["reason_code"]=detail
        proof["stages"].append(row)
        progress(name,status,elapsed,detail)
    try:
        with tempfile.TemporaryDirectory(prefix="psyai-private-case34-") as temp:
            work=Path(temp)
            archive=base64.b64decode(PACK,validate=True)
            if len(archive)>22_000_000 or hashlib.sha256(archive).hexdigest()!=PACK_SHA:
                raise RuntimeError("PRIVATE_ARCHIVE_HASH_MISMATCH")
            if not re.fullmatch(r"[0-9a-f]{40}",PRIVATE_HEAD):
                raise RuntimeError("PRIVATE_REPO_HEAD_INVALID")
            source=work/"source"
            safe_extract(gzip.decompress(archive),source)
            (work/"PRIVATE_SOURCE_VERIFIED_ARCHIVE.json").write_text(
                canon({"head":PRIVATE_HEAD,"archive_sha256":PACK_SHA,"verified":True}),
                encoding="ascii")
            raw=base64.b64decode(CASE34,validate=True)
            if len(raw)!=13098 or hashlib.sha256(raw).hexdigest()!=CASE34_SHA:
                raise RuntimeError("CASE34_ORIGINAL_SHA_MISMATCH")
            marker=re.compile(r"(?m)^[ \t]*(Клиент|Психолог)\s*:\s*")
            lines=list(marker.finditer(raw.decode("utf-8-sig")))
            if len(lines)!=34 or sum(x.group(1)=="Клиент" for x in lines)!=17:
                raise RuntimeError("CASE34_ROLE_COUNTS_MISMATCH")
            original=work/"case34.txt"
            original.write_bytes(raw)
            original.chmod(0o600)
            proof["case34_original_sha256_verified"]=True
            proof["source_sha"]=PRIVATE_HEAD
            stage("PRIVATE_ARCHIVE_AND_CASE34_SHA","PASS")
            gpu=import_helper(work)
            total,used,free=gpu.gpu_memory()
            if total<CAP_MIB+1024:raise RuntimeError("GPU_TOTAL_TOO_SMALL")
            import torch
            if not torch.cuda.is_available() or "T4" not in torch.cuda.get_device_name(0):
                raise RuntimeError("GPU_NOT_TESLA_T4")
            free=gpu.gpu_memory()[2]
            reserve=max(0,free-CAP_MIB+128)
            guard=torch.empty(reserve*MIB,dtype=torch.uint8,device="cuda")
            guard.fill_(0)
            torch.cuda.synchronize()
            if gpu.gpu_memory()[2]>CAP_MIB or gpu.gpu_memory()[2]<512:
                raise RuntimeError("GPU8_MEMORY_RESERVATION_FAIL")
            stage("GPU8_MEMORY_PARTITION","PASS")
            install_deps(source)
            stage("PYTHON_DEPENDENCIES","PASS")
            model=prepare_model(work,gpu)
            proof["model_sha256_verified"]=True
            stage("PINNED_GEMMA","PASS")
            prepare_cuda(work,gpu)
            stage("PINNED_CUDA","PASS")
            e5rev=install_e5(work,source)
            proof["e5_revision"]=e5rev
            stage("E5_VERIFIED","PASS")
            nli,nlirev=install_nli(work)
            proof["nli_revision"]=nlirev
            stage("NLI_LOCAL_INSTALLED","PASS")
            env=os.environ.copy()
            env.update(PSYAI_HOME=str(work),PSYAI_DATA_DIR=str(work/"data"),
                PSYAI_PATHS_FILE=str(work/"paths.json"),
                PSYAI_LICENSE_ENFORCE="0",PSYAI_SKIP_AUTO_INSTALL="1",
                PYTHONNOUSERSITE="1",PYTHONDONTWRITEBYTECODE="1",
                PSYAI_COLAB_VERIFIED_PRIVATE_HEAD=PRIVATE_HEAD,
                PSYAI_COLAB_VERIFIED_PRIVATE_ARCHIVE_SHA256=PACK_SHA)
            for folder in ("models","temp","cache","logs","evidence","data"):
                (work/folder).mkdir(exist_ok=True)
            resultfile=work/"evidence"/"CASE34_HYBRID_LAST_RUN.json"
            # DO NOT provide a prompt, dialogue or user-controlled strings as
            # arguments to the public subprocess; only the private path.
            argv=[sys.executable,"-B",
                  str(source/"tools"/"run_case34_hybrid_acceptance.py"),
                  "--run","--work",str(work),"--source",str(original),
                  "--nli-model-dir",str(nli),"--output",str(work/"evidence"),
                  "--mode","HYBRID","--hard-timeout-seconds","1800"]
            progress("FULL_PSYAI_CASE34","START")
            before=time.monotonic()
            with tempfile.TemporaryFile(mode="w+b") as diagnostic:
                process=subprocess.Popen(argv,cwd=source,env=env,stdin=subprocess.DEVNULL,
                    stdout=diagnostic,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    import psutil
                    while process.poll() is None:
                        if time.monotonic()-before>2200:
                            raise RuntimeError("FULL_CASE34_EXECUTION_TIMEOUT")
                        # Leave 128 MiB reserve beyond our fixed 8-GiB ceiling.
                        if gpu.gpu_memory()[2]<128:
                            raise RuntimeError("GPU8_CAP_EXCEEDED_DURING_CASE34")
                        time.sleep(3)
                    rc=process.returncode
                finally:
                    if process.poll() is None:
                        try:
                            parent=psutil.Process(process.pid)
                            children=parent.children(recursive=True)
                        except (psutil.NoSuchProcess,psutil.AccessDenied):
                            children=[]
                        for child in reversed(children):
                            try:child.terminate()
                            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                        process.terminate()
                        try:process.wait(timeout=8)
                        except subprocess.TimeoutExpired:process.kill()
            proof.update(summary_only(work,rc))
            proof["model_started"]=proof.get("real_gemma") is True
            proof["full_case34"]=bool(proof.get("real_gemma"))
            proof["execution_exit_code"]=int(rc)
            proof["case34_execution_seconds"]=round(time.monotonic()-before,2)
            stage("FULL_PSYAI_CASE34","PASS" if rc==0 else "FAIL")
            proof["status"]=("CANDIDATE_FOR_EXPERT_REVIEW"
               if rc==0 and proof.get("case34_status")=="CANDIDATE_FOR_EXPERT_REVIEW"
               else "NOT_ACCEPTED")
    except Exception as e:
        kind=str(e)
        if not re.fullmatch(r"[A-Z0-9_]{2,70}",kind):
            kind=type(e).__name__.upper()
        stage("STOPPED","BLOCKED",kind)
        proof["reason_code"]=kind
    proof["elapsed_seconds"]=round(time.monotonic()-started,2)
    proof["receipt_sha256"]=hashlib.sha256(canon(proof).encode("ascii")).hexdigest()
    print(MARKER+canon(proof),flush=True)
    return 0 if proof["status"]=="CANDIDATE_FOR_EXPERT_REVIEW" else 2

if __name__=="__main__":
    raise SystemExit(main())
