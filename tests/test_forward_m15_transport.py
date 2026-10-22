"""Synthetic tests for public-only M15 transport. No exchange/network calls."""
from __future__ import annotations
import json
import unittest
from tools import forward_m15_transport as m

def synthetic(missing=False,wrong_symbol=False):
    n=224
    start=1792713600000
    rows=[]
    for i in range(n):
        t=start+i*m.BAR_MS
        rows.append([str(t),"100","102","99","101","5","500"])
    if missing:
        rows.pop(25)
    now=start+(n+3)*m.BAR_MS
    return json.dumps({"retCode":0,"retMsg":"OK","time":now,
        "result":{"category":"linear","symbol":"BTCUSDT" if wrong_symbol else "SOLUSDT",
                  "list":list(reversed(rows))}}).encode(),now

class TransportTests(unittest.TestCase):
    def test_ordering_closure_hash_and_scope(self):
        raw,now=synthetic()
        csv,receipt=m.parse(raw,"SOLUSDT",now)
        self.assertTrue(csv.startswith(b"start_ms,open,high,low,close,observed_at_ms"))
        self.assertEqual(receipt["bar_count"],224)
        self.assertEqual(receipt["first_start_ms"],1792713600000)
        self.assertEqual(receipt["source_body_sha256"],m.digest(raw))
        self.assertEqual(receipt["normalized_csv_sha256"],m.digest(csv))
        self.assertEqual(receipt["forward_closed_bars"],224)
    def test_no_incomplete_or_wrong_symbol(self):
        raw,now=synthetic(wrong_symbol=True)
        with self.assertRaisesRegex(ValueError,"BLOCKED_WRONG_PUBLIC_MARKET_SOURCE"):
            m.parse(raw,"SOLUSDT",now)
        raw,now=synthetic()
        with self.assertRaisesRegex(ValueError,"BLOCKED_SOURCE_TIMESTAMP_DRIFT"):
            m.parse(raw,"SOLUSDT",now+400000)
    def test_gap_is_fail_closed(self):
        raw,now=synthetic(missing=True)
        with self.assertRaisesRegex(ValueError,"BLOCKED_CLOSED_BARS_GAP"):
            m.parse(raw,"SOLUSDT",now)
    def test_order_linked_closing_only(self):
        raw,now=synthetic()
        a=json.loads(raw)
        new=now-m.BAR_MS//2
        a["result"]["list"].insert(0,[str(new),"100","102","99","101","5","500"])
        # Partial bar has invalid grid timestamp => fail closed, not silent inclusion.
        with self.assertRaisesRegex(ValueError,"BLOCKED_INVALID_KLINE_OHLC"):
            m.parse(json.dumps(a).encode(),"SOLUSDT",now)

if __name__=="__main__":
    unittest.main()
