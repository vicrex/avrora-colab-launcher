#!/usr/bin/env python3
"""One-shot synthetic Colab T4 vector benchmark. No PsyAI private data, model, or downloads."""
import hashlib, json, os, subprocess, tempfile, sys
from pathlib import Path

REMOTE = r"""
import hashlib,json,time
import numpy as np
import torch
SEED=20261117
DIM=384
result={"schema":"PSYAI_VECTOR_COLAB_ABLATION_V1","synthetic":True,"gemma_inference":False,"private_source":False,"sizes":[]}
assert torch.cuda.is_available(),"NO_CUDA"
gpu=torch.cuda.get_device_properties(0)
result["gpu"]=gpu.name
result["gpu_vram_gib"]=round(gpu.total_memory/(2**30),2)
rng=np.random.default_rng(SEED)
for n in (34,340,3400):
    x=rng.standard_normal((n,DIM),dtype=np.float32)
    x/=np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12)
    gold=rng.integers(0,n,size=64)
    queries=x[gold]+rng.standard_normal((64,DIM),dtype=np.float32)*0.025
    queries/=np.maximum(np.linalg.norm(queries,axis=1,keepdims=True),1e-12)
    xc=np.ascontiguousarray(x); qc=np.ascontiguousarray(queries)
    for _ in range(3): cpu=qc@xc.T
    start=time.perf_counter()
    for _ in range(30): cpu=qc@xc.T
    cpu_ms=(time.perf_counter()-start)*1000/30
    cpu_top=np.argsort(-cpu,axis=1)[:,:8]
    start=time.perf_counter()
    xg=torch.from_numpy(xc).cuda(); qg=torch.from_numpy(qc).cuda()
    torch.cuda.synchronize()
    transfer_ms=(time.perf_counter()-start)*1000
    for _ in range(5): gpu_scores=qg@xg.T; torch.cuda.synchronize()
    start=time.perf_counter()
    for _ in range(30): gpu_scores=qg@xg.T; torch.cuda.synchronize()
    gpu_ms=(time.perf_counter()-start)*1000/30
    gpu_top=torch.topk(gpu_scores,8,dim=1).indices.cpu().numpy()
    recall_cpu=float(np.mean(np.any(cpu_top==gold[:,None],axis=1)))
    recall_gpu=float(np.mean(np.any(gpu_top==gold[:,None],axis=1)))
    agree=all(set(cpu_top[i].tolist())==set(gpu_top[i].tolist()) for i in range(64))
    assert agree and recall_cpu==1.0 and recall_gpu==1.0
    result["sizes"].append({"n":n,"dim":DIM,"queries":64,"topk":8,
      "cpu_batch_ms":round(cpu_ms,4),"gpu_batch_ms":round(gpu_ms,4),
      "gpu_transfer_ms":round(transfer_ms,4),"recall_at_8":recall_cpu,
      "gpu_matches_cpu_top8":agree})
    del xg,qg,gpu_scores
result["gpu_peak_mib"]=round(torch.cuda.max_memory_allocated()/(2**20),1)
result["status"]="PASS"
canonical=json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=True)
result["receipt_sha256"]=hashlib.sha256(canonical.encode("ascii")).hexdigest()
print("PSYAI_VECTOR_RECEIPT="+json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=True),flush=True)
"""
def main():
    output=Path("psyai-vector-colab-proof.json")
    blocked={"schema":"PSYAI_VECTOR_COLAB_ABLATION_V1","status":"BLOCKED","synthetic":True,
             "gemma_inference":False,"private_source":False}
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        blocked["reason"]="EXISTING_ADC_ABSENT"
        output.write_text(json.dumps(blocked,indent=2)+"\n")
        print("PSYAI_VECTOR_COLAB_STATUS=BLOCKED_EXISTING_ADC_ABSENT")
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="psyai-vector-") as tmp:
            script=Path(tmp)/"remote.py"; script.write_text(REMOTE,encoding="utf8")
            cmd=subprocess.run(["colab","--auth=adc","run","--gpu","T4",str(script)],
                 stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False,timeout=480)
            text=cmd.stdout.decode("utf8","replace")
            tokens=[line.split("PSYAI_VECTOR_RECEIPT=",1)[1].strip()
                    for line in text.splitlines() if "PSYAI_VECTOR_RECEIPT=" in line]
            if cmd.returncode or len(tokens)!=1: raise ValueError("REMOTE_NO_VALID_RECEIPT")
            row=json.loads(tokens[0]); claimed=row.pop("receipt_sha256",None)
            actual=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")).hexdigest()
            if claimed!=actual or row.get("status")!="PASS" or row.get("schema")!=blocked["schema"] or len(row.get("sizes",[]))!=3:
                raise ValueError("INVALID_RECEIPT")
            row["receipt_sha256"]=claimed
            output.write_text(json.dumps(row,indent=2)+"\n")
            print("PSYAI_VECTOR_COLAB_STATUS=PASS")
            print("PSYAI_VECTOR_COLAB_SYNTHETIC_ONLY=TRUE")
            return 0
    except subprocess.TimeoutExpired:
        blocked["reason"]="COLAB_TIMEOUT_480S"
    except (ValueError,KeyError,TypeError):
        blocked["reason"]="NO_VALID_REMOTE_RECEIPT"
    output.write_text(json.dumps(blocked,indent=2)+"\n")
    print("PSYAI_VECTOR_COLAB_STATUS="+blocked["reason"])
    return 2
if __name__=="__main__":sys.exit(main())
