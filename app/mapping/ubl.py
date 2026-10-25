"""Maps a canonical Invoice to PINT AE 1.0.4 UBL 2.1 XML.

The element order and structure follow the official example
"Standard invoice Mandatory fields.xml" shipped with PINT AE 1.0.4.
Comments give the PINT business term (ibt-/btae-) each element carries.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from lxml import etree

from app.models import Invoice, Party, money

NS = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
CN_NS = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
CUSTOMIZATION_ID = "urn:peppol:pint:billing-1@ae-1"
PROFILE_ID = "urn:peppol:bis:billing"


def _q(prefix, tag):
    return f"{{{NS[prefix]}}}{tag}"


def _sub(parent, prefix, tag, text=None, **attrs):
    el = etree.SubElement(parent, _q(prefix, tag), **{k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def _amt(parent, tag, value, currency):
    return _sub(parent, "cbc", tag, f"{money(value):.2f}", currencyID=currency)


def _party(parent, wrapper, p: Party):
    party = _sub(_sub(parent, "cac", wrapper), "cac", "Party")
    if p.endpoint_id:
        _sub(party, "cbc", "EndpointID", p.endpoint_id, schemeID="0235")          # ibt-034 / ibt-049
    addr = _sub(party, "cac", "PostalAddress")
    if p.street:
        _sub(addr, "cbc", "StreetName", p.street)
    if p.city:
        _sub(addr, "cbc", "CityName", p.city)
    if p.emirate:
        _sub(addr, "cbc", "CountrySubentity", p.emirate)
    _sub(_sub(addr, "cac", "Country"), "cbc", "IdentificationCode", p.country)
    if p.trn is not None:
        pts = _sub(party, "cac", "PartyTaxScheme")
        _sub(pts, "cbc", "CompanyID", p.trn)                                       # ibt-031 / ibt-048
        _sub(_sub(pts, "cac", "TaxScheme"), "cbc", "ID", "VAT")
    ple = _sub(party, "cac", "PartyLegalEntity")
    if p.legal_name:
        _sub(ple, "cbc", "RegistrationName", p.legal_name)                         # ibt-027 / ibt-044
    if p.trade_license:
        _sub(ple, "cbc", "CompanyID", p.trade_license, schemeAgencyID="TL",
             schemeAgencyName="Trade License issuing Authority")                    # btae-15 / btae-16


def to_ubl(inv: Invoice) -> bytes:
    is_cn = inv.type_code == "381"
    nsmap = dict(NS)
    if is_cn:
        nsmap[None] = CN_NS
    root_tag = f"{{{nsmap[None]}}}{'CreditNote' if is_cn else 'Invoice'}"
    root = etree.Element(root_tag, nsmap=nsmap)
    cur = inv.currency

    _sub(root, "cbc", "CustomizationID", CUSTOMIZATION_ID)                         # ibt-024
    _sub(root, "cbc", "ProfileID", PROFILE_ID)                                     # ibt-023
    _sub(root, "cbc", "ProfileExecutionID", "00000000")                            # btae-02 transaction type flags
    _sub(root, "cbc", "ID", inv.number)                                            # ibt-001
    _sub(root, "cbc", "UUID", str(uuid.uuid5(uuid.NAMESPACE_URL, f"{inv.seller.trn}/{inv.number}")))  # btae-07
    _sub(root, "cbc", "IssueDate", inv.issue_date.isoformat())                     # ibt-002
    if inv.due_date and not is_cn:
        _sub(root, "cbc", "DueDate", inv.due_date.isoformat())                     # ibt-009
    _sub(root, "cbc", "CreditNoteTypeCode" if is_cn else "InvoiceTypeCode", inv.type_code)  # ibt-003
    _sub(root, "cbc", "DocumentCurrencyCode", cur)                                 # ibt-005
    if is_cn:
        dr = _sub(root, "cac", "DiscrepancyResponse")
        _sub(dr, "cbc", "ResponseCode", inv.credit_reason_code)                    # btae-03 credit note reason
    if is_cn and inv.original_invoice_number:
        ref = _sub(_sub(root, "cac", "BillingReference"), "cac", "InvoiceDocumentReference")
        _sub(ref, "cbc", "ID", inv.original_invoice_number)                        # ibt-025
        if inv.original_invoice_date:
            _sub(ref, "cbc", "IssueDate", inv.original_invoice_date.isoformat())   # ibt-026

    _party(root, "AccountingSupplierParty", inv.seller)
    _party(root, "AccountingCustomerParty", inv.buyer)

    if inv.iban:
        pm = _sub(root, "cac", "PaymentMeans")
        _sub(pm, "cbc", "PaymentMeansCode", "30", name="Credit transfer")         # ibt-081
        _sub(_sub(pm, "cac", "PayeeFinancialAccount"), "cbc", "ID", inv.iban)     # ibt-084
    if inv.payment_terms:
        _sub(_sub(root, "cac", "PaymentTerms"), "cbc", "Note", inv.payment_terms)  # ibt-020

    # ----- VAT breakdown (ibg-23) -----
    breakdown = inv.vat_breakdown
    tt = _sub(root, "cac", "TaxTotal")
    _amt(tt, "TaxAmount", inv.total_vat, cur)                                      # ibt-110
    _sub(tt, "cbc", "TaxIncludedIndicator", "false")
    for (cat, rate), (base, vat) in breakdown.items():
        if inv.stated_vat is not None and len(breakdown) == 1:
            vat = money(inv.stated_vat)  # keep what the document said, so wrong VAT is caught by the rules
        st = _sub(tt, "cac", "TaxSubtotal")
        _amt(st, "TaxableAmount", base, cur)                                       # ibt-116
        _amt(st, "TaxAmount", vat, cur)                                            # ibt-117
        tc = _sub(st, "cac", "TaxCategory")
        _sub(tc, "cbc", "ID", cat)                                                 # ibt-118
        _sub(tc, "cbc", "Percent", f"{rate.normalize():f}")                        # ibt-119
        _sub(_sub(tc, "cac", "TaxScheme"), "cbc", "ID", "VAT")

    # ----- document totals (ibg-22) -----
    lmt = _sub(root, "cac", "LegalMonetaryTotal")
    excl = inv.stated_total_excl_vat if inv.stated_total_excl_vat is not None else inv.total_excl_vat
    incl = inv.stated_total_incl_vat if inv.stated_total_incl_vat is not None else inv.total_incl_vat
    _amt(lmt, "LineExtensionAmount", inv.total_excl_vat, cur)                      # ibt-106
    _amt(lmt, "TaxExclusiveAmount", excl, cur)                                     # ibt-109
    _amt(lmt, "TaxInclusiveAmount", incl, cur)                                     # ibt-112
    _amt(lmt, "PayableAmount", incl, cur)                                          # ibt-115

    # ----- lines (ibg-25) -----
    for i, l in enumerate(inv.lines, 1):
        ln = _sub(root, "cac", "CreditNoteLine" if is_cn else "InvoiceLine")
        _sub(ln, "cbc", "ID", i)                                                   # ibt-126
        _sub(ln, "cbc", "CreditedQuantity" if is_cn else "InvoicedQuantity",
             f"{Decimal(l.quantity).normalize():f}", unitCode=l.unit_code)        # ibt-129/130
        _amt(ln, "LineExtensionAmount", l.net, cur)                                # ibt-131
        item = _sub(ln, "cac", "Item")
        _sub(item, "cbc", "Description", l.description)                            # ibt-154
        _sub(item, "cbc", "Name", l.description[:100])                             # ibt-153
        if l.goods_or_services == "S":
            aii = _sub(item, "cac", "AdditionalItemIdentification")
            _sub(aii, "cbc", "ID", l.service_code or "999999", schemeID="SAC")     # btae-17 service accounting code
        cc = _sub(item, "cac", "CommodityClassification")
        _sub(cc, "cbc", "CommodityCode", l.goods_or_services)                      # btae-13 goods/services
        if l.goods_or_services == "G":
            _sub(cc, "cbc", "ItemClassificationCode", l.hs_code or "999999", listID="HS")  # ibt-158
        ctc = _sub(item, "cac", "ClassifiedTaxCategory")
        _sub(ctc, "cbc", "ID", l.vat_category)                                     # ibt-151
        _sub(ctc, "cbc", "Percent", f"{l.vat_rate.normalize():f}")                 # ibt-152
        _sub(_sub(ctc, "cac", "TaxScheme"), "cbc", "ID", "VAT")
        price = _sub(ln, "cac", "Price")
        _amt(price, "PriceAmount", l.unit_price, cur)                              # ibt-146
        _sub(price, "cbc", "BaseQuantity", "1", unitCode=l.unit_code)              # ibt-149
        ac = _sub(price, "cac", "AllowanceCharge")
        _sub(ac, "cbc", "ChargeIndicator", "false")
        _amt(ac, "Amount", 0, cur)                                                 # ibt-147 price discount
        _amt(ac, "BaseAmount", l.unit_price, cur)                                  # ibt-148 gross price
        ext = _sub(ln, "cac", "ItemPriceExtension")
        _amt(ext, "Amount", l.net + l.vat, cur)                                    # btae-10 line amount incl. VAT
        _amt(_sub(ext, "cac", "TaxTotal"), "TaxAmount", l.vat, cur)                # btae-08 line VAT

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
