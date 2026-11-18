import pymupdf, json, sys, pathlib, re
cand = json.load(open(sys.argv[1])); outdir = pathlib.Path(sys.argv[2])
credits = json.load(open(outdir / "credits.json"))
bydoi = {c["doi"]: c["pdf"] for c in cand if c["doi"]}
bydoi["10.1021/acs.est.6c01796"] = str(pathlib.Path.home()/"Zotero/storage/BIV4V2FX/Hartmann et al. - 2026 - Lost in a Sea of Information The Microplastics Publication Deluge.pdf")
PAT = re.compile(r"download|sharingguidelines|legitimately share|licensed to|for personal use|accessed by|ip address|resources board|calepa|epa\.gov|scott", re.I)
for c in credits:
    d = pymupdf.open(bydoi[c["doi"]]); pg = d[0]
    n = 0
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            txt = "".join(s["text"] for s in l["spans"])
            if PAT.search(txt):
                pg.add_redact_annot(pymupdf.Rect(l["bbox"]) + (-2, -2, 2, 2), fill=(1, 1, 1)); n += 1
    pg.apply_redactions()
    left = pg.get_text()
    assert not re.search(r"download|resources board|calepa", left, re.I), (c["doi"], "stamp remains")
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)); pix.save(outdir / c["file"])
    c["redacted_lines"] = n
    print(c["file"], "redacted", n)
json.dump(credits, open(outdir / "credits.json", "w"), indent=1)
