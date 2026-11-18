import json, math, random, re, pathlib
TIER3={"840","156","826","276","724","380","036","124","410","392","356","076","250","528"}
TIER2={"578","620","752","208","056","364","792","484","152","710","458","764","360","616","756","040","246","372","300","704","586","682","818","566","032","554","643","608","050","170","604","404","203"}
NO_DATA={"304","732","238","260"}
def load(geo):
    w=json.load(open(pathlib.Path(geo)/"world.json"))
    for c in w["countries"]:
        c["tier"]=3 if c["id"] in TIER3 else 2 if c["id"] in TIER2 else 0 if c["id"] in NO_DATA else 1
        rings=[[tuple(map(float,p.split(","))) for p in r.split("L")] for r in re.findall(r"M([^Z]+)Z",c["d"])]
        c["rings"]=rings
        xs=[p[0] for r in rings for p in r]; ys=[p[1] for r in rings for p in r]
        c["bbox"]=(min(xs),min(ys),max(xs),max(ys))
        # centroid of largest ring
        big=max(rings,key=len); c["cx"]=sum(p[0] for p in big)/len(big); c["cy"]=sum(p[1] for p in big)/len(big)
    return w
def pip(x,y,rings):
    inside=False
    for r in rings:
        n=len(r); j=n-1
        for i in range(n):
            xi,yi=r[i]; xj,yj=r[j]
            if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi+1e-12)+xi: inside=not inside
            j=i
    return inside
def spring_style(c,W=1000,H=486.7,f=0.9):
    dx=(c["cx"]-W/2)*f; dy=(c["cy"]-H/2)*f*0.6
    d=abs(c["cx"]-W/2)/(W/2)
    return f'style="--dx:{dx:.0f}px;--dy:{dy:.0f}px;--dl:{(1-d)*0.25:.2f}s"'
