"""AVRORA P816 single-Colab job: ALL 12 discovery weeks + separate May AUX, 220 true preceding M15 bars.

Execution model and independent CHECK2 are imported from the already reviewed public launcher;
private candles are loaded only from a SHA-pinned dedicated private checkout. Discovery only.
No network, exchange API, Drive permissions or raw-trade output.
"""
from __future__ import annotations
import base64, csv, gzip, hashlib, io, json, math, os, pathlib, re, subprocess, sys, tempfile
from collections import defaultdict
from datetime import datetime, timezone

# Workspace includes tools/hourly_wave_research.py and tools/hourly_wave_check2.py.
try:
    from tools import hourly_wave_research as primary
    from tools import hourly_wave_check2 as independent
except ImportError:  # remote script has these modules alongside the evaluator
    import hourly_wave_research as primary
    import hourly_wave_check2 as independent

SCHEMA='AVRORA_P816_COMPLETE13_COLAB_CHECK2_V1'
DATA_SCHEMA='AVRORA_P816_13W_PREWEEK220_PRIVATE_DATA_V1'
PANEL_GZ_SHA='7e1bed08982de6e5ff1ec60cbd8afef68067298adcffd590149b43a099dbb297'
PANEL_CSV_SHA='a51b08d7bdc60e60a9f00b81520ac055761c3949efafa2947005c641a6b9d742'
SOURCE_ZIP_SHA='2f9a097048b04db0745be7fa3943319821cb6cd774c06c89a2447c11cd2775e9'
PRIVATE_DIR='research/P816_FULL13_PREWEEK220'
PARTS=10
TOTAL_GROUPS=78
TOTAL_ROWS=69576
WARMUP=220
TRADING_BARS=672
DISCOVERY_DAYS=84
AUX_DAYS=7
SYMBOLS=('BTCUSDT','ETHUSDT','LINKUSDT','NEARUSDT','SOLUSDT','XRPUSDT')
AUX='2026-05-01'
MARKER='AVRORA_FULL13_VERIFIED='  # one line, aggregate only


def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def h(raw):return hashlib.sha256(raw).hexdigest()

def gate():
    if os.getenv('REAL','OFF')!='OFF' or os.getenv('HOLDOUT','SEALED')!='SEALED':
        raise ValueError('BLOCKED_REAL_OR_HOLDOUT')


def load_private(checkout):
    gate()
    d=pathlib.Path(checkout).resolve()/PRIVATE_DIR
    path=d/'data_manifest.json'
    if not path.is_file():raise ValueError('BLOCKED_PRIVATE_P816_MANIFEST_MISSING')
    meta=json.loads(path.read_text('utf-8'))
    for key,expected in {
        'schema':DATA_SCHEMA,'source_archive_sha256':SOURCE_ZIP_SHA,
        'full_panel_gzip_sha256':PANEL_GZ_SHA, 'full_panel_csv_sha256':PANEL_CSV_SHA,
        'periods':13,'total_rows':TOTAL_ROWS,
        'warmup_bars':WARMUP,'trade_bars':TRADING_BARS,
        'real':'OFF','holdout':'SEALED','oos':False}.items():
        if type(meta.get(key))!=type(expected) or meta[key]!=expected:
            raise ValueError('BLOCKED_DATA_PIN_'+key)
    if meta.get('symbols')!=list(SYMBOLS):raise ValueError('BLOCKED_SYMBOLS')
    weeks=meta.get('discovery_week_starts',[])
    if len(weeks)!=12 or len(set(weeks))!=12 or sorted(weeks)!=weeks or meta.get('aux_may_week_start')!=AUX:
        raise ValueError('BLOCKED_PERIODS')
    if meta.get('source_original_P900_parquet_sha256') is None or len(meta['source_original_P900_parquet_sha256'])!=6:
        raise ValueError('BLOCKED_SOURCE_PARQUETS_UNVERIFIED')
    pieces=[]
    for k in range(1,PARTS+1):
        f=d/f'P816_PANEL.private.b64.part{k:02d}'
        if not f.is_file() or f.stat().st_size>160_000:raise ValueError('BLOCKED_PANEL_PART')
        s=f.read_text('ascii').strip()
        if not re.fullmatch(r'[A-Za-z0-9+/]*={0,2}',s):raise ValueError('BLOCKED_PANEL_ENCODING')
        pieces.append(s)
    try:compressed=base64.b64decode(''.join(pieces),validate=True)
    except ValueError as exc:raise ValueError('BLOCKED_PANEL_B64') from exc
    if len(compressed)!=meta['full_panel_gzip_bytes'] or h(compressed)!=PANEL_GZ_SHA:
        raise ValueError('BLOCKED_PANEL_GZIP_SHA')
    return compressed,meta


