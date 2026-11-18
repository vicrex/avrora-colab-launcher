#!/usr/bin/env python3
"""Safe live GitHub commit-status telemetry; independent of Actions log downloads.

Requires GITHUB_TOKEN with statuses:write in the GitHub Actions job.
Only allowlisted stage names and coarse elapsed time; never raw subprocess output.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

STAGE_NAMES = frozenset({
    "t4_gpu", "eight_gib_vram_partition", "install_hf_client",
    "model_download", "model_sha256", "pinned_model", "llama_clone",
    "cuda_configure", "cuda_build", "cuda_llama_binary", "model_inference",
    "gpu8_inference", "stopped",
})
RESULT_STATES = {"START": "pending", "PASS": "success", "FAIL": "failure",
                 "TIMEOUT": "error", "BLOCKED": "error"}


class GitHubStatusJournal:
    def __init__(self, token=None, repo=None, sha=None, run_id=None):
        self._token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
        self._repo = repo if repo is not None else os.getenv("GITHUB_REPOSITORY", "")
        self._sha = sha if sha is not None else os.getenv("GITHUB_SHA", "")
        self._run_id = run_id if run_id is not None else os.getenv("GITHUB_RUN_ID", "")
        self.enabled = bool(self._token and self._repo and self._sha)
        self.accepted = 0
        self.rejected = 0
        self.last_error = None

    def send(self, state: str, context: str, description: str) -> bool:
        if not self.enabled:
            self.rejected += 1
            self.last_error = "MISSING_GITHUB_STATUS_AUTH"
            return False
        if state not in {"pending", "success", "failure", "error"}:
            raise ValueError("INVALID_STATUS_STATE")
        if not (context == "psyai-gpu8/heartbeat" or
                context.startswith("psyai-gpu8/stage/")):
            raise ValueError("INVALID_STATUS_CONTEXT")
        if len(context) > 100:
            raise ValueError("STATUS_CONTEXT_TOO_LONG")
        payload = {"state": state, "context": context,
                   "description": description[:140]}
        if self._run_id:
            payload["target_url"] = (
                f"https://github.com/{self._repo}/actions/runs/{self._run_id}"
            )
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self._repo}/statuses/{self._sha}",
            data=json.dumps(payload, ensure_ascii=True).encode("ascii"),
            method="POST",
            headers={"Authorization": f"Bearer {self._token}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": "PSYAI-GPU8-StatusBridge",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as resp:
                good = resp.status == 201
            if not good:
                self.last_error = "STATUS_API_UNEXPECTED_RESPONSE"
                self.rejected += 1
                return False
            self.accepted += 1
            return True
        except urllib.error.HTTPError as exc:
            self.last_error = f"STATUS_API_HTTP_{exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError):
            self.last_error = "STATUS_API_TRANSPORT_ERROR"
        self.rejected += 1
        return False

    def heartbeat(self, elapsed_seconds: float, phase: str) -> bool:
        # A heartbeat confirms the CLI bridge is alive, NOT that GPU is allocated.
        safe_phase = phase if phase in STAGE_NAMES else "waiting_for_colab_output"
        elapsed_minutes = max(0, int(elapsed_seconds // 60))
        return self.send("pending", "psyai-gpu8/heartbeat",
                         f"Bridge alive {elapsed_minutes}m; phase={safe_phase}")

    def stage(self, name: str, result: str, elapsed_seconds=None) -> bool:
        if name not in STAGE_NAMES or result not in RESULT_STATES:
            raise ValueError("UNSAFE_OR_UNKNOWN_STAGE")
        duration = ""
        if isinstance(elapsed_seconds, (int, float)):
            duration = f"; {max(0, int(elapsed_seconds))}s"
        return self.send(RESULT_STATES[result],
                         f"psyai-gpu8/stage/{name}",
                         f"{name}: {result}{duration}")

    def finish(self, success: bool, reason_code: str) -> bool:
        # Never attach raw error text, URLs, or credentials to public statuses.
        safe = reason_code if (
            isinstance(reason_code, str) and len(reason_code) < 90 and
            reason_code.isupper() and
            reason_code.replace("_", "").isalnum()
        ) else "UNCLASSIFIED"
        return self.send("success" if success else "failure",
                         "psyai-gpu8/heartbeat",
                         f"GPU8 preflight: {safe}")
