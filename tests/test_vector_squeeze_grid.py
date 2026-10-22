"""Offline FULL13 vector grid contracts, independent varied-parameter CHECK2."""
import copy
import math
import os
import unittest
from unittest.mock import patch

from tools import structural_short as primary
from tools import vector_squeeze_grid as grid
from tools import vector_squeeze_grid_check2 as check2

def candles(n=892,t=350):
    price=100.
    rows=[]
    for i in range(n):
        op=price
        price=op*0.9995
        rows.append((1680000000000+i*900000,op,max(op,price)*1.001,
                     min(op,price)*0.999,price))
    for i in range(t-16,t-8):
        ts,op,hi,lo,cl=rows[i]
        rows[i]=(ts,op,max(hi,cl*1.008),min(lo,cl*0.992),cl)
    flat=rows[t-9][4]
    for i in range(t-8,t):
        ts,op,hi,lo,cl=rows[i]
        rows[i]=(ts,flat,flat*1.0004,flat*.9996,flat)
    ts,op,hi,lo,cl=rows[t]
    rows[t]=(ts,flat,flat*1.001,flat*.987,flat*.988)
    return rows

class VectorGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid,cls.sha=grid.load_grid()
        cls.manifest,_=primary.load_manifest()

    def test_registered_twelve_identities_and_batch_limits(self):
        self.assertEqual(len(self.grid["candidates"]),12)
        self.assertEqual(len({grid.sha(grid.canon(x).encode())
                              for x in self.grid["candidates"]}),12)
        self.assertEqual(grid.BATCH_SIZE,4)
        self.assertEqual(grid.MAX_BATCHES,3)
        for entry in self.grid["candidates"]:
            p=grid.params_for(entry,self.manifest["fixed_parameters"])
            self.assertEqual(p["squeeze_max_range_ratio"],entry["range_ratio"])
            self.assertEqual(p["break_atr"],entry["break_atr"])
            self.assertEqual(p["body_atr"],entry["body_atr"])
            self.assertEqual(p["max_notional"],500)
            self.assertEqual(p["start_equity_usdt"],300)

    def test_independent_all_twelve_signal_vectors(self):
        bars=candles()
        for spec in self.grid["candidates"]:
            params=grid.params_for(spec,self.manifest["fixed_parameters"])
            a=primary.find_squeeze_events(bars,"2026-07-01","BTCUSDT",params)
            b=check2.derive_squeezes(bars,"2026-07-01","BTCUSDT",params)
            self.assertTrue(any(x["signal_i"]==350 for x in a),spec["id"])
            self.assertEqual([x["signal_i"] for x in a],
                             [x["signal_i"] for x in b],spec["id"])
            for left,right in zip(a,b):
                check2.assert_equal({k:v for k,v in left.items() if k!="bars"},
                                    {k:v for k,v in right.items() if k!="bars"},
                                    spec["id"])

    def test_full_equity_ledger_parity_for_distinct_parameters(self):
        series=candles()
        data={("2026-07-01",sym):series for sym in ("BTCUSDT","ETHUSDT")}
        for spec in (self.grid["candidates"][0],self.grid["candidates"][-1]):
            params=grid.params_for(spec,self.manifest["fixed_parameters"])
            one=primary.book(data,{"fixed_parameters":params},grid.MODE,False)
            independent=check2.simulate(data,grid.MODE,False,params)
            check2.assert_equal(one,independent,spec["id"]+"_FULL_LEDGER")
            self.assertTrue(all(x["notional"]<=500.000001
                                and x["stop_risk_usdt"]<=5.000001 for x in one["ledger"]))

    def test_future_bars_cannot_change_closed_breakout(self):
        t=350
        bars=candles()
        alt=list(bars)
        for i in range(t+2,t+8):
            ts,op,hi,lo,cl=alt[i]
            alt[i]=(ts,op,op*1.12,op*.88,op)
        for spec in self.grid["candidates"]:
            p=grid.params_for(spec,self.manifest["fixed_parameters"])
            old=primary.find_squeeze_events(bars,"2026-07-01","BTCUSDT",p)
            new=primary.find_squeeze_events(alt,"2026-07-01","BTCUSDT",p)
            left=[{k:v for k,v in x.items() if k!="bars"} for x in old
                  if x["signal_i"]==t]
            right=[{k:v for k,v in x.items() if k!="bars"} for x in new
                   if x["signal_i"]==t]
            self.assertEqual(left,right)

    def test_fail_closed_missing_full13_and_no_grid_authorization(self):
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED",
                                     "AVRORA_GRID_SHADOW_ENABLED":"YES"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_GRID_FULL13_SHAPE"):
                grid.evaluate({}, {}, self.grid, self.sha, 0)
            with self.assertRaisesRegex(ValueError,"BLOCKED_GRID_BATCH_INDEX"):
                grid.evaluate({}, {}, self.grid, self.sha, 3)
        with patch.dict(os.environ,{"REAL":"OFF","HOLDOUT":"SEALED",
                                     "AVRORA_GRID_SHADOW_ENABLED":""}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_GRID_NOT_AUTHORIZED"):
                grid.gate()
        with patch.dict(os.environ,{"REAL":"ON","HOLDOUT":"SEALED",
                                     "AVRORA_GRID_SHADOW_ENABLED":"YES"}):
            with self.assertRaisesRegex(ValueError,"BLOCKED_REAL_OR_HOLDOUT"):
                grid.gate()

if __name__=="__main__":unittest.main()
