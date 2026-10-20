"""Mandatory per-hour candidate decision card for external AVRORA private map ingestion.
Only public, aggregate-only, independently verified receipts; never private candle rows.
"""
import hashlib,json,math,os,re,sys
from pathlib import Path
from tools import hourly_wave_research as wave


def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',', ':'),allow_nan=False)
def sha(obj):return hashlib.sha256(canonical(obj).encode()).hexdigest()
def vec(label):
    parts=re.findall(r'[a-z][a-z0-9_]{1,}',label.lower().replace('_',' '))
    counts={}
    for token in parts:
        key=int(hashlib.sha256(token.encode()).hexdigest()[:8],16)%256
        counts[key]=counts.get(key,0)+1
    norm=math.sqrt(sum(v*v for v in counts.values())) or 1
    return {str(k):round(v/norm,9) for k,v in sorted(counts.items())}

def make_card(candidate,receipt_path,run_id,attempt,cache_hit,source='schedule'):
    if os.environ.get('REAL','OFF')!='OFF' or os.environ.get('HOLDOUT','SEALED')!='SEALED':
        raise ValueError('BLOCKED_SAFETY')
    manifest=wave.load_manifest()
    if not any(z['id']==candidate for z in manifest['candidates']):raise ValueError('BLOCKED_CANDIDATE')
    if not re.fullmatch(r'[0-9]{1,25}',str(run_id)):raise ValueError('BLOCKED_RUN_ID')
    card={'schema':'AVRORA_PER_RUN_VECTOR_DELTA_V1','run_id':str(run_id),'attempt':str(attempt),
          'trigger':source,'candidate':candidate,'real':'OFF','holdout':'SEALED',
          'oos_proven':False,'maker_fill_proven':False,
          'source_sha256':wave.SOURCE_SHA,'manifest_sha256':sha(manifest),
          'cache_hit':bool(cache_hit),'metrics':None}
    p=Path(receipt_path)
    if not p.is_file():
        card['status']='BLOCKED_NO_VERIFIED_RECEIPT';card['decision']='BLOCKED'
        card['insights']=['Нет проверенного результата; нельзя объявлять исследовательский прогон успешным']
    else:
        receipt=wave.verify_receipt(wave.MARKER+p.read_text('utf-8').strip(),manifest,candidate)
        card['status']='IDLE_CACHED_VERIFIED' if cache_hit else 'VERIFIED_NEW_COMPUTATION'
        card['decision']='REJECT' if receipt['decision']=='REJECT_DISCOVERY' else 'RESEARCH_REVIEW_REQUIRED_NOT_LIVE'
        card['receipt_sha256']=receipt['receipt_sha256']
        card['metrics']={k:receipt[k] for k in ('proposals','closed_trades','net20_usdt','net25_usdt','pf20','trades_per_symbol_day')}
        card['insights']=['Каузальная проверка CHECK2 пройдена; May/July уже были использованы; OOS нет',
                          'Нельзя считать свечной вход подтверждённым PostOnly исполнением']
        if receipt['net25_usdt']<=0:card['insights'].append('Издержки 25 bps уничтожают исследовательский результат')
        if receipt['trades_per_symbol_day']<4:card['insights'].append('Недостаточная частота относительно цели 4 сделки/символ/день')
    card['vector']=vec(' '.join([candidate,card['status'],card['decision'],*card['insights']]))
    card['identity']=sha({'candidate':candidate,'source':card['source_sha256'],
                         'engine_sha':wave.sha(Path(wave.__file__).read_bytes()),
                         'manifest':card['manifest_sha256']})
    card['card_sha256']=sha(card)
    return card


def run():
    candidate=os.environ.get('AVRORA_CANDIDATE_ID','')
    rid=os.environ.get('GITHUB_RUN_ID','')
    if not candidate or not rid:raise ValueError('BLOCKED_MISSING_RUN_CONTEXT')
    card=make_card(candidate,os.environ.get('AVRORA_RECEIPT','hourly_research_receipt.json'),
                   rid,os.environ.get('GITHUB_RUN_ATTEMPT','1'),
                   os.environ.get('AVRORA_CACHED','false')=='true',os.environ.get('GITHUB_EVENT_NAME','manual'))
    p=Path('research_vector_delta.json');p.write_text(json.dumps(card,ensure_ascii=False,indent=2)+'\n','utf-8')
    print('VECTOR_DELTA_SAVED',card['status'],card['decision'],card['card_sha256'])

if __name__=='__main__':
    try:run()
    except (OSError,ValueError) as e:
        print(str(e) if str(e).startswith('BLOCKED_') else 'BLOCKED_VECTOR_MAP_INGRESS',file=sys.stderr)
        sys.exit(1)