"""AVRORA owner-only public preregistration, never a strategy executor."""
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

REPO = 'vicrex/avrora-colab-launcher'
PREFIX = 'AVRORA_RESEARCH_V1'
MARKER = '<!-- AVRORA_PUBLIC_PREREG:'
HOSTS = {'github.com', 'arxiv.org', 'huggingface.co', 'openreview.net'}

class Blocked(ValueError):
    pass

def canonical(o):
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def digest(o):
    return hashlib.sha256(canonical(o).encode()).hexdigest()

def check_text(s, n=1000):
    if not isinstance(s, str) or not 1 <= len(s) <= n or '\x00' in s:
        raise Blocked('BLOCKED_TEXT')
    if re.search(r'(?i)(-----BEGIN|github_pat_|ghp_[a-zA-Z0-9]|private[_-]?key\s*[:=]|(?:^|\s)[a-zA-Z]:[\\/])', s):
        raise Blocked('BLOCKED_PRIVATE_CONTENT')
    return s

def parse(body):
    if not isinstance(body, str) or len(body.encode()) > 8192 or not body.startswith(PREFIX+'\n'):
        raise Blocked('BLOCKED_PREFIX_OR_SIZE')
    try:
        x = json.loads(body.split('\n', 1)[1])
    except (TypeError, ValueError):
        raise Blocked('BLOCKED_JSON') from None
    if not isinstance(x, dict) or set(x) != {'schema', 'delivery_id', 'source', 'spec'}:
        raise Blocked('BLOCKED_ENVELOPE')
    if type(x['schema']) is not int or x['schema'] != 1 or x['source'] != 'chatgpt-model-search':
        raise Blocked('BLOCKED_SOURCE')
    if not re.fullmatch('[a-zA-Z0-9_.:-]{5,130}', check_text(x['delivery_id'], 130)):
        raise Blocked('BLOCKED_ID')
    s = x['spec']
    if not isinstance(s, dict) or set(s) != {'adapter','mechanism','dataset','parameters','real','holdout'}:
        raise Blocked('BLOCKED_FIELDS')
    if s['adapter'] != 'unreviewed-model-proposal' or s['real'] != 'OFF' or s['holdout'] != 'SEALED':
        raise Blocked('BLOCKED_EXECUTION')
    if not isinstance(s['dataset'], str) or not (s['dataset']=='MISSING' or re.fullmatch('[a-f0-9]{64}',s['dataset'])):
        raise Blocked('BLOCKED_DATASET')
    m=s['mechanism']
    if not isinstance(m,dict) or not {'model','revision','hypothesis'}.issubset(m) or set(m)-{'model','revision','hypothesis','source_url'}:
        raise Blocked('BLOCKED_MECHANISM')
    for k in ('model','revision','hypothesis'):
        check_text(m[k])
    if 'source_url' in m:
        u=urlparse(check_text(m['source_url'],500))
        if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password:
            raise Blocked('BLOCKED_SOURCE_URL')
    p=s['parameters']
    if not isinstance(p,dict) or not {'horizon_bars','baseline'}.issubset(p) or set(p)-{'horizon_bars','baseline','price_available_at','prereg_description'}:
        raise Blocked('BLOCKED_PARAMETERS')
    if type(p['horizon_bars']) is not int or not 1<=p['horizon_bars']<=96:
        raise Blocked('BLOCKED_HORIZON')
    for k in p:
        if k!='horizon_bars': check_text(p[k])
    return x

def dupe(number, target, issues):
    """Inspect ALL issues; API order cannot determine canonical earliest issue."""
    earlier_duplicate = False
    for issue in issues:
        other_number = issue.get('number')
        if (type(other_number) is not int or other_number == number
                or 'pull_request' in issue):
            continue
        try:
            old = parse(issue.get('body'))
        except Blocked:
            continue
        if old['delivery_id'] != target['delivery_id']:
            continue
        if digest(old) != digest(target):
            return 'BLOCKED_ID_COLLISION'
        if other_number < number:
            earlier_duplicate = True
    return 'BLOCKED_DUPLICATE' if earlier_duplicate else None

