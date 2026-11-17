#!/usr/bin/env python3
"""One bounded T4 run of the real PsyAI E→S→V2→PDF/DOCX pipeline on 34 synthetic turns.
Never transfers real consultations. Private source is read-only and deleted after use.
No EXE, no AVRORA, no automatic retries. Only allowlisted aggregate metrics leave Colab.
"""
from __future__ import annotations
import base64,gzip,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from psyai_private_colab_runner import source_archive,sha,canon

SCHEMA="PSYAI_GEMMA34_FULL_SYNTH_V1"
MARKER="PSYAI_GEMMA34_RECEIPT="
OUT=Path("psyai-gemma34-fullpath-proof.json")
REMOTE=r'''
import base64,hashlib,gzip,io,json,os,pathlib,subprocess,sys,tarfile,tempfile,time,threading,urllib.request
SCHEMA="PSYAI_GEMMA34_FULL_SYNTH_V1"
MARKER="PSYAI_GEMMA34_RECEIPT="
REV="__REV__"
PACK_SHA="__PACK_SHA__"
PACK="__PACK__"
MODEL_REPO="google/gemma-4-12B-it-qat-q4_0-gguf"
MODEL_REV="ef7b15515d7ed7f34305a08edb5717e7989d6dc9"
MODEL_FILE="gemma-4-12b-it-qat-q4_0.gguf"
MODEL_SHA="93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b"
LLAMA_REV="ad9d9e8f50e6ff9a6bfbbdd3aef6d74a8428cf4e"
p={"schema":SCHEMA,"status":"BLOCKED","case":"SYNTHETIC_34_NOT_REAL_CASE34",
  "source_sha":REV,"model_sha_verified":False,"real_gemma_generation":False,
  "full_psychological_bundle":False,"quality_acceptance":"NOT_VERIFIED",
  "original_case34_seconds":None,"10_to_15min_real_case34":"NOT_VERIFIED",
  "stages":[]}
START=time.monotonic();server=None
def stage(name,ok=True,extra=None):
 row={"name":name,"pass":bool(ok),"total_elapsed_s":round(time.monotonic()-START,1)}
 row.update(extra or {})
 p["stages"].append(row)
 print("PSYAI_STEP_"+name+"="+("PASS" if ok else "FAIL"),flush=True)
def run(cmd,cwd=None,timeout=600):
 return subprocess.run(cmd,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,check=False,timeout=timeout)
def gpu():
 q=subprocess.run(["nvidia-smi","--query-gpu=name,memory.total,memory.free","--format=csv,noheader,nounits"],
   stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15)
 if q.returncode:raise RuntimeError("GPU_MISSING")
 v=q.stdout.decode().splitlines()[0].split(",")
 return v[0].strip(),int(v[1]),int(v[2])
def rpc(path,data=None,timeout=30):
 u="http://127.0.0.1:18880"+path
 if data is None:req=urllib.request.Request(u)
 else:req=urllib.request.Request(u,json.dumps(data,ensure_ascii=False).encode("utf8"),
    {"Content-Type":"application/json"},method="POST")
 with urllib.request.urlopen(req,timeout=timeout) as f:return json.load(f)
def stop_guard(proc,free):
 flags={"peak_mib":0,"tripped":False}
 def watch():
  while proc.poll() is None:
   try:
    _,_,available=gpu()
    flags["peak_mib"]=max(flags["peak_mib"],free-available)
    if flags["peak_mib"]>8192:
     flags["tripped"]=True;proc.terminate();break
   except Exception:pass
   time.sleep(.4)
 t=threading.Thread(target=watch,daemon=True);t.start()
 return flags,t
try:
 os.environ["PSYAI_SKIP_AUTO_INSTALL"]="1"
 os.environ["PYTHONDONTWRITEBYTECODE"]="1"
 name,mem,free=gpu()
 if "T4" not in name:raise RuntimeError("GPU_NOT_T4")
 p["gpu_name"]=name;p["total_vram_mib"]=mem
 stage("T4_ALLOCATED")
 with tempfile.TemporaryDirectory(prefix="psyai-gemma34-") as td:
  base=pathlib.Path(td);app=base/"app";app.mkdir()
  packed=base64.b64decode(PACK,validate=True)
  if hashlib.sha256(packed).hexdigest()!=PACK_SHA:raise RuntimeError("SOURCE_ARCHIVE_BAD_HASH")
  with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as archive:
   for item in archive.getmembers():
    rel=pathlib.PurePosixPath(item.name)
    if rel.is_absolute() or ".." in rel.parts or not(item.isfile() or item.isdir()):
     raise RuntimeError("SOURCE_ARCHIVE_UNSAFE")
   archive.extractall(app,filter="data")
  sys.path.insert(0,str(app))
  stage("PRIVATE_SOURCE_READ_ONLY")
  if run([sys.executable,"-m","pip","install","-q","-r","requirements.txt","-r","requirements-dev.txt","huggingface_hub"],cwd=app,timeout=550).returncode:
   raise RuntimeError("DEPENDENCIES_FAILED")
  stage("DEPENDENCIES")
  from huggingface_hub import hf_hub_download
  t0=time.monotonic()
  try:model=pathlib.Path(hf_hub_download(repo_id=MODEL_REPO,revision=MODEL_REV,
   filename=MODEL_FILE,local_dir=str(base/"model"),token=False,etag_timeout=30))
  except Exception:raise RuntimeError("GEMMA_DOWNLOAD_FAILED") from None
  h=hashlib.sha256()
  with model.open("rb") as f:
   for block in iter(lambda:f.read(8*1024*1024),b""):h.update(block)
  if h.hexdigest()!=MODEL_SHA:raise RuntimeError("GEMMA_SHA_MISMATCH")
  p["model_sha_verified"]=True
  p["download_verify_s"]=round(time.monotonic()-t0,2)
  stage("GEMMA_GGUF_VERIFIED")
  llama=base/"llama.cpp";t0=time.monotonic()
  if run(["git","clone","--quiet","--depth","1","https://github.com/ggml-org/llama.cpp.git",str(llama)],timeout=330).returncode:
   raise RuntimeError("LLAMA_CLONE_FAILED")
  if run(["git","-C",str(llama),"fetch","--quiet","--depth","1","origin",LLAMA_REV],timeout=130).returncode:
   raise RuntimeError("LLAMA_PIN_FAILED")
  if run(["git","-C",str(llama),"checkout","--quiet",LLAMA_REV],timeout=30).returncode:
   raise RuntimeError("LLAMA_PIN_FAILED")
  if run(["cmake","-S",str(llama),"-B",str(llama/"build"),"-DGGML_CUDA=ON",
          "-DLLAMA_BUILD_TESTS=OFF","-DLLAMA_CURL=OFF","-DCMAKE_CUDA_ARCHITECTURES=75"],timeout=350).returncode:
   raise RuntimeError("CUDA_CONFIG_FAILED")
  if run(["cmake","--build",str(llama/"build"),"--target","llama-server","-j","4"],timeout=1080).returncode:
   raise RuntimeError("CUDA_BUILD_FAILED")
  p["build_s"]=round(time.monotonic()-t0,2)
  stage("PINNED_LLAMA_CUDA_BUILT")
  exe=next((x for x in (llama/"build").rglob("llama-server") if x.is_file() and os.access(x,os.X_OK)),None)
  if exe is None:raise RuntimeError("SERVER_BIN_MISSING")
  # Existing 8 GiB VRAM target, with CPU fallback for other layers.
  args=[str(exe),"-m",str(model),"-ngl","16","-c","16384","-b","128","-ub","128",
     "-t","8","--host","127.0.0.1","--port","18880","--jinja"]
  log=(base/"private_model.log").open("wb")
  server=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  flags,thread=stop_guard(server,free)
  t0=time.monotonic();ready=False
  for _ in range(300):
   if server.poll() is not None:break
   try:
    state=rpc("/health",timeout=2)
    if state.get("status")=="ok":ready=True;break
   except Exception:time.sleep(1)
  p["load_s"]=round(time.monotonic()-t0,2)
  if flags["tripped"]:raise RuntimeError("VRAM_LIMIT_REACHED")
  if not ready:raise RuntimeError("SERVER_BOOT_FAILED")
  stage("REAL_GEMMA_SERVER",True,{"context":16384,"offloaded_layers":16})
  t0=time.monotonic()
  try:
   response=rpc("/v1/chat/completions",{"messages":[{"role":"user","content":"Ответь одним словом: что помогает кораблю найти берег ночью?"}],
         "max_tokens":45,"temperature":0.0},timeout=220)
  except Exception:raise RuntimeError("CANARY_GENERATION_FAILED") from None
  value=response.get("choices",[{}])[0].get("message",{}).get("content")
  if not isinstance(value,str) or not value.strip():raise RuntimeError("CANARY_EMPTY")
  p["canary_s"]=round(time.monotonic()-t0,2)
  p["real_gemma_generation"]=True
  stage("REAL_GEMMA_RESPONSE")
  import deep_analysis as deep
  import analysis_bundle as ab
  import analysis_bundle_rag as ragmod
  import context_window as cw
  import deep_analysis_report as exporter
  phrases=[
   "В последнее время я чаще замечаю напряжение перед встречами.",
   "Когда вы впервые заметили это переживание?",
   "В начале месяца я волновался перед разговором с коллегой.",
   "Как вы тогда ощущали себя?",
   "Я почувствовал тошноту и подумал, что не справлюсь.",
   "Что вы сделали после этой мысли?",
   "Я позвонил другу и начал с ним разговаривать.",
   "Что произошло с вашим вниманием?",
   "Я отвлёкся и на какое-то время забыл о тошноте.",
   "Вы имеете в виду, что тошнота исчезла?",
   "Нет, я этого не говорил, просто перестал думать о ней.",
   "Что для вас значило это различие?",
   "Я заметил, что могу переключаться на другие дела.",
   "Как вы проверяли, что именно изменилось?",
   "Я пока никак не проверял состояние тела.",
   "Могли ли быть и другие объяснения?",
   "Возможно, настроение изменилось из-за разговора, но я не знаю.",
   "Как менялись переживания в других обстоятельствах?",
   "В магазине я тоже отвлекался, но иногда снова тревожился.",
   "Как вы относитесь к возвращению тревоги?",
   "Меня это огорчает, кажется, будто я потерял контроль.",
   "Что помогало вам раньше?",
   "Я гулял и разговаривал с друзьями.",
   "Какие отношения для вас сейчас важны?",
   "Мне важно чувствовать уважение и самостоятельность.",
   "Что происходит, когда этого не хватает?",
   "Я начинаю раздражаться и замыкаюсь.",
   "Как вам кажется, что за этим может стоять?",
   "Может быть, страх оценки, но я не уверен.",
   "Что бы вы хотели исследовать дальше?",
   "Я хочу лучше понимать, откуда приходит тревога.",
   "Есть ли ситуации, где вы чувствовали себя устойчивее?",
   "Да, когда обсуждал проблемы спокойно, но это бывало не всегда.",
   "Давайте уточним, какие условия отличали эти случаи."
  ]
  assert len(phrases)==34
  transcript=[{"id":"u%02d"%(i+1),"speaker":"Клиент" if i%2==0 else "Психолог",
       "role":"client" if i%2==0 else "therapist","text":phrase}
       for i,phrase in enumerate(phrases)]
  prepared=deep.prepare({"client_uuid":"synthetic-acceptance","session_uuid":"synthetic-34",
    "label":"SYNTHETIC_34","data_sha":deep.digest(transcript),
    "roles_confirmed":True,"transcript":transcript},1)
  assert len(prepared["references"])==34
  stage("SYNTHETIC_DIALOGUE_34")
  # No private RAG books available in Colab. Run full E/S/V2, with empty research corpus.
  deep.library_fingerprint=lambda _:"synthetic-empty-library"
  ragmod.retrieve=lambda *a,**kw: ({},[],{"index_sha":"synthetic-empty-library",
    "status":"no_imported_books","topics":[],"timings":{},"generation_calls":0})
  token_counter=cw.TokenCounter(server=lambda:("http://127.0.0.1:18880/v1","bench"))
  window=cw.Window(16384,token_counter,max_output=3000,source="actual-llama-T4")
  stages={}
  def on_stage(n):stages[str(n)]=round(time.monotonic()-analysis_started,2)
  sent=[]
  def chat(messages,**kwargs):
   task="UNKNOWN"
   try:task=json.loads(messages[1]["content"]).get("task","UNKNOWN")
   except Exception:pass
   t0=time.monotonic()
   body={"messages":messages,"temperature":kwargs.get("temperature",0.15),
      "max_tokens":kwargs.get("max_tokens",1800),"response_format":kwargs.get("response_format")}
   try:
    answer=rpc("/v1/chat/completions",body,timeout=min(700,max(90,int(kwargs.get("timeout",600))+30)))
   except Exception:raise RuntimeError("MODEL_REQUEST_FAILED") from None
   choice=answer["choices"][0]
   content=choice["message"].get("content")
   usage=answer.get("usage",{})
   duration=round(time.monotonic()-t0,2)
   sent.append({"task":task,"seconds":duration,
      "prompt_tokens":usage.get("prompt_tokens"),"completion_tokens":usage.get("completion_tokens"),
      "finish_reason":choice.get("finish_reason")})
   if not isinstance(content,str) or not content:raise RuntimeError("MODEL_EMPTY_RESPONSE")
   if choice.get("finish_reason")=="length":raise deep.DeepError("model_truncated_output")
   return content,"gemma-4-12b-it-qat-q4_0"
  analysis_started=time.monotonic()
  try:
   result=ab.generate(prepared,object(),chat,window,selection={"candidates":[]},
        model="gemma-4-12b-it-qat-q4_0",phase=on_stage)
   p["full_psychological_bundle"]=True
  except Exception as exc:
   p["analysis_error_type"]=type(exc).__name__
   p["analysis_error_code"]=str(exc)[:110] if type(exc).__name__ in ("DeepError",) else "UNVERIFIED"
   result=None
  p["analysis_seconds"]=round(time.monotonic()-analysis_started,2)
  p["call_count"]=len(sent)
  p["model_calls"]=sent
  p["stage_times_s"]=stages
  p["peak_extra_vram_mib"]=flags["peak_mib"]
  stage("REAL_PSYAI_E_S_V2",bool(result),{"analysis_seconds":p["analysis_seconds"],"calls":len(sent)})
  if result is not None:
   from collections import Counter
   stats=Counter(ab.atomic_claim_status(result,c) for c in result.get("claims",[]))
   p["claim_status_counts"]=dict(stats)
   p["hypotheses"]=sum(c.get("kind")=="hypothesis" for c in result.get("claims",[]))
   p["accepted_edges"]=len(result.get("analysis_bundle",{}).get("visualizations",{}).get("edges",[]))
   snapshot={"result":result,"revision":1,"stale":False,"status":"draft",
      "include_full":True}
   t0=time.monotonic()
   try:
    pdf=exporter.pdf(snapshot)
    docx=exporter.docx(snapshot)
    p["pdf_valid"]=pdf[:4]==b"%PDF"
    p["docx_valid"]=docx[:2]==b"PK"
   except Exception:
    p["pdf_valid"]=False;p["docx_valid"]=False
   p["export_seconds"]=round(time.monotonic()-t0,2)
   stage("PDF_AND_WORD_EXPORT",p["pdf_valid"] and p["docx_valid"])
   p["quality_acceptance"]="STRUCTURAL_ONLY_NO_REAL_CASE34_EXPERT_REVIEW"
   if p["pdf_valid"] and p["docx_valid"]:
    p["status"]="SYNTHETIC_REAL_MODEL_E2E_PASS"
  if not p["full_psychological_bundle"]:
   p["status"]="REAL_MODEL_PARTIAL_FAIL"
  if flags["tripped"]:p["status"]="VRAM_LIMIT_REACHED"
except BaseException as exc:
 p["status"]="BLOCKED"
 msg=str(exc)
 allow={"GPU_MISSING","GPU_NOT_T4","SOURCE_ARCHIVE_BAD_HASH","SOURCE_ARCHIVE_UNSAFE",
  "DEPENDENCIES_FAILED","GEMMA_DOWNLOAD_FAILED","GEMMA_SHA_MISMATCH",
  "LLAMA_CLONE_FAILED","LLAMA_PIN_FAILED","CUDA_CONFIG_FAILED",
  "CUDA_BUILD_FAILED","SERVER_BIN_MISSING","VRAM_LIMIT_REACHED",
  "SERVER_BOOT_FAILED","CANARY_GENERATION_FAILED","CANARY_EMPTY"}
 p["blocked_reason"]=msg if msg in allow else type(exc).__name__
finally:
 try:
  if server is not None and server.poll() is None:
   server.terminate()
   try:server.wait(timeout=8)
   except subprocess.TimeoutExpired:server.kill();server.wait()
 except Exception:pass
 p["total_runtime_s"]=round(time.monotonic()-START,2)
 p["receipt_sha256"]=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(",",":"),
   ensure_ascii=True).encode("ascii")).hexdigest()
 print(MARKER+json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=True),flush=True)
'''
def main():
    receipt={"schema":SCHEMA,"status":"BLOCKED","reason":"PREPARE_FAILED"}
    try:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("EXISTING_COLAB_ADC_ABSENT")
        if not Path("private_psyai").is_dir():
            raise ValueError("PRIVATE_PSYAI_SOURCE_MISSING")
        rev,packed=source_archive()
        with tempfile.TemporaryDirectory(prefix="psyai-gemma34-bridge-") as tmp:
            d=Path(tmp);script=d/"remote.py";log=d/"log.txt"
            payload=REMOTE.replace("__REV__",rev).replace("__PACK_SHA__",sha(packed)).replace("__PACK__",base64.b64encode(packed).decode("ascii"))
            compile(payload,"psyai_gemma34_remote.py","exec")
            script.write_text(payload,encoding="utf8")
            script.chmod(0o600)
            with log.open("wb") as out:
                p=subprocess.run(["colab","--auth=adc","run","--gpu","T4","--timeout","1750",str(script)],
                    stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=2700,check=False)
            raw=log.read_text(encoding="utf8",errors="replace")
            candidates=[line.split(MARKER,1)[1].strip()
                for line in raw.splitlines() if MARKER in line]
            if len(candidates)!=1:
                receipt={"schema":SCHEMA,"status":"BLOCKED",
                 "reason":"REMOTE_RECEIPT_MISSING","cli_code":p.returncode,
                 "transport_diagnostic":{"allocated":"session ready" in raw.lower(),
                   "kernel_started":"executing" in raw.lower(),
                   "timeout":"timeout" in raw.lower(),
                   "traceback":"traceback (most recent call last)" in raw.lower(),
                   "capacity":"allocation refused" in raw.lower(),
                   "quota":"backend rejected" in raw.lower()}}
            else:
                proof=json.loads(candidates[0]);h=proof.pop("receipt_sha256",None)
                actual=sha(canon(proof).encode("ascii"))
                if h!=actual or proof.get("source_sha")!=rev or proof.get("schema")!=SCHEMA:
                    raise ValueError("REMOTE_PROOF_INVALID")
                proof["receipt_sha256"]=h;receipt=proof
    except subprocess.TimeoutExpired:
        receipt={"schema":SCHEMA,"status":"BLOCKED","reason":"COLAB_TRANSPORT_LIMIT"}
    except Exception as e:
        code=str(e)
        receipt={"schema":SCHEMA,"status":"BLOCKED",
                 "reason":code if code in {"EXISTING_COLAB_ADC_ABSENT","PRIVATE_PSYAI_SOURCE_MISSING","REMOTE_PROOF_INVALID"} else type(e).__name__}
    OUT.write_text(json.dumps(receipt,indent=2,ensure_ascii=True)+"\n",encoding="utf8")
    print("PSYAI_GEMMA34_STATUS="+receipt["status"],flush=True)
    print("PSYAI_GEMMA34_STEPS="+str(len(receipt.get("stages",[]))),flush=True)
    print("PSYAI_GEMMA34_REASON="+receipt.get("reason",receipt.get("blocked_reason","")),flush=True)
    # Exit nonzero only for invalid transport, blocked, or missing real bundle.
    return 0 if receipt["status"]=="SYNTHETIC_REAL_MODEL_E2E_PASS" else 2
if __name__=="__main__":sys.exit(main())