def parse_full(compressed,meta):
    gate()
    if h(compressed)!=PANEL_GZ_SHA:raise ValueError('BLOCKED_PANEL_SHA')
    try:raw=gzip.decompress(compressed)
    except (OSError,EOFError) as exc:raise ValueError('BLOCKED_PANEL_GZIP') from exc
    if len(raw)>8_000_000 or len(raw)!=meta.get('full_panel_csv_bytes') or h(raw)!=meta['full_panel_csv_sha256']:
        raise ValueError('BLOCKED_PANEL_CANONICAL_CSV_SHA')
    rows=csv.DictReader(io.StringIO(raw.decode('utf-8')))
    if rows.fieldnames!=['period','symbol','timestamp_ms','open','high','low','close']:
        raise ValueError('BLOCKED_PANEL_COLUMNS')
    data=defaultdict(list)
    for row in rows:
        key=(row['period'],row['symbol'])
        if key[0] not in (*meta['discovery_week_starts'],AUX) or key[1] not in SYMBOLS:
            raise ValueError('BLOCKED_PANEL_GROUP')
        try:bar=(int(row['timestamp_ms']),*[float(row[k]) for k in ('open','high','low','close')])
        except ValueError as exc:raise ValueError('BLOCKED_BAD_OHLC') from exc
        t,op,hi,lo,cl=bar
        if not all(math.isfinite(x) for x in bar) or t<=0 or not(0<lo<=min(op,cl)<=max(op,cl)<=hi):
            raise ValueError('BLOCKED_BAD_BAR')
        data[key].append(bar)
    if len(data)!=TOTAL_GROUPS or sum(map(len,data.values()))!=TOTAL_ROWS:
        raise ValueError('BLOCKED_DATASET_INCOMPLETE')
    for (week,symbol), bars in data.items():
        if len(bars)!=WARMUP+TRADING_BARS:raise ValueError('BLOCKED_PARTIAL_WEEK')
        first=int(datetime.fromisoformat(week).replace(tzinfo=timezone.utc).timestamp()*1000)
        if bars[WARMUP][0]!=first or bars[-1][0]!=first+(TRADING_BARS-1)*900000:
            raise ValueError('BLOCKED_TRADE_WINDOW')
        for a,b in zip(bars,bars[1:]):
            if b[0]-a[0]!=900000:raise ValueError('BLOCKED_M15_GRID')
    return dict(data)


def select_signals(fn,bars,params):
    # Indicators see 220 genuine earlier bars; trading starts exactly at first
    # week's open and every accepted trade must have a complete future horizon.
    return [s for s in fn(bars,params)
            if WARMUP<=s['entry_i'] and s['entry_i']+params['max_bars']<len(bars)]


def build_portfolio(data,params,signal_fn,fill_fn):
    proposals=[]
    for (week,symbol),bars in sorted(data.items()):
        for s in select_signals(signal_fn,bars,params):
            proposals.append((s['signal_t'],symbol,week,bars,s))
    proposals.sort(key=lambda z:(z[0],z[1],z[2]))
    ledger=[]
    for _,symbol,week,bars,s in proposals:
        trade=fill_fn(bars,s,params)
        if trade is None:continue
        active=[t for t in ledger if t['entry_t']<=trade['entry_t']<=t['exit_t']]
        if len(active)>=2 or any(t['symbol']==symbol for t in active):continue
        ledger.append({**trade,'symbol':symbol,'period':week})
    return proposals,ledger


def compare_exact(actual,expected,scope):
    # Reuse independent review's entire-field numerical tolerance checking.
    independent.same_fields(actual,expected,scope)


