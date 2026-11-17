#!/usr/bin/env python3
"""One-shot real multilingual E5 encoding in Colab T4; synthetic consultation only.
No patient data, private PsyAI sources, or Gemma generation.
"""
import hashlib,json,os,subprocess,tempfile,sys
from pathlib import Path
SCHEMA="PSYAI_REAL_E5_COLAB_V1"
REMOTE=r"""
import hashlib,json,time,random,sys
result={"schema":"PSYAI_REAL_E5_COLAB_V1","status":"BLOCKED",
        "synthetic_only":True,"clinical_quality":"NOT_TESTED",
        "gemma_generation":False,"stages":[]}
def step(name,ok,details=None):
    result["stages"].append({"stage":name,"pass":bool(ok),**(details or {})})
try:
 import importlib.util,subprocess
 if importlib.util.find_spec("transformers") is None:
    install=subprocess.run([sys.executable,"-m","pip","install","-q","transformers>=4.50,<5","safetensors"],check=False,timeout=180)
    assert install.returncode==0,"TRANSFORMERS_INSTALL_FAILED"
 import numpy as np
 import torch
 from transformers import AutoModel,AutoTokenizer
 repo="intfloat/multilingual-e5-small"
 revision="614241f622f53c4eeff9890bdc4f31cfecc418b3"
 assert torch.cuda.is_available(),"T4_NOT_ALLOCATED"
 props=torch.cuda.get_device_properties(0)
 result["gpu"]=props.name
 result["gpu_total_gib"]=round(props.total_memory/(2**30),2)
 step("T4_ALLOCATED",True)
 t0=time.perf_counter()
 tokenizer=AutoTokenizer.from_pretrained(repo,revision=revision,trust_remote_code=False)
 model=AutoModel.from_pretrained(repo,revision=revision,trust_remote_code=False)
 model.eval()
 result["load_seconds"]=round(time.perf_counter()-t0,2)
 step("PINNED_E5_LOADED",True,{"revision":revision,"dimension":int(model.config.hidden_size)})
 lines=[
 "Клиент: Иногда я замечаю тошноту.",
 "Клиент: Когда я отвлёкся, я забыл о тошноте.",
 "Психолог: Вы говорите, что симптом исчез?",
 "Клиент: Нет, я сказал, что забыл о нём.",
 "Клиент: На следующей встрече я снова вспомнил о симптоме.",
 "Психолог: Что вы чувствовали в тот момент?",
 "Клиент: Я тревожился перед встречей.",
 "Клиент: В магазине я отвлекался на разговор.",
 "Психолог: Есть ли другие объяснения происходящего?",
 "Клиент: Не знаю, возможно, дело во внимании.",
 "Клиент: Вчера я почувствовал облегчение.",
 "Клиент: Я не говорю, что полностью выздоровел.",
 "Психолог: Мы можем проверить эту гипотезу.",
 "Клиент: Я хочу разобраться в своих ощущениях.",
 "Клиент: Моя тревога иногда усиливается вечером.",
 "Психолог: Что происходило перед усилением тревоги?",
 "Клиент: Сначала я разговаривал с другом.",
 "Клиент: Я пока не знаю причины.",
 "Психолог: Уточним, в какой ситуации это возникло.",
 "Клиент: Я говорил про один эпизод, не про все случаи.",
 "Клиент: На работе я чувствовал напряжение.",
 "Клиент: Это было в прошлом месяце.",
 "Психолог: Какие мысли появились в тот момент?",
 "Клиент: Я подумал, что могу не справиться.",
 "Клиент: Позже моя оценка ситуации изменилась.",
 "Клиент: Я не уверен, что это связано с разговором.",
 "Психолог: С какой альтернативой можно сравнить?",
 "Клиент: Иногда симптомы возникают без тревоги.",
 "Клиент: Я не утверждал, что это лечение.",
 "Клиент: Я вспомнил один хороший момент.",
 "Психолог: Какой опыт вы хотели бы проверить?",
 "Клиент: Мне нужно больше наблюдений.",
 "Клиент: Я пока считаю это предположением.",
 "Психолог: Сформулируем вопрос без диагноза."
 ]
 assert len(lines)==34
 def encode(texts,device):
    tok=tokenizer(texts,padding=True,truncation=True,max_length=128,return_tensors="pt")
    tok={k:v.to(device) for k,v in tok.items()}
    with torch.no_grad():
      x=model(**tok).last_hidden_state
      m=tok["attention_mask"].unsqueeze(-1)
      v=(x*m).sum(1)/m.sum(1).clamp(min=1)
      v=torch.nn.functional.normalize(v,p=2,dim=1)
    if device=="cuda": torch.cuda.synchronize()
    return v.cpu().numpy()
 docs=["passage: "+s for s in lines]
 queries=["query: Клиент сообщил, что тошнота исчезла.",
          "query: Клиент сообщил, что забыл о тошноте.",
          "query: Психолог спросил клиента о исчезновении симптома.",
          "query: В каком эпизоде пациент не уверен в причинах?",
          "query: В каких репликах клиент говорит об ограничениях?"]
 start=time.perf_counter()
 cpu=encode(docs+queries,"cpu")
 result["cpu_encoding_39_seconds"]=round(time.perf_counter()-start,3)
 step("CPU_E5_EMBEDDINGS",cpu.shape==(39,384))
 model.to("cuda");torch.cuda.synchronize()
 start=time.perf_counter();gpu=encode(docs+queries,"cuda")
 result["gpu_encoding_39_seconds"]=round(time.perf_counter()-start,3)
 step("GPU_E5_EMBEDDINGS",gpu.shape==(39,384))
 result["cpu_gpu_mean_cosine"]=round(float(np.mean(np.sum(cpu*gpu,axis=1))),5)
 qvectors=cpu[34:];dvectors=cpu[:34]
 sim=qvectors@dvectors.T
 ranks=np.argsort(-sim,axis=1)[:,:5]
 result["retrieval_top5_utterances"]=[[int(i)+1 for i in row] for row in ranks]
 result["retrieval_cosine_top1"]=[round(float(sim[k,row[0]]),4) for k,row in enumerate(ranks)]
 step("VECTOR_RETRIEVAL",all(len(row)==5 for row in ranks))
 # Source relation/type guard: no claim may be ACCEPTED based on cosine score.
 scope={"speaker":"CLIENT","referent":"CLIENT","domain":"ATTENTION_MEMORY",
   "aspect":"ATTENTION","state":"UNKNOWN","time":"PAST"}
 unsupported={"speaker":"CLIENT","referent":"CLIENT","domain":"SYMPTOM_STATE",
   "aspect":"PRESENCE","state":"ABSENT","time":"PAST"}
 def admission(src,claim,only_vector_score):
   if src["speaker"]!=claim["speaker"] or src["referent"]!=claim["referent"]:return "REVIEW_REQUIRED"
   if src["domain"]=="ATTENTION_MEMORY" and claim["domain"]=="SYMPTOM_STATE":return "REVIEW_REQUIRED"
   if src["aspect"]=="ATTENTION" and claim["aspect"] in ("PRESENCE","INTENSITY","DURATION"):return "REVIEW_REQUIRED"
   return "V2_REQUIRED" # This guard is NEVER an independent proof of SUPPORT
 fake_sim=0.999999
 assert admission(scope,unsupported,fake_sim)=="REVIEW_REQUIRED"
 assert admission(scope,scope,fake_sim)=="V2_REQUIRED"
 step("SEMANTIC_TYPE_SAFETY",True,{"false_supported":0,
      "note":"Guard demonstration only; not the real PsyAI V2 clinical gate"})
 result["raw_embeddings_persisted"]=False
 result["status"]="PASS"
except Exception as exc:
 result["status"]="BLOCKED"
 result["failure_type"]=type(exc).__name__
 result["failure_stage"]=(result["stages"][-1]["stage"] if result["stages"] else "PRESTART")
for k in list(result):
 assert k not in ("dialogue","sources","embedding_vectors")
payload=json.dumps(result,ensure_ascii=True,sort_keys=True,separators=(",",":"))
result["receipt_sha256"]=hashlib.sha256(payload.encode("ascii")).hexdigest()
print("PSYAI_E5_RESULT="+json.dumps(result,ensure_ascii=True,sort_keys=True,separators=(",",":")),flush=True)
"""
def main():
    outfile=Path("psyai-real-e5-colab-proof.json")
    receipt={"schema":SCHEMA,"status":"BLOCKED","synthetic_only":True,"gemma_generation":False}
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        receipt["reason"]="EXISTING_ADC_ABSENT"
    else:
        try:
            with tempfile.TemporaryDirectory(prefix="psyai-real-e5-") as d:
                p=Path(d)/"e5_colab.py"
                p.write_text(REMOTE,encoding="utf8")
                run=subprocess.run(["colab","--auth=adc","run","--gpu","T4","--timeout","600",str(p)],
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=930,check=False)
                raw=run.stdout.decode("utf8","replace")
                found=[x.split("PSYAI_E5_RESULT=",1)[1].strip() for x in raw.splitlines() if "PSYAI_E5_RESULT=" in x]
                if run.returncode or len(found)!=1:
                    receipt["reason"]="NO_REMOTE_RECEIPT"
                    low=raw.lower()
                    receipt["transport_diagnostic"]={
                        "exit_code":run.returncode,
                        "remote_session_ready":"session ready" in low,
                        "remote_execution_started":"executing" in low,
                        "kernel_timeout":"timeout waiting for output" in low,
                        "backend_allocation_rejected":"allocation refused" in low or "backend rejected" in low,
                        "remote_python_traceback":"traceback (most recent call last)" in low,
                        "out_of_memory":"out of memory" in low or "cuda out of memory" in low,
                        "module_missing":"modulenotfounderror" in low,
                        "cli_argument_error":"no such option" in low or "unexpected extra argument" in low,
                        "no_receipt":len(found)!=1}
                    raise RuntimeError("SAFE_DIAGNOSTIC_RECORDED")
                reply=json.loads(found[0]);claim=reply.pop("receipt_sha256",None)
                actual=hashlib.sha256(json.dumps(reply,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii")).hexdigest()
                if reply.get("schema")!=SCHEMA or claim!=actual or reply.get("synthetic_only") is not True:
                    raise ValueError("BAD_REMOTE_RECEIPT")
                reply["receipt_sha256"]=claim
                receipt=reply
        except subprocess.TimeoutExpired:receipt["reason"]="COLAB_TIMEOUT"
        except RuntimeError:pass
        except (KeyError,ValueError,TypeError):receipt["reason"]="INVALID_OR_MISSING_REMOTE_RECEIPT"
    outfile.write_text(json.dumps(receipt,indent=2,ensure_ascii=True)+"\n")
    print("PSYAI_REAL_E5_COLAB_STATUS="+receipt["status"])
    if receipt.get("reason"):print("PSYAI_REAL_E5_COLAB_REASON="+receipt["reason"])
    return 0 if receipt["status"]=="PASS" else 2
if __name__=="__main__":sys.exit(main())
