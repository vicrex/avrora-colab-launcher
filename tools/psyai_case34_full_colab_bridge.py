#!/usr/bin/env python3
"""One-shot private CASE34 → already-authorized Colab T4, no raw GitHub output.

Source comes exclusively from verified private GitHub SSH checkout; dialogue
comes exclusively from the owner's Actions encrypted secret. Both are packed
into a temporary 0600 Colab script transmitted over the existing Colab ADC.
No output containing dialogue, model text, or source code is published.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
import time

SCHEMA="PSYAI_CASE34_FULL_COLAB_V1"
MARKER="PSYAI_CASE34_FULL_RECEIPT="
SOURCE=Path("private_psyai")
OUTPUT=Path("psyai_case34_full_proof.json")
TEMPLATE=Path("tools/psyai_case34_colab_full_remote.py")
GPU_HELPER=Path("tools/psyai_case34_gpu8_colab_probe.py")
ORIGINAL_SHA="3fb91a7a0286389073d0da9099d99081b6d49e913b7d34381e359d744d0720cc"
REV_RE=r"[a-f0-9]{40}"
DROPPED_TOP={".github","docs","tests","reports","notebooks","examples"}
FORBIDDEN_NAMES={".env","id_rsa","id_ed25519","credentials.json",
                 "service-account.json","арете-кейс-01.txt"}
FORBIDDEN_SUFFIX={".pem",".p12",".pfx",".key",".db",".sqlite",
                  ".sqlite3",".gguf",".pdf",".docx",".zip",".tar",".gz"}


def canon(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True)

def sha(v):
    return hashlib.sha256(v).hexdigest()

def private_source_archive():
    if not SOURCE.is_dir():raise ValueError("PRIVATE_SOURCE_CHECKOUT_MISSING")
    rev=subprocess.check_output(["git","-C",str(SOURCE),"rev-parse","HEAD"],
        stderr=subprocess.DEVNULL,timeout=20).decode().strip()
    if not re.fullmatch(REV_RE,rev):raise ValueError("PRIVATE_SOURCE_COMMIT_INVALID")
    raw=subprocess.check_output(["git","-C",str(SOURCE),"archive","--format=tar",
        rev],stderr=subprocess.DEVNULL,timeout=100)
    output=io.BytesIO()
    count=0
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:") as inp:
        with tarfile.open(fileobj=output,mode="w") as out:
            for m in inp.getmembers():
                p=PurePosixPath(m.name)
                if p.is_absolute() or ".." in p.parts or not (m.isdir() or m.isfile()):
                    raise ValueError("UNSAFE_PRIVATE_ARCHIVE_ENTRY")
                if p.parts[0] in DROPPED_TOP:
                    continue
                name=p.name.lower()
                if name in FORBIDDEN_NAMES or any(name.endswith(s) for s in FORBIDDEN_SUFFIX):
                    raise ValueError("FORBIDDEN_PRIVATE_ARCHIVE_CONTENT")
                if m.isdir():
                    out.addfile(m)
                else:
                    source_file=inp.extractfile(m)
                    if not source_file:raise ValueError("INVALID_PRIVATE_ARCHIVE_MEMBER")
                    out.addfile(m,source_file)
                    count+=1
    if not 100 <= count <= 5000:
        raise ValueError("PRIVATE_SOURCE_FILE_COUNT_UNEXPECTED")
    packed=gzip.compress(output.getvalue(),compresslevel=9,mtime=0)
    if len(packed)>22_000_000:
        raise ValueError("PRIVATE_SOURCE_ARCHIVE_OVER_LIMIT")
    return rev,packed,count


def verify_original_secret():
    encoded=os.environ.get("PSYAI_CASE34_SOURCE_B64","").strip()
    if not encoded:raise ValueError("CASE34_ENCRYPTED_SOURCE_SECRET_MISSING")
    if len(encoded)>50000:raise ValueError("CASE34_SECRET_TOO_LARGE")
    try:raw=base64.b64decode(encoded,validate=True)
    except (ValueError,base64.binascii.Error):
        raise ValueError("CASE34_SECRET_B64_BAD") from None
    if len(raw)!=13098 or sha(raw)!=ORIGINAL_SHA:
        raise ValueError("CASE34_ORIGINAL_HASH_MISMATCH")
    text=raw.decode("utf-8-sig")
    markers=re.findall(r"(?m)^[ \t]*(Клиент|Психолог)\s*:\s*",text)
    if len(markers)!=34 or markers.count("Клиент")!=17 or markers.count("Психолог")!=17:
        raise ValueError("CASE34_ORIGINAL_ROLES_MISMATCH")
    return raw


def build_ephemeral_script(src_sha,packed,original,helper):
    if not re.fullmatch(REV_RE,src_sha):raise ValueError("INVALID_SOURCE_SHA")
    if sha(original)!=ORIGINAL_SHA:raise ValueError("WRONG_ORIGINAL")
    text=TEMPLATE.read_text(encoding="utf-8")
    replace={
        "__PSYAI_PRIVATE_GIT_ARCHIVE_B64__":base64.b64encode(packed).decode("ascii"),
        "__PSYAI_PRIVATE_GIT_ARCHIVE_SHA256__":sha(packed),
        "__PSYAI_PRIVATE_GIT_COMMIT_SHA__":src_sha,
        "__PSYAI_CASE34_PRIVATE_ORIGINAL_B64__":base64.b64encode(original).decode("ascii"),
        "__PSYAI_PINNED_GPU8_HELPER_B64__":base64.b64encode(helper).decode("ascii"),
    }
    for key,value in replace.items():
        if text.count(key)!=1:
            raise ValueError("REMOTE_TEMPLATE_PLACEHOLDER_CONTRACT_FAIL")
        text=text.replace(key,value)
    if len(text)>30_000_000:
        raise ValueError("REMOTE_SCRIPT_SIZE_LIMIT")
    compile(text,"<private_generated_colab_script>","exec")
    return text


def safe_gpu_allocation_reason(log):
    """Return only a fixed reason code; no remote log is emitted."""
    fragment=log.read_bytes()[-16000:].decode("utf-8","replace").lower()
    if any(x in fragment for x in ("failed to assign","toomanyassignments","http 412","status 412","accelerator unavailable")):
        return "COLAB_GPU_ASSIGNMENT_REJECTED"
    if any(x in fragment for x in ("not entitled","no access to gpu")):
        return "COLAB_GPU_NOT_ENTITLED"
    return "OTHER_FAILURE"


def bounded_receipt(log,original_sha,expected_src):
    # Never expose or return raw remote log content. Parse ONLY exact bounded
    # generated marker line and then restrict its fields by schema.
    lines=log.read_text(encoding="utf-8",errors="replace").splitlines()
    records=[x.split(MARKER,1)[1] for x in lines if MARKER in x]
    if len(records)!=1:raise ValueError("REMOTE_RECEIPT_MISSING_OR_DUPLICATE")
    parsed=json.loads(records[0])
    checksum=parsed.pop("receipt_sha256","")
    if not isinstance(checksum,str) or sha(canon(parsed).encode("ascii"))!=checksum:
        raise ValueError("REMOTE_RECEIPT_SHA_INVALID")
    if (parsed.get("schema")!=SCHEMA or parsed.get("source_sha")!=expected_src
        or parsed.get("case34_original_sha256_verified") is not True
        or parsed.get("source_published") is not False):
        raise ValueError("REMOTE_RECEIPT_CONTRACT_INVALID")
    # Block arbitrary free text: only numeric / known boolean fields.
    allowed={"schema","status","source_sha","source_private","source_published",
             "model_started","generation_verified","full_case34",
             "target_seconds","vram_cap_mib","stages","case34_original_sha256_verified",
             "model_sha256_verified","e5_revision","nli_revision","result_receipt",
             "case34_status","full_analysis_seconds","analysis_seconds",
             "export_seconds","wall_total_seconds","real_gemma","performance",
             "quality","model_claims","graph_edges","graph_edge_candidates",
             "hypothesis_count","hybrid_shadow_seconds","failure_codes",
             "pdf_bytes","pdf_sha256","docx_bytes","docx_sha256",
             "execution_exit_code","case34_execution_seconds","reason_code",
             "elapsed_seconds","automated_checks_pass",
              "model_calls","cache_hits","retries","input_tokens",
              "output_tokens","prefill_seconds","decode_seconds",
              "psyai_last_stage","psyai_stage_count"}
    proof={k:parsed[k] for k in allowed if k in parsed}
    if proof.get("status") not in {"CANDIDATE_FOR_EXPERT_REVIEW","NOT_ACCEPTED",
                                 "BLOCKED_OR_FAILED"}:
        raise ValueError("REMOTE_INVALID_RESULT_STATE")
    proof["receipt_sha256"]=sha(canon(proof).encode("ascii"))
    return proof


def blocked(reason):
    if not re.fullmatch(r"[A-Z_0-9]{2,75}",reason):reason="UNCLASSIFIED_ERROR"
    value={"schema":SCHEMA,"status":"BLOCKED_OR_FAILED","reason_code":reason,
           "full_case34":False,"case34_original_sha256_verified":False,
           "source_published":False}
    value["receipt_sha256"]=sha(canon(value).encode("ascii"))
    return value


def main():
    proof=blocked("NOT_STARTED")
    try:
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("EXISTING_COLAB_ADC_MISSING")
        original=verify_original_secret()
        src_sha,packed,count=private_source_archive()
        expected=os.environ.get("PSYAI_CASE34_PINNED_PRIVATE_SHA","")
        if src_sha!=expected or not re.fullmatch(REV_RE,expected):
            raise ValueError("PRIVATE_SOURCE_SHA_NOT_PINNED")
        helper=GPU_HELPER.read_bytes()
        with tempfile.TemporaryDirectory(prefix="psyai-case34-colab-private-") as directory:
            path=Path(directory)/"remote_private_case34.py"
            log=Path(directory)/"remote_capture.log"
            path.write_text(build_ephemeral_script(src_sha,packed,original,helper),
                            encoding="utf-8")
            path.chmod(0o600)
            print("CASE34_COLAB_FULL_REAL_EXECUTION_START",flush=True)
            proof=None
            for variant in ("T4","L4"):
                with log.open("wb") as output:
                    try:
                        child=subprocess.run(["colab","--auth=adc","run","--gpu",variant,
                            "--timeout","3000",str(path)],stdout=output,stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,timeout=3300,check=False)
                        returncode=child.returncode
                    except (OSError,subprocess.TimeoutExpired):
                        raise ValueError("COLAB_PRIVATE_TRANSPORT_TIMEOUT") from None
                if returncode:
                    reason=safe_gpu_allocation_reason(log)
                    if variant=="T4" and reason=="COLAB_GPU_ASSIGNMENT_REJECTED":
                        print("CASE34_T4_REFUSED_TRY_L4_ONCE",flush=True)
                        continue
                    if reason!="OTHER_FAILURE":
                        proof=blocked(reason)
                        break
                proof=bounded_receipt(log,ORIGINAL_SHA,src_sha)
                proof["colab_exit_code"]=returncode
                proof["gpu_variant"]=variant
                proof["receipt_sha256"]=sha(canon({k:v for k,v in proof.items()
                                                    if k!="receipt_sha256"}).encode("ascii"))
                break
            if proof is None:raise ValueError("COLAB_GPU_ASSIGNMENT_REJECTED")
            allowed=proof.get("status")=="CANDIDATE_FOR_EXPERT_REVIEW" and returncode==0
            if not allowed:print("CASE34_COLAB_FULL_NOT_ACCEPTED",flush=True)
    except (ValueError,OSError,subprocess.CalledProcessError,json.JSONDecodeError) as exc:
        allowed={"CASE34_ENCRYPTED_SOURCE_SECRET_MISSING","CASE34_SECRET_TOO_LARGE",
                 "CASE34_SECRET_B64_BAD","CASE34_ORIGINAL_HASH_MISMATCH",
                 "CASE34_ORIGINAL_ROLES_MISMATCH","PRIVATE_SOURCE_CHECKOUT_MISSING",
                 "PRIVATE_SOURCE_COMMIT_INVALID","UNSAFE_PRIVATE_ARCHIVE_ENTRY",
                 "FORBIDDEN_PRIVATE_ARCHIVE_CONTENT","PRIVATE_SOURCE_FILE_COUNT_UNEXPECTED",
                 "PRIVATE_SOURCE_ARCHIVE_OVER_LIMIT","EXISTING_COLAB_ADC_MISSING",
                 "PRIVATE_SOURCE_SHA_NOT_PINNED","COLAB_PRIVATE_TRANSPORT_TIMEOUT",
                 "REMOTE_RECEIPT_MISSING_OR_DUPLICATE","REMOTE_RECEIPT_SHA_INVALID",
                 "REMOTE_RECEIPT_CONTRACT_INVALID","REMOTE_INVALID_RESULT_STATE",
                 "REMOTE_SCRIPT_SIZE_LIMIT","REMOTE_TEMPLATE_PLACEHOLDER_CONTRACT_FAIL",
                 "WRONG_ORIGINAL","INVALID_SOURCE_SHA"}
        code=str(exc)
        proof=blocked(code if code in allowed else "CASE34_COLAB_UNKNOWN_BLOCKER")
    OUTPUT.write_text(canon(proof)+"\n",encoding="ascii")
    print("CASE34_COLAB_FULL_STATUS="+proof["status"],flush=True)
    return 0 if proof["status"]=="CANDIDATE_FOR_EXPERT_REVIEW" else 2


if __name__=="__main__":
    raise SystemExit(main())
