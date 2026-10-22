"""Generic PRIVATE-to-Drive research delivery, never uploads to public artifacts.

Uses existing Google authorized_user ADC GitHub Secret, not a new OAuth grant.
No credentials, token, raw data, or strategy contents are printed to logs.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

FOLDER="1MXTBe21rTm1fVYzjUQ6NNf8cJzOQ0NKX"
API="https://www.googleapis.com/drive/v3/files"
UPLOAD="https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,parents,size,md5Checksum"
MAX_BYTES=4_000_000

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--name",required=True)
    ap.add_argument("--receipt",required=True)
    args=ap.parse_args()
    if (not args.name.startswith("AVRORA_MARTINGALE_RESEARCH_")
            or not args.name.endswith(".json")
            or not args.name.replace("_","").replace(".","").isalnum()
            or not os.environ.get("AVRORA_COLAB_ADC_JSON_B64")):
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_DELIVERY_CONFIG")
    path=Path(args.input)
    data=path.read_bytes()
    if not data or len(data)>MAX_BYTES:
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_UNBOUNDED_REPORT")
    parsed=json.loads(data)
    digest=hashlib.sha256(data).hexdigest()
    if (parsed.get("schema")!="AVRORA_P816_MARTINGALE_COMPARISON_DISCOVERY_SHADOW_V1"
            or parsed.get("real")!="OFF"
            or parsed.get("holdout")!="SEALED"
            or parsed.get("oos_proven") is not False
            or parsed.get("maker_fill_proven") is not False):
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_WRONG_REPORT")
    audit=parsed.copy();report_sha=audit.pop("receipt_sha256")
    canonical=json.dumps(audit,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
    if hashlib.sha256(canonical.encode()).hexdigest()!=report_sha:
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_REPORT_SHA")
    stage="CREDENTIAL_PARSE"
    try:
        import requests
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        cred_info=json.loads(base64.b64decode(os.environ["AVRORA_COLAB_ADC_JSON_B64"],validate=True))
        if cred_info.get("type")!="authorized_user":
            raise RuntimeError("wrong adc")
        credentials=Credentials.from_authorized_user_info(cred_info)
        stage="TOKEN_REFRESH"
        credentials.refresh(Request())
        headers={"Authorization":"Bearer "+credentials.token}
        # Same GitHub run + version => same deterministic filename. Avoid duplicates.
        q=f"name = '{args.name}' and '{FOLDER}' in parents and trashed = false"
        stage="LIST_FOLDER"
        listing=requests.get(API,params={"q":q,"pageSize":10,"fields":"files(id,name,size),nextPageToken"},
                             headers=headers,timeout=40)
        # ADC tokens for Colab may allow file creation but not listing a user folder.
        # We try a single create on the FIRST GitHub attempt; retries fail closed.
        can_list=listing.status_code==200
        if not can_list:
            if listing.status_code!=403 or os.environ.get("GITHUB_RUN_ATTEMPT","1")!="1":
                listing.raise_for_status()
            print("DRIVE_FOLDER_LIST_FORBIDDEN_FIRST_ATTEMPT_CREATE_ONLY")
        existing=listing.json().get("files",[]) if can_list else []
        if len(existing)>1:
            raise RuntimeError("ambiguous existing artifacts")
        if existing:
            file_id=existing[0]["id"]
        else:
            meta=json.dumps({"name":args.name,"parents":[FOLDER],"mimeType":"application/json"},
                            separators=(",",":")).encode()
            delim="AVRORARESEARCHBOUNDARY"
            content_type=f"multipart/related; boundary={delim}"
            payload=(f"--{delim}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                      +meta+f"\r\n--{delim}\r\nContent-Type: application/json\r\n\r\n".encode()
                      +data+f"\r\n--{delim}--\r\n".encode())
            stage="UPLOAD_NEW"
            response=requests.post(UPLOAD,
                        headers={**headers,"Content-Type":content_type},
                        data=payload,timeout=120)
            response.raise_for_status()
            file_id=response.json()["id"]
        stage="DOWNLOAD_READBACK"
        response=requests.get(f"{API}/{file_id}",params={"alt":"media"},
                              headers=headers,timeout=120)
        response.raise_for_status()
        raw=response.content
        if raw!=data or hashlib.sha256(raw).hexdigest()!=digest:
            raise RuntimeError("byte level readback mismatch")
        stage="ACK_RECEIPT"
        out={"schema":"AVRORA_PRIVATE_DRIVE_READBACK_ACK_V1",
             "status":"DRIVE_SHA_READBACK_VERIFIED",
             "drive_file_id":file_id,
             "drive_file_url":"https://drive.google.com/file/d/"+file_id+"/view",
             "sha256":digest,"bytes":len(data),
             "private_research_receipt_sha":report_sha,
             "uploaded_strategy_content_public":False}
        receipt=Path(args.receipt)
        if receipt.exists():raise RuntimeError("duplicate receipt file")
        receipt.write_text(json.dumps(out,sort_keys=True,separators=(",",":"))+"\n")
    except Exception as exc:
        # Classify only the failure type and HTTP status. Never print URLs, auth headers or tokens.
        status=getattr(getattr(exc,"response",None),"status_code",None)
        suffix=("HTTP_"+str(status)) if type(status) is int else "INTERNAL"
        raise SystemExit("BLOCKED_PRIVATE_DRIVE_STAGE_"+stage+"_"+suffix)
    print("PASS_PRIVATE_DRIVE_SHA_ACK",out["drive_file_id"],out["sha256"],out["bytes"])

if __name__=="__main__":main()
