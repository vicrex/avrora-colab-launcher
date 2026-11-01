"""Adversarial offline provenance tests; no network, no live trading."""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools import avrora_public_market_firstseen_probe as producer
from tools import avrora_firstseen_check2 as verifier


def frame(topic,data,**fields):
    return json.dumps({"topic":topic,"data":data,**fields},separators=(",",":"))


def fake_capture(root):
    root=Path(root)
    obj=producer.Probe(root/"source.gz")
    wall=1793527200000;mono=1000000
    for sym in producer.SYMBOLS:
        obj.ingest(frame("publicTrade."+sym,[{
            "s":sym,"S":"Buy","i":"event-"+sym,"p":"1","v":"1",
            "T":wall-1,"seq":11}]),wall,mono)
        wall+=1;mono+=1000
        obj.ingest(frame("orderbook.50."+sym,{
            "s":sym,"b":[["1","1"]],"a":[["2","1"]],"u":100,"seq":101},
            type="snapshot",cts=wall-1),wall,mono)
        wall+=1;mono+=1000
        obj.ingest(frame("orderbook.50."+sym,{
            "s":sym,"b":[],"a":[],"u":104,"seq":108},
            type="delta",cts=wall-1),wall,mono)
        wall+=1;mono+=1000
    receipt=obj.receipt()
    receipt["accepted_subscribe_acks"]=2  # ACKs are not in original gzip.
    receipt["receipt_sha256"]=hashlib.sha256(producer.canonical({
        k:v for k,v in receipt.items() if k!="receipt_sha256"})).hexdigest()
    (root/"receipt.json").write_bytes(producer.canonical(receipt)+b"\n")
    return root/"source.gz",root/"receipt.json"


class RawCheck2Tests(unittest.TestCase):
    def test_independent_replay_exact_6symbol_raw_parity_without_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw,receipt=fake_capture(tmp)
            out=verifier.check(raw,receipt)
            self.assertEqual(out["captured_market_frames"],18)
            self.assertEqual(out["book_update_id_jumps_not_gaps"],6)
            self.assertEqual(out["book_update_uncertainties"],0)
            self.assertFalse(out["subscription_acks_independently_replayed"])
            self.assertFalse(out["maker_fills_proven"])
            self.assertFalse(out["economic_net_profit_proven"])
            self.assertEqual(out,verifier.check(raw,receipt))

    def test_modified_receipt_rejected_even_when_reforged(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw,receipt=fake_capture(tmp)
            d=json.loads(receipt.read_bytes())
            d["observed_unique_trades"]["BTCUSDT"]=999
            d["receipt_sha256"]=hashlib.sha256(producer.canonical({
                k:v for k,v in d.items() if k!="receipt_sha256"})).hexdigest()
            receipt.write_bytes(producer.canonical(d)+b"\n")
            with self.assertRaisesRegex(ValueError,"SOURCE_RECEIPT_PARITY"):
                verifier.check(raw,receipt)

    def test_tampered_raw_source_digest_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw,receipt=fake_capture(tmp)
            raw.write_bytes(raw.read_bytes()+b"x")
            with self.assertRaisesRegex(ValueError,"COMPRESSED_SHA"):
                verifier.check(raw,receipt)

    def test_false_profit_or_firstseen_completeness_claim_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw,receipt=fake_capture(tmp)
            d=json.loads(receipt.read_bytes())
            d["maker_queue_priority_proven"]=True
            d["receipt_sha256"]=hashlib.sha256(producer.canonical({
                k:v for k,v in d.items() if k!="receipt_sha256"})).hexdigest()
            receipt.write_bytes(producer.canonical(d)+b"\n")
            with self.assertRaisesRegex(ValueError,"RESEARCH_SCOPE"):
                verifier.check(raw,receipt)

if __name__=="__main__":
    unittest.main()
