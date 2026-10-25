"""Draws an invoice as a PDF in one of eight layouts.

Each layout imitates a different kind of SME invoice template: English-only,
Arabic-only (right-to-left), and bilingual; different fonts, table styles,
date formats and number formats (including Eastern Arabic digits).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import unicodedata
from fontTools.ttLib import TTFont as FTFont

from app.models import EMIRATES, Invoice

FONT_DIR = Path(__file__).parent / "fonts"
for fam in ("NotoNaskhArabic", "Amiri", "Cairo", "Tajawal"):
    for w in ("Regular", "Bold"):
        pdfmetrics.registerFont(TTFont(f"{fam}-{w}", str(FONT_DIR / f"{fam}-{w}.ttf")))

CMAPS = {fam: set(FTFont(str(FONT_DIR / f"{fam}-Regular.ttf")).getBestCmap())
         for fam in ("NotoNaskhArabic", "Amiri", "Cairo", "Tajawal")}


def fit_to_font(s: str, fam: str) -> str:
    """Some fonts lack the 'isolated' Arabic presentation forms. Replace those with the
    base letter, which the font draws in its isolated shape anyway."""
    cmap = CMAPS[fam]
    out = []
    for ch in s:
        if ord(ch) > 127 and ord(ch) not in cmap:
            dec = unicodedata.decomposition(ch).split()
            if len(dec) == 2 and dec[0].startswith("<") and int(dec[1], 16) in cmap:
                ch = chr(int(dec[1], 16))
        out.append(ch)
    return "".join(out)


W, H = A4
EASTERN = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

LABELS = {
    "tax_invoice": ("TAX INVOICE", "فاتورة ضريبية"),
    "credit_note": ("TAX CREDIT NOTE", "إشعار دائن ضريبي"),
    "inv_no": ("Invoice No.", "رقم الفاتورة"),
    "cn_no": ("Credit Note No.", "رقم الإشعار"),
    "date": ("Date", "التاريخ"),
    "due": ("Due Date", "تاريخ الاستحقاق"),
    "orig": ("Against Invoice", "مقابل الفاتورة"),
    "seller": ("From", "من"),
    "buyer": ("Bill To", "فاتورة إلى"),
    "trn": ("TRN", "الرقم الضريبي"),
    "tl": ("Trade License", "الرخصة التجارية"),
    "no": ("#", "م"),
    "desc": ("Description", "البيان"),
    "qty": ("Qty", "الكمية"),
    "price": ("Unit Price", "سعر الوحدة"),
    "amount": ("Amount", "المبلغ"),
    "vat_pct": ("VAT %", "الضريبة %"),
    "vat": ("VAT", "الضريبة"),
    "total": ("Total", "الإجمالي"),
    "subtotal": ("Total excl. VAT", "الإجمالي قبل الضريبة"),
    "vat_total": ("VAT 5%", "ضريبة القيمة المضافة 5%"),
    "grand": ("Total incl. VAT", "الإجمالي شامل الضريبة"),
    "terms": ("Payment terms", "شروط الدفع"),
    "bank": ("Bank", "البنك"),
    "iban": ("IBAN", "الآيبان"),
    "thanks": ("Thank you for your business.", "شكراً لتعاملكم معنا."),
    "sign": ("Authorised signature", "التوقيع المعتمد"),
}


@dataclass
class Layout:
    name: str
    lang: str            # "en", "ar" or "bi"
    font: str            # font family
    accent: str          # hex colour
    header: str          # "band", "plain", "boxed"
    parties: str         # "side" or "stack"
    table: str           # "grid", "zebra", "lines"
    line_vat: bool       # show VAT per line
    date_fmt: str        # "dmy", "iso", "long"
    digits: str          # "western" or "eastern"
    currency: str        # label printed next to amounts
    thousands: bool      # 1,234.50 vs 1234.50


LAYOUTS = [
    Layout("L1_en_band", "en", "Cairo", "#1F4E79", "band", "side", "grid", True, "dmy", "western", "AED", True),
    Layout("L2_en_plain", "en", "NotoNaskhArabic", "#333333", "plain", "stack", "lines", False, "long", "western", "AED", True),
    Layout("L3_en_boxed", "en", "Tajawal", "#7A3E00", "boxed", "side", "zebra", False, "iso", "western", "Dhs", False),
    Layout("L4_ar_band", "ar", "NotoNaskhArabic", "#0B5345", "band", "side", "grid", True, "dmy", "western", "د.إ", True),
    Layout("L5_ar_eastern", "ar", "Amiri", "#4A235A", "plain", "stack", "lines", False, "long", "eastern", "درهم", True),
    Layout("L6_bi_band", "bi", "Cairo", "#7B241C", "band", "side", "grid", True, "dmy", "western", "AED", True),
    Layout("L7_bi_boxed", "bi", "Tajawal", "#1B4F72", "boxed", "side", "zebra", False, "iso", "western", "AED", True),
    Layout("L8_bi_mixed", "bi", "Amiri", "#145A32", "plain", "stack", "lines", True, "dmy", "eastern", "د.إ", False),
]


def _has_ar(s: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in s)


def shape(s: str) -> str:
    """Arabic letters must be joined (reshaped) and reordered right-to-left before drawing."""
    return get_display(arabic_reshaper.reshape(s)) if _has_ar(s) else s


class Doc:
    def __init__(self, path: Path, lay: Layout):
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.lay = lay
        self.rtl = lay.lang == "ar"
        self.reg, self.bold = f"{lay.font}-Regular", f"{lay.font}-Bold"
        self.acc = HexColor(lay.accent)

    # mirror x for right-to-left documents
    def X(self, x):
        return W - x if self.rtl else x

    def al(self, align):
        if not self.rtl:
            return align
        return {"left": "right", "right": "left"}.get(align, align)

    def text(self, x, y, s, size=9, bold=False, align="left", color=black, mirror=True):
        c = self.c
        c.setFillColor(color)
        c.setFont(self.bold if bold else self.reg, size)
        s = fit_to_font(shape(str(s)), self.lay.font)
        if mirror:
            x, align = self.X(x), self.al(align)
        if align == "left":
            c.drawString(x, y, s)
        elif align == "right":
            c.drawRightString(x, y, s)
        else:
            c.drawCentredString(x, y, s)

    def label(self, key):
        en, ar = LABELS[key]
        return {"en": en, "ar": ar, "bi": f"{en} / {ar}"}[self.lay.lang]

    def num(self, v: Decimal, decimals=2) -> str:
        s = f"{v:,.{decimals}f}" if self.lay.thousands else f"{v:.{decimals}f}"
        return s.translate(EASTERN) if self.lay.digits == "eastern" else s

    def digits(self, s: str) -> str:
        return s.translate(EASTERN) if self.lay.digits == "eastern" else s

    def date(self, d) -> str:
        f = self.lay.date_fmt
        if f == "iso":
            s = d.isoformat()
        elif f == "long":
            s = f"{d.day} {AR_MONTHS[d.month - 1]} {d.year}" if self.lay.lang == "ar" else d.strftime("%d %B %Y")
        else:
            s = d.strftime("%d/%m/%Y")
        return self.digits(s)

    def rect(self, x, y, w, h, fill=None, stroke=None, lw=0.6):
        c = self.c
        xx = W - x - w if self.rtl else x
        c.setLineWidth(lw)
        if fill is not None:
            c.setFillColor(fill)
        if stroke is not None:
            c.setStrokeColor(stroke)
        c.rect(xx, y, w, h, fill=1 if fill is not None else 0, stroke=1 if stroke is not None else 0)

    def hline(self, x1, x2, y, color=black, lw=0.5):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(lw)
        self.c.line(self.X(x1), y, self.X(x2), y)


def _party_lines(d: Doc, p, extra) -> list[tuple[str, bool]]:
    lang = d.lay.lang
    name = p.legal_name
    lines = [(name, True)]
    if lang == "bi" and p.legal_name_alt:
        lines.append((p.legal_name_alt, False))
    city_en, city_ar = extra["city_en"], extra["city_ar"]
    street = extra["street_ar"] if lang == "ar" else extra["street_en"]
    city = city_ar if lang == "ar" else city_en
    lines.append((f"{street}, {city}", False))
    lines.append((("الإمارات العربية المتحدة" if lang == "ar" else "United Arab Emirates"), False))
    if p.trn:
        lines.append((f"{d.label('trn')}: {d.digits(p.trn)}", True))
    if p.trade_license:
        lines.append((f"{d.label('tl')}: {d.digits(p.trade_license)}", False))
    return lines


def render(inv: Invoice, extra: dict, lay: Layout, path: Path) -> None:
    """Draw `inv` to `path`. `extra` holds printed-only details (addresses in both languages, bank name)."""
    d = Doc(path, lay)
    c = d.c
    is_cn = inv.type_code == "381"
    M = 40
    y = H - 50

    # ---- header ----
    title = d.label("credit_note" if is_cn else "tax_invoice")
    seller_name = inv.seller.legal_name
    if lay.header == "band":
        d.rect(0, H - 95, W, 95, fill=d.acc)
        d.text(M, H - 48, seller_name, 15, True, color=white)
        d.text(M, H - 66, f"{d.label('trn')}: {d.digits(inv.seller.trn or '')}", 9, color=white)
        d.text(W - M, H - 52, title, 16, True, "right", white)
        y = H - 125
    elif lay.header == "boxed":
        d.rect(M, H - 100, 200, 60, stroke=d.acc, lw=1.2)
        d.text(M + 100, H - 75, "LOGO" if lay.lang != "ar" else "شعار", 14, True, "center", d.acc)
        d.text(W - M, H - 58, title, 15, True, "right", d.acc)
        d.text(W - M, H - 76, seller_name, 10, True, "right")
        y = H - 130
    else:
        d.text(W / 2, H - 55, title, 17, True, "center", d.acc, mirror=False)
        d.hline(M, W - M, H - 66, d.acc, 1.2)
        y = H - 92

    # ---- document details ----
    no_label = d.label("cn_no" if is_cn else "inv_no")
    details = [(no_label, d.digits(inv.number)), (d.label("date"), d.date(inv.issue_date))]
    if inv.due_date and not is_cn:
        details.append((d.label("due"), d.date(inv.due_date)))
    if is_cn and inv.original_invoice_number:
        details.append((d.label("orig"), d.digits(inv.original_invoice_number)))
    dx = W - M - 230
    for i, (k, v) in enumerate(details):
        d.text(dx, y - i * 14, f"{k}:", 9, True)
        d.text(W - M, y - i * 14, v, 9, False, "right")

    # ---- parties ----
    s_lines = _party_lines(d, inv.seller, extra["seller"])
    b_lines = _party_lines(d, inv.buyer, extra["buyer"])
    if lay.parties == "side":
        top = y - len(details) * 14 - 16
        for col_x, head, lines in ((M, d.label("seller"), s_lines), (M + 260, d.label("buyer"), b_lines)):
            d.text(col_x, top, head, 10, True, color=d.acc)
            for j, (t, b) in enumerate(lines):
                d.text(col_x, top - 14 - j * 12, t, 8.5, b)
        y = top - 14 - max(len(s_lines), len(b_lines)) * 12 - 18
    else:
        top = y
        d.text(M, top, d.label("seller"), 10, True, color=d.acc)
        for j, (t, b) in enumerate(s_lines):
            d.text(M, top - 14 - j * 12, t, 8.5, b)
        top2 = top - 14 - len(s_lines) * 12 - 10
        top2 = min(top2, y - len(details) * 14 - 8)
        d.text(M, top2, d.label("buyer"), 10, True, color=d.acc)
        for j, (t, b) in enumerate(b_lines):
            d.text(M, top2 - 14 - j * 12, t, 8.5, b)
        y = top2 - 14 - len(b_lines) * 12 - 18

    # ---- line table ----
    cols = [("no", 22, "center"), ("desc", 0, "left"), ("qty", 42, "right"), ("price", 70, "right"), ("amount", 72, "right")]
    if lay.line_vat:
        cols += [("vat", 58, "right"), ("total", 72, "right")]
    fixed = sum(w for _, w, _ in cols)
    cols = [(k, (W - 2 * M - fixed) if w == 0 else w, a) for k, w, a in cols]
    row_h = 26 if lay.lang == "bi" else 18
    # header row
    d.rect(M, y - row_h + 6, W - 2 * M, row_h, fill=d.acc if lay.table != "lines" else HexColor("#EEEEEE"))
    x = M
    for k, w, a in cols:
        hcol = white if lay.table != "lines" else black
        if lay.lang == "bi":
            en, ar = LABELS[k]
            d.text(x + (w / 2 if a == "center" else (w - 4 if a == "right" else 4)), y - 3, en, 7.5, True, a, hcol)
            d.text(x + (w / 2 if a == "center" else (w - 4 if a == "right" else 4)), y - 14, ar, 7.5, True, a, hcol)
        else:
            d.text(x + (w / 2 if a == "center" else (w - 4 if a == "right" else 4)), y - 6, d.label(k), 8, True, a, hcol)
        x += w
    y -= row_h
    for i, l in enumerate(inv.lines, 1):
        net = l.stated_net if l.stated_net is not None else l.net
        desc = extra["line_desc"][i - 1]
        if lay.table == "zebra" and i % 2 == 0:
            d.rect(M, y - 8, W - 2 * M, 18, fill=HexColor("#F2F2F2"))
        vals = {"no": d.digits(str(i)), "desc": desc, "qty": d.num(l.quantity, 0 if l.quantity == int(l.quantity) else 2),
                "price": d.num(l.unit_price), "amount": d.num(net), "vat": d.num(l.vat), "total": d.num(net + l.vat)}
        x = M
        for k, w, a in cols:
            size = 8 if k != "desc" else (7.5 if len(desc) > 38 else 8)
            d.text(x + (w / 2 if a == "center" else (w - 4 if a == "right" else 4)), y - 3, vals[k], size, False, a)
            x += w
        if lay.table == "grid":
            d.hline(M, W - M, y - 8, HexColor("#BBBBBB"))
        y -= 18
    d.hline(M, W - M, y + 10, d.acc, 1)

    # ---- totals ----
    excl = inv.stated_total_excl_vat if inv.stated_total_excl_vat is not None else inv.total_excl_vat
    vat = inv.stated_vat if inv.stated_vat is not None else inv.total_vat
    incl = inv.stated_total_incl_vat if inv.stated_total_incl_vat is not None else excl + vat
    tx = W - M - 250
    y -= 10
    for k, v, b in (("subtotal", excl, False), ("vat_total", vat, False), ("grand", incl, True)):
        if b:
            d.rect(tx - 6, y - 6, 256, 18, fill=HexColor("#EEEEEE"))
        d.text(tx, y, d.label(k), 9 if not b else 9.5, b)
        d.text(W - M, y, f"{d.num(v)} {lay.currency}", 9 if not b else 10, b, "right")
        y -= 18

    # ---- payment and footer ----
    y -= 16
    if inv.payment_terms:
        d.text(M, y, f"{d.label('terms')}: {extra['terms_text']}", 8.5)
        y -= 13
    if inv.iban:
        d.text(M, y, f"{d.label('bank')}: {extra['bank']}", 8.5)
        d.text(M, y - 13, f"{d.label('iban')}: {inv.iban}", 8.5)
        y -= 26
    d.text(W - M, 95, d.label("sign"), 8.5, align="right")
    d.hline(W - M - 150, W - M, 108, black, 0.5)
    if extra.get("stamp"):
        c.saveState()
        cx = (W - M - 75) if not d.rtl else (M + 75)
        c.setStrokeColor(HexColor("#1A5276"))
        c.setLineWidth(1.5)
        c.circle(cx, 140, 34)
        c.setFont(d.bold, 6.5)
        c.setFillColor(HexColor("#1A5276"))
        c.drawCentredString(cx, 140, fit_to_font(shape(inv.seller.legal_name[:24]), lay.font))
        c.restoreState()
    d.text(W / 2, 50, d.label("thanks"), 8, align="center", color=HexColor("#666666"), mirror=False)
    c.showPage()
    c.save()