def receipt(x, number):
    h=digest(x)
    return (f'{MARKER}{h} -->\nAVRORA_PUBLIC_INGRESS_V1\n'
            f'status: PUBLIC_REGISTERED_BLOCKED_EXECUTION\n'
            f'delivery_id: {x["delivery_id"]}\nissue: {number}\nspec_sha256: {h}\n'
            'reason: ADAPTER_NOT_REVIEWED\nreal: OFF\nholdout: SEALED\n'
            'economic_run: NOT_RUN\ndrive_ack: NOT_DELIVERED')

def process(issue, issues, comments, api):
    if issue.get('user',{}).get('login')!='vicrex': return 'SKIPPED_UNTRUSTED_AUTHOR'
    number=issue.get('number')
    if type(number) is not int or number<1: raise Blocked('BLOCKED_ISSUE_NUMBER')
    spec=parse(issue.get('body'))
    why=dupe(number,spec,issues())
    if why: raise Blocked(why)
    expected=receipt(spec,number)
    old=comments(number)
    if any(row.get('body')==expected for row in old): return 'IDLE_ALREADY_REGISTERED'
    if any(MARKER in (row.get('body') or '') for row in old):
        raise Blocked('BLOCKED_EDIT_AFTER_PREREG')
    created=api('POST',f'/repos/{REPO}/issues/{number}/comments',{'body':expected})
    cid=created.get('id')
    if type(cid) is not int or cid<1: raise Blocked('BLOCKED_COMMENT_CREATE')
    readback=api('GET',f'/repos/{REPO}/issues/comments/{cid}')
    if readback.get('body')!=expected: raise Blocked('BLOCKED_READBACK')
    return 'PUBLIC_REGISTERED_BLOCKED_EXECUTION'

def gh(method, path, payload=None):
    secret=os.environ.get('GH_TOKEN','')
    if not secret: raise Blocked('BLOCKED_TOKEN_MISSING')
    req=urllib.request.Request('https://api.github.com'+path,method=method,
        data=canonical(payload).encode() if payload is not None else None,
        headers={'Authorization':'Bearer '+secret,'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as response:
        return json.load(response)

def pages(endpoint):
    all_rows=[]
    for n in range(1,5):
        if n>3: raise Blocked('BLOCKED_PAGING_LIMIT')
        q='&' if '?' in endpoint else '?'
        batch=gh('GET',f'{endpoint}{q}per_page=100&page={n}')
        if not isinstance(batch,list): raise Blocked('BLOCKED_API_FORMAT')
        all_rows.extend(batch)
        if len(batch)<100:return all_rows
    raise Blocked('BLOCKED_PAGING_LIMIT')

def main():
    if os.getenv('REAL','OFF')!='OFF' or os.getenv('HOLDOUT','SEALED')!='SEALED':
        return 2
    try:
        event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        # Always read current Issue to avoid preregistering a stale event body.
        if 'issue' in event:
            if event['issue'].get('user',{}).get('login') != 'vicrex':
                print('AVRORA_PUBLIC_INGRESS SKIPPED_UNTRUSTED_AUTHOR')
                return 0
            n = str(event['issue'].get('number', ''))
        else:
            n = os.getenv('ISSUE_NUMBER','')
        if not re.fullmatch('[1-9][0-9]{0,8}',n):
            raise Blocked('BLOCKED_MANUAL_NUMBER')
        issue = gh('GET',f'/repos/{REPO}/issues/{n}')
        result=process(issue,lambda:pages(f'/repos/{REPO}/issues?state=all'),
                       lambda n:pages(f'/repos/{REPO}/issues/{n}/comments'),gh)
        print('AVRORA_PUBLIC_INGRESS '+result)
        return 0
    except (Blocked, ValueError, OSError, KeyError):
        # Fail closed; never print untrusted issue data or API headers.
        print('AVRORA_PUBLIC_INGRESS BLOCKED_VALIDATION_OR_DELIVERY')
        return 2

if __name__=='__main__':
    sys.exit(main())
