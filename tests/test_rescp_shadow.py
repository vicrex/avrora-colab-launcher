import math
import os
import unittest
from unittest.mock import patch

from tools import rescp_shadow as primary
from tools import rescp_check2 as checker

def bars(n=520,shock=None):
    p=100.;out=[]
    for t in range(n):
        change=.0007*math.sin(t*.053)+.0003*math.cos(t*.13)
        if shock is not None and t>=shock:change+=.002
        op=p;p=op*math.exp(change)
        out.append((1670000000000+900000*t,op,max(op,p)*1.001,min(op,p)*.999,p))
    return out

class ResCPLite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=bars()

    def test_requires_explicit_research_permission(self):
        with patch.dict(os.environ,{'REAL':'OFF','HOLDOUT':'SEALED','AVRORA_ALLOW_RESCP_SHADOW':''}):
            with self.assertRaisesRegex(ValueError,'BLOCKED_RESCP_SHADOW_NOT_APPROVED'):primary.gate()
        with patch.dict(os.environ,{'REAL':'ON','HOLDOUT':'SEALED','AVRORA_ALLOW_RESCP_SHADOW':'YES'}):
            with self.assertRaisesRegex(ValueError,'BLOCKED_REAL_OR_HOLDOUT'):primary.gate()

    def test_ridge_does_not_train_on_future(self):
        beta=primary.frozen_forecaster(self.data)
        self.assertEqual(beta,primary.frozen_forecaster(bars(shock=220)))
        self.assertEqual(len(beta),17)

    def test_independent_calibration_and_signals(self):
        a,trades,fall=primary.group_compute(self.data,'2026-07-01','BTCUSDT')
        b,other,fb=checker.group(self.data,'2026-07-01','BTCUSDT')
        for key in a:checker.compare(a[key],b[key],key)
        checker.compare(trades,other,'trades')
        self.assertEqual(fall,fb)
        self.assertGreater(len(a['reservoir']),100)

    def test_prefix_stability(self):
        a,ta,_=primary.group_compute(bars(470),'2026-07-01','BTCUSDT')
        b,tb,_=primary.group_compute(bars(520,shock=470),'2026-07-01','BTCUSDT')
        for key in a:checker.compare(a[key],b[key][:len(a[key])],key)
        checker.compare(ta,[x for x in tb if x['signal_t']<=bars(470)[-5][0]],'trades')

    def test_label_maturity_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'BLOCKED_UNMATURED_CALIBRATION'):
            primary.radii([(100,1.,tuple([.2]*12))]*96,tuple([.2]*12),102)

    def test_weighted_quantile_check(self):
        self.assertEqual(primary.wquant([1,3,5],[1,1,20]),5)
        self.assertEqual(checker.wquant([5,1,3],[20,1,1]),5)

    def test_checker_detects_mutation(self):
        a,_,_=primary.group_compute(self.data,'2026-07-01','BTCUSDT')
        good={k:primary.metric(v) for k,v in a.items()}
        wrong={k:dict(v) for k,v in good.items()}
        wrong['reservoir']['winkler_bps']+=1000
        with self.assertRaisesRegex(ValueError,'BLOCKED_CHECK2_VALUE'):checker.compare(good,wrong)

    def test_portfolio_max_two(self):
        t=[dict(period='2026-07-01',symbol=s,entry_t=1000,exit_t=4000)
           for s in ('BTCUSDT','ETHUSDT','SOLUSDT')]
        self.assertEqual(len(primary.portfolio(t)),2)

    def test_scope_requires_full13(self):
        with patch.dict(os.environ,{'REAL':'OFF','HOLDOUT':'SEALED','AVRORA_ALLOW_RESCP_SHADOW':'YES'}):
            with self.assertRaisesRegex(ValueError,'BLOCKED_FULL13_SHAPE'):
                primary.evaluate({})

if __name__=='__main__':unittest.main()
