import pymupdf, json, re, sys, pathlib
cand = json.load(open(sys.argv[1])); outdir = pathlib.Path(sys.argv[2]); outdir.mkdir(parents=True, exist_ok=True)
want = ["10.1021/acs.est.6c01796","10.1186/s43591-022-00033-3","10.1177/0003702820930292","10.1016/j.envpol.2021.118393","10.1073/pnas.2300582121",
"10.1016/j.envpol.2021.117697","10.1016/j.hazadv.2022.100057","10.1186/s43591-023-00065-3","10.1021/acs.est.4c02406","10.3390/biomedicines11020264",
"10.1016/j.scitotenv.2018.07.207","10.1016/j.envpol.2019.113904","10.1016/j.marpolbul.2021.113111","10.1136/tc-2023-057925","10.1021/acs.est.3c10776","10.1186/s43591-021-00011-1"]
# Hartmann is not necessarily in the scan list; add it explicitly
extra = {"10.1021/acs.est.6c01796": str(pathlib.Path.home()/"Zotero/storage/BIV4V2FX/Hartmann et al. - 2026 - Lost in a Sea of Information The Microplastics Publication Deluge.pdf")}
bydoi = {}
for c in cand:
    if c["doi"] and c["doi"] not in bydoi: bydoi[c["doi"]] = c["pdf"]
bydoi.update(extra)
credits = []
for i, doi in enumerate(want):
    pdf = bydoi.get(doi)
    if not pdf: print("missing", doi); continue
    d = pymupdf.open(pdf); pg = d[0]; t = pg.get_text()
    m = re.search(r"[^.\n]*(creative commons attribution[^.\n]*|cc[ -]by[^.\n]*)", t, re.I)
    if not m or re.search(r"noncommercial|non-commercial|by-nc|no ?derivatives", t, re.I): print("license check failed", doi); continue
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)); fn = outdir / f"p{i:02d}.png"; pix.save(fn)
    md = d.metadata or {}
    credits.append({"file": fn.name, "doi": doi, "title": (md.get("title") or "").strip(), "author": (md.get("author") or "").strip(), "license_text": m.group(0).strip()[:200]})
json.dump(credits, open(outdir / "credits.json", "w"), indent=1)
for c in credits: print(c["file"], c["doi"], "|", c["license_text"][:70])
