"""Checks that the synthetic dataset behaves as designed:
clean invoices are valid once the seller profile is applied, and every error
meant for the official rules is caught by them."""
import json
from pathlib import Path

import pytest

from app.mapping.ubl import to_ubl
from app.models import Invoice
from app.profile import apply_profile
from app.validation.schematron import is_valid, validate_xml

DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic"
pytestmark = pytest.mark.skipif(not DATA.exists(), reason="dataset not generated")


def _docs():
    profiles = json.loads((DATA / "seller_profiles.json").read_text(encoding="utf-8"))
    for f in sorted((DATA / "ground_truth").glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        inv = Invoice(**g["invoice"])
        apply_profile(inv, profiles[inv.seller.trn])
        yield g, inv


def test_clean_invoices_are_valid():
    failures = [g["doc_id"] for g, inv in _docs() if not g["errors"] and not is_valid(validate_xml(to_ubl(inv)))]
    assert failures == []


def test_official_rule_errors_are_caught():
    official = {"vat_miscalculated", "total_mismatch", "line_total_wrong",
                "buyer_trn_short", "buyer_trn_bad_format", "buyer_trn_missing"}
    missed = [g["doc_id"] for g, inv in _docs()
              if g["errors"] and g["errors"][0]["type"] in official and is_valid(validate_xml(to_ubl(inv)))]
    assert missed == []
