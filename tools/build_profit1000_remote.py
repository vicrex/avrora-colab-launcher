"""Ephemeral Colab packaging for 1000 retrospective *real P816 OHLC* cost stress runs.

Uses exact existing private P816 data source loader and immutable SHA pins.
No executable strategy code is changed; no private source or market data
is uploaded as GitHub artifacts. Actual remote Colab still runs that raw
P816 history in a single temporary CPU process, as owner previously approved.
"""
from __future__ import annotations
import argparse
import base64
from pathlib import Path

from tools import avrora_profit1000_full13 as study
from tools import full13_wave_colab as dataset
from tools import hourly_wave_research as primary


def build(checkout):
    compressed,meta=dataset.load_private(checkout)
    manifest=primary.load_manifest()
    dataset.parse_full(compressed,meta)
    for path in study.PUBLIC_SOURCE_FILES:
        if not (Path(__file__).parent/path).is_file():
            raise ValueError("BLOCKED_PROFIT1000_PUBLIC_SOURCE_MISSING")
    files={path:(Path(__file__).parent/path).read_bytes()
           for path in study.PUBLIC_SOURCE_FILES}
    files.update({
        "P816_panel.gz":compressed,
        "data_manifest.json":dataset.canon(meta).encode("utf-8"),
        "prereg.json":primary.canonical(manifest).encode("utf-8"),
    })
    if len(files)!=7 or sum(map(len,files.values()))>1_200_000:
        raise ValueError("BLOCKED_PROFIT1000_BUNDLE_RESOURCE_CAP")
    encoded={k:base64.b64encode(v).decode("ascii") for k,v in files.items()}
    # Package includes only existing public research code, prereg and source
    # bytes in an *ephemeral* script; remote emits only sanitized receipt.
    return (
        "import base64,os,pathlib,subprocess,sys,tempfile\n"
        "if os.getenv('REAL','OFF')!='OFF' or os.getenv('HOLDOUT','SEALED')!='SEALED':\n"
        " raise SystemExit('BLOCKED_PROFIT1000_UNSAFE_ENV')\n"
        "with tempfile.TemporaryDirectory(prefix='avrora-profit1000-') as d:\n"
        " p=pathlib.Path(d)\n"
        f" bundle={repr(encoded)}\n"
        " for name,raw in bundle.items(): (p/name).write_bytes(base64.b64decode(raw,validate=True))\n"
        " result=subprocess.run([sys.executable,'avrora_profit1000_full13.py',"
        "'remote','--source-gz','P816_panel.gz','--source-manifest',"
        "'data_manifest.json','--prereg','prereg.json'],cwd=p,"
        "capture_output=True,text=True,timeout=1200,check=False,"
        "env={**os.environ,'REAL':'OFF','HOLDOUT':'SEALED'})\n"
        " if result.returncode: raise SystemExit('BLOCKED_PROFIT1000_REMOTE_STUDY_FAILED')\n"
        f" if result.stdout.count({study.MARKER!r})!=1: raise SystemExit('BLOCKED_PROFIT1000_REMOTE_RECEIPT_SHAPE')\n"
        f" print(result.stdout.strip(),flush=True)\n"
    )


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--private-checkout",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    target=Path(a.out)
    if target.exists():raise ValueError("BLOCKED_PROFIT1000_REMOTE_OVERWRITE")
    script=build(a.private_checkout)
    compile(script,str(target),"exec")
    target.write_text(script,encoding="utf-8")
    target.chmod(0o600)
    print("READY_COLAB_PROFIT1000_REAL_OHLC_BUNDLE_SIZE",len(script))


if __name__=="__main__":
    main()
