import pymupdf, pathlib, re, json, sys
root = pathlib.Path.home() / "Zotero" / "storage"
out = []
pdfs = list(root.glob("*/*.pdf"))
print("pdfs", len(pdfs), file=sys.stderr)
for f in pdfs:
    try:
        d = pymupdf.open(f)
        if d.page_count < 2: continue
        t = d[0].get_text()
    except Exception:
        continue
    tl = t.lower()
    if "microplastic" not in tl: continue
    lic = None
    if re.search(r"creative commons attribution 4\.0|cc[ -]by 4\.0|cc[ -]by\b", tl) and not re.search(r"noncommercial|non-commercial|by-nc|cc by-nc|no ?derivatives|-nd\b", tl):
        lic = "CC BY"
    if not lic: continue
    doi = re.search(r"10\.\d{4,9}/[^\s\"<>]+", t)
    title = (d.metadata or {}).get("title") or ""
    out.append({"pdf": str(f), "doi": doi.group(0).rstrip(".,;)") if doi else None, "title": title.strip(), "year": re.search(r"(20[0-2]\d)", t).group(1) if re.search(r"(20[0-2]\d)", t) else None})
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(len(out))
