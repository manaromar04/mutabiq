"""Tests for the XML generator and the official PINT AE validation.

Run with:  pytest -q
"""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from app.mapping.ubl import to_ubl
from app.models import Invoice, InvoiceLine, Party
from app.validation.schematron import RULES_DIR, is_valid, validate_xml


def sample_invoice(**changes) -> Invoice:
    seller = Party(legal_name="Al Noor Trading LLC", trn="100234567800003", street="Sheikh Zayed Road",
                   city="Dubai", emirate="DXB", trade_license="CN-1234567")
    buyer = Party(legal_name="مؤسسة الريان للتجارة", trn="100456789000003", street="Al Wahda Street",
                  city="Sharjah", emirate="SHJ")
    inv = Invoice(
        number="INV-2026-0001", issue_date=date(2026, 10, 12), due_date=date(2026, 11, 11),
        seller=seller, buyer=buyer, iban="AE070331234567890123456", payment_terms="Net 30",
        lines=[InvoiceLine(description="A4 paper boxes", quantity=D(10), unit_price=D("45.50"), hs_code="480256"),
               InvoiceLine(description="Installation service", quantity=D(3), unit_price=D("320"),
                           goods_or_services="S", unit_code="HUR")],
    )
    return inv.model_copy(update=changes)


@pytest.mark.parametrize("path", sorted((RULES_DIR).glob("trn-*/example/*.xml")), ids=lambda p: p.name)
def test_official_examples_are_valid(path: Path):
    """Sanity check: every official example from OpenPeppol passes our validator."""
    assert is_valid(validate_xml(path.read_bytes()))


def test_generated_invoice_is_valid():
    results = validate_xml(to_ubl(sample_invoice()))
    assert is_valid(results), [r.rule_id for r in results]


def test_generated_credit_note_is_valid():
    cn = sample_invoice(number="CN-2026-0001", type_code="381", original_invoice_number="INV-2026-0001",
                        original_invoice_date=date(2026, 10, 12))
    results = validate_xml(to_ubl(cn))
    assert is_valid(results), [r.rule_id for r in results]


def test_wrong_vat_is_caught():
    results = validate_xml(to_ubl(sample_invoice(stated_vat=D("99.00"))))
    assert not is_valid(results)


def test_short_trn_is_caught():
    inv = sample_invoice()
    inv.buyer.trn = "10045678900003"  # 14 digits
    ids = [r.rule_id for r in validate_xml(to_ubl(inv))]
    assert "ibr-132-ae" in ids


def test_missing_buyer_name_is_caught():
    inv = sample_invoice()
    inv.buyer.legal_name = ""
    ids = [r.rule_id for r in validate_xml(to_ubl(inv))]
    assert "ibr-007" in ids
