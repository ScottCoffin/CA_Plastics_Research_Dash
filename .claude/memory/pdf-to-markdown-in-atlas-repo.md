---
name: pdf-to-markdown-in-atlas-repo
description: "In the CA Plastics Research Atlas repo, read and verify PDFs with the pdf-to-markdown skill whenever possible"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 4588fb1b-94a5-45a3-ad59-858dde15d3f6
  modified: 2026-11-10T05:28:08.012Z
---

In the CA_Plastics_Research_Dash repo, use the `pdf-to-markdown` skill whenever a PDF must be read, checked or quoted (for example verifying Need Ledger quotes against the OPC/SFEI/DTSC source PDFs). Write its output into the repo's ignored `scratch/`, never next to the PDF in Zotero storage.

**Why:** The user asked for this on 2026-11-09, after an ad-hoc pdfminer diagnosis of ledger quotes. pdf-to-markdown keeps tables and layout, and it is the owner's preferred reader.

**How to apply:** Do manual reads and verification with the skill. Pipeline code in the repo (for example `scripts/check_need_ledger_quotes.py`, built on pdfminer.six) keeps the repo's own parser, per the global CLAUDE.md rule. Source PDFs live in Zotero; see [[zotero-a2-source-pdfs]].
