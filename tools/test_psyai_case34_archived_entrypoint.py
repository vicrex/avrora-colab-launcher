#!/usr/bin/env python3
"""Offline synthetic CASE34 archived private source entrypoint reproduction.

Checks the EXACT filtered tar the Colab bridge sends, with verified archive
attestation and real driver argv, but NO original consultation, GGUF, E5 or GPU.
Failure text is never printed: the assertion checks a known safe constant.
"""
import gzip,hashlib,importlib.util,io,json,os,pathlib,subprocess,sys,tarfile,tempfile

BRIDGE=pathlib.Path("tools/psyai_case34_full_colab_bridge.py")
spec=importlib.util.spec_from_file_location("case34_bridge_for_test",BRIDGE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def main():
    rev,packed,count=mod.private_source_archive()
    with tempfile.TemporaryDirectory(prefix="psyai-case34-synthetic-archive-") as td:
        root=pathlib.Path(td)
        source=root/"source"
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed)),mode="r:") as tar:
            for m in tar.getmembers():
                p=pathlib.PurePosixPath(m.name)
                assert not p.is_absolute() and ".." not in p.parts
                assert m.isfile() or m.isdir()
            tar.extractall(source,filter="data")
        code=source/"tools"/"run_case34_hybrid_acceptance.py"
        assert code.is_file() and (source/"tools"/"e2e_full_gemma.py").is_file()
        compile(code.read_bytes(),str(code),"exec")
        digest=hashlib.sha256(packed).hexdigest()
        (root/"PRIVATE_SOURCE_VERIFIED_ARCHIVE.json").write_text(
            json.dumps({"head":rev,"archive_sha256":digest,"verified":True},sort_keys=True),encoding="ascii")
        fake=root/"synthetic.txt"
        fake.write_text("Клиент: Only synthetic fixture, intentionally incorrect SHA!\n",
                        encoding="utf-8")
        nli=root/"nli";nli.mkdir()
        (nli/"config.json").write_text("{}",encoding="ascii")
        (root/"data").mkdir()
        env=os.environ.copy()
        env.update(PSYAI_HOME=str(root),PSYAI_DATA_DIR=str(root/"data"),
                   PSYAI_PATHS_FILE=str(root/"paths.json"),
                   PSYAI_LICENSE_ENFORCE="0",
                   PSYAI_SKIP_AUTO_INSTALL="1",
                   PSYAI_COLAB_VERIFIED_PRIVATE_HEAD=rev,
                   PSYAI_COLAB_VERIFIED_PRIVATE_ARCHIVE_SHA256=digest,
                   PYTHONDONTWRITEBYTECODE="1")
        cmd=[sys.executable,"-B",str(code),
             "--run","--work",str(root),"--source",str(fake),
             "--nli-model-dir",str(nli),"--output",str(root/"evidence"),
             "--mode","HYBRID","--hard-timeout-seconds","1800"]
        r=subprocess.run(cmd,cwd=source,env=env,stdin=subprocess.DEVNULL,
                         capture_output=True,text=True,timeout=35)
        # Expected: entrypoint, imports, archive provenance and argparse passed;
        # synthetic source intentionally rejected at SHA before any model work.
        if r.returncode!=2 or "CASE34_SAFE_FAILURE_CODE=CASE34_SOURCE_SHA_MISMATCH" not in r.stdout:
            kinds=["ModuleNotFoundError","ImportError","SyntaxError","AttributeError",
                   "TypeError","FileNotFoundError","ValueError","PermissionError"]
            output=r.stdout+"\n"+r.stderr
            present=[x for x in kinds if x in output]
            print("BLOCKED_ARCHIVED_ENTRYPOINT_CLASS="+(",".join(present) or "UNKNOWN"))
            return 2
        receipt=root/"evidence"/"CASE34_HYBRID_LAST_RUN.json"
        if not receipt.is_file():
            print("BLOCKED_ARCHIVED_ENTRYPOINT_MISSING_SAFE_RECEIPT")
            return 2
        j=json.loads(receipt.read_text(encoding="utf-8"))
        assert j.get("verification",{}).get("automated_failures")==[
            "CASE34_SOURCE_SHA_MISMATCH"]
        print("PASS_CASE34_ARCHIVE_ENTRYPOINT_IMPORT_ARGV_PROVENANCE")
        print("PASS_CASE34_SYNTHETIC_SOURCE_REJECTED_SAFE_RECEIPT_NO_GPU")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