def run_complete(data,meta,manifest,candidate,params,engine=primary,checker=independent):
    gate()
    if candidate not in [q['id'] for q in manifest['candidates']]:
        raise ValueError('BLOCKED_UNREGISTERED_CANDIDATE')
    proposals,ledger=build_portfolio(data,params,engine.signals,engine.simulate_one)
    ip,il=build_portfolio(data,params,checker.independent_signals,checker.independent_fill)
    def stripped(q):return [{'symbol':symbol,'period':week,**sig} for _,symbol,week,_,sig in q]
    compare_exact(stripped(proposals),stripped(ip),'signals')
    compare_exact(ledger,il,'complete_ledger')
    engine.check_trades(ledger)
    # Pre-registered future-prefix causality checks on every week and symbol.
    prefix_checks=0
    for bars in data.values():
        for stop_i in (320,540,800):
            for fn in (engine.signals,checker.independent_signals):
                prior=fn(bars[:stop_i],params)
                stable=[x for x in fn(bars,params) if x['signal_i']<stop_i-1]
                if prior!=stable:raise ValueError('BLOCKED_FUTURE_LOOKAHEAD')
                prefix_checks+=1
    if len(ledger)>len(proposals):raise ValueError('BLOCKED_LEDGER')
    discovery=[t for t in ledger if t['period']!=AUX]
    auxiliary=[t for t in ledger if t['period']==AUX]
    def subtotal(trades,key):return round(sum(t[key] for t in trades),6)
    def subset(trades):
        pos=sum(max(0,t['net20']) for t in trades);neg=-sum(min(0,t['net20']) for t in trades)
        return {'trades':len(trades), 'net20_usdt':subtotal(trades,'net20'),
            'net25_usdt':subtotal(trades,'net25'),
            'net40_usdt':round(sum(t['gross']-t['notional']*0.0040 for t in trades),6),
            'pf20':round(pos/neg,6) if neg else None}
    d=subset(discovery);aux=subset(auxiliary)
    weeks={w:subset([t for t in discovery if t['period']==w]) for w in meta['discovery_week_starts']}
    symbols={sym:subset([t for t in discovery if t['symbol']==sym]) for sym in SYMBOLS}
    receipt={
        'schema':SCHEMA,'status':'PASS_FULL13_CAUSAL_CHECK2',
        'candidate':candidate,'params':params,
        'source_zip_sha256':SOURCE_ZIP_SHA,'panel_gzip_sha256':PANEL_GZ_SHA,
        'panel_csv_sha256':meta['full_panel_csv_sha256'],
        'source_parquet_sha256':meta['source_original_P900_parquet_sha256'],
        'model_sha256':h(pathlib.Path(engine.__file__).read_bytes()),
        'checker_sha256':h(pathlib.Path(checker.__file__).read_bytes()),
        'manifest_sha256':h(canon(manifest).encode()),
        'warmup_bars_per_period':WARMUP,'trade_bars_per_period':TRADING_BARS,
        'bars_total':TOTAL_ROWS,'discovery_week_count':12,'may_aux_week_count':1,
        'periods_complete':len(data),'discovery_days':DISCOVERY_DAYS,
        'proposals_total':len(proposals),'closed_trades_total':len(ledger),
        'lookahead_prefix_checks':prefix_checks,
        'discovery':{**d,'net20_usdt_day':round(d['net20_usdt']/DISCOVERY_DAYS,6),
                     'trades_per_symbol_day':round(d['trades']/(DISCOVERY_DAYS*6),6)},
        'may_aux':aux,'by_week':weeks,'by_symbol':symbols,
        'check2':'PASS_FULL_SIGNALS_AND_LEDGER','real':'OFF','holdout':'SEALED','oos':False,
        'execution_proxy':'NEXT_BAR_OPEN_STOP_FIRST_GAP_OPEN','maker_fills_proven':False,
        'funding_modeled':False,'slippage_modeled':False,
        'decision':'REJECT_FOR_LIVE_DISCOVERY_ONLY',
        'notes':'12 previously used discovery weeks; May is an auxiliary 7-day period, never included in 84-day discovery PnL'
    }
    receipt['receipt_sha256']=h(canon(receipt).encode())
    return receipt


