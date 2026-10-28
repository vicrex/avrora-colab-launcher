"""Run a private PsyAI checkout on Colab CPU without publishing its source or logs.

Existing Colab ADC authenticates Google, not GitHub. The source checkout must be
read-only and separately authorized. Only synthetic test data are permitted.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

MARKER = "PSYAI_PRIVATE_COLAB_EVIDENCE="
SCHEMA = "PSYAI_PRIVATE_COLAB_PREWINDOWS_V1"
SOURCE = Path("private_psyai")
OUTPUT = Path("psyai-private-colab-proof.json")

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def blocked(reason):
    x = {"schema": SCHEMA, "status": "BLOCKED", "reason": reason,
         "model_e2e": False, "windows_e2e": False, "full_tz_accepted": False}
    x["receipt_sha256"] = sha(canon(x).encode("ascii"))
    return x

def source_archive():
    rev = subprocess.check_output(
        ["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
        timeout=15, stderr=subprocess.DEVNULL).decode().strip()
    if not re.fullmatch("[a-f0-9]{40}", rev):
        raise ValueError("SOURCE_SHA_INVALID")
    raw = subprocess.check_output(
        ["git", "-C", str(SOURCE), "archive", "--format=tar", "HEAD"],
        timeout=60, stderr=subprocess.DEVNULL)
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        members = tar.getmembers()
    if not 50 <= len(members) <= 5000:
        raise ValueError("UNEXPECTED_SOURCE_FILE_COUNT")
    forbidden_names = {".env", "id_rsa", "id_ed25519", "credentials.json", "service-account.json"}
    forbidden_ext = (".pem", ".p12", ".pfx", ".key", ".sqlite", ".sqlite3", ".db", ".gguf")
    for item in members:
        path = Path(item.name)
        if (not item.isfile() and not item.isdir()) or path.is_absolute() or ".." in path.parts:
            raise ValueError("UNSAFE_ARCHIVE_ENTRY")
        if path.name.lower() in forbidden_names or path.name.lower().endswith(forbidden_ext):
            raise ValueError("FORBIDDEN_TRACKED_SECRET_OR_DATA")
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    if len(packed) > 22_000_000:
        raise ValueError("SOURCE_ARCHIVE_EXCEEDS_LIMIT")
    return rev, packed

def remote_script(revision, packed):
    # PRIVATE source is embedded only in a temporary runner file, then passed
    # to the same authenticated Colab CPU used by the existing launcher.
    template = r'''import base64,collections,gzip,hashlib,io,json,os,pathlib,re,subprocess,sys,tarfile,tempfile,xml.etree.ElementTree as ET
MARKER="PSYAI_PRIVATE_COLAB_EVIDENCE="
SCHEMA="PSYAI_PRIVATE_COLAB_PREWINDOWS_V1"
REV="__REV__"
PACK_HASH="__HASH__"
PACK="__PACK__"
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def digest(x): return hashlib.sha256(x).hexdigest()
r={"schema":SCHEMA,"status":"BLOCKED","source_sha":REV,"archive_sha256":PACK_HASH,
   "model_e2e":False,"windows_e2e":False,"full_tz_accepted":False,
   "cpu_count":os.cpu_count(),"steps":[]}
try:
    with open("/proc/meminfo",encoding="ascii") as f:
        r["ram_gib"]=round(next(int(x.split()[1]) for x in f if x.startswith("MemTotal:"))/1048576,2)
    with tempfile.TemporaryDirectory(prefix="psyai-private-colab-") as d:
        root=pathlib.Path(d)
        payload=base64.b64decode(PACK,validate=True)
        if digest(payload)!=PACK_HASH: raise ValueError("ARCHIVE_HASH_MISMATCH")
        tar_bytes=gzip.decompress(payload)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as src:
            for m in src.getmembers():
                path=pathlib.PurePosixPath(m.name)
                if path.is_absolute() or ".." in path.parts or not (m.isfile() or m.isdir()):
                    raise ValueError("UNSAFE_SOURCE_ARCHIVE")
            src.extractall(root/"app",filter="data")
        app=root/"app"
        logs=root/"logs";logs.mkdir()
        (root/"home").mkdir();(root/"tmp").mkdir()
        env=os.environ.copy()
        env.update({"PSYAI_SKIP_AUTO_INSTALL":"1","PYTHONDONTWRITEBYTECODE":"1",
                    "PYTHONNOUSERSITE":"1","CUDA_VISIBLE_DEVICES":"",
                    "HOME":str(root/"home"),"TMPDIR":str(root/"tmp")})
        def call(name,command,timeout):
            with (logs/(name+".log")).open("wb") as log:
                try:
                    process=subprocess.run(command,cwd=app,env=env,stdin=subprocess.DEVNULL,
                        stdout=log,stderr=subprocess.STDOUT,timeout=timeout,check=False)
                    ok=process.returncode==0
                    r["steps"].append({"name":name,"ok":ok,"exit_code":process.returncode})
                    return ok
                except (OSError,subprocess.TimeoutExpired) as err:
                    r["steps"].append({"name":name,"ok":False,"reason":type(err).__name__})
                    return False
        if call("dependencies",[sys.executable,"-m","pip","install","-q",
                                 "-r","requirements.txt","-r","requirements-dev.txt"],1000):
            ok=call("prewindows",[sys.executable,"tools/run_pre_windows_acceptance.py"],2500)
            evidence=app/".psyai_test_runs"/"prewindows"/"LAST_PREWINDOWS_RESULT.json"
            if evidence.is_file():
                e=json.loads(evidence.read_text(encoding="utf-8"))
                r["registry_counts"]=e.get("registry_counts",{})
                r["pytest"]=e.get("pytest",{})
                r["blocker_count"]=len(e.get("blockers",[]))
                r["suite_status"]=e.get("status")
                r["step_checks"]=[{"name":x.get("name"),"ok":x.get("ok"),
                                   "exit_code":x.get("exit_code"),
                                   "error_type":x.get("error")}
                                  for x in e.get("commands",[])]
                # Do NOT export pytest failure messages, arguments, fixture values,
                # stack traces, consultation text or unfiltered Node stdout.
                # The only allowlisted identifiers are Python TEST MODULE names.
                xml=app/".psyai_test_runs"/"prewindows"/"python-junit.xml"
                try:
                    testsuite=ET.parse(xml).getroot()
                    module_failures=collections.Counter()
                    errors=collections.Counter()
                    testcase_count=0
                    for case in testsuite.iter("testcase"):
                        testcase_count+=1
                        problem=case.find("failure")
                        kind="failure"
                        if problem is None:
                            problem=case.find("error")
                            kind="error"
                        if problem is None:
                            continue
                        raw=case.attrib.get("classname","")
                        # Extract only safe module names, never parametrized names
                        # (their values can contain consultation-like fixture data).
                        safe_parts=re.findall(r"(?:^|[./])(?P<mod>test_[a-zA-Z0-9_]{1,90})(?=\.|/|$)",raw)
                        name=safe_parts[0] if safe_parts else "UNKNOWN_TEST_MODULE"
                        module_failures[(name,kind)]+=1
                        category=problem.attrib.get("type","")
                        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,70}",category):
                            # Pytest normally puts exception class in the message
                            # attribute, NOT in type; never publish its raw text.
                            safe_message=problem.attrib.get("message","")[:350]
                            found=re.search(r"(?<![A-Za-z_])(AssertionError|"
                                r"ModuleNotFoundError|ImportError|AttributeError|"
                                r"FileNotFoundError|KeyError|TypeError|ValueError|"
                                r"RuntimeError|OperationalError|IntegrityError|"
                                r"PermissionError|TimeoutError|IndexError|"
                                r"NameError|LookupError|OSError)(?![A-Za-z_])",
                                safe_message)
                            category=found.group(1) if found else "UNKNOWN_ERROR_TYPE"
                        errors[category]+=1
                    r["junit_case_count"]=testcase_count
                    r["python_failure_modules"]=[{"module":mod,"kind":kind,"count":n}
                        for (mod,kind),n in sorted(module_failures.items(),
                            key=lambda x:(-x[1],x[0]))[:60]]
                    r["python_error_types"]=[{"type":typ,"count":n}
                        for typ,n in sorted(errors.items(),key=lambda x:(-x[1],x[0]))[:25]]
                    r["junit_diagnostics"]="AVAILABLE"
                except (OSError,ValueError,ET.ParseError) as diagnostic:
                    r["junit_diagnostics"]="UNAVAILABLE_"+type(diagnostic).__name__
            r["status"]="PREWINDOWS_PASS" if ok and r.get("suite_status")=="PASS" else "PREWINDOWS_FAIL"
        else:
            r["status"]="BLOCKED_DEPENDENCY_INSTALL"
except Exception as error:
    r["status"]="BLOCKED_REMOTE_EXECUTION"
    r["reason"]=type(error).__name__
r["receipt_sha256"]=digest(canon(r).encode("ascii"))
print(MARKER+canon(r),flush=True)
'''
    return template.replace("__REV__", revision).replace("__HASH__", sha(packed)).replace(
        "__PACK__", base64.b64encode(packed).decode("ascii"))

def main():
    proof = blocked("UNSTARTED")
    try:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("EXISTING_COLAB_ADC_MISSING")
        if not SOURCE.is_dir():
            raise ValueError("PRIVATE_SOURCE_CHECKOUT_MISSING")
        rev, packed = source_archive()
        with tempfile.TemporaryDirectory(prefix="psyai-colab-bridge-") as tmp:
            path = Path(tmp) / "private_script.py"
            log = Path(tmp) / "remote-output.log"
            path.write_text(remote_script(rev, packed), encoding="utf-8")
            path.chmod(0o600)
            try:
                with log.open("wb") as stream:
                    subprocess.run(["colab", "--auth=adc", "run", str(path)],
                                   stdin=subprocess.DEVNULL, stdout=stream,
                                   stderr=subprocess.STDOUT, timeout=4100, check=False)
            except (OSError, subprocess.TimeoutExpired):
                raise ValueError("COLAB_TRANSPORT_BLOCKED") from None
            lines = [line.split(MARKER, 1)[1] for line in
                     log.read_text(encoding="utf-8", errors="replace").splitlines()
                     if MARKER in line]
            if len(lines) != 1:
                raise ValueError("REMOTE_RECEIPT_MISSING_OR_DUPLICATE")
            obj = json.loads(lines[0])
            expected = obj.pop("receipt_sha256", "")
            if sha(canon(obj).encode("ascii")) != expected:
                raise ValueError("REMOTE_RECEIPT_HASH_MISMATCH")
            if (obj.get("schema") != SCHEMA or obj.get("source_sha") != rev or
                obj.get("archive_sha256") != sha(packed) or
                obj.get("model_e2e") is not False or obj.get("windows_e2e") is not False):
                raise ValueError("REMOTE_RECEIPT_SOURCE_OR_SCOPE_MISMATCH")
            whitelist = ("schema", "status", "source_sha", "archive_sha256",
                         "model_e2e", "windows_e2e", "full_tz_accepted",
                         "cpu_count", "ram_gib", "registry_counts", "pytest",
                         "blocker_count", "suite_status", "step_checks", "steps", "reason",
                         "junit_case_count", "python_failure_modules",
                         "python_error_types", "junit_diagnostics")
            proof = {k: obj[k] for k in whitelist if k in obj}
            proof["receipt_sha256"] = sha(canon(proof).encode("ascii"))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        allowed = {"EXISTING_COLAB_ADC_MISSING","PRIVATE_SOURCE_CHECKOUT_MISSING",
                   "COLAB_TRANSPORT_BLOCKED","REMOTE_RECEIPT_MISSING_OR_DUPLICATE",
                   "REMOTE_RECEIPT_HASH_MISMATCH","REMOTE_RECEIPT_SOURCE_OR_SCOPE_MISMATCH",
                   "SOURCE_SHA_INVALID","UNEXPECTED_SOURCE_FILE_COUNT",
                   "UNSAFE_ARCHIVE_ENTRY","FORBIDDEN_TRACKED_SECRET_OR_DATA",
                   "SOURCE_ARCHIVE_EXCEEDS_LIMIT"}
        proof = blocked(str(exc) if str(exc) in allowed else type(exc).__name__)
    OUTPUT.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print("PSYAI_PRIVATE_COLAB", proof["status"], proof.get("reason", ""))
    return 0 if proof["status"] == "PREWINDOWS_PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
