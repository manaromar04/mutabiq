"""Mutabiq's internal ("canonical") invoice model.

Every invoice, whatever it looked like originally (PDF, scan, Excel, Arabic
or English), is turned into this one structure. The mapping step then writes
it out as PINT AE UBL XML. Keeping one internal model means extraction,
validation and the review screen all talk about the same fields.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from pydantic import BaseModel, Field

TWO = Decimal("0.01")
EMIRATES = {"AUH": "Abu Dhabi", "DXB": "Dubai", "SHJ": "Sharjah", "AJM": "Ajman",
            "UAQ": "Umm Al Quwain", "RAK": "Ras Al Khaimah", "FUJ": "Fujairah"}


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(TWO, rounding=ROUND_HALF_UP)


class Party(BaseModel):
    legal_name: str
    trn: Optional[str] = Field(None, description="15-digit VAT Tax Registration Number")
    street: str = ""
    city: str = ""
    emirate: str = "DXB"          # PINT AE CountrySubentity code, e.g. DXB, AUH, SHJ
    country: str = "AE"
    trade_license: Optional[str] = None

    @property
    def endpoint_id(self) -> Optional[str]:
        """Peppol address in the UAE (scheme 0235) is the 10-digit TIN = first 10 digits of the TRN."""
        return self.trn[:10] if self.trn and len(self.trn) >= 10 else None


class InvoiceLine(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal = Decimal("5")
    vat_category: str = "S"       # S = standard rated, Z = zero rated, E = exempt
    unit_code: str = "H87"        # H87 = piece; C62 = unit; HUR = hour
    goods_or_services: str = "G"  # G = goods, S = services
    hs_code: Optional[str] = None # Harmonised System code, required by PINT AE for goods
    service_code: Optional[str] = None  # Service accounting code (SAC), required for services

    @property
    def net(self) -> Decimal:
        return money(self.quantity * self.unit_price)

    @property
    def vat(self) -> Decimal:
        return money(self.net * self.vat_rate / 100)


class Invoice(BaseModel):
    number: str
    issue_date: date
    due_date: Optional[date] = None
    type_code: str = "380"        # 380 = tax invoice, 381 = tax credit note
    currency: str = "AED"
    seller: Party
    buyer: Party
    lines: list[InvoiceLine]
    iban: Optional[str] = None
    payment_terms: Optional[str] = None
    original_invoice_number: Optional[str] = None   # credit notes only
    original_invoice_date: Optional[date] = None
    credit_reason_code: str = "DL8.61.1.E"          # credit notes only (PINT AE code list)
    # Totals printed on the document. Extraction fills these from what it reads;
    # if they disagree with the computed totals, that is an error to flag.
    stated_total_excl_vat: Optional[Decimal] = None
    stated_vat: Optional[Decimal] = None
    stated_total_incl_vat: Optional[Decimal] = None

    # ----- computed totals -----
    @property
    def total_excl_vat(self) -> Decimal:
        return money(sum((l.net for l in self.lines), Decimal(0)))

    @property
    def vat_breakdown(self) -> dict[tuple[str, Decimal], tuple[Decimal, Decimal]]:
        """{(category, rate): (taxable amount, VAT amount)}"""
        out: dict = {}
        for l in self.lines:
            k = (l.vat_category, l.vat_rate)
            base, _ = out.get(k, (Decimal(0), Decimal(0)))
            out[k] = (base + l.net, Decimal(0))
        return {k: (money(b), money(b * k[1] / 100)) for k, (b, _) in out.items()}

    @property
    def total_vat(self) -> Decimal:
        if self.stated_vat is not None:
            return money(self.stated_vat)
        return money(sum((v for _, v in self.vat_breakdown.values()), Decimal(0)))

    @property
    def total_incl_vat(self) -> Decimal:
        return money(self.total_excl_vat + self.total_vat)
