"""Regression checks for the existing hourly private Colab candidate bridge.

No credentials, raw historical data, Colab network calls, or private checkouts.
"""
from pathlib import Path
import re
import unittest
from tools import hourly_wave_research as research

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github"/"workflows"/"avrora-private-wave.yml"


class HourlyColabBridgeTests(unittest.TestCase):
    def test_same_hourly_workflow_not_second_scheduler(self):
        text=WORKFLOW.read_text("utf-8")
        self.assertEqual(text.count('cron: "37 * * * *"'),1)
        self.assertEqual(len(re.findall(r"(?m)^on:$",text)),1)
        self.assertIn("AVRORA_PRIVATE_WAVE_ENABLED",text)
        self.assertIn('REAL: "OFF"',text)
        self.assertIn('HOLDOUT: "SEALED"',text)
        self.assertIn("permissions:\n  contents: read",text)
        self.assertNotIn("contents: write",text)
        self.assertNotIn("drive.googleapis.com",text)
        self.assertNotIn("AVRORA_DRIVE",text)

    def test_old_wave_cache_cannot_block_new_candidate(self):
        text=WORKFLOW.read_text("utf-8")
        self.assertIn("id: research_candidate",text)
        self.assertIn("id: candidate_cache",text)
        self.assertIn("steps.research_candidate.outputs.id",text)
        self.assertIn("steps.candidate_cache.outputs.cache-hit",text)
        self.assertIn("steps.existing_proof.outputs.cache-hit != 'true' || steps.candidate_cache.outputs.cache-hit != 'true'",text)
        self.assertIn("python tools/hourly_wave_research.py run",text)
        self.assertIn("python tools/hourly_wave_research.py verify",text)
        self.assertIn("actions/upload-artifact@v4",text)
        self.assertIn("actions/cache/save@v4",text)
        self.assertIn("private_source/research/WAVE_FIB_01/private_source/*",text)
        self.assertIn("ref: 9c607da975dda64b7f50fe34004fa78e7225ff68",text)
        self.assertIn("Erase temporary credentials and private source checkout",text)
        self.assertIn("github.event_name == 'workflow_dispatch'",text)
        self.assertNotIn("pull_request_target:",text)

    def test_non_data_research_manifest_only_allows_12_immutable_ids(self):
        manifest=research.load_manifest()
        self.assertEqual([x["id"] for x in manifest["candidates"]],
                         ["FIVE_WAVE_%02d" % i for i in range(1,13)])
        altered={**manifest,"candidates":[dict(x) for x in manifest["candidates"]]}
        altered["candidates"][0]["id"]="FIVE_WAVE_01\\nRUN_MALICIOUS=true"
        with self.assertRaisesRegex(ValueError,"CANDIDATE_ID"):
            research.validate_manifest(altered)
        altered={**manifest,"candidates":list(reversed(manifest["candidates"]))}
        with self.assertRaisesRegex(ValueError,"CANDIDATE_ORDER"):
            research.validate_manifest(altered)


if __name__ == "__main__":
    unittest.main()
