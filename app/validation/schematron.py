"""Runs the official PINT AE 1.0.4 validation rules against a UBL invoice.

OpenPeppol publishes the rules as Schematron files and also ships them
pre-compiled to XSLT 2.0. Python's usual XML library (lxml) only supports
XSLT 1.0, so we use Saxon (the `saxonche` package) to run them.

Each run produces an SVRL report (Schematron Validation Report Language).
We turn every <svrl:failed-assert> into a simple RuleResult.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lxml import etree
from saxonche import PySaxonProcessor

RULES_DIR = Path(__file__).resolve().parents[2] / "rules" / "pint-ae-1.0.4"
SVRL_NS = {"svrl": "http://purl.oclc.org/dsdl/svrl"}

# The two rule sets that make up PINT AE validation:
#  1. PINT-UBL-validation: the shared international PINT rules
#  2. PINT-jurisdiction-aligned-rules: UAE-specific rules (ibr-...-ae)
RULE_SETS = ("PINT-UBL-validation-preprocessed.xslt", "PINT-jurisdiction-aligned-rules.xslt")


@dataclass
class RuleResult:
    rule_id: str
    severity: str          # "fatal" or "warning"
    message: str
    location: str
    rule_set: str


_proc = PySaxonProcessor(license=False)


@lru_cache(maxsize=None)
def _compiled(doc_type: str, xslt_name: str):
    """Compile each stylesheet once and reuse it (compiling takes ~1 s)."""
    path = RULES_DIR / f"trn-{doc_type}" / "schematron" / xslt_name
    return _proc.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(path))


def detect_doc_type(xml: bytes) -> str:
    root = etree.fromstring(xml)
    return "creditnote" if etree.QName(root).localname == "CreditNote" else "invoice"


def validate_xml(xml: bytes) -> list[RuleResult]:
    """Return every failed rule (empty list = invoice is valid)."""
    doc_type = detect_doc_type(xml)
    node = _proc.parse_xml(xml_text=xml.decode("utf-8"))
    results: list[RuleResult] = []
    for name in RULE_SETS:
        svrl = _compiled(doc_type, name).transform_to_string(xdm_node=node)
        tree = etree.fromstring(svrl.encode("utf-8"))
        for fa in tree.iterfind(".//svrl:failed-assert", SVRL_NS):
            text = " ".join("".join(fa.itertext()).split())
            results.append(RuleResult(
                rule_id=fa.get("id", ""),
                severity=(fa.get("flag") or "fatal").lower(),
                message=text,
                location=fa.get("location", ""),
                rule_set=name.split("-preprocessed")[0].replace(".xslt", ""),
            ))
    return results


def is_valid(results: list[RuleResult]) -> bool:
    """An invoice is valid when no *fatal* rule failed (warnings are allowed)."""
    return not any(r.severity == "fatal" for r in results)
