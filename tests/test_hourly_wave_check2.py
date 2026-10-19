"""Independent signal+fill+portfolio parity, including deliberate corruption."""
import unittest
from tools import hourly_wave_research as a
from tools import hourly_wave_check2 as b


def synthetic_five_wave():
    knots=[(0,120),(10,100),(20,110),(30,105),(40,125),
           (50,115),(60,135),(61,132),(62,131),(63,138),
           (65,142),(80,142),(90,140)]
    series=[]
    for minute in range(95):
        value=140.0
        for (x0,y0),(x1,y1) in zip(knots,knots[1:]):
            if x0<=minute<=x1:
                value=y0+(y1-y0)*(minute-x0)/(x1-x0)
                break
        v=100+0.25*(value-100)
        series.append((minute*900000,v,v+0.05,v-0.05,v))
    return series


class WaveCheck2Test(unittest.TestCase):
    def setUp(self):
        self.params=a.load_manifest()["candidates"][0]
        self.bars=synthetic_five_wave()

    def test_all_signals_match_on_causal_synthetic_series(self):
        main=a.signals(self.bars,self.params)
        independent=b.independent_signals(self.bars,self.params)
        self.assertGreater(len(main),0)
        b.same_fields(main,independent,"synthetic")
        mutated=[dict(x) for x in main]
        mutated[0]["entry_i"]+=1
        with self.assertRaisesRegex(ValueError,"CHECK2_VALUE"):
            b.same_fields(mutated,independent,"tamper")

    def test_independent_fill_and_candle_collision(self):
        signals=a.signals(self.bars,self.params)
        self.assertTrue(signals)
        primary=a.simulate_one(self.bars,signals[0],self.params)
        reference=b.independent_fill(self.bars,signals[0],self.params)
        self.assertIsNotNone(primary)
        b.same_fields([primary],[reference],"fill")
        altered=dict(primary,net20=primary["net20"]+0.1)
        with self.assertRaisesRegex(ValueError,"CHECK2_VALUE"):
            b.same_fields([altered],[reference],"fee_corruption")

    def test_full_portfolio_ledger(self):
        series={("may_2026","BTCUSDT"):self.bars}
        proposals=[(s["signal_t"],"BTCUSDT","may_2026",self.bars,s)
                   for s in a.signals(self.bars,self.params)]
        proposals.sort(key=lambda p:(p[0],p[1],p[2]))
        ledger=[]
        for _,symbol,period,bars,signal in proposals:
            candidate=a.simulate_one(bars,signal,self.params)
            if candidate is None:
                continue
            occupied=[trade for trade in ledger if trade["entry_t"]<=candidate["entry_t"]<=trade["exit_t"]]
            if len(occupied)>=2 or any(trade["symbol"]==symbol for trade in occupied):
                continue
            ledger.append({**candidate,"symbol":symbol,"period":period})
        self.assertGreater(len(ledger),0)
        check=b.verify_all(series,self.params,proposals,ledger)
        self.assertEqual(check["check2"],"PASS_FULL_SIGNAL_AND_LEDGER_PARITY")
        corrupt=[dict(x) for x in ledger]
        corrupt[0]["reason"]="INVENTED_FILL"
        with self.assertRaisesRegex(ValueError,"CHECK2_VALUE"):
            b.verify_all(series,self.params,proposals,corrupt)
        altered=[(p[0],p[1],p[2],p[3],dict(p[4])) for p in proposals]
        altered[0][4]["pivot5_confirm_i"]+=1
        with self.assertRaisesRegex(ValueError,"CHECK2_VALUE"):
            b.verify_all(series,self.params,altered,ledger)

    def test_no_future_dependency_before_confirmation(self):
        short=self.bars[:64]
        self.assertEqual([s for s in a.signals(self.bars,self.params) if s["signal_i"]<=62],
                         [s for s in a.signals(short,self.params) if s["signal_i"]<=62])
        self.assertEqual([s for s in b.independent_signals(self.bars,self.params) if s["signal_i"]<=62],
                         [s for s in b.independent_signals(short,self.params) if s["signal_i"]<=62])


if __name__=="__main__":
    unittest.main()
