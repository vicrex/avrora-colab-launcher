import copy, math, os, unittest
from unittest.mock import patch
from tools import structural_short as a
from tools import structural_short_check2 as b

def candles(n=892,shock=248):
    price=100.;out=[]
    for i in range(n):
        op=price
        step=-.0007+0.0001*math.cos(i/8)
        if i==shock:step=-.005
        price=op*math.exp(step)
        high=max(op,price)*1.001
        low=min(op,price)*.999
        out.append((1680000000000+900000*i,op,high,low,price))
    return out

class StructuralShortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.series=candles()
        cls.manifest,_=a.load_manifest()

    def test_frozen_contract_and_lock(self):
        self.assertEqual(self.manifest["candidate_ids"],list(a.CANDIDATES))
        self.assertEqual(self.manifest["fixed_parameters"]["support_lookback"],12)
        self.assertEqual(self.manifest["fixed_parameters"]["start_equity_usdt"],300)

    def test_unsafe_or_unapproved_blocks(self):
        with patch.dict(os.environ,{"AVRORA_STRUCT_SHORT_ENABLED":"YES","REAL":"ON","HOLDOUT":"SEALED"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_REAL_OR_HOLDOUT"):a.gate()
        with patch.dict(os.environ,{"AVRORA_STRUCT_SHORT_ENABLED":"","REAL":"OFF","HOLDOUT":"SEALED"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_STRUCTURAL_SHORT_NOT_AUTHORIZED"):a.gate()

    def test_same_signal_stream_as_independent_checker(self):
        left=a.find_events(self.series,"2026-07-01","BTCUSDT",self.manifest["fixed_parameters"])
        right=b.derive(self.series,"2026-07-01","BTCUSDT")
        self.assertGreaterEqual(len(left),1)
        self.assertEqual(len(left),len(right))
        for x,y in zip(left,right):
            self.assertEqual(x["signal_i"],y["signal_i"])
            self.assertEqual(x["trend"],y["trend"])
            b.assert_equal({k:v for k,v in x.items() if k!="bars"},
                           {k:v for k,v in y.items() if k!="bars"})

    def test_future_prefix_no_lookahead(self):
        earlier=a.find_events(candles(510),"2026-07-01","BTCUSDT",self.manifest["fixed_parameters"])
        changed=candles(600)
        for i in range(510,len(changed)):
            row=list(changed[i]);row[1:]=[90.,93.,87.,89.]
            changed[i]=tuple(row)
        later=a.find_events(changed,"2026-07-01","BTCUSDT",self.manifest["fixed_parameters"])
        # Full 12-bar horizon must be available for entry/exit.
        b.assert_equal(
          [{k:v for k,v in e.items() if k!="bars"} for e in earlier],
          [{k:v for k,v in e.items() if k!="bars"} for e in later
           if e["signal_i"]<510-a.MAX_DURATION-1])

    def test_new_retest_is_causal_and_recomputed_independently(self):
        params=self.manifest["fixed_parameters"]
        original=a.find_events(self.series,"2026-07-01","BTCUSDT",params)
        self.assertGreater(len(original),0)
        first=original[0]
        t=first["signal_i"];k=t+1
        support=min(self.series[j][3] for j in range(t-12,t))
        atr=first["atr"]
        changed=list(self.series)
        op=support+0.30*atr
        close=support-0.30*atr
        changed[k]=(changed[k][0],op,support+0.35*atr,
                    close-0.10*atr,close)
        left=a.find_retest_events(changed,"2026-07-01","BTCUSDT",params)
        right=b.derive_retests(changed,"2026-07-01","BTCUSDT")
        self.assertGreaterEqual(len(left),1)
        self.assertEqual([x["signal_i"] for x in left],
                         [x["signal_i"] for x in right])
        for x,y in zip(left,right):
            b.assert_equal({key:value for key,value in x.items() if key!="bars"},
                           {key:value for key,value in y.items() if key!="bars"})
            self.assertEqual(x["entry_t"],changed[x["signal_i"]+1][0])
            self.assertLess(x["signal_t"],x["entry_t"])
        self.assertTrue(any(x["signal_i"]==k for x in left))

    def test_new_retest_requires_closed_rejection_not_future_bounce(self):
        p=self.manifest["fixed_parameters"]
        first=a.find_events(self.series,"2026-07-01","BTCUSDT",p)[0]
        t=first["signal_i"];k=t+1
        support=min(self.series[j][3] for j in range(t-12,t))
        broken=list(self.series)
        op=support+0.30*first["atr"]
        close=support+0.05*first["atr"]  # no close below former support
        broken[k]=(broken[k][0],op,op+0.1*first["atr"],
                   close-0.1*first["atr"],close)
        retests=a.find_retest_events(broken,"2026-07-01","BTCUSDT",p)
        self.assertFalse(any(x["signal_i"]==k for x in retests))

    def test_v3_squeeze_signal_is_causal_and_independent(self):
        # Artificial controlled compression after prolonged downtrend;
        # do not use historical profitability to design this fixture.
        base=candles()
        t=350
        barlist=list(base)
        for i in range(t-16,t-8):
            ts,op,hi,lo,cl=barlist[i]
            barlist[i]=(ts,op,max(hi,cl*1.008),min(lo,cl*0.992),cl)
        flat=barlist[t-9][4]
        for i in range(t-8,t):
            ts,op,hi,lo,cl=barlist[i]
            barlist[i]=(ts,flat,flat*1.0004,flat*.9996,flat)
        ts,op,hi,lo,cl=barlist[t]
        barlist[t]=(ts,flat,flat*1.001,flat*0.987,flat*0.988)
        first=a.find_squeeze_events(barlist,"2026-07-01","BTCUSDT",self.manifest["fixed_parameters"])
        second=b.derive_squeezes(barlist,"2026-07-01","BTCUSDT")
        self.assertEqual([e["signal_i"] for e in first],[e["signal_i"] for e in second])
        self.assertTrue(any(e["signal_i"]==t for e in first))
        for x,y in zip(first,second):
            b.assert_equal({k:v for k,v in x.items() if k!="bars"},
                           {k:v for k,v in y.items() if k!="bars"})
            self.assertLess(x["signal_t"],x["entry_t"])
        mutated=list(barlist)
        for i in range(t+2,t+8):
            ts,op,hi,lo,cl=mutated[i]
            mutated[i]=(ts,op,max(hi,op*1.12),min(lo,op*.89),op)
        changed=a.find_squeeze_events(mutated,"2026-07-01","BTCUSDT",
                                      self.manifest["fixed_parameters"])
        self.assertEqual(
          [{k:v for k,v in e.items() if k!="bars"} for e in first if e["signal_i"]==t],
          [{k:v for k,v in e.items() if k!="bars"} for e in changed if e["signal_i"]==t])

    def test_stop_first_in_same_candle(self):
        first=a.find_events(self.series,"2026-07-01","BTCUSDT",self.manifest["fixed_parameters"])[0]
        index=first["signal_i"]+1
        row=list(self.series[index])
        stop=max(first["signal_high"],row[1]+1.25*first["atr"])
        target=row[1]-1.8*(stop-row[1])
        row[2]=stop*1.01
        row[3]=target*.99
        modified=list(self.series);modified[index]=tuple(row)
        event=dict(first,bars=modified)
        x=a.predict_fill(event,200.,self.manifest["fixed_parameters"])
        y=b.fill(event,200.)
        self.assertEqual(x["reason"],"STOP_FIRST")
        b.assert_equal(x,y)

    def test_independent_execution_and_bankroll_on_two_symbols(self):
        data={("2026-07-01",s):self.series for s in ("BTCUSDT","ETHUSDT")}
        for mode in a.CANDIDATES:
            x=a.book(data,self.manifest,mode,aux=False)
            y=b.simulate(data,mode,aux=False)
            b.assert_equal(x,y)
            self.assertLessEqual(x["final_equity"],300+x["proposals"]*500)
            self.assertTrue(all(z["stop_risk_usdt"]<=5.00001 for z in x["ledger"]))
            self.assertTrue(all(z["notional"]<=500.00001 for z in x["ledger"]))
            self.assertTrue(all(z["entry_t"]>z["signal_t"] for z in x["ledger"]))

    def test_rejects_incomplete_panel(self):
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED",
                                     "AVRORA_STRUCT_SHORT_ENABLED":"YES"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_STRUCTURAL_FULL13_SHAPE"):
                a.run_evaluation({},self.manifest,"abc")

    def test_checker_rejects_modified_trade(self):
        sample=a.find_events(self.series,"2026-07-01","BTCUSDT",self.manifest["fixed_parameters"])[0]
        good=a.predict_fill(sample,200.,self.manifest["fixed_parameters"])
        altered=copy.deepcopy(good);altered["net20_usdt"]+=100.
        with self.assertRaisesRegex(ValueError,"BLOCKED_SHORT_CHECK2_VALUE"):
            b.assert_equal(good,altered)

    def test_gap_open_worse_than_stop(self):
        e=a.find_events(self.series,"2026-07-01","BTCUSDT",self.manifest["fixed_parameters"])[0]
        first=e["signal_i"]+1
        stop=max(e["signal_high"],self.series[first][1]+1.25*e["atr"])
        arr=list(self.series)
        later=first+1
        arr[later]=(arr[later][0],stop*1.01,stop*1.02,stop*1.00,stop*1.005)
        mod=dict(e,bars=arr)
        left=a.predict_fill(mod,150,self.manifest["fixed_parameters"])
        right=b.fill(mod,150)
        self.assertEqual(left["reason"],"GAP_STOP")
        self.assertLess(left["gross_usdt"],0)
        b.assert_equal(left,right)

if __name__=="__main__":unittest.main()