def verify_receipt(result,manifest,candidate):
    if not isinstance(result,dict) or result.get('schema')!=SCHEMA:
        raise ValueError('BLOCKED_RECEIPT_SCHEMA')
    digest=result.get('receipt_sha256')
    if not isinstance(digest,str) or h(canon({k:v for k,v in result.items() if k!='receipt_sha256'}).encode())!=digest:
        raise ValueError('BLOCKED_RECEIPT_SHA')
    if result.get('candidate')!=candidate or result.get('status')!='PASS_FULL13_CAUSAL_CHECK2':
        raise ValueError('BLOCKED_RECEIPT_SCOPE')
    pins={'source_zip_sha256':SOURCE_ZIP_SHA,'panel_gzip_sha256':PANEL_GZ_SHA,'bars_total':TOTAL_ROWS,
          'warmup_bars_per_period':220,'trade_bars_per_period':672,'periods_complete':78,
          'discovery_week_count':12,'may_aux_week_count':1,'discovery_days':84,
          'lookahead_prefix_checks':468,
          'check2':'PASS_FULL_SIGNALS_AND_LEDGER','real':'OFF','holdout':'SEALED','oos':False,
          'maker_fills_proven':False,'decision':'REJECT_FOR_LIVE_DISCOVERY_ONLY'}
    for key,v in pins.items():
        if type(result.get(key))!=type(v) or result[key]!=v:raise ValueError('BLOCKED_RECEIPT_PIN_'+key)
    for field,actual in [('model_sha256',primary.__file__),('checker_sha256',independent.__file__)]:
        if result.get(field)!=h(pathlib.Path(actual).read_bytes()):
            raise ValueError('BLOCKED_RECEIPT_PIN_'+field)
    p=next((q for q in manifest['candidates'] if q['id']==candidate),None)
    if p is None or result.get('params')!=p:raise ValueError('BLOCKED_CANDIDATE_PARAMS')
    if result.get('manifest_sha256')!=h(canon(manifest).encode()):raise ValueError('BLOCKED_MANIFEST_SHA')
    for phase,days in [('discovery',84),('may_aux',7)]:
        block=result.get(phase,{});n=block.get('trades')
        if type(n) is not int or n<0:raise ValueError('BLOCKED_TRADES')
        for f in ('net20_usdt','net25_usdt','net40_usdt'):
            if type(block.get(f)) not in (int,float) or not math.isfinite(block[f]):raise ValueError('BLOCKED_NET')
        if not(block['net20_usdt']>=block['net25_usdt']>=block['net40_usdt']):
            raise ValueError('BLOCKED_COST_ORDER')
    if len(result.get('by_week',{}))!=12 or len(result.get('by_symbol',{}))!=6:
        raise ValueError('BLOCKED_SCOPE_COMPLETE')
    if abs(sum(w['net20_usdt'] for w in result['by_week'].values())-result['discovery']['net20_usdt'])>0.0001:
        raise ValueError('BLOCKED_WEEK_SUM')
    if abs(sum(w['net20_usdt'] for w in result['by_symbol'].values())-result['discovery']['net20_usdt'])>0.0001:
        raise ValueError('BLOCKED_SYMBOL_SUM')
    if result['discovery']['trades']+result['may_aux']['trades']!=result.get('closed_trades_total'):
        raise ValueError('BLOCKED_TRADE_COUNT')
    if abs(result['discovery']['net20_usdt_day']-round(result['discovery']['net20_usdt']/84,6))>1e-8:
        raise ValueError('BLOCKED_DAY_DENOMINATOR')
    return result


def build_colab_script(compressed,meta,manifest,candidate):
    # Single remotely executed Python notebook/script: neither weeks nor symbols
    # are farmed to individual jobs. All 13 periods are needed for one signed result.
    code=pathlib.Path(__file__).read_bytes()
    eng=pathlib.Path(primary.__file__).read_bytes()
    chk=pathlib.Path(independent.__file__).read_bytes()
    resources={'full13_wave_colab.py':code,'hourly_wave_research.py':eng,
        'hourly_wave_check2.py':chk,'P816_panel.gz':compressed,
        'data_manifest.json':canon(meta).encode(),'prereg.json':canon(manifest).encode()}
    encoded={k:base64.b64encode(v).decode() for k,v in resources.items()}
    return ('import base64,json,os,pathlib,subprocess,sys,tempfile\n'
      "if os.environ.get('REAL','OFF')!='OFF' or os.environ.get('HOLDOUT','SEALED')!='SEALED':\n raise SystemExit('BLOCKED_SAFETY_GATE')\n"
      'with tempfile.TemporaryDirectory(prefix="avrora-full13-") as d:\n'
      ' p=pathlib.Path(d)\n'
      f' files={repr(encoded)}\n'
      " for name,content in files.items(): (p/name).write_bytes(base64.b64decode(content))\n"
      f' result=subprocess.run([sys.executable,"full13_wave_colab.py","evaluate",str(p/"P816_panel.gz"),str(p/"data_manifest.json"),str(p/"prereg.json"),{candidate!r}],cwd=p,capture_output=True,text=True,timeout=1200)\n'
      " if result.returncode: raise SystemExit('BLOCKED_FULL13_EXECUTION')\n"
      f' if result.stdout.count({MARKER!r})!=1: raise SystemExit("BLOCKED_FULL13_RESULT_SHAPE")\n'
      " print(result.stdout.strip(),flush=True)\n")


