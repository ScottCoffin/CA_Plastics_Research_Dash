import json, math, sys, pathlib
D = pathlib.Path(sys.argv[1])
A1,A2,A3,A4=1.340264,-0.081106,0.000893,0.003796; M=math.sqrt(3)/2
def ee(lon,lat):
    lam=math.radians(lon); phi=math.radians(lat)
    th=math.asin(M*math.sin(phi)); t2=th*th; t6=t2**3
    x=lam*math.cos(th)/(M*(A1+3*A2*t2+t6*(7*A3+9*A4*t2)))
    y=th*(A1+A2*t2+t6*(A3+A4*t2))
    return x,y
XM,YM=2.7066,1.3173
W=1000.0; S=W/(2*XM); H=round(2*YM*S,1)
def P(lon,lat):
    x,y=ee(lon,lat); return (x+XM)*S,(YM-y)*S
def decode(topo):
    tr=topo.get("transform"); arcs=[]
    for arc in topo["arcs"]:
        x=y=0; pts=[]
        for p in arc:
            if tr:
                x+=p[0]; y+=p[1]
                pts.append((x*tr["scale"][0]+tr["translate"][0], y*tr["scale"][1]+tr["translate"][1]))
            else: pts.append(tuple(p[:2]))
        arcs.append(pts)
    def ring(idx):
        out=[]
        for i in idx:
            a=arcs[i] if i>=0 else arcs[~i][::-1]
            out.extend(a if not out else a[1:])
        return out
    return ring
def geom_d(g,ring,step=1):
    polys=g["arcs"] if g["type"]=="MultiPolygon" else [g["arcs"]] if g["type"]=="Polygon" else []
    parts=[]
    for poly in polys:
        for r in poly:
            pts=ring(r)
            if step>1: pts=pts[::step]+[pts[-1]]
            un=[pts[0]]
            for lo,la in pts[1:]:
                plo=un[-1][0]
                while lo-plo>180: lo-=360
                while lo-plo<-180: lo+=360
                un.append((lo,la))
            mn=min(q[0] for q in un); mx=max(q[0] for q in un)
            copies=[0]
            if mn<-180: copies.append(360)
            if mx>180: copies.append(-360)
            for sh in copies:
              xy=[P(lo+sh,la) for lo,la in un]
            # drop tiny rings
              xs=[p[0] for p in xy]; ys=[p[1] for p in xy]
              if max(xs)-min(xs)<0.6 and max(ys)-min(ys)<0.6: continue
              s="M"+"L".join(f"{x:.1f},{y:.1f}" for x,y in xy)+"Z"
              parts.append(s)
    return "".join(parts)
w=json.loads((D/"countries-110m.json").read_text())
ring=decode(w); out=[]
for g in w["objects"]["countries"]["geometries"]:
    cid=g.get("id"); name=g.get("properties",{}).get("name","")
    if cid=="010": continue
    d=geom_d(g,ring)
    if d: out.append({"id":cid,"name":name,"d":d})
u=json.loads((D/"states-10m.json").read_text()); ring2=decode(u)
ca=[g for g in u["objects"]["states"]["geometries"] if g["id"]=="06"][0]
cad=geom_d(ca,ring2,step=3)
# bbox of CA
import re
nums=[tuple(map(float,p.split(","))) for p in re.findall(r"[\d.]+,[\d.]+",cad)]
bb=(min(n[0] for n in nums),min(n[1] for n in nums),max(n[0] for n in nums),max(n[1] for n in nums))
sph=[P(-180,la) for la in range(-90,91,2)]+[P(180,la) for la in range(90,-91,-2)]
sphere="M"+"L".join(f"{x:.1f},{y:.1f}" for x,y in sph)+"Z"
yt=P(0,84)[1]; yb=P(0,-57)[1]
json.dump({"sphere":sphere,"crop":[round(yt,1),round(yb,1)],"w":W,"h":H,"countries":out,"ca":cad,"ca_bbox":bb},open(D/"world.json","w"))
print(len(out),"countries; viewBox 0 0",W,H,"; CA bbox",[round(v,1) for v in bb],"; bytes",(D/"world.json").stat().st_size)
no=[c for c in out if c["id"]=="578"][0]; print("Norway path len",len(no["d"]))
