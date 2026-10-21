"""Fail-closed public prereg -> execution-readiness handoff.

This module NEVER loads external model code, market data or Colab credentials.
It records a durable, idempotent block receipt for unreviewed hypotheses.
"""
import json
import os
import re
import sys
from pathlib import Path

from tools import public_research_ingress as ingress

REPO = "vicrex/avrora-colab-launcher"
OWNER = "vicrex"
BOT = "github-actions[bot]"
MARKER = "<!-- AVRORA_EVALUATION_GATE:"
SCHEMA = "AVRORA_EVALUATION_GATE_V1"
BLOCKED = "BLOCKED_ADAPTER_NOT_REVIEWED_NO_EXECUTION"


def issue_number(event, dispatch_number=""):
    if not isinstance(event, dict):
        raise ingress.Blocked("BLOCKED_EVENT")
    if "issue" in event:
        row = event["issue"]
        if row.get("user", {}).get("login") != OWNER:
            raise ingress.Blocked("BLOCKED_UNTRUSTED_AUTHOR")
        number = str(row.get("number", ""))
    else:
        number = str(dispatch_number)
    if not re.fullmatch(r"[1-9][0-9]{0,8}", number):
        raise ingress.Blocked("BLOCKED_ISSUE_NUMBER")
    return int(number)


def proof(issue, comments):
    """Verify the immutable prereg SHA against exactly one trusted bot receipt."""
    if issue.get("user", {}).get("login") != OWNER:
        raise ingress.Blocked("BLOCKED_UNTRUSTED_AUTHOR")
    n = issue.get("number")
    if type(n) is not int or n < 1:
        raise ingress.Blocked("BLOCKED_ISSUE_NUMBER")
    candidate = ingress.parse(issue.get("body"))
    expected = ingress.receipt(candidate, n)
    prereg = [c for c in comments
              if ingress.MARKER in (c.get("body") or "")]
    if len(prereg) != 1 or prereg[0].get("user", {}).get("login") != BOT:
        raise ingress.Blocked("BLOCKED_PREREG_NOT_VERIFIED")
    if prereg[0].get("body") != expected:
        raise ingress.Blocked("BLOCKED_PREREG_SHA_MISMATCH")
    return candidate


def gate_comment(candidate, n):
    """Only an immutable blocked receipt; execution must be a separate code review."""
    sha = ingress.digest(candidate)
    return (f"{MARKER}{sha} -->\n{SCHEMA}\n"
            f"issue: {n}\nspec_sha256: {sha}\n"
            f"status: {BLOCKED}\n"
            "adapter_review: REQUIRED\n"
            "dataset_pin: REQUIRED\n"
            "independent_check2: REQUIRED\n"
            "economic_run: NOT_RUN\n"
            "real: OFF\nholdout: SEALED\n"
            "drive_ack: NOT_DELIVERED")


def deliver(issue, comments, api):
    """Create at most one gate comment with API readback. No model execution."""
    candidate = proof(issue, comments)
    n = issue["number"]
    expected = gate_comment(candidate, n)
    prior = [c for c in comments if MARKER in (c.get("body") or "")]
    if prior:
        if len(prior) != 1 or prior[0].get("user", {}).get("login") != BOT:
            raise ingress.Blocked("BLOCKED_GATE_COMMENT_CONFLICT")
        if prior[0].get("body") != expected:
            raise ingress.Blocked("BLOCKED_GATE_SPEC_MUTATION")
        return "IDLE_GATE_ALREADY_RECORDED"
    posted = api("POST", f"/repos/{REPO}/issues/{n}/comments",
                 {"body": expected})
    cid = posted.get("id")
    if type(cid) is not int or cid < 1:
        raise ingress.Blocked("BLOCKED_GATE_COMMENT_WRITE")
    readback = api("GET", f"/repos/{REPO}/issues/comments/{cid}")
    if readback.get("body") != expected:
        raise ingress.Blocked("BLOCKED_GATE_READBACK")
    return BLOCKED


def main():
    if os.getenv("REAL", "OFF") != "OFF" or os.getenv("HOLDOUT", "SEALED") != "SEALED":
        print("AVRORA_GATE BLOCKED_UNSAFE_MODE")
        return 2
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        n = issue_number(event, os.environ.get("ISSUE_NUMBER", ""))
        issue = ingress.gh("GET", f"/repos/{REPO}/issues/{n}")
        comments = ingress.pages(f"/repos/{REPO}/issues/{n}/comments")
        outcome = deliver(issue, comments, ingress.gh)
        report = {
            "schema": SCHEMA, "issue": n,
            "spec_sha256": ingress.digest(ingress.parse(issue.get("body"))),
            "status": BLOCKED, "delivery": outcome,
            "economic_run": "NOT_RUN", "real": "OFF",
            "holdout": "SEALED", "drive_ack": "NOT_DELIVERED"
        }
        output = Path(os.environ.get("AVRORA_GATE_OUTPUT", "evaluation_gate.json"))
        output.write_text(ingress.canonical(report) + "\n", encoding="utf-8")
        print("AVRORA_GATE " + outcome)
        return 0
    except (ingress.Blocked, KeyError, ValueError, OSError):
        # Do not print potentially private issue body, headers, or token.
        print("AVRORA_GATE BLOCKED_VALIDATION_OR_DELIVERY")
        return 2


if __name__ == "__main__":
    sys.exit(main())
