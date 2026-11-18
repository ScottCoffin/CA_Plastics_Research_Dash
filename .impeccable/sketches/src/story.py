"""Scroll-story prototype for the Spectral Match global landing (design iteration only)."""
import sys, json, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sketchlib import load, pip

S = pathlib.Path(__file__).parent
repo = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
trend = json.load(open(repo / "site/data/trend_global.json"))
by = trend["by_year"]
YEARS = list(range(1970, 2027))
VALS = [int(by.get(str(y), 0)) for y in YEARS]

# ---- pixel world map (Spectral Match) ----
w = load(S / "geo")
W, H = w["w"], w["h"]
C0, C1 = w["crop"]
MW = 1290
k = MW / W
MH = (C1 - C0) * k
CELL = 7
cols, rows = int(MW // CELL), int(MH // CELL)
SPH = [[tuple(map(float, q.split(","))) for q in w["sphere"][1:-1].split("L")]]
ca = w["ca"]
b = w["ca_bbox"]
carings = [[tuple(map(float, q.split(","))) for q in r.split("L")] for r in re.findall(r"M([^Z]+)Z", ca)]
cells = []
for r in range(rows):
    uy = C0 + (r + 0.5) * CELL / k
    line = []
    for c in range(cols):
        ux = (c + 0.5) * CELL / k
        ch = "."
        if pip(ux, uy, SPH):
            if b[0] <= ux <= b[2] and b[1] <= uy <= b[3] and pip(ux, uy, carings):
                ch = "c"
            else:
                for cc in w["countries"]:
                    bb = cc["bbox"]
                    if bb[0] <= ux <= bb[2] and bb[1] <= uy <= bb[3] and pip(ux, uy, cc["rings"]):
                        ch = str(cc["tier"])
                        break
        line.append(ch)
    cells.append("".join(line))
RASTER = "|".join(cells)
ZC = 0.26
zrows = []
yy = b[1] + ZC / 2
while yy < b[3]:
    xx = b[0] + ZC / 2
    row = []
    while xx < b[2]:
        if pip(xx, yy, carings):
            row.append("w" if xx < b[0] + (b[2] - b[0]) * (0.25 + 0.5 * (yy - b[1]) / (b[3] - b[1])) else "l")
        else:
            row.append(".")
        xx += ZC
    zrows.append("".join(row))
    yy += ZC
CARAS = "|".join(zrows)
outline = "".join(f'<path d="{c["d"]}"/>' for c in w["countries"])
no = [c for c in w["countries"] if c["id"] == "578"][0]
cax = ((b[0] + b[2]) / 2) * k
cay = ((b[1] + b[3]) / 2 - C0) * k
nb = no["bbox"]
nox = ((nb[0] + nb[2]) / 2) * k
noy = ((nb[1] + nb[3]) / 2 + 4 - C0) * k

TEMPLATE = (S / "story_template.html").read_text(encoding="utf-8")
html = (TEMPLATE
        .replace("__YEARS__", json.dumps(YEARS))
        .replace("__VALS__", json.dumps(VALS))
        .replace("__FETCHED__", trend["fetched_at"][:10])
        .replace("__QV__", trend["query_version"])
        .replace("__RASTER__", RASTER).replace("__CARAS__", CARAS)
        .replace("__CELL__", str(CELL))
        .replace("__MW__", str(MW)).replace("__MH__", f"{MH:.0f}")
        .replace("__VB__", f"0 {C0} {W} {C1 - C0}")
        .replace("__SPHERE__", w["sphere"])
        .replace("__OUTLINE__", outline)
        .replace("__CA__", ca).replace("__NO__", no["d"])
        .replace("__CAX__", f"{cax:.0f}").replace("__CAY__", f"{cay:.0f}")
        .replace("__NOX__", f"{nox:.0f}").replace("__NOY__", f"{noy:.0f}"))
out.write_text(html, encoding="utf-8")
print("wrote", out, len(html), "total works", sum(VALS))
