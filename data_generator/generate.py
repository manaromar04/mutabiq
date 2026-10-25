"""Generates Mutabiq's synthetic bilingual invoice dataset.

    python -m data_generator.generate --out data/synthetic --seed 2026

Output:
    documents/            the invoices as PDF, JPG (scanned / photographed) or XLSX
    ground_truth/         one JSON per document: every field exactly as printed
    manifest.csv          one row per document (layout, language, variant, errors)
    injected_errors.csv   one row per planted error, with the component expected to catch it

The same seed always produces exactly the same dataset, so results are reproducible.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from app.models import Invoice, InvoiceLine, Party, money
from data_generator import catalog as C
from data_generator.degrade import photo, scan
from data_generator.render import LAYOUTS, render

N_SELLERS = 12
DOCS_PER_SELLER = 25
N_BUYERS = 40


# ------------------------------------------------------------------ parties
def make_trn(rng: random.Random) -> str:
    """Valid UAE TRN format per PINT AE rule ibr-132-ae: 15 digits, starts with 1, ends with 03."""
    return "1" + "".join(str(rng.randint(0, 9)) for _ in range(12)) + "03"


def make_iban(rng: random.Random) -> str:
    return "AE" + f"{rng.randint(10, 99)}" + "".join(str(rng.randint(0, 9)) for _ in range(19))


@dataclass
class Company:
    name_en: str
    name_ar: str
    trn: str
    emirate: str
    city_en: str
    city_ar: str
    street_en: str
    street_ar: str
    trade_license: str | None
    sells: str = "mixed"                # "goods", "services", "mixed"
    layout: int = 0
    spreadsheet: bool = False
    iban: str | None = None
    bank: str | None = None
    terms: tuple | None = None
    number_fmt: str = "INV-2026-{:04d}"
    stamp: bool = False
    print_tl: bool = True               # is the trade licence printed on the invoice?
    print_iban: bool = True             # are bank details printed on the invoice?
    next_no: int = 1
    history: list = field(default_factory=list)


def make_company(rng: random.Random, used: set) -> Company:
    while True:
        stem = rng.choice(C.NAME_STEMS)
        form = rng.choice(C.LEGAL_FORMS)
        if (stem, form) not in used:
            used.add((stem, form))
            break
    emirate = rng.choice(["DXB", "DXB", "SHJ", "AUH", "AJM", "RAK", "UAQ", "FUJ"])
    city_en, city_ar = rng.choice(C.EMIRATE_CITIES[emirate])
    street_en, street_ar = rng.choice(C.STREETS)
    sells = "services" if "Services" in form[0] or "Solutions" in form[0] else ("goods" if "Trading" in form[0] else "mixed")
    return Company(
        name_en=f"{stem[0]} {form[0]}", name_ar=form[1].format(stem[1]), trn=make_trn(rng), emirate=emirate,
        city_en=city_en, city_ar=city_ar, street_en=street_en, street_ar=street_ar,
        trade_license=rng.choice([f"CN-{rng.randint(1000000, 9999999)}", str(rng.randint(100000, 999999))]),
        sells=sells,
    )


def party_for(co: Company, lang: str) -> tuple[Party, dict]:
    primary, alt = (co.name_ar, co.name_en) if lang == "ar" else (co.name_en, co.name_ar)
    p = Party(legal_name=primary, legal_name_alt=alt if lang == "bi" else None, trn=co.trn,
              street=co.street_ar if lang == "ar" else co.street_en, city=co.city_ar if lang == "ar" else co.city_en,
              emirate=co.emirate, trade_license=co.trade_license if co.print_tl else None)
    extra = {"city_en": co.city_en, "city_ar": co.city_ar, "street_en": co.street_en, "street_ar": co.street_ar}
    return p, extra


# ------------------------------------------------------------------ invoices
def make_lines(rng: random.Random, co: Company, lang: str) -> tuple[list[InvoiceLine], list[str]]:
    pool = (C.GOODS if co.sells == "goods" else C.SERVICES if co.sells == "services" else C.GOODS + C.SERVICES)
    items = rng.sample(pool, k=min(len(pool), rng.choice([1, 2, 2, 3, 3, 4, 5, 6])))
    lines, printed = [], []
    for en, ar, code, (lo, hi), unit in items:
        is_service = (en, ar, code, (lo, hi), unit) in C.SERVICES
        qty = Decimal(rng.choice([1, 1, 2, 3, 4, 5, 6, 8, 10, 12, 20, 25, 50]) if unit not in ("TNE", "MON") else rng.choice([1, 2, 3]))
        price = money(rng.uniform(lo, hi))
        desc = ar if lang == "ar" else en
        if lang == "bi" and rng.random() < 0.5:
            desc = ar
        lines.append(InvoiceLine(description=desc, quantity=qty, unit_price=price, unit_code=unit,
                                 goods_or_services="S" if is_service else "G",
                                 hs_code=None if is_service else code, service_code=code if is_service else None))
        printed.append(desc)
    return lines, printed


def make_invoice(rng: random.Random, co: Company, buyer: Company, issue: date, credit_of: dict | None = None):
    lay = LAYOUTS[co.layout]
    lang = lay.lang
    seller_p, seller_x = party_for(co, lang)
    buyer_p, buyer_x = party_for(buyer, lang)
    if credit_of:
        src = credit_of["invoice"]
        k = rng.randint(1, len(src.lines))
        lines = [l.model_copy() for l in src.lines[:k]]
        for l in lines:
            l.quantity = Decimal(max(1, int(l.quantity) // 2))
        printed = credit_of["printed"][:k]
        number = f"CN-{co.number_fmt.format(co.next_no).split('-')[-1]}"
    else:
        lines, printed = make_lines(rng, co, lang)
        number = co.number_fmt.format(co.next_no)
    co.next_no += 1
    terms_en, terms_ar = co.terms or ("", "")
    inv = Invoice(
        number=number, issue_date=issue,
        due_date=None if credit_of or not co.terms else issue + timedelta(days={"Net 15": 15, "Net 30": 30, "Net 60": 60}.get(terms_en, 0)),
        type_code="381" if credit_of else "380", seller=seller_p, buyer=buyer_p, lines=lines,
        iban=co.iban if co.print_iban else None, payment_terms=terms_en or None,
        original_invoice_number=credit_of["invoice"].number if credit_of else None,
        original_invoice_date=credit_of["invoice"].issue_date if credit_of else None,
    )
    extra = {"seller": seller_x, "buyer": buyer_x, "line_desc": printed, "bank": co.bank or "",
             "terms_text": {"en": terms_en, "ar": terms_ar, "bi": f"{terms_en} / {terms_ar}"}[lang], "stamp": co.stamp}
    return inv, extra


# ------------------------------------------------------------------ error injection
ERROR_TYPES = {
    # error type: component expected to catch it
    "vat_miscalculated": "official_rules",
    "total_mismatch": "official_rules",
    "line_total_wrong": "official_rules",
    "buyer_trn_short": "official_rules",
    "buyer_trn_bad_format": "official_rules",
    "buyer_trn_missing": "official_rules",
    "due_before_issue": "uae_checks",
    "unusual_amount": "anomaly_detection",
}


def inject(rng: random.Random, inv: Invoice, kind: str) -> str:
    """Change what is *printed* on the invoice so it contains a realistic mistake. Returns a short description."""
    if kind == "vat_miscalculated":
        how = rng.choice(["rate10", "on_gross", "typo"])
        excl = inv.total_excl_vat
        vat = {"rate10": excl * Decimal("0.10"), "on_gross": excl * Decimal("1.05") * Decimal("0.05"),
               "typo": inv.total_vat + Decimal(rng.choice([1, 9, 10, 90, 100]))}[how]
        inv.stated_vat = money(vat)
        inv.stated_total_excl_vat = excl
        inv.stated_total_incl_vat = money(excl + inv.stated_vat)
        return f"VAT printed as {inv.stated_vat} instead of {inv.total_vat} ({how})"
    if kind == "total_mismatch":
        inv.stated_total_incl_vat = money(inv.total_incl_vat + Decimal(rng.choice([-100, -10, 10, 50, 100])))
        return f"Total incl. VAT printed as {inv.stated_total_incl_vat} instead of {inv.total_incl_vat}"
    if kind == "line_total_wrong":
        l = rng.choice(inv.lines)
        l.stated_net = money(l.net + Decimal(rng.choice([-50, -10, 10, 20, 100])))
        inv.stated_total_excl_vat = money(sum((x.stated_net if x.stated_net is not None else x.net) for x in inv.lines))
        inv.stated_vat = inv.total_vat
        inv.stated_total_incl_vat = money(inv.stated_total_excl_vat + inv.stated_vat)
        return f"Line '{l.description[:30]}' total printed as {l.stated_net} instead of {l.net}"
    if kind == "buyer_trn_short":
        old = inv.buyer.trn
        pos = rng.randint(1, 12)
        inv.buyer.trn = old[:pos] + old[pos + 1:]
        return f"Buyer TRN printed with 14 digits ({inv.buyer.trn})"
    if kind == "buyer_trn_bad_format":
        old = inv.buyer.trn
        inv.buyer.trn = old[:-2] + rng.choice(["01", "07", "30", "00"])
        return f"Buyer TRN does not end in 03 ({inv.buyer.trn})"
    if kind == "buyer_trn_missing":
        inv.buyer.trn = None
        return "Buyer TRN not printed"
    if kind == "due_before_issue":
        inv.due_date = inv.issue_date - timedelta(days=rng.randint(3, 30))
        return f"Due date {inv.due_date} is before issue date {inv.issue_date}"
    if kind == "unusual_amount":
        l = max(inv.lines, key=lambda x: x.net)
        l.quantity = l.quantity * rng.choice([15, 20, 30])
        return f"Quantity of '{l.description[:30]}' inflated to {l.quantity}"
    raise ValueError(kind)


# ------------------------------------------------------------------ spreadsheet output
def write_xlsx(inv: Invoice, extra: dict, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice"
    ws["A1"] = "TAX INVOICE" if inv.type_code == "380" else "TAX CREDIT NOTE"
    ws["A1"].font = Font(bold=True, size=14)
    rows = [("Seller", inv.seller.legal_name), ("Seller TRN", inv.seller.trn), ("Invoice No.", inv.number),
            ("Date", inv.issue_date.strftime("%d/%m/%Y")), ("Customer", inv.buyer.legal_name),
            ("Customer TRN", inv.buyer.trn or ""), ("Customer address", f"{extra['buyer']['street_en']}, {extra['buyer']['city_en']}")]
    if inv.due_date:
        rows.append(("Due date", inv.due_date.strftime("%d/%m/%Y")))
    for i, (k, v) in enumerate(rows, 3):
        ws.cell(i, 1, k).font = Font(bold=True)
        ws.cell(i, 2, v)
    r = len(rows) + 4
    for j, h in enumerate(["#", "Description", "Qty", "Unit price", "Amount"], 1):
        ws.cell(r, j, h).font = Font(bold=True)
    for i, (l, desc) in enumerate(zip(inv.lines, extra["line_desc"]), 1):
        net = l.stated_net if l.stated_net is not None else l.net
        for j, v in enumerate([i, desc, float(l.quantity), float(l.unit_price), float(net)], 1):
            ws.cell(r + i, j, v)
    r += len(inv.lines) + 2
    excl = inv.stated_total_excl_vat if inv.stated_total_excl_vat is not None else inv.total_excl_vat
    vat = inv.stated_vat if inv.stated_vat is not None else inv.total_vat
    incl = inv.stated_total_incl_vat if inv.stated_total_incl_vat is not None else excl + vat
    for k, v in (("Total excl. VAT", excl), ("VAT 5%", vat), ("Total incl. VAT", incl)):
        ws.cell(r, 4, k).font = Font(bold=True)
        ws.cell(r, 5, float(v))
        r += 1
    ws.column_dimensions["B"].width = 42
    wb.save(path)


# ------------------------------------------------------------------ main
def main(out: Path, seed: int) -> None:
    rng = random.Random(seed)
    if out.exists():
        shutil.rmtree(out)
    (out / "documents").mkdir(parents=True)
    (out / "ground_truth").mkdir()

    used: set = set()
    sellers = [make_company(rng, used) for _ in range(N_SELLERS)]
    buyers = [make_company(rng, used) for _ in range(N_BUYERS)]
    fmts = ["INV-2026-{:04d}", "TI/26/{:03d}", "{:05d}", "AE-INV-{:04d}", "S{:04d}", "INV{:04d}"]
    for i, s in enumerate(sellers):
        s.layout = i % len(LAYOUTS)
        s.spreadsheet = i == N_SELLERS - 1            # one seller invoices from Excel
        s.iban = make_iban(rng)
        s.print_iban = rng.random() < 0.8
        s.print_tl = rng.random() < 0.6
        s.bank = rng.choice(C.BANKS)
        s.terms = rng.choice(C.PAYMENT_TERMS) if rng.random() < 0.85 else None
        s.number_fmt = fmts[i % len(fmts)]
        s.next_no = rng.randint(1, 400)
        s.stamp = rng.random() < 0.5
        s.customers = rng.sample(buyers, 6)

    # decide which documents get an error: about 30% of invoices, spread over error types
    total_docs = N_SELLERS * DOCS_PER_SELLER
    error_plan = list(ERROR_TYPES) * 9            # 8 types x 9 = 72 planted errors
    error_plan += [None] * (total_docs - len(error_plan))
    rng.shuffle(error_plan)

    # The business profile: master data each SME enters once in Mutabiq. Some of it
    # (trade licence, bank account, default payment terms) is often missing from the
    # printed invoice but is mandatory in PINT AE, so Mutabiq fills it from the profile.
    profiles = {s.trn: {"legal_name_en": s.name_en, "legal_name_ar": s.name_ar, "trn": s.trn,
                        "trade_license": s.trade_license, "iban": s.iban, "bank": s.bank, "emirate": s.emirate,
                        "default_payment_terms": (s.terms or ("Due on receipt", ""))[0]} for s in sellers}
    (out / "seller_profiles.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest, errors = [], []
    doc_i = 0

    def emit(inv, extra, s, variant, err_kind, err_desc, duplicate_of=None):
        nonlocal doc_i
        doc_i += 1
        doc_id = f"doc_{doc_i:04d}"
        lay = LAYOUTS[s.layout]
        ext = {"pdf": ".pdf", "scan": ".jpg", "photo": ".jpg", "xlsx": ".xlsx"}[variant]
        path = out / "documents" / f"{doc_id}{ext}"
        deg = {}
        if variant == "xlsx":
            write_xlsx(inv, extra, path)
        else:
            pdf = path if variant == "pdf" else out / f"_{doc_id}.pdf"
            render(inv, extra, lay, pdf)
            if variant != "pdf":
                deg = (scan if variant == "scan" else photo)(pdf, path, rng)
                pdf.unlink()
        gt = {"doc_id": doc_id, "file": path.name, "layout": "spreadsheet" if variant == "xlsx" else lay.name,
              "language": "en" if variant == "xlsx" else lay.lang, "variant": variant, "degradation": deg,
              "duplicate_of": duplicate_of, "errors": [{"type": err_kind, "description": err_desc}] if err_kind else [],
              "invoice": json.loads(inv.model_dump_json())}
        (out / "ground_truth" / f"{doc_id}.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append({"doc_id": doc_id, "file": path.name, "seller": s.name_en, "layout": gt["layout"],
                         "language": gt["language"], "variant": variant, "type_code": inv.type_code,
                         "invoice_number": inv.number, "lines": len(inv.lines), "error": err_kind or "",
                         "duplicate_of": duplicate_of or ""})
        if err_kind:
            errors.append({"doc_id": doc_id, "error_type": err_kind, "expected_detector": ERROR_TYPES.get(err_kind, "anomaly_detection"),
                           "description": err_desc})
        return doc_id

    issued = []  # (doc_id, invoice, extra, seller)
    k = 0
    for s in sellers:
        day = date(2026, 1, 5) + timedelta(days=rng.randint(0, 20))
        for _ in range(DOCS_PER_SELLER):
            day += timedelta(days=rng.randint(3, 12))
            buyer = rng.choice(s.customers)
            credit_src = None
            if issued and rng.random() < 0.06:
                own = [x for x in issued if x[3] is s and x[1].type_code == "380"]
                if own:
                    src = rng.choice(own)
                    credit_src = {"invoice": src[1], "printed": src[2]["line_desc"]}
                    buyer = next((b for b in buyers if b.trn == src[1].buyer.trn), buyer)
            inv, extra = make_invoice(rng, s, buyer, min(day, date(2026, 10, 20)), credit_src)
            kind = error_plan[k]
            k += 1
            if credit_src and kind in ("unusual_amount", "due_before_issue"):
                kind = None
            desc = inject(rng, inv, kind) if kind else None
            variant = "xlsx" if s.spreadsheet else rng.choices(["pdf", "scan", "photo"], [55, 30, 15])[0]
            doc_id = emit(inv, extra, s, variant, kind, desc)
            issued.append((doc_id, inv, extra, s))

    # duplicates: the same invoice uploaded twice (e.g. once as PDF, once as a phone photo)
    for doc_id, inv, extra, s in rng.sample([x for x in issued if not manifest[int(x[0][4:]) - 1]["error"] and x[1].type_code == "380"], 12):
        variant = "xlsx" if s.spreadsheet else rng.choice(["pdf", "scan", "photo"])
        emit(inv, extra, s, variant, "duplicate_invoice", f"Same invoice as {doc_id}", duplicate_of=doc_id)
    ERROR_TYPES["duplicate_invoice"] = "anomaly_detection"
    for e in errors:
        e["expected_detector"] = ERROR_TYPES[e["error_type"]]

    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0]))
        w.writeheader()
        w.writerows(manifest)
    with open(out / "injected_errors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(errors[0]))
        w.writeheader()
        w.writerows(errors)
    print(f"{len(manifest)} documents, {len(errors)} injected errors -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/synthetic"))
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    main(a.out, a.seed)
