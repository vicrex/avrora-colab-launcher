import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import public_research_ingress as p
from tools import public_research_review_gate as g


def candidate():
    return {
        "schema": 1, "source": "chatgpt-model-search",
        "delivery_id": "research:20261021:rescp",
        "spec": {
            "adapter": "unreviewed-model-proposal",
            "mechanism": {"model": "ResCP", "revision": "pinned-public-revision",
                          "hypothesis": "Causal H4 coverage gate", "source_url": "https://arxiv.org/abs/2510.05060"},
            "dataset": "MISSING",
            "parameters": {"horizon_bars": 4, "baseline": "rolling-quantile"},
            "real": "OFF", "holdout": "SEALED"
        }
    }


def issue(n=15, author="vicrex", body=None):
    return {"number": n, "user": {"login": author},
            "body": body or p.PREFIX + "\n" + p.canonical(candidate())}


def prereg(n=15, author=g.BOT, body=None):
    return {"id": 99, "user": {"login": author},
            "body": body or p.receipt(candidate(), n)}


class GateTests(unittest.TestCase):
    def test_valid_requires_exact_bot_sha(self):
        self.assertEqual(g.proof(issue(), [prereg()]), candidate())
        self.assertIn(p.digest(candidate()), g.gate_comment(candidate(), 15))

    def test_missing_or_forged_receipt_fail_closed(self):
        for receipt in ([], [prereg(author="vicrex")],
                        [prereg(body=p.receipt(candidate(), 16))],
                        [prereg(), prereg()]):
            with self.assertRaises(p.Blocked):
                g.proof(issue(), receipt)

    def test_edit_after_prereg_is_blocked(self):
        x = candidate()
        x["spec"]["parameters"]["horizon_bars"] = 8
        edited = issue(body=p.PREFIX + "\n" + p.canonical(x))
        with self.assertRaisesRegex(p.Blocked, "SHA_MISMATCH"):
            g.proof(edited, [prereg()])

    def test_unsafe_or_external_candidate_cannot_route(self):
        with self.assertRaisesRegex(p.Blocked, "AUTHOR"):
            g.proof(issue(author="external"), [prereg()])
        x = candidate()
        x["spec"]["adapter"] = "command-executor"
        with self.assertRaises(p.Blocked):
            g.proof(issue(body=p.PREFIX + "\n" + p.canonical(x)), [prereg()])

    def test_idempotent_durable_gate_receipt(self):
        c = [prereg()]
        writes = []

        def api(method, path, payload=None):
            if method == "POST":
                writes.append(payload)
                row = {"id": 100, "body": payload["body"], "user": {"login": g.BOT}}
                c.append(row)
                return row
            return c[1]

        self.assertEqual(g.deliver(issue(), c, api), g.BLOCKED)
        self.assertEqual(g.deliver(issue(), c, api), "IDLE_GATE_ALREADY_RECORDED")
        self.assertEqual(len(writes), 1)
        self.assertIn("economic_run: NOT_RUN", writes[0]["body"])
        self.assertIn("adapter_review: REQUIRED", writes[0]["body"])

    def test_gate_tamper_and_readback_fail_closed(self):
        bad = {"body": g.gate_comment(candidate(), 15) + "\ntamper",
               "user": {"login": g.BOT}}
        with self.assertRaisesRegex(p.Blocked, "GATE_SPEC_MUTATION"):
            g.deliver(issue(), [prereg(), bad], lambda *args: None)
        with self.assertRaisesRegex(p.Blocked, "GATE_READBACK"):
            g.deliver(issue(), [prereg()],
                      lambda method, path, payload=None: {"id": 200, "body": "wrong"})

    def test_rejects_untrusted_event(self):
        with self.assertRaisesRegex(p.Blocked, "UNTRUSTED"):
            g.issue_number({"issue": issue(author="bad")})
        with self.assertRaisesRegex(p.Blocked, "ISSUE_NUMBER"):
            g.issue_number({}, "../../secrets")
        self.assertEqual(g.issue_number({"issue": issue()}), 15)

    def test_main_smoke_with_mocked_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            evt = Path(tmp) / "event.json"
            out = Path(tmp) / "gate.json"
            evt.write_text(json.dumps({"issue": issue()}))
            comments = [prereg()]
            def api(method, path, payload=None):
                if method == "POST":
                    row = {"id": 300, "body": payload["body"], "user": {"login": g.BOT}}
                    comments.append(row)
                    return row
                if path.endswith("/comments/300"):
                    return comments[-1]
                return issue()
            with patch.dict(os.environ, {
                "GITHUB_EVENT_PATH": str(evt), "GH_TOKEN": "test", "REAL": "OFF",
                "HOLDOUT": "SEALED", "AVRORA_GATE_OUTPUT": str(out)}):
                with patch.object(g.ingress, "gh", side_effect=api):
                    with patch.object(g.ingress, "pages", side_effect=lambda path: comments):
                        self.assertEqual(g.main(), 0)
                        report = json.loads(out.read_text())
                        self.assertEqual(report["status"], g.BLOCKED)
                        self.assertEqual(report["economic_run"], "NOT_RUN")
                        self.assertEqual(g.main(), 0)
                        self.assertEqual(len(comments), 2)

    def test_unsafe_mode_rejected(self):
        with patch.dict(os.environ, {"REAL": "ON"}):
            self.assertEqual(g.main(), 2)


if __name__ == "__main__":
    unittest.main()
