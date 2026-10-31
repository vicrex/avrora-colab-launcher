"""Package exact pinned PRIVATE HAWKES source into one ephemeral Colab script.

The bundle and source are never uploaded as public workflow artifacts.
Only the portable SHA receipt of 100 math-only trials is retained.
"""
from __future__ import annotations
import argparse
import base64
import io
from pathlib import Path
import zipfile

from tools.avrora_hundred_mle_colab import FILES


def build(source,template):
    folder=Path(source)
    entries={}
    for path in FILES:
        p=folder/path
        if path.endswith("/__init__.py"):
            entries[path]=b""
        else:
            if not p.is_file():
                raise ValueError("BLOCKED_MLE_PRIVATE_SOURCE_MISSING")
            raw=p.read_bytes()
            if not raw or len(raw)>16000:
                raise ValueError("BLOCKED_MLE_PRIVATE_SOURCE_SIZE")
            entries[path]=raw
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            zi=zipfile.ZipInfo(name,(2020,1,1,0,0,0))
            zi.compress_type=zipfile.ZIP_DEFLATED
            zi.external_attr=(0o644<<16)
            z.writestr(zi,entries[name])
    data=base64.b64encode(stream.getvalue()).decode("ascii")
    if len(data)>60000:
        raise ValueError("BLOCKED_MLE_BUNDLE_LIMIT")
    template=Path(template).read_text(encoding="utf-8")
    needle='SOURCE_ZIP_B64 = "__SOURCE_ZIP_B64__"'
    if template.count(needle)!=1:
        raise ValueError("BLOCKED_MLE_TEMPLATE_CONTRACT")
    return template.replace(needle,'SOURCE_ZIP_B64 = "'+data+'"')


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--private-source",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    output=Path(args.out)
    if output.exists():
        raise ValueError("BLOCKED_MLE_BUNDLE_OVERWRITE")
    script=build(args.private_source,Path(__file__).with_name("avrora_hundred_mle_colab.py"))
    compile(script,str(output),"exec")
    output.write_text(script,encoding="utf-8")
    print("READY_EPHEMERAL_PRIVATE_MLE_RUNNER",len(script))


if __name__=="__main__":
    main()
