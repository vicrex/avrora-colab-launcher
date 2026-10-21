import json, math, os, unittest
from unittest.mock import patch
from tools import h4_directional_audit as a
from tools import h4_directional_check2 as b

def fixture(n=270,alter_at=None):
    value=100.
    bars=[]
    for t in range(n):
        d=0.0006*math.sin(t/17)+0.0003*math.cos(t/11)
        if alter_at is not None and t>=alter_at:d+=0.05
        op=value;value=op*math.exp(d)
        bars.append((1660000000000+t*900000,op,max(op,value)*1.001,min(op,value)*.999,value))
    return bars

class FrozenH4Audit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars=fixture(300)
        cls.events=a.group_events(cls.bars,"2021-01-01","BTCUSDT")

    def test_no_trading_or_holdout(self):
        with patch.dict(os.environ,{"REAL":"ON","AVRORA_H4_AUDIT_ALLOWED":"YES"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_REAL_OR_HOLDOUT"):a.guard()
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED","AVRORA_H4_AUDIT_ALLOWED":""}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_H4_AUDIT_NOT_AUTHORIZED"):a.guard()

    def test_independent_entire_signal_stream(self):
        other=b.group(self.bars,"2021-01-01","BTCUSDT")
        b.assert_near(self.events,other)
        self.assertEqual(len(self.events),76)

    def test_future_modified_does_not_change_past_proposals(self):
        one=a.group_events(fixture(275),"2021-01-01","BTCUSDT")
        two=a.group_events(fixture(300,alter_at=275),"2021-01-01","BTCUSDT")
        b.assert_near(one,[v for v in two if v["t"]<=one[-1]["t"]])
        for m in a.MODES:
            _,t1=a.portfolio(one,m)
            _,t2=a.portfolio([v for v in two if v["t"]<=one[-1]["t"]],m)
            b.assert_near(t1,t2)

    def test_summaries_agree_with_independent_checker(self):
        own=a.summarize(self.events,7)
        independent=b.aggregate(b.group(self.bars,"2021-01-01","BTCUSDT"),7)
        b.assert_near(own,independent)

    def test_cost_monotonicity(self):
        data=a.summarize(self.events,7)
        for result in data["methods"].values():
            net=result["net_by_cost_bps_usdt"]
            self.assertGreaterEqual(net["16"],net["20"])
            self.assertGreaterEqual(net["20"],net["25"])
            self.assertGreaterEqual(net["25"],net["40"])

    def test_policies_are_frozen(self):
        self.assertEqual(a.MODES,("RIDGE_SIGN_0","RIDGE_SIGN_10","RIDGE_SIGN_20","MOM4_SIGN","REVERSE_MOM4"))
        self.assertEqual(a.STRESS_BPS,(16,20,25,40))
        with self.assertRaisesRegex(ValueError,"BLOCKED_UNREVIEWED_GATE"):
            a.side_for(self.events[0],"UNKNOWN")

    def test_shadow_portfolio_capacity(self):
        rows=[]
        for s in ("BTCUSDT","ETHUSDT","SOLUSDT"):
            x=dict(self.events[0]);x["symbol"]=s;x["pred"]=100.
            rows.append(x)
        offered,trades=a.portfolio(rows,"RIDGE_SIGN_0")
        self.assertEqual(offered,3)
        self.assertEqual(len(trades),2)

    def test_high_frequency_portfolio_remains_bounded_and_independent(self):
        # Previously re-scanning the full accepted ledger made this O(N^2).
        stream=[]
        seed=self.events[0]
        for i in range(12000):
            x=dict(seed)
            x["entry_t"]=seed["entry_t"]+900000*i
            x["exit_t"]=x["entry_t"]+2700000
            x["symbol"]=("BTCUSDT","ETHUSDT","SOLUSDT")[i%3]
            x["pred"]=25.0
            stream.append(x)
        offered,accepted=a.portfolio(stream,"RIDGE_SIGN_0")
        other_offered,other_accepted=b.proposals(stream,"RIDGE_SIGN_0")
        self.assertEqual(offered,other_offered)
        self.assertEqual(offered,12000)
        self.assertEqual(len(accepted),len(other_accepted))
        self.assertGreater(len(accepted),2000)
        for x,y in zip(accepted,other_accepted):
            self.assertEqual((x["entry_t"],x["symbol"],x["exit_t"]),
                             (y[0],y[1],y[3]))

    def test_checker_rejects_tampered_summary(self):
        good=a.summarize(self.events,7)
        bad=json.loads(json.dumps(good))
        bad["methods"]["RIDGE_SIGN_20"]["gross_usdt"]+=100
        with self.assertRaisesRegex(ValueError,"BLOCKED_H4_CHECK2_VALUE"):
            b.assert_near(good,bad)

    def test_full13_missing_blocks(self):
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED","AVRORA_H4_AUDIT_ALLOWED":"YES"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_H4_INCOMPLETE_PANEL"):
                a.execute({},{"discovery_week_starts":[]})

if __name__=="__main__":unittest.main()
