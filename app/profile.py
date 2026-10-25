"""Business profile: master data an SME enters once in Mutabiq.

PINT AE requires some details that small businesses often leave off their
printed invoices (trade licence, payment means, a due date). Mutabiq fills
these from the seller's profile instead of asking the user every time.
"""
from __future__ import annotations

from datetime import timedelta

from app.models import Invoice

TERM_DAYS = {"Net 15": 15, "Net 30": 30, "Net 60": 60, "Due on receipt": 0}


def apply_profile(inv: Invoice, profile: dict) -> list[str]:
    """Fill missing seller details from the profile. Returns a list of what was filled (for the audit trail)."""
    filled = []
    if not inv.seller.trade_license and profile.get("trade_license"):
        inv.seller.trade_license = profile["trade_license"]
        filled.append("seller.trade_license")
    if not inv.iban and profile.get("iban"):
        inv.iban = profile["iban"]
        filled.append("iban")
    if inv.type_code == "380" and inv.due_date is None:
        terms = inv.payment_terms or profile.get("default_payment_terms") or "Due on receipt"
        inv.due_date = inv.issue_date + timedelta(days=TERM_DAYS.get(terms, 0))
        filled.append("due_date")
    return filled