def remote_run(compressed,meta,manifest,candidate):
    code=build_colab_script(compressed,meta,manifest,candidate)
    with tempfile.TemporaryDirectory(prefix='avrora-full13-job-') as root:
        script=pathlib.Path(root)/'study.py';script.write_text(code,encoding='utf-8');script.chmod(0o600)
        log=pathlib.Path(root)/'remote.log'
        with log.open('wb') as f:
            p=subprocess.run(['colab','--auth=adc','run',str(script)],stdout=f,stderr=subprocess.STDOUT,
                             timeout=1500,env={**os.environ,'REAL':'OFF','HOLDOUT':'SEALED'})
        if p.returncode!=0:raise ValueError('BLOCKED_FULL13_COLAB_FAILED')
        body=log.read_text('utf-8')
        msgs=[x.split(MARKER,1)[1] for x in body.splitlines() if MARKER in x]
        if len(msgs)!=1:raise ValueError('BLOCKED_FULL13_COLAB_MARKER')
        return verify_receipt(json.loads(msgs[0]),manifest,candidate)


def main(args):
    gate()
    if not args:raise ValueError('BLOCKED_MISSING_MODE')
    mode=args[0]
    if mode=='select':
        if len(args)!=1:raise ValueError('BLOCKED_SELECT_ARGS')
        print('id='+primary.select(primary.load_manifest()))
        return
    if mode=='verify':
        if len(args)!=3:raise ValueError('BLOCKED_VERIFY_ARGS')
        candidate=args[2]
        receipt=json.loads(pathlib.Path(args[1]).read_text('utf-8'))
        verify_receipt(receipt,primary.load_manifest(),candidate)
        print('PASS_FULL13_RECEIPT_SHA_AND_SCOPE')
        return
    if mode=='run':
        if len(args)!=2:raise ValueError('BLOCKED_RUN_ARGS')
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):raise ValueError('BLOCKED_COLAB_AUTH_ABSENT')
        checkout=os.environ.get('AVRORA_PRIVATE_CHECKOUT')
        if not checkout:raise ValueError('BLOCKED_PRIVATE_SOURCE_NOT_CHECKED_OUT')
        compressed,meta=load_private(checkout)
        manifest=primary.load_manifest()
        candidate=args[1]
        if candidate not in [p['id'] for p in manifest['candidates']]:
            raise ValueError('BLOCKED_UNREGISTERED_CANDIDATE')
        receipt=remote_run(compressed,meta,manifest,candidate)
        out=pathlib.Path('full13_research_receipt.json')
        out.write_text(canon(receipt)+'\n',encoding='utf-8')
        verify_receipt(receipt,manifest,candidate)
        print('PASS_FULL13_COLAB_AGGREGATE_ONLY')
        return
    if mode=='evaluate':
        if len(args)!=5:raise ValueError('BLOCKED_EVALUATE_ARGUMENTS')
        _,p,mf,cat,candidate=args
        meta=json.loads(pathlib.Path(mf).read_text('utf-8'))
        manifest=primary.validate_manifest(json.loads(pathlib.Path(cat).read_text('utf-8')))
        compressed=pathlib.Path(p).read_bytes()
        data=parse_full(compressed,meta)
        params=next((c for c in manifest['candidates'] if c['id']==candidate),None)
        if params is None:raise ValueError('BLOCKED_UNREGISTERED_CANDIDATE')
        result=run_complete(data,meta,manifest,candidate,params)
        verify_receipt(result,manifest,candidate)
        print(MARKER+canon(result))
        return
    raise ValueError('BLOCKED_UNKNOWN_MODE')


if __name__=='__main__':
    try:main(sys.argv[1:])
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as e:
        msg=str(e)
        print(msg if msg.startswith('BLOCKED_') else 'BLOCKED_FULL13_RESEARCH',file=sys.stderr)
        raise SystemExit(1) from None