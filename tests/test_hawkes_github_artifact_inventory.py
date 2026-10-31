"""Synthetic-only adversarial GitHub metadata inventory tests."""
from datetime import date
import unittest

from tools import hawkes_github_artifact_inventory as inv
from tools.hawkes_seven_day_archive_audit import required_days, SYMBOLS


def fake_artifacts(asof=date(2026,10,31)):
    items=[]
    for i,day in enumerate(required_days(asof)):
        for j,sym in enumerate(SYMBOLS):
            art_id=10000+i*10+j
            items.append({
                "id":art_id,
                "name":f"avrora-official-trades-{sym}-{day.isoformat()}-{41190000000+art_id}",
                "expired":False,
            })
    return {"artifacts":items,"total_count":len(items)}


class ArtifactInventoryTests(unittest.TestCase):
    ASOF=date(2026,10,31)

    def test_complete_42_metadata_is_still_not_file_proof(self):
        r=inv.inventory([fake_artifacts()],self.ASOF)
        self.assertEqual(r["status"],"METADATA_42_PRESENT_BYTES_UNVERIFIED")
        self.assertEqual(r["found_symbol_day_pairs_with_unexpired_artifacts"],42)
        self.assertEqual(r["missing_symbol_days"],[])
        self.assertFalse(r["official_gzip_bytes_sha_verified"])
        self.assertFalse(r["provider_event_completeness_proven"])
        self.assertFalse(r["individual_event_first_seen_proven"])
        self.assertFalse(r["hawkes_model_fit_ready"])
        self.assertFalse(r["independent_check2"])
        self.assertFalse(r["live_trading_authorized"])
        self.assertEqual(r["real"],"OFF")
        self.assertEqual(r["holdout"],"SEALED")
        self.assertEqual(r["receipt_sha256"],inv.sha(inv.canonical({
            k:v for k,v in r.items() if k!="receipt_sha256"})))

    def test_no_artifacts_blocks_42_pairs(self):
        r=inv.inventory([{"artifacts":[]}],self.ASOF)
        self.assertEqual(r["status"],"BLOCKED_ARCHIVE_METADATA_COVERAGE_MISSING")
        self.assertEqual(len(r["missing_symbol_days"]),42)

    def test_missing_symbol_day_does_not_get_padded(self):
        p=fake_artifacts()
        p["artifacts"].pop()
        r=inv.inventory([p],self.ASOF)
        self.assertEqual(len(r["missing_symbol_days"]),1)
        self.assertEqual(r["found_symbol_day_pairs_with_unexpired_artifacts"],41)

    def test_expired_only_does_not_count(self):
        p=fake_artifacts()
        p["artifacts"][0]["expired"]=True
        r=inv.inventory([p],self.ASOF)
        self.assertEqual(r["stale_expired_artifacts"],1)
        self.assertEqual(len(r["missing_symbol_days"]),1)

    def test_partial_pagination_never_passes_even_with_42(self):
        r=inv.inventory([fake_artifacts()],self.ASOF,complete_listing=False)
        self.assertEqual(r["status"],"BLOCKED_ARCHIVE_INVENTORY_PARTIAL_LISTING")
        self.assertFalse(r["api_listing_complete"])

    def test_duplicate_candidates_are_reported(self):
        p=fake_artifacts()
        extra=dict(p["artifacts"][0])
        extra["id"]=123456
        extra["name"]=extra["name"].rsplit("-",1)[0]+"-49999999999"
        p["artifacts"].append(extra)
        r=inv.inventory([p],self.ASOF)
        self.assertEqual(r["multiple_artifact_candidates_for_pair"],1)
        self.assertEqual(r["found_symbol_day_pairs_with_unexpired_artifacts"],42)
        self.assertFalse(r["official_gzip_bytes_sha_verified"])

    def test_fake_metadata_and_repeated_name_block(self):
        p=fake_artifacts()
        p["artifacts"][0]["id"]=True
        r=inv.inventory([p],self.ASOF)
        self.assertEqual(r["status"],"BLOCKED_ARCHIVE_INVENTORY_UNTRUSTED_METADATA")
        self.assertEqual(r["invalid_artifact_metadata"],1)
        p=fake_artifacts()
        p["artifacts"].append(dict(p["artifacts"][0]))
        r=inv.inventory([p],self.ASOF)
        self.assertEqual(r["invalid_artifact_metadata"],1)

    def test_wrong_symbol_or_date_is_not_an_archive(self):
        p=fake_artifacts()
        p["artifacts"][-1]["name"]="avrora-official-trades-DOGEUSDT-2026-10-30-41190000001"
        r=inv.inventory([p],self.ASOF)
        self.assertEqual(len(r["missing_symbol_days"]),1)

    def test_invalid_provider_page_blocks(self):
        for page in ({"wrong":[]}, {"artifacts":[1]}, {"artifacts":None}):
            with self.subTest(page=page),self.assertRaisesRegex(
                    ValueError,"API_SCHEMA|ITEM_SCHEMA"):
                inv.inventory([page],self.ASOF)

    def test_token_is_required(self):
        with self.assertRaisesRegex(ValueError,"MISSING_ACTIONS_READ_TOKEN"):
            inv.fetch_metadata("")

if __name__=="__main__":
    unittest.main()
