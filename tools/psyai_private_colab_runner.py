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
    # Catch Python syntax failures before reserving Colab time; compile
    # directly from bytes so this read-only public runner creates no private
    # __pycache__ files and never exposes source lines in its logs.
    source_python = sorted(SOURCE.rglob("*.py"))
    if not source_python:
        raise ValueError("PYTHON_SOURCE_SUITE_MISSING")
    for script in source_python:
        if script.is_symlink() or not script.is_file():
            raise ValueError("UNSAFE_SOURCE_PYTHON_ENTRY")
        try:
            compile(script.read_bytes(), str(script.relative_to(SOURCE)), "exec")
        except (SyntaxError, UnicodeError, OSError, ValueError):
            raise ValueError("PYTHON_SOURCE_SYNTAX_INVALID") from None
    # Catch a broken Node test module before reserving a Colab session.
    # Paths, syntax errors and private source lines never go to public logs.
    node_tests = sorted(SOURCE.glob("tests/test_*.cjs"))
    if not node_tests:
        raise ValueError("NODE_SUITE_MISSING")
    # Parse every actual UI script, too; a broken browser asset can be
    # missed by a test that does not import that specific script.
    node_scripts = node_tests + sorted(SOURCE.glob("static/*.js"))
    for script in node_scripts:
        try:
            check = subprocess.run(["node", "--check", str(script)],
                check=False, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError("NODE_SYNTAX_PREFLIGHT_UNAVAILABLE") from None
        if check.returncode:
            raise ValueError("NODE_TEST_SYNTAX_INVALID")
    # Exercise the synthetic Atlas DOM and provenance regression on the
    # runner before asking Colab to execute the entire application suite.
    atlas_test = SOURCE / "tests" / "test_decision_atlas.cjs"
    if not atlas_test.is_file():
        raise ValueError("NODE_ATLAS_TEST_MISSING")
    try:
        atlas = subprocess.run(["node", "--test", str(atlas_test.resolve())],
            check=False, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("NODE_ATLAS_PREFLIGHT_UNAVAILABLE") from None
    if atlas.returncode:
        raise ValueError("NODE_ATLAS_PREFLIGHT_FAILED")
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
                # Map static acceptance categories only. Never send the actual
                # blocker strings because they may contain private test paths.
                categories=collections.Counter()
                for issue in e.get("blockers",[]):
                    if not isinstance(issue,str):
                        categories["OTHER"]+=1
                    elif ": functional code and positive/negative test evidence absent" in issue:
                        categories["PER_CONTROL_RUNTIME_EVIDENCE_MISSING"]+=1
                    elif ": functional implementation unfinished" in issue:
                        categories["SPEC_OR_BLOCKED_CONTROL"]+=1
                    elif ": real test reference missing" in issue:
                        categories["CONTROL_TEST_REFERENCE_MISSING"]+=1
                    elif ": implementation paths missing" in issue:
                        categories["CONTROL_IMPLEMENTATION_MISSING"]+=1
                    elif "Python test failures/errors/skips" in issue:
                        categories["PYTHON_SUITE_INCOMPLETE"]+=1
                    elif "One or more full test commands failed." in issue:
                        categories["TEST_COMMAND_FAILED"]+=1
                    elif "Missing Node UI regression files" in issue:
                        categories["NODE_TEST_DISCOVERY_FAILED"]+=1
                    else:
                        categories["OTHER"]+=1
                r["acceptance_blocker_breakdown"]=dict(sorted(categories.items()))
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
                    test_failures=collections.Counter()
                    skipped_tests=collections.Counter()
                    errors=collections.Counter()
                    testcase_count=0
                    for case in testsuite.iter("testcase"):
                        testcase_count+=1
                        if case.find("skipped") is not None:
                            # Only declarative module/function names, NEVER skip
                            # messages, values, code, paths or fixture arguments.
                            cls=case.attrib.get("classname","")
                            mods=re.findall(r"(?:^|[./])(?P<mod>test_[a-zA-Z0-9_]{1,90})(?=\.|/|$)",cls)
                            fn=case.attrib.get("name","").split("[",1)[0]
                            if mods and re.fullmatch(r"test_[a-zA-Z0-9_]{1,90}",fn):
                                skipped_tests[(mods[0],fn)]+=1
                            continue
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
                        # Pytest parameter values must never enter a public report.
                        function=case.attrib.get("name","").split("[",1)[0]
                        if re.fullmatch(r"test_[a-zA-Z0-9_]{1,90}",function):
                            test_failures[(name,function,kind)]+=1
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
                    r["python_failed_tests"]=[{"module":mod,"test":fn,"kind":kind,"count":n}
                        for (mod,fn,kind),n in sorted(test_failures.items(),
                            key=lambda x:(-x[1],x[0]))[:130]]
                    r["python_skipped_tests"]=[{"module":mod,"test":fn,"count":n}
                        for (mod,fn),n in sorted(skipped_tests.items())[:40]]
                    r["python_error_types"]=[{"type":typ,"count":n}
                        for typ,n in sorted(errors.items(),key=lambda x:(-x[1],x[0]))[:25]]
                    r["junit_diagnostics"]="AVAILABLE"
                except (OSError,ValueError,ET.ParseError) as diagnostic:
                    r["junit_diagnostics"]="UNAVAILABLE_"+type(diagnostic).__name__
                # Parse only numeric TAP counters and preexisting test filenames,
                # never reveal Node assertion messages or stack traces.
                node_log=app/".psyai_test_runs"/"prewindows"/"node.log"
                try:
                    with node_log.open("r",encoding="utf-8",errors="replace") as stream:
                        node_text=stream.read(3000000)
                    node_counts={}
                    for key in ("tests","pass","fail","cancelled","skipped","todo"):
                        match=re.search(r"(?m)^# "+key+r" (\d+)\s*$",node_text)
                        if match:
                            node_counts[key]=int(match.group(1))
                    # Failure labels may contain arbitrary fixture text:
                    # never publish them. Recover only strict on-disk test
                    # module names from the neighbouring TAP stack lines.
                    node_failed=collections.Counter()
                    node_locations=[]
                    for match in re.finditer(r"(?m)^\s*not ok \d+ - [^\n]*$",node_text):
                        # Some Node TAP failures are module-load failures:
                        # the filename appears only in the 'not ok' header.
                        # Others have a TestContext stack line ending ')'.
                        # Neither raw header nor stack is ever published.
                        tail=node_text[match.start():match.end()+1800]
                        found=re.search(r"(?:^|[/\\])(?P<name>test_[a-zA-Z0-9_]{1,90}\.cjs)(?::(?P<line>\d{1,5}):\d+)?(?=[)\]\s]|$)",tail,re.M)
                        module=found.group("name") if found else "UNKNOWN_TEST_MODULE"
                        node_failed[module]+=1
                        if found:
                            lineno=int(found.group("line") or 0)
                            detail={"module":module,"source_line":lineno}
                            # Only an allowlisted exception CLASS, never the
                            # message, call arguments, source or assertion.
                            kind=re.search(r"(?m)^\s*name:\s*'(AssertionError|ReferenceError|"
                                r"TypeError|SyntaxError|RangeError|Error)'\s*$",tail)
                            detail["error_kind"]=kind.group(1) if kind else "UNKNOWN"
                            # An exact match against a static TEST DECLARATION
                            # discloses only its ordinal, never its raw label.
                            source=app/"tests"/module
                            if source.is_file():
                                titles=re.findall(r"(?m)^\s*test\(['\"]([^'\"\n]{1,140})['\"]",
                                                  source.read_text(encoding="utf-8",errors="replace"))
                                label=match.group(0).split(" - ",1)[-1].strip()
                                if titles.count(label)==1:
                                    detail["test_ordinal"]=titles.index(label)+1
                            node_locations.append(detail)
                    r["node_tap_counts"]=node_counts
                    r["node_failed_modules"]=[{"module":n,"count":count}
                        for n,count in node_failed.most_common(30)]
                    r["node_failed_locations"]=node_locations[:40]
                    r["node_diagnostics"]="AVAILABLE" if node_counts else "UNAVAILABLE_TAP"
                except OSError:
                    r["node_diagnostics"]="UNAVAILABLE_LOG"
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
                         "blocker_count", "acceptance_blocker_breakdown", "suite_status", "step_checks", "steps", "reason",
                         "junit_case_count", "python_failure_modules",
                         "python_error_types", "python_failed_tests", "python_skipped_tests", "junit_diagnostics", "node_tap_counts",
                         "node_failed_modules", "node_failed_locations", "node_diagnostics")
            proof = {k: obj[k] for k in whitelist if k in obj}
            proof["receipt_sha256"] = sha(canon(proof).encode("ascii"))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        allowed = {"EXISTING_COLAB_ADC_MISSING","PRIVATE_SOURCE_CHECKOUT_MISSING",
                   "COLAB_TRANSPORT_BLOCKED","REMOTE_RECEIPT_MISSING_OR_DUPLICATE",
                   "REMOTE_RECEIPT_HASH_MISMATCH","REMOTE_RECEIPT_SOURCE_OR_SCOPE_MISMATCH",
                   "SOURCE_SHA_INVALID","UNEXPECTED_SOURCE_FILE_COUNT",
                   "UNSAFE_ARCHIVE_ENTRY","FORBIDDEN_TRACKED_SECRET_OR_DATA",
                   "SOURCE_ARCHIVE_EXCEEDS_LIMIT", "NODE_SUITE_MISSING",
                   "NODE_SYNTAX_PREFLIGHT_UNAVAILABLE", "NODE_TEST_SYNTAX_INVALID",
                   "NODE_ATLAS_TEST_MISSING", "NODE_ATLAS_PREFLIGHT_UNAVAILABLE",
                   "NODE_ATLAS_PREFLIGHT_FAILED", "PYTHON_SOURCE_SUITE_MISSING",
                   "UNSAFE_SOURCE_PYTHON_ENTRY", "PYTHON_SOURCE_SYNTAX_INVALID"}
        proof = blocked(str(exc) if str(exc) in allowed else type(exc).__name__)
    OUTPUT.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print("PSYAI_PRIVATE_COLAB", proof["status"], proof.get("reason", ""))
    return 0 if proof["status"] == "PREWINDOWS_PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
