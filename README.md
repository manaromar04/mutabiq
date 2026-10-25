# Mutabiq (مطابق)

**An intelligent e-invoicing compliance system for UAE small and medium enterprises.**

Capstone project, Ajman University. Student: Manar Nabeeh Yousef Omar (202311439).

From 1 July 2027, UAE businesses below AED 50 million in revenue must issue
B2B invoices as structured **PINT AE** e-invoices. Mutabiq takes the invoices
SMEs already have (PDFs, scans, Excel, in Arabic and English), extracts the
data, converts it to PINT AE UBL XML, checks it against the official rules,
flags problems for an accountant to review, and reports how ready the business is.

## Project structure

| Folder | What is inside |
|---|---|
| `app/models.py` | The internal invoice model every document is converted into |
| `app/mapping/ubl.py` | Writes an invoice as PINT AE 1.0.4 UBL XML |
| `app/profile.py` | Fills mandatory details from the seller's business profile |
| `app/validation/schematron.py` | Runs the **official** PINT AE 1.0.4 rules (OpenPeppol Schematron) |
| `rules/pint-ae-1.0.4/` | Official PINT AE Billing 1.0.4 package: rules, code lists, examples, docs |
| `data_generator/` | Creates the synthetic bilingual invoice dataset |
| `data/synthetic/` | The generated dataset (PDFs, ground truth, injected errors) |
| `tests/` | Automated tests |

## Running it

Open the repo in **GitHub Codespaces** (Code → Codespaces → Create). Everything installs automatically. Then:

```bash
pytest -q                                                   # run the tests
python -m data_generator.generate --out data/synthetic      # regenerate the dataset
```

## Status

- [x] Official PINT AE 1.0.4 validation running (all 28 official examples pass)
- [x] Invoice model and PINT AE XML generator (generated invoices and credit notes pass validation)
- [x] Synthetic invoice dataset (312 documents, 83 planted errors; see `data/synthetic/README.md`)
- [ ] Extraction (OCR + LLM)
- [ ] UAE-specific checks and anomaly detection
- [ ] Web app (upload, review queue, readiness report)
- [ ] Deployment (Render + Neon)
- [ ] Evaluation
