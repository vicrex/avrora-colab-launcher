#!/usr/bin/env python3
"""Verify private Drive CASE34 source can be fetched with EXISTING Colab ADC.
No content, credentials, path, or excerpt printed; only check against SHA.
"""
import hashlib,json,os,sys
from pathlib import Path
EXPECTED_SHA="3fb91a7a0286389073d0da9099d99081b6d49e913b7d34381e359d744d0720cc"
FILE_ID="1iVB3TgJhDT-XpNa96ZnLOBykSMtS7sIG"
def main():
    out={"schema":"PSYAI_CASE34_PRIVATE_DRIVE_ACCESS_V1",
         "source_sha_verified":False,"google_drive_access":False,
         "public_visibility":False,"bytes":0,"status":"BLOCKED"}
    try:
        import google.auth
        import google.auth.transport.requests
        from urllib.request import Request,urlopen
        creds,project=google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
        creds.refresh(google.auth.transport.requests.Request())
        import urllib.error
        req=Request("https://www.googleapis.com/drive/v3/files/"+FILE_ID+"?alt=media",
           headers={"Authorization":"Bearer "+creds.token})
        with urlopen(req,timeout=45) as resp:
            payload=resp.read(100000)
        sha=hashlib.sha256(payload).hexdigest()
        out["bytes"]=len(payload)
        out["source_sha_verified"]=sha==EXPECTED_SHA
        out["google_drive_access"]=out["source_sha_verified"]
        out["status"]="PASS" if out["google_drive_access"] else "BLOCKED"
        if not out["google_drive_access"]:out["reason"]="FILE_BYTES_MISMATCH"
    except Exception as exc:
        out["reason"]=type(exc).__name__
        out["http_code"]=int(getattr(exc,"code",0)) if getattr(exc,"code",None) else None
    Path("psyai-case34-drive-access.json").write_text(
        json.dumps(out,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("PSYAI_CASE34_DRIVE_ACCESS="+out["status"])
    print("PSYAI_CASE34_DRIVE_REASON="+out.get("reason","NONE"))
    return 0 if out["status"]=="PASS" else 2
if __name__=="__main__":sys.exit(main())
