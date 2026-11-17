#!/usr/bin/env python3
"""One-shot measured Russian NLI in Colab T4. Synthetic data ONLY.
No clinical text, Gemma, private repo, or user artifacts cross the boundary.
"""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path

SCHEMA="PSYAI_RU_NLI_REAL_V1"
OUT=Path("psyai-ru-nli-proof.json")
REMOTE=r"""
import hashlib,json,time,threading,subprocess,sys,importlib
SCHEMA="PSYAI_RU_NLI_REAL_V1"
RESULT="PSYAI_NLI_RECEIPT="
start=time.monotonic();done=threading.Event()
result={"schema":SCHEMA,"status":"BLOCKED","synthetic_only":True,
    "medical_case":False,"gemma_generation":False,
    "full_psyai_e2e":False,"source_quotes_exported":False,
    "nli_model":"MoritzLaurer/mDeBERTa-v3-base-mnli-xnli","stages":[]}
def heartbeat():
 while not done.wait(25):
  print("PSYAI_NLI_RUNNING",flush=True)
threading.Thread(target=heartbeat,daemon=True).start()
def stage(name):
 result["stages"].append({"name":name,"seconds_from_start":round(time.monotonic()-start,2)})
 print("PSYAI_NLI_STAGE="+name,flush=True)
try:
 if not importlib.util.find_spec("transformers"):
  proc=subprocess.run([sys.executable,"-m","pip","install","-q",
      "transformers>=4.46,<5","sentencepiece","huggingface_hub"],
      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False,timeout=220)
  if proc.returncode:raise ValueError("DEPENDENCIES_INSTALL_FAILED")
 stage("DEPENDENCIES")
 import torch
 from transformers import AutoTokenizer,AutoModelForSequenceClassification
 from huggingface_hub import HfApi
 if not torch.cuda.is_available():raise ValueError("T4_UNAVAILABLE")
 gpu=torch.cuda.get_device_name(0)
 result["gpu"]=gpu
 if "T4" not in gpu:raise ValueError("GPU_NOT_T4")
 stage("T4")
 repo=result["nli_model"]
 commit=HfApi().model_info(repo,timeout=45).sha
 if not commit or len(commit)!=40:raise ValueError("NLI_COMMIT_UNVERIFIED")
 result["nli_revision"]=commit
 t0=time.monotonic()
 tokenizer=AutoTokenizer.from_pretrained(repo,revision=commit,
    use_fast=True,trust_remote_code=False)
 model=AutoModelForSequenceClassification.from_pretrained(
    repo,revision=commit,trust_remote_code=False).eval()
 result["cold_model_load_s"]=round(time.monotonic()-t0,2)
 labels={str(v).lower():int(k) for k,v in model.config.id2label.items()}
 if not {"entailment","contradiction","neutral"}<=set(labels):
  raise ValueError("NLI_LABEL_MISMATCH")
 stage("PINNED_NLI_LOADED")
 # Eight independent fabricated Russian contrasts, no copied client dialogue.
 examples=[
  ("Я переключился на разговор и забыл о неприятном ощущении.",
   "Неприятное ощущение исчезло.",False,"attention_vs_state"),
  ("Клиент сказал, что забыл о неприятном ощущении.",
   "Клиент сообщил, что забыл об ощущении.",True,"attributed_paraphrase"),
  ("Психолог рассказал о герое романа, у которого исчезло ощущение.",
   "У клиента исчезло ощущение.",False,"fiction_vs_client"),
  ("Пример литературного героя привёл психолог.",
   "Литературного героя упомянул клиент.",False,"wrong_speaker"),
  ("Клиент сказал, что иногда испытывает тревогу.",
   "Клиент всегда испытывает тревогу.",False,"frequency_strengthening"),
  ("Клиент сказал, что не совершал описанное действие.",
   "Клиент совершил описанное действие.",False,"negation"),
  ("Клиент описал эпизод одиночества.",
   "Клиент намерен причинить себе вред.",False,"loneliness_vs_intent"),
  ("Психолог задал вопрос, помогло ли обсуждение.",
   "Обсуждение доказанно помогло клиенту.",False,"question_vs_effect")
 ]
 def predict(device,repeats):
  x=tokenizer([a for a,b,_,_ in examples],
    [b for a,b,_,_ in examples],padding=True,truncation=True,
    max_length=384,return_tensors="pt").to(device)
  model.to(device)
  if device=="cuda":torch.cuda.synchronize()
  with torch.inference_mode():
   scores=torch.softmax(model(**x).logits,dim=-1)
  if device=="cuda":torch.cuda.synchronize()
  t0=time.monotonic()
  with torch.inference_mode():
   for _ in range(repeats):
    scores=torch.softmax(model(**x).logits,dim=-1)
    if device=="cuda":torch.cuda.synchronize()
  return scores.cpu().tolist(),round((time.monotonic()-t0)/repeats,4)
 values_cpu,cpu_s=predict("cpu",2)
 result["cpu_inference_batch_s"]=cpu_s
 stage("REAL_NLI_CPU")
 values_gpu,gpu_s=predict("cuda",3)
 result["gpu_inference_batch_s"]=gpu_s
 result["gpu_peak_mib"]=round(torch.cuda.max_memory_allocated()/(2**20),1)
 stage("REAL_NLI_T4")
 scores=[];false_positive=[]
 for i,(premise,hypothesis,should_entail,label) in enumerate(examples):
  p=values_cpu[i]
  ent=float(p[labels["entailment"]])
  contra=float(p[labels["contradiction"]])
  neu=float(p[labels["neutral"]])
  is_entailed=ent>=0.50
  if not should_entail and is_entailed:false_positive.append(label)
  scores.append(dict(case=label,expected_entail=should_entail,
    entail=round(ent,4),contradiction=round(contra,4),
    neutral=round(neu,4),predicted_entail=is_entailed,
    compatible=is_entailed==should_entail))
 result["contrast_results"]=scores
 result["false_entailment_cases"]=false_positive
 result["positive_case_retrieved"]=scores[1]["predicted_entail"]
 result["nli_is_independent_proof"]=False
 result["final_supported_from_nli"]=0
 result["status"]="BENCH_COMPLETE"
 stage("ANALYTIC_CONTRASTS")
except Exception as exc:
 msg=str(exc)
 result["status"]="BLOCKED"
 result["reason"]=msg if msg in {"DEPENDENCIES_INSTALL_FAILED","T4_UNAVAILABLE",
   "GPU_NOT_T4","NLI_COMMIT_UNVERIFIED","NLI_LABEL_MISMATCH"} else type(exc).__name__
finally:
 done.set()
 result["wall_s"]=round(time.monotonic()-start,2)
 canonical=json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=True)
 result["receipt_sha256"]=hashlib.sha256(canonical.encode("ascii")).hexdigest()
 print(RESULT+json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=True),flush=True)
"""
def main():
 receipt={"schema":SCHEMA,"status":"BLOCKED","reason":"NOT_STARTED",
  "synthetic_only":True,"gemma_generation":False}
 if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
  receipt["reason"]="EXISTING_ADC_MISSING"
 else:
  try:
   with tempfile.TemporaryDirectory(prefix="psyai-nli-") as d:
    script=Path(d)/"remote.py";log=Path(d)/"private.log"
    compile(REMOTE,"colab_nli_remote.py","exec")
    script.write_text(REMOTE,encoding="utf8")
    with log.open("wb") as f:
     run=subprocess.run(["colab","--auth=adc","run","--gpu","T4",
         "--timeout","600",str(script)],stdout=f,stderr=subprocess.STDOUT,
         timeout=960,stdin=subprocess.DEVNULL,check=False)
    raw=log.read_text(encoding="utf8",errors="replace")
    found=[x.split("PSYAI_NLI_RECEIPT=",1)[1].strip() for x in raw.splitlines()
      if "PSYAI_NLI_RECEIPT=" in x]
    if len(found)!=1:
     receipt={"schema":SCHEMA,"status":"BLOCKED",
       "reason":"REMOTE_RECEIPT_MISSING",
       "cli_returncode":run.returncode,
       "last_stage":next((v.split("PSYAI_NLI_STAGE=",1)[1].strip()
                         for v in reversed(raw.splitlines())
                         if "PSYAI_NLI_STAGE=" in v),"NONE"),
       "diagnostic":{"allocated":"session ready" in raw.lower(),
          "executing":"executing" in raw.lower(),
          "timeout":"timeout" in raw.lower(),
          "heartbeat_seen":"PSYAI_NLI_RUNNING" in raw}}
    else:
     p=json.loads(found[0]);given=p.pop("receipt_sha256",None)
     actual=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(",",":"),
       ensure_ascii=True).encode("ascii")).hexdigest()
     if given!=actual or p.get("schema")!=SCHEMA:raise ValueError("RECEIPT_INVALID")
     p["receipt_sha256"]=given;receipt=p
  except subprocess.TimeoutExpired:
   receipt["reason"]="COLAB_JOB_TIMEOUT"
  except Exception as exc:
   receipt["reason"]=type(exc).__name__
 OUT.write_text(json.dumps(receipt,indent=2,ensure_ascii=True)+"\n",encoding="utf8")
 print("PSYAI_RU_NLI_STATUS="+receipt["status"],flush=True)
 return 0 if receipt["status"]=="BENCH_COMPLETE" else 2
if __name__=="__main__":sys.exit(main())
