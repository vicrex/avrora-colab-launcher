"""Aggregate-only per-hour full-P816 decision. Never fabricate economics on failure."""
import hashlib,json,os,pathlib,re
try:
    from .full13_wave_colab import SCHEMA as RECEIPT_SCHEMA,canon,verify_receipt,primary
except ImportError:
    from full13_wave_colab import SCHEMA as RECEIPT_SCHEMA,canon,verify_receipt,primary
SCHEMA='AVRORA_FULL13_HOURLY_DECISION_DELTA_V1'
def make(run_id,attempt,candidate,receipt_path,cache_hit=False,trigger='schedule'):
    if not re.fullmatch(r'[0-9]{6,25}',str(run_id)) or not re.fullmatch(r'[1-9][0-9]?',str(attempt)):
        raise ValueError('BLOCKED_RUN_ID')
    if trigger not in ('schedule','workflow_dispatch'):raise ValueError('BLOCKED_EVENT')
    card={'schema':SCHEMA,'run_id':str(run_id),'attempt':str(attempt),'trigger':trigger,
        'candidate':candidate,'cache_hit':bool(cache_hit),'real':'OFF','holdout':'SEALED',
        'oos':False,'maker_fill_proven':False,'status':'BLOCKED_NO_VERIFIED_FULL13_RECEIPT',
        'decision':'BLOCKED','economics_proven':False,'reason_code':'BLOCKED_NO_VERIFIED_FULL13_RECEIPT',
        'metrics':None,'receipt_sha256':None}
    try:
        m=primary.load_manifest()
        if candidate not in [x['id'] for x in m['candidates']]:raise ValueError('BLOCKED_CANDIDATE')
        r=verify_receipt(json.loads(pathlib.Path(receipt_path).read_text()),m,candidate)
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError):pass
    else:
        card.update(status='IDLE_CACHED_VERIFIED' if cache_hit else 'VERIFIED_NEW_FULL13_COMPUTATION',
          decision='REJECT_FOR_LIVE_DISCOVERY_ONLY',economics_proven=True,reason_code=None,
          receipt_sha256=r['receipt_sha256'],
          metrics={'discovery':r['discovery'],'may_aux':r['may_aux'],
                   'by_week':r['by_week'],'by_symbol':r['by_symbol'],
                   'warmup_bars':r['warmup_bars_per_period'],
                   'bars_total':r['bars_total'],'discovery_days':r['discovery_days'],
                   'check2':r['check2'],'lookahead_prefix_checks':r['lookahead_prefix_checks'],
                   'source_sha256':r['panel_gzip_sha256']})
    card['card_sha256']=hashlib.sha256(canon(card).encode()).hexdigest()
    return card

def main():
    c=make(os.environ.get('GITHUB_RUN_ID',''),os.environ.get('GITHUB_RUN_ATTEMPT','1'),
           os.environ.get('AVRORA_CANDIDATE_ID',''),os.environ.get('AVRORA_RECEIPT','full13_research_receipt.json'),
           os.environ.get('AVRORA_CACHED','false')=='true',os.environ.get('GITHUB_EVENT_NAME','schedule'))
    pathlib.Path('full13_vector_delta.json').write_text(canon(c)+'\n')
    print('AVRORA_FULL13_DELTA_WRITTEN '+c['status'])
if __name__=='__main__':main()
