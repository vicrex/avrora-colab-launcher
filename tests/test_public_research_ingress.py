import copy
import json
import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from tools import public_research_ingress as p


def proposal():
    return {'schema':1,'source':'chatgpt-model-search','delivery_id':'hourly:20261021:1',
      'spec':{'adapter':'unreviewed-model-proposal',
       'mechanism':{'model':'Conformal-forecast','revision':'sha-not-yet-reviewed',
         'hypothesis':'Test M15 regime using completed candles only',
         'source_url':'https://arxiv.org/abs/2401.00001'},
       'dataset':'MISSING','parameters':{'horizon_bars':4,'baseline':'rolling median'},
       'real':'OFF','holdout':'SEALED'}}

def issue(x=None,n=7,owner='vicrex'):
    return {'number':n,'user':{'login':owner},
            'body':p.PREFIX+'\n'+json.dumps(x or proposal())}

class Ingress(unittest.TestCase):
    def test_accepts_only_public_contract(self):
        self.assertEqual(p.parse(issue()['body']),proposal())
    def test_rejects_unsafe_execution(self):
        for field,value in [('real','ON'),('holdout','OPEN'),('adapter','vwap-ledger-reviewed')]:
            x=proposal();x['spec'][field]=value
            with self.assertRaises(p.Blocked):p.parse(issue(x)['body'])
    def test_rejects_raw_series(self):
        x=proposal();x['spec']['candles']=[1,2,3]
        with self.assertRaises(p.Blocked):p.parse(issue(x)['body'])
    def test_rejects_source_url(self):
        for url in ['http://arxiv.org/a','https://evil.com/a','https://drive.google.com/a']:
            x=proposal();x['spec']['mechanism']['source_url']=url
            with self.assertRaises(p.Blocked):p.parse(issue(x)['body'])
    def test_rejects_private_patterns(self):
        for val in ['-----BEGIN PRIVATE KEY-----','C:\\source\\repo','private_key: abc']:
            x=proposal();x['spec']['mechanism']['hypothesis']=val
            with self.assertRaises(p.Blocked):p.parse(issue(x)['body'])
    def test_same_id_conflict_and_duplicate(self):
        x=proposal();other=copy.deepcopy(x);other['spec']['parameters']['horizon_bars']=8
        self.assertEqual(p.dupe(7,x,[issue(other,n=3)]),'BLOCKED_ID_COLLISION')
        self.assertEqual(p.dupe(7,x,[issue(x,n=3)]),'BLOCKED_DUPLICATE')
    def test_delivery_twice_creates_one_comment(self):
        obj=issue();comments=[];writes=[]
        def gh(method,url,payload=None):
            if method=='POST':
                writes.append(payload)
                row={'id':123,'body':payload['body']}
                comments.append(row)
                return row
            return comments[0]
        args=(obj,lambda:[obj],lambda _:comments,gh)
        self.assertEqual(p.process(*args),'PUBLIC_REGISTERED_BLOCKED_EXECUTION')
        self.assertEqual(p.process(*args),'IDLE_ALREADY_REGISTERED')
        self.assertEqual(len(writes),1)
        self.assertIn(p.digest(proposal()),comments[0]['body'])
        self.assertIn('economic_run: NOT_RUN',comments[0]['body'])
    def test_readback_failure(self):
        def gh(method,url,payload=None):return {'id':123,'body':'wrong'}
        with self.assertRaisesRegex(p.Blocked,'BLOCKED_READBACK'):
            p.process(issue(),lambda:[],lambda _:[],gh)
    def test_issue_mutation(self):
        x=proposal();x['spec']['parameters']['baseline']='changed'
        old={'body':p.receipt(proposal(),7)}
        with self.assertRaisesRegex(p.Blocked,'BLOCKED_EDIT_AFTER_PREREG'):
            p.process(issue(x),lambda:[],lambda _:[old],lambda *args:None)
    def test_owner_guard(self):
        self.assertEqual(p.process(issue(owner='external'),lambda:self.fail(),
                lambda _:self.fail(),lambda *args:self.fail()),'SKIPPED_UNTRUSTED_AUTHOR')
    def test_two_sequential_receipts_are_distinct_and_idempotent(self):
        a = proposal()
        b = copy.deepcopy(a)
        b['delivery_id'] = 'hourly:20261021:2'
        b['spec']['mechanism']['model'] = 'Regime-conditioned-forecast'
        stored = []
        def api(method, url, payload=None):
            if method == 'POST':
                row = {'id':len(stored)+1, 'body':payload['body']}
                stored.append(row)
                return row
            return stored[int(url.rsplit('/',1)[-1])-1]
        scenarios = [(issue(a,7),7),(issue(b,8),8)]
        for current, number in scenarios:
            def current_comments(n):
                return [z for z in stored if f'issue: {n}\n' in z['body']]
            args = (current, lambda:[row for row,_ in scenarios], current_comments, api)
            self.assertEqual(p.process(*args), 'PUBLIC_REGISTERED_BLOCKED_EXECUTION')
            self.assertEqual(p.process(*args), 'IDLE_ALREADY_REGISTERED')
        self.assertEqual(len(stored),2)
        self.assertNotEqual(stored[0]['body'],stored[1]['body'])
        self.assertIn(p.digest(a),stored[0]['body'])
        self.assertIn(p.digest(b),stored[1]['body'])

    def test_duplicate_scan_not_dependent_on_issue_order(self):
        x=proposal()
        future=issue(x,n=12)
        earlier=issue(x,n=3)
        # A later identical issue may be listed before an earlier duplicate.
        self.assertEqual(p.dupe(7,x,[future,earlier]), 'BLOCKED_DUPLICATE')
        mutated=copy.deepcopy(x)
        mutated['spec']['parameters']['baseline']='altered'
        self.assertEqual(p.dupe(7,x,[future,issue(mutated,n=4)]), 'BLOCKED_ID_COLLISION')

    def test_future_identical_issue_not_reverse_duplicate(self):
        x=proposal()
        self.assertIsNone(p.dupe(7,x,[issue(x,n=10)]))

    def test_restricted_run_no_private_execution(self):
        txt=p.receipt(proposal(),12)
        self.assertIn('PUBLIC_REGISTERED_BLOCKED_EXECUTION',txt)
        self.assertIn('economic_run: NOT_RUN',txt)
        self.assertIn('drive_ack: NOT_DELIVERED',txt)

    def test_main_reads_live_issue_not_stale_event_body(self):
        current = issue(n=7)
        stale = issue(n=7)
        stale['body'] = 'AVRORA_RESEARCH_V1\n{}'
        with tempfile.TemporaryDirectory() as d:
            event_path = Path(d) / 'event.json'
            event_path.write_text(json.dumps({'issue': stale}))
            with patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event_path),
                                         'GH_TOKEN': 'test-only', 'REAL':'OFF', 'HOLDOUT':'SEALED'}):
                with patch.object(p, 'gh', return_value=current) as getter:
                    with patch.object(p, 'process', return_value='IDLE_ALREADY_REGISTERED') as processor:
                        self.assertEqual(p.main(), 0)
                        self.assertEqual(processor.call_args.args[0], current)
                        getter.assert_called_once_with('GET', f'/repos/{p.REPO}/issues/7')

    def test_main_skips_untrusted_event_before_any_read(self):
        with tempfile.TemporaryDirectory() as d:
            event_path = Path(d) / 'event.json'
            event_path.write_text(json.dumps({'issue': issue(owner='external')}))
            with patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event_path),
                                         'GH_TOKEN': 'test-only', 'REAL':'OFF', 'HOLDOUT':'SEALED'}):
                with patch.object(p, 'gh') as getter:
                    self.assertEqual(p.main(), 0)
                    getter.assert_not_called()

    def test_delivery_hash_stable(self):
        self.assertEqual(p.digest(proposal()),p.digest(copy.deepcopy(proposal())))

if __name__=='__main__':unittest.main()
