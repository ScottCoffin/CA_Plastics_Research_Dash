// ---------- story ----------
// Timeline in scroll units (about 0.95 screen heights each). TOT is the story length. Tune dwell here.
const TOT=31.5;
const TU={move:[.25,.75],pop:[1.3,1.9],gdis:[2.5,3.0],U:[2.95,3.7],stack:[5.6,6.4],papersOut:[7.0,7.3],
 K:[7.3,8.1],Kl:[8.3,8.7,10.3,10.5],B:[10.5,11.2],glow:[12.1,12.6],burst:[12.6,13.2],
 C:[13.4,15.6],Cax:[17.4,17.7,20.5,20.65],Ann:[17.85,18.75],Ev:[20.7,21.4],Evg:[21.2,21.45,23.3,23.45],Nw:[23.5,24.2],Nwl:[24,24.3,26,26.15],spring:[23.8,24.2,25.9,26.25],
 Mp:[26.25,26.9],Mpu:[26.7,27,28.4,28.55],Z:[28.55,29.2],Zu:[29,29.3]};
const PD=.4/TOT,DD=.45/TOT;
const T={};for(const k in TU)T[k]=TU[k].map(v=>v/TOT);
const stage=document.getElementById("stage"),cv=document.getElementById("cv"),g=cv.getContext("2d"),story=document.getElementById("story");
const total=VALS.reduce((a,b)=>a+b,0);
const UNIT=Math.max(50,Math.round(total/900/10)*10);
document.getElementById("unit").textContent=UNIT;
const colDots=VALS.map(v=>Math.round(v/UNIT));
const N=colDots.reduce((a,b)=>a+b,0),CI0=Math.max(0,colDots.findIndex(v=>v>0));
const TEAL=[67,100,135],TEAL2=[134,169,191],TEAL1=[197,234,223],MATCH=[250,107,104],YEL=[255,244,154],GOLD=[226,183,20];
const rng=s=>()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296};
const rnd=rng(42);
const KINDS=["frag","frag","fiber","film","bead","grain","flake"];
const P=[];let W=0,H=0,dpr=1;const CH={};let DUST=[];
const hue=([r,g2,b])=>{const mx=Math.max(r,g2,b),mn=Math.min(r,g2,b),d=mx-mn;if(d<22)return 400+mx;let h=mx===r?((g2-b)/d)%6:mx===g2?(b-r)/d+2:(r-g2)/d+4;h*=60;return h<0?h+360:h};
for(let i=0;i<N;i++){const kind=KINDS[Math.floor(rnd()*KINDS.length)];const verts=[];const nv=kind==="film"?5:4;for(let v=0;v<nv;v++){const a=v/nv*Math.PI*2+rnd()*.6;verts.push([Math.cos(a)*(.6+rnd()*.6),Math.sin(a)*(.6+rnd()*.6)]);}
 P.push({kind,rgb:[200,200,200],rot:rnd()*6.28,spin:(rnd()-.5)*6,size:1.7+rnd()*1.9,verts,seed:rnd(),ur:rnd(),ua:rnd()*6.28});}
let KL=[],NL=[],MAPU=null,ZU={cell:1};
const RAS="__RASTER__".split("|"),RC=RAS[0].length,RR=RAS.length;
const ZR="__CARAS__".split("|");
const MCOL={"0":[230,236,239],"1":TEAL1,"2":TEAL2,"3":TEAL,"c":MATCH};
const scene=document.getElementById("scene"),itemsImg=document.getElementById("items");
const capBox=sel=>{const el=document.querySelector(sel);if(!el)return{r:0,b:0,t:H};let rr=0,bb=0,tt=1e9;el.querySelectorAll("h1,h2,p").forEach(k=>{const rg=document.createRange();rg.selectNodeContents(k);const q=rg.getBoundingClientRect();rr=Math.max(rr,q.right);bb=Math.max(bb,q.bottom);tt=Math.min(tt,q.top);});const s=stage.getBoundingClientRect();return{r:rr-s.left,b:bb-s.top,t:tt-s.top};};

// ---- the opening picnic: the blanket photo plus separate item cut-outs, laid out as a picnic ----
// sheet centre (x,y) -> blanket position (x,y), rotation, scale; listed in drawing order (plates before what sits on them)
const LAYOUT=[[190,355,330,320,0,.78],[530,355,1190,330,0,.78],[865,355,720,790,0,.78],
 [1095,315,120,330,.08,.7],[1197,315,525,350,-.1,.7],[1295,315,1375,330,.1,.7],
 [280,880,770,470,-.06,.72],[290,625,1130,640,-.45,.75],[635,610,525,570,.35,.75],[760,610,615,600,-.2,.75],
 [1005,625,330,320,-.25,.62],[1325,625,1190,330,.35,.62],
 [130,100,600,205,.2,.8],[330,100,1010,820,-.3,.8],[530,100,240,650,.1,.8],[730,100,960,190,-.1,.8],[925,100,1395,620,.2,.8],
 [1350,250,660,150,.95,.7],[1440,250,1040,150,.5,.7],[715,880,1335,860,0,.72],[1180,880,330,865,.15,.62]];
const SC={comps:[]};let DEB=[];
const HD=.06/TOT,CD=.45/TOT,KD=.35/TOT;
// Split one picture (item or blanket) into Voronoi shards cut from its own pixels.
// cells: [gx,gy,r,g,b] on a grid of size f; sprite px of a cell centre = (g+.5)*f - off; item-local = sprite px - sprite size/2
function fracture(c,cells,extra,f,offX,offY,nSeed,rr){
 const seeds=[];for(let i=0;i<nSeed;i++){const q=cells[Math.floor(rr()*cells.length)];seeds.push([q[0]+rr()-.5,q[1]+rr()-.5]);}
 const near=(gx,gy)=>{let bi=0,bd=1e18;for(let k=0;k<seeds.length;k++){const dx=seeds[k][0]-gx,dy=seeds[k][1]-gy,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;bi=k;}}return bi;};
 const sh=seeds.map(()=>({cells:[],all:[],gx0:1e9,gy0:1e9,gx1:-1,gy1:-1,sx:0,sy:0}));
 const add=(q,core)=>{const k=near(q[0],q[1]),s=sh[k];s.all.push(q);if(core){s.cells.push(q);s.sx+=q[0];s.sy+=q[1];}if(q[0]<s.gx0)s.gx0=q[0];if(q[0]>s.gx1)s.gx1=q[0];if(q[1]<s.gy0)s.gy0=q[1];if(q[1]>s.gy1)s.gy1=q[1];return k;};
 cells.forEach(q=>{q[5]=add(q,true);});extra.forEach(q=>add(q,false));
 const loc=(gx,gy)=>[(gx+.5)*f-offX-c.bw/2,(gy+.5)*f-offY-c.bh/2];
 // crack lines are cut per 2 px (not per grid cell) so fracture edges come out straight and clean
 c.shards=sh.map((s,k)=>[s,k]).filter(([s])=>s.cells.length).map(([s,k])=>{const gx0=s.gx0-1,gy0=s.gy0-1,w=(s.gx1+1-gx0+1)*f,h=(s.gy1+1-gy0+1)*f,R2=2,mw=Math.ceil(w/R2),mh=Math.ceil(h/R2);
  const mc=document.createElement("canvas");mc.width=mw;mc.height=mh;const m=mc.getContext("2d"),id=m.createImageData(mw,mh);
  for(let my=0;my<mh;my++)for(let mx=0;mx<mw;mx++){const px=gx0*f+(mx+.5)*R2,py=gy0*f+(my+.5)*R2;if(near(px/f-.5,py/f-.5)===k)id.data[(my*mw+mx)*4+3]=255;}m.putImageData(id,0,0);
  const sx=gx0*f-offX,sy=gy0*f-offY,cv2=document.createElement("canvas");cv2.width=w;cv2.height=h;const x2=cv2.getContext("2d");
  x2.drawImage(c.sp,sx,sy,w,h,0,0,w,h);x2.globalCompositeOperation="destination-in";x2.imageSmoothingEnabled=true;x2.drawImage(mc,0,0,w,h);
  const[cx,cy]=loc(s.sx/s.cells.length,s.sy/s.cells.length),[lx0,ly0]=[sx-c.bw/2,sy-c.bh/2];
  const len=Math.hypot(cx,cy)||1,dir=Math.atan2(cy,cx)+(rr()-.5)*.9,dist=c.ground?18+rr()*60:(70+rr()*190)*(.6+.4*Math.min(1,len/120));
  return{sp:cv2,w,h,lx0,ly0,cx,cy,ox:Math.cos(dir)*dist,oy:Math.sin(dir)*dist,rs:(rr()-.5)*(c.ground?.6:3.2),thr:rr(),cells:s.cells};});
 const idx=new Map();c.shards.forEach((s,i)=>s.cells.forEach(q=>idx.set(q,i)));
 c.pts=cells.map(q=>{const[lx,ly]=loc(q[0],q[1]);return[c.shards[idx.get(q)],lx,ly,q[2],q[3],q[4]];});
}
function compose(){
 const f=4,sw=itemsImg.naturalWidth,sh=itemsImg.naturalHeight,lw=Math.ceil(sw/f),lh=Math.ceil(sh/f);
 const oc=document.createElement("canvas");oc.width=lw;oc.height=lh;const o=oc.getContext("2d",{willReadFrequently:true});o.drawImage(itemsImg,0,0,lw,lh);
 const d=o.getImageData(0,0,lw,lh).data,fg=new Uint8Array(lw*lh);for(let i=0;i<lw*lh;i++)fg[i]=d[i*4+3]>110?1:0;
 const lab=new Int32Array(lw*lh).fill(-1),comps=[],st=[];
 for(let i=0;i<lw*lh;i++){if(!fg[i]||lab[i]>=0)continue;const c={area:0,x0:1e9,y0:1e9,x1:-1,y1:-1,cells:[],sx:0,sy:0};lab[i]=comps.length;st.push(i);
  while(st.length){const j=st.pop(),x=j%lw,y=(j/lw)|0;c.area++;c.sx+=x;c.sy+=y;c.cells.push(j);if(x<c.x0)c.x0=x;if(x>c.x1)c.x1=x;if(y<c.y0)c.y0=y;if(y>c.y1)c.y1=y;
   for(const q of [x>0?j-1:-1,x<lw-1?j+1:-1,y>0?j-lw:-1,y<lh-1?j+lw:-1])if(q>=0&&fg[q]&&lab[q]<0){lab[q]=lab[i];st.push(q);}}
  comps.push(c);}
 const big=comps.filter(c=>c.area>=30),taken=new Set(),items=[],tq=rng(55),fr=rng(91);
 big.forEach(c=>{const mx=(c.sx/c.area+.5)*f,my=(c.sy/c.area+.5)*f;let bi=-1,bd=1e18;LAYOUT.forEach((L,k)=>{if(taken.has(k))return;const dd=(L[0]-mx)**2+(L[1]-my)**2;if(dd<bd){bd=dd;bi=k;}});
  if(bi<0||bd>140*140)return;taken.add(bi);const L=LAYOUT[bi],id0=lab[c.cells[0]];
  const x0=Math.max(0,c.x0-2),y0=Math.max(0,c.y0-2),x1=Math.min(lw-1,c.x1+2),y1=Math.min(lh-1,c.y1+2);
  const bx=x0*f,by=y0*f,bw=Math.min(sw-bx,(x1-x0+1)*f),bh=Math.min(sh-by,(y1-y0+1)*f);
  // sprite: the item's own pixels, with any neighbour's pixels cut away
  const mw=x1-x0+1,mh=y1-y0+1,mc=document.createElement("canvas");mc.width=mw;mc.height=mh;const m=mc.getContext("2d"),idd=m.createImageData(mw,mh);
  const ext=[],seen=new Set(c.cells);
  c.cells.forEach(j=>{const x=j%lw,y=(j/lw)|0;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const X=x+dx,Y=y+dy;if(X<x0||Y<y0||X>x1||Y>y1)continue;idd.data[((Y-y0)*mw+(X-x0))*4+3]=255;const jj=Y*lw+X;if(!seen.has(jj)&&lab[jj]!==id0&&!(lab[jj]>=0)){seen.add(jj);ext.push([X,Y,0,0,0]);}}});m.putImageData(idd,0,0);
  const sc=document.createElement("canvas");sc.width=bw;sc.height=bh;const s=sc.getContext("2d");s.drawImage(itemsImg,bx,by,bw,bh,0,0,bw,bh);
  s.globalCompositeOperation="destination-in";s.imageSmoothingEnabled=true;s.drawImage(mc,0,0,mw*f,mh*f);
  const it={sp:sc,bw,bh,tx:L[2],ty:L[3],r0:L[4],sc:L[5],k:bi,area:c.area,up:.7+tq()*.6,vx:tq()-.5,spin:(tq()-.5)*2};
  const cells=c.cells.map(j=>[j%lw,(j/lw)|0,d[j*4],d[j*4+1],d[j*4+2]]);
  fracture(it,cells,ext,f,bx,by,Math.round(clamp(c.area/220,6,18)),fr);items.push(it);});
 items.sort((a,b)=>a.k-b.k);
 // the blanket: alpha-keyed off its black backdrop, torn into larger pieces that fray into fibres
 const nw=scene.naturalWidth,nh=scene.naturalHeight;
 const kc=document.createElement("canvas");kc.width=nw;kc.height=nh;const kx=kc.getContext("2d",{willReadFrequently:true});kx.drawImage(scene,0,0);const kd=kx.getImageData(0,0,nw,nh);
 for(let k=0;k<kd.data.length;k+=4){const l=.3*kd.data[k]+.59*kd.data[k+1]+.11*kd.data[k+2];kd.data[k+3]=Math.round(255*clamp((l-14)/26,0,1));}kx.putImageData(kd,0,0);
 const F=8,gw=Math.ceil(nw/F),gh=Math.ceil(nh/F),gc=document.createElement("canvas");gc.width=gw;gc.height=gh;const gx=gc.getContext("2d",{willReadFrequently:true});gx.drawImage(scene,0,0,gw,gh);
 const gd=gx.getImageData(0,0,gw,gh).data,gin=new Uint8Array(gw*gh),gcells=[],gext=[];
 for(let j=0;j<gw*gh;j++){const k=j*4;if(.3*gd[k]+.59*gd[k+1]+.11*gd[k+2]>40){gin[j]=1;gcells.push([j%gw,(j/gw)|0,gd[k],gd[k+1],gd[k+2]]);}}
 gcells.forEach(q=>{for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const X=q[0]+dx,Y=q[1]+dy;if(X<0||Y<0||X>=gw||Y>=gh)continue;const j=Y*gw+X;if(!gin[j]){gin[j]=2;gext.push([X,Y,0,0,0]);}}});
 const ground={sp:kc,bw:nw,bh:nh,tx:nw/2,ty:nh/2,r0:0,sc:1,ground:true,up:0,vx:0,spin:0};
 fracture(ground,gcells,gext,F,0,0,26,fr);
 SC.comps=[ground,...items];
 const tr=rng(77),ordr=items.map(c=>[tr(),c]).sort((a,b)=>a[0]-b[0]);ground.ord=-1;ordr.forEach(([,c],i)=>c.ord=i);
 // data particles: sampled from the items' pixels; the blanket (about 18%) turns into fibres
 const pr=rng(3),pool=[];items.forEach(c=>c.pts.forEach(q=>pool.push([c,q])));
 P.forEach(p=>{let c,q;if(pr()<.18){c=ground;q=ground.pts[Math.floor(pr()*ground.pts.length)];p.kind="fiber";}else{[c,q]=pool[Math.floor(pr()*pool.length)];}
  p.c=c;p.sh=q[0];p.lx=q[1]+(pr()-.5)*4;p.ly=q[2]+(pr()-.5)*4;p.rgb=[q[3],q[4],q[5]];p.thr=pr();
  p.ea=Math.atan2(p.ly-p.sh.cy,p.lx-p.sh.cx)+(pr()-.5)*2;p.edist=c.ground?.2+pr()*.5:.3+pr()*1.1;});
 // debris: many small crumbs, one spray per shard, that swirl in with the cloud and fade
 const dr=rng(13),all=[];SC.comps.forEach(c=>c.pts.forEach(q=>all.push([c,q])));DEB=[];
 for(let i=0;i<3800;i++){const[c,q]=all[Math.floor(dr()*all.length)],a=Math.atan2(q[2]-q[0].cy,q[1]-q[0].cx)+(dr()-.5)*2.4,dd=(c.ground?10:25)+dr()*(c.ground?50:120);
  DEB.push({c,sh:q[0],lx:q[1]+(dr()-.5)*6,ly:q[2]+(dr()-.5)*6,rgb:css([q[3],q[4],q[5]]),thr:dr(),dx:Math.cos(a)*dd,dy:Math.sin(a)*dd+dr()*20,s:.8+dr()*1.8,ua:dr()*6.28,ur:Math.pow(dr(),.6)});}
}
function phaseOf(c,p,nI){let s0,c0;if(c.ground){c0=T.gdis[0];s0=c0;}else{s0=T.pop[0]+c.ord/Math.max(1,nI-1)*(T.pop[1]-T.pop[0]);c0=s0+PD*.85;}
 return{tt:c.ground?0:eo(seg(p,s0,s0+PD)),c0,k0:c0+HD+CD*.55,st:.03*seg(p,c0,c0+HD)+.97*eo(seg(p,c0+HD,c0+HD+CD))};}
function itemXf(c,R){const s=R.w/scene.naturalWidth,tt=c.ph?c.ph.tt:0,k=c.sc*(1+.3*tt),r=c.r0+c.spin*.35*tt;return{s,k,r,co:Math.cos(r),si:Math.sin(r),X:R.x+c.tx*s+c.vx*W*.015*tt,Y:R.y+c.ty*s-H*.07*c.up*tt,tt};}
function shardFrame(c){const st=c.ph.st;c.shards.forEach(s=>{const a=s.rs*st;s.co=Math.cos(a);s.si=Math.sin(a);s.px=s.cx+s.ox*st;s.py=s.cy+s.oy*st;});}
function shardPt(c,s,lx,ly){const f=c.xf,ux=lx-s.cx,uy=ly-s.cy,X1=s.px+ux*s.co-uy*s.si,Y1=s.py+ux*s.si+uy*s.co,K=f.k*f.s;return[f.X+(X1*f.co-Y1*f.si)*K,f.Y+(X1*f.si+Y1*f.co)*K];}

function layout(){
 const r=stage.getBoundingClientRect();W=r.width;H=r.height;dpr=Math.min(2,devicePixelRatio||1);
 cv.width=W*dpr;cv.height=H*dpr;g.setTransform(dpr,0,0,dpr,0,0);
 const gut=Math.max(16,Math.min(48,W*.034)),narrow=W<860;CH.narrow=narrow;
 // text never overlaps visuals: visuals sit right of the widest side caption; on phones, between the top and bottom captions
 const tops=[".c1",".c1n",".c2",".cb",".c5",".c4",".c7"],side=[...tops,".c2b"].map(capBox),bot=[".c2b"].map(capBox);
 const textR=Math.max(...side.map(o=>o.r))+40,capB=Math.max(...tops.map(capBox).map(o=>o.b))+20;
 const VX0=narrow?gut:Math.max(textR,W*.4),VX1=W-gut,VY0=narrow?capB:H*.14,VY1=narrow?Math.min(...bot.map(o=>o.t))-16:H*.94;CH.VX0=VX0;CH.VY0=VY0;
 const order=P.map((p,i)=>[p.seed,i]).sort((a,b)=>a[0]-b[0]);
 // picnic: full screen on load; just below the title once it arrives
 const c0=capBox(".c0"),nwS=scene.naturalWidth,nhS=scene.naturalHeight;
 CH.sceneBig=fitContain(nwS,nhS,narrow?{x:-W*.25,y:H*.2,w:W*1.5,h:H*.6}:{x:gut,y:60+H*.02,w:W-2*gut,h:H-60-H*.06});
 CH.sceneT=fitContain(nwS,nhS,narrow?{x:-W*.25,y:c0.b+24,w:W*1.5,h:H-c0.b-24-H*.08}:{x:gut,y:c0.b+20,w:W-2*gut,h:H-c0.b-20-H*.04});
 placeStack({x:VX0,y:VY0,w:VX1-VX0,h:VY1-VY0});
 const sc=W/1440+.35;P.forEach(p=>{p.eo=[Math.cos(p.ea)*p.edist*130*sc,Math.sin(p.ea)*p.edist*130*sc];});
 // U: loose data cloud
 const cx=(VX0+VX1)/2,cy=(VY0+VY1)/2,RXu=(VX1-VX0)/2,RYu=(VY1-VY0)/2;CH.ucx=cx;CH.ucy=cy;CH.uRX=RXu*.9;CH.uRY=RYu*.9;
 P.forEach(p=>{const rr=Math.pow(p.ur,.6);p.U=[cx+Math.cos(p.ua)*rr*RXu*.9,cy+Math.sin(p.ua)*rr*RYu*.9];});
 // K: an ordered mandala: concentric rings, colour sorted around the circle, every piece pointing outward
 const R=Math.min(VX1-VX0,VY1-VY0)/2*.84;CH.K=[cx,cy,R];
 const s0=R*Math.sqrt(Math.PI/N)*.97,slots=[];let rr=s0*.75,ring=0;
 while(slots.length<N){let n=Math.max(1,Math.round(2*Math.PI*rr/s0));n=Math.min(n,N-slots.length);const off=ring*.37;for(let k=0;k<n;k++)slots.push([rr,(k/n*Math.PI*2+off)%(Math.PI*2)]);rr+=s0;ring++;}
 slots.sort((a,b)=>a[1]-b[1]||a[0]-b[0]);
 const lum=c=>.3*c[0]+.59*c[1]+.11*c[2],byHue=[...P].sort((a,b)=>hue(a.rgb)-hue(b.rgb)||lum(a.rgb)-lum(b.rgb));
 byHue.forEach((p,j)=>{const[r2,th]=slots[j];p.K=[cx+Math.cos(th)*r2,cy+Math.sin(th)*r2];p.kr=r2/R;p.kth=th;p.ksz=s0*.36/p.size*(1.25-.4*Math.min(1,p.kr));});
 KL=[];const NWg=48,wedges=Array.from({length:NWg},()=>[]);P.forEach(p=>wedges[Math.floor(p.kth/(Math.PI*2)*NWg)%NWg].push(p));
 wedges.forEach(w=>{w.sort((a,b)=>a.kr-b.kr);for(let i=1;i<w.length;i++)if(w[i].kr-w[i-1].kr<s0*1.6/R)KL.push([w[i-1],w[i]]);});
 const dr=rng(17);DUST=[];for(let i=0;i<3000;i++){const q=P[Math.floor(dr()*N)].rgb,a=dr()*6.28,r3=R*(1.06+.75*Math.pow(dr(),1.4));const x=cx+Math.cos(a)*r3*1.2,y=cy+Math.sin(a)*r3;
  if(x<VX0||x>VX1||y<(narrow?VY0:60)||y>(narrow?VY1:H))continue;DUST.push([x,y,.6+dr()*1.2,q,dr()]);}
 // B: the light bulb, filled with the particles (colour order kept)
 const bp=[...document.querySelectorAll("#bulbsrc path")];CH.bulbPaths=bp.map(q=>new Path2D(q.getAttribute("d")));
 const bh=Math.min(H*.7,(VY1-VY0)*.96,(VX1-VX0)*1.4),bsc=bh/270,bcx=(VX0+VX1)/2,bx0=bcx-100*bsc,by0=(VY0+VY1)/2-135*bsc;CH.bulb=[bcx,by0+100*bsc,bh,bsc,bx0,by0];
 const tc=document.createElement("canvas").getContext("2d"),outer=CH.bulbPaths[0],inside=(x,y)=>tc.isPointInPath(outer,x,y)||(x>68&&x<132&&y>208&&y<258);
 let dd=Math.sqrt(26500/N),bs=[];for(let it=0;it<30;it++){bs=[];for(let y=12,row=0;y<258;y+=dd*.88,row++)for(let x=16+(row%2)*dd/2;x<186;x+=dd)if(inside(x,y))bs.push([x,y]);if(bs.length>=N)break;dd*=.97;}
 const ang=([x,y])=>(Math.atan2(y-110,x-100)+Math.PI*2.5)%(Math.PI*2);bs=bs.map(b=>[...b,ang(b)]).sort((a,b)=>a[2]-b[2]);
 const step=bs.length/N,byK=[...P].sort((a,b)=>a.kth-b.kth);
 byK.forEach((p,j)=>{const b=bs[Math.floor(j*step)];p.B=[bx0+b[0]*bsc,by0+b[1]*bsc];p.bsz=dd*bsc*.42/p.size;});
 // C: unit chart. Desktop: headline middle-left over the empty early years; phones: headline below the chart
 const c3=capBox(".c3"),c3s=document.querySelector(".c3s"),srcH=c3s.getBoundingClientRect().height;
 const x0=Math.max(24,W*.06),x1=W-x0,chartTop=60+H*.07,base=narrow?c3.t-28-srcH-30:H*.95-srcH-30,n=YEARS.length,stride=(x1-x0)/n;
 c3s.style.top=(base+30)+"px";c3s.style.left=x0+"px";
 Object.assign(CH,{x0,x1,base,stride,chartTop});annMeasure();const head=ANN[2].h+26;
 let gap=Math.max(1.6,Math.min(6.2,stride/3.3,(base-chartTop-head)/Math.ceil(Math.max(...colDots)/3)));
 CH.txt=narrow?null:{l:0,t:c3.t-12,r:c3.r+16,b:c3.b+14};
 if(CH.txt)colDots.forEach((dd2,i)=>{const X=x0+i*stride+stride/2;if(X<=CH.txt.r&&dd2>0)gap=Math.min(gap,(base-CH.txt.b)/Math.ceil(dd2/3));});
 Object.assign(CH,{x0,x1,base,stride,gap,chartTop});
 const cs=[];colDots.forEach((d2,ci)=>{for(let k=0;k<d2;k++)cs.push([x0+ci*stride+stride/2+((k%3)-1)*gap,base-(Math.floor(k/3)+.5)*gap,ci]);});
 order.forEach(([,i],j)=>{const s=cs[j]||cs[cs.length-1];P[i].C=[s[0],s[1]];P[i].ci=s[2];P[i].cj=j/N;});
 annLayout();
 // Ev: global evidence grid (illustrative weights)
 const ROWS=narrow?["occur.","effects","methods","fate","solutions"]:["occurrence","effects","methods","fate and transport","solutions"],COLS=narrow?["ocean","fresh","soil","air","biota","people"]:["ocean","freshwater","soil","air","food and biota","people"];
 const WTS=[[30,20,8,5,12,4],[18,10,4,1,16,6],[10,6,3,2,3,1],[8,6,3,2,1,0],[4,2,0,0,1,0]];
 const sw=WTS.flat().reduce((a,b)=>a+b,0);const cnt=WTS.map(rw=>rw.map(v=>Math.floor(v/sw*N)));cnt[0][0]+=N-cnt.flat().reduce((a,b)=>a+b,0);
 const gx0=VX0+(narrow?56:120),gy0=VY0+28,cw=(VX1-gx0)/COLS.length,chh=(VY1-gy0-24)/ROWS.length;Object.assign(CH,{ROWS,COLS,gx0,gy0,cw,chh});
 let idx=0;cnt.forEach((rw,ri)=>rw.forEach((c,ci)=>{const sp=Math.max(3.2,Math.min(6,Math.sqrt((cw-14)*(chh-14)/Math.max(c,1))));const pr=Math.max(1,Math.floor((cw-14)/sp));
  for(let k=0;k<c&&idx<N;k++,idx++){const p=P[order[idx][1]];p.Ev=[gx0+ci*cw+8+(k%pr)*sp+sp/2,gy0+ri*chh+8+Math.floor(k/pr)*sp+sp/2];p.evsp=sp;}}));
 // Nw: collaboration network, 7 communities
 const nr=rng(11),NCOM=7,coms=[];for(let k=0;k<NCOM;k++){const a=k/NCOM*6.28+nr()*.5;coms.push([(VX0+VX1)/2+Math.cos(a)*(VX1-VX0)*.32,(VY0+VY1)/2+Math.sin(a)*(VY1-VY0)*.3]);}
 CH.coms=coms;const members=coms.map(()=>[]);
 order.forEach(([,i],j)=>{const k=j%NCOM,p=P[i];const s=Math.sqrt(-2*Math.log(nr()+1e-6))*Math.min(W,H)*.045,a=nr()*6.28;p.Nw=[coms[k][0]+Math.cos(a)*s,coms[k][1]+Math.sin(a)*s];p.com=k;members[k].push(p);});
 NL=[];members.forEach((ms,k)=>{ms.forEach(p=>{for(let e=0;e<2;e++){const q=ms[Math.floor(nr()*ms.length)];if(q!==p)NL.push([p,q]);}if(nr()<.04){const o=members[(k+1+Math.floor(nr()*(NCOM-1)))%NCOM];NL.push([p,o[Math.floor(nr()*o.length)]]);}});});
 // Mp: world pixels, below the c6 caption
 const c6=capBox(".c6"),my0=c6.b+24,mw=Math.min(W-2*gut,(H*.96-my0)*RC/RR),cell=mw/RC,mx0=(W-mw)/2;MAPU={mx0,my0,cell,mw};
 const land=[];for(let r4=0;r4<RR;r4++)for(let cc=0;cc<RC;cc++){const ch=RAS[r4][cc];if(ch===".")continue;const wt=ch==="c"?40:ch==="3"?4:ch==="2"?2:ch==="1"?1:.3;land.push([cc,r4,ch,wt]);}
 const mr=rng(5);const pick=land.map(l=>[Math.pow(mr(),1/l[3]),l]).sort((a,b)=>b[0]-a[0]).slice(0,N).map(x=>x[1]);
 order.forEach(([,i],j)=>{const l=pick[j%pick.length];P[i].Mp=[mx0+(l[0]+.5)*cell,my0+(l[1]+.5)*cell];P[i].mch=l[2];});
 // Z: zoom to California at local scale
 const zc=Math.min((VY1-VY0)/ZR.length,(VX1-VX0)/ZR[0].length),zx0=(VX0+VX1)/2-zc*ZR[0].length/2,zy0=VY0;ZU={zx0,zy0,cell:zc};
 const zl=[];ZR.forEach((row,r4)=>{for(let cc=0;cc<row.length;cc++)if(row[cc]!==".")zl.push([cc,r4,row[cc]]);});
 const zr=rng(9);for(let k=zl.length-1;k>0;k--){const j=Math.floor(zr()*(k+1));[zl[k],zl[j]]=[zl[j],zl[k]];}
 order.forEach(([,i],j)=>{const l=zl[j%zl.length];P[i].Z=[zx0+(l[0]+.5)*zc,zy0+(l[1]+.5)*zc];P[i].zc=(l[2]==="w"?zr()<.5:zr()<.12)?MATCH:(zr()<.5?TEAL:TEAL2);});
}
// ---- chart annotations: wrapped labels placed clear of the dots and the headline, with arrows ----
const ANN=[{y:1972,head:"Carpenter et al. 1972",sub:"“Polystyrene spherules in coastal waters”"},
 {y:2004,head:"Thompson et al. 2004",sub:"“Lost at sea: where is all the plastic?”"},
 {y:2026,head:"Hartmann et al. 2026",sub:"“Lost in a sea of information: the microplastics publication deluge”",note:`2026 to date: ${VALS[VALS.length-1].toLocaleString()} works`}];
function wrapText(text,font,maxW){g.font=font;const out=[];let line="";text.split(" ").forEach(w=>{const t=line?line+" "+w:w;if(g.measureText(t).width>maxW&&line){out.push(line);line=w;}else line=t;});if(line)out.push(line);return out;}
function annMeasure(){const fs=CH.narrow?11.5:13,lh=fs+4,maxW=CH.narrow?136:Math.min(250,W*.18);
 ANN.forEach(a=>{a.lines=[...wrapText(a.head,`600 ${fs}px 'Schibsted Grotesk',sans-serif`,maxW).map(t=>[t,600]),...wrapText(a.sub,`400 ${fs}px 'Schibsted Grotesk',sans-serif`,maxW).map(t=>[t,400])];
  if(a.note)wrapText(a.note,`400 ${fs-2}px 'Martian Mono',monospace`,maxW).forEach(l=>a.lines.push([l,"mono"]));a.h=a.lines.length*lh;
  a.w=Math.min(maxW,Math.max(...a.lines.map(l=>{g.font=l[1]==="mono"?`400 ${fs-2}px 'Martian Mono',monospace`:`${l[1]} ${fs}px 'Schibsted Grotesk',sans-serif`;return g.measureText(l[0]).width;})));a.fs=fs;a.lh=lh;});}
function annLayout(){
 const{x0,x1,base,stride,gap,chartTop}=CH;
 const X=i=>x0+i*stride+stride/2,top=i=>base-Math.ceil(colDots[i]/3)*gap;
 const hitTxt=(x,y,w,h)=>{const t=CH.txt;return t&&x<t.r&&x+w>t.l&&y<t.b&&y+h>t.t;};
 const fits=(x,y,w,h)=>{if(x<x0-4||x+w>x1||hitTxt(x,y,w,h))return false;for(let i=0;i<YEARS.length;i++){const xi=X(i);if(xi>=x-8&&xi<=x+w+8&&top(i)<y+h+10)return false;}return true;};
 ANN.forEach(a=>{
  a.i=YEARS.indexOf(a.y);a.tx=X(a.i);a.ty=top(a.i)-6;});
 const[c72,t04,h26]=ANN;
 h26.y0=chartTop;h26.x0=Math.max(x0,Math.min(x1-h26.w,h26.tx-stride*.9-h26.w));
 c72.y0=base-62-c72.h;c72.x0=c72.tx+stride*2.5;
 t04.y0=base-90-t04.h;t04.x0=Math.max(x0,t04.tx-stride*2-t04.w);
 if(c72.x0<t04.x0+t04.w+12&&c72.x0+c72.w>t04.x0-12)t04.y0=Math.min(t04.y0,c72.y0-t04.h-20);
 while(!fits(t04.x0,t04.y0,t04.w,t04.h)&&t04.y0<base-t04.h-30)t04.y0+=8;
 ANN.forEach(a=>{const left=a.tx>a.x0+a.w/2;a.ax=left?a.x0+a.w+6:a.x0-6;a.ay=a.y0+Math.min(a.h-a.lh*.5,a.lh*1.2);a.cxp=a.tx;a.cyp=a.ay;});
}
function drawAnn(a,f){if(f<=0)return;g.save();g.globalAlpha=Math.min(1,f*2);g.textAlign="left";g.textBaseline="top";
 a.lines.forEach((l,k)=>{g.font=l[1]==="mono"?`400 ${a.fs-2}px 'Martian Mono',monospace`:`${l[1]} ${a.fs}px 'Schibsted Grotesk',sans-serif`;g.fillStyle=l[1]===600?"#17203a":"#4f5a74";g.fillText(l[0],a.x0,a.y0+k*a.lh+1);});
 const q=Math.min(1,f*1.4),pt=s=>{const u=1-s;return[u*u*a.ax+2*u*s*a.cxp+s*s*a.tx,u*u*a.ay+2*u*s*a.cyp+s*s*a.ty];};
 g.globalAlpha=1;g.strokeStyle="#D9443F";g.lineWidth=1.4;g.lineCap="round";g.beginPath();for(let k=0;k<=24;k++){const s=q*k/24,[x,y]=pt(s);k?g.lineTo(x,y):g.moveTo(x,y);}g.stroke();
 if(q>.98){const[x,y]=pt(1),[xp,yp]=pt(.92),an=Math.atan2(y-yp,x-xp);g.beginPath();g.moveTo(x,y);g.lineTo(x-Math.cos(an-.45)*8,y-Math.sin(an-.45)*8);g.moveTo(x,y);g.lineTo(x-Math.cos(an+.45)*8,y-Math.sin(an+.45)*8);g.stroke();}
 g.restore();}
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),seg=(p,a,b)=>clamp((p-a)/(b-a),0,1);
const win=(p,w)=>seg(p,w[0],w[1])*(1-seg(p,w[2],w[3]));
const eo=t=>1-Math.pow(1-t,3),eio=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
const LT=[246,248,249],DK=[0,0,0];
const mix=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t];
const css=(c,a=1)=>`rgba(${c[0]|0},${c[1]|0},${c[2]|0},${a})`;
function progress(){const r=story.getBoundingClientRect();return clamp(-r.top/(r.height-innerHeight),0,1);}
function shape(p,x,y,s,a,rgb,alpha,straight){g.save();g.translate(x,y);g.rotate(a);g.globalAlpha=alpha;const col=css(rgb);
 if(p.kind==="fiber"){g.strokeStyle=col;g.lineWidth=Math.max(1.1,s*.45);g.lineCap="round";g.beginPath();if(straight){g.moveTo(-s*1.7,0);g.lineTo(s*1.7,0);}else{g.moveTo(-s*2.4,0);g.quadraticCurveTo(-s,-s*1.6,0,0);g.quadraticCurveTo(s,s*1.6,s*2.4,0);}g.stroke();}
 else if(p.kind==="bead"){g.fillStyle=col;g.beginPath();g.arc(0,0,s*.9,0,7);g.fill();}
 else if(p.kind==="grain"){g.fillStyle=col;g.fillRect(-s*.7,-s*.7,s*1.4,s*1.4);}
 else{g.fillStyle=col;if(p.kind==="film")g.globalAlpha=alpha*.65;g.beginPath();p.verts.forEach((v,i)=>{const X=v[0]*s*(p.kind==="flake"?1.6:1.2),Y=v[1]*s*(p.kind==="flake"?.7:1.2);i?g.lineTo(X,Y):g.moveTo(X,Y)});g.closePath();g.fill();}
 g.restore();}
const fades=[...document.querySelectorAll("#stage [data-a]")].map(el=>({el,a:+el.dataset.a/TOT,b:el.dataset.b?+el.dataset.b/TOT:9,cap:el.classList.contains("cap")}));
const cue=document.getElementById("cue"),hdr=document.querySelector("header.top");
const RAYS=Array.from({length:40},(_,i)=>[i/40*Math.PI*2+rnd()*.08,.6+rnd()*.6]);
const FD=.25/TOT;let T0=0,lastPluck=0;
function lerpRect(a,b,m){return{x:a.x+(b.x-a.x)*m,y:a.y+(b.y-a.y)*m,w:a.w+(b.w-a.w)*m,h:a.h+(b.h-a.h)*m};}
function frame(t){
 const p=reduce?19.5/TOT:progress();
 const bp=seg(p,...T.burst),litNow=bp>=1;
 stage.style.background=css(litNow?LT:DK);stage.classList.toggle("lit",litNow);
 hdr.classList.toggle("on-dark",bp<.8&&story.getBoundingClientRect().bottom>60);
 g.clearRect(0,0,W,H);
 // opening: the blanket, then each item lights up, quickly; then the scroll cue
 const nI=SC.comps.length-1,stag=1200/Math.max(1,nI);
 SC.comps.forEach(c=>{c.rv=reduce?1:c.ground?eo(clamp((t-T0)/450,0,1)):eo(clamp((t-T0-350-c.ord*stag)/260,0,1));});
 const introDone=reduce?1:seg(t-T0,350+1200+250,350+1200+650);
 cue.style.opacity=String(introDone*(1-seg(p,.05/TOT,.25/TOT)));
 // picnic: full screen, then just below the title; it shatters in place
 const R=lerpRect(CH.sceneBig,CH.sceneT,eio(seg(p,...T.move)));
 SC.comps.forEach(c=>{c.ph=phaseOf(c,p,nI);c.xf=itemXf(c,R);if(p>=c.ph.c0)shardFrame(c);});
 if(SC.comps.length){[SC.comps[0],...SC.comps.slice(1).sort((a,b)=>(a.ph.tt-b.ph.tt)||(a.k-b.k))].forEach(c=>{const f=c.xf,ph=c.ph,K=f.k*f.s;if(c.rv<=.004)return;
   if(p<ph.c0){g.save();g.globalAlpha=c.rv;if(!c.ground){g.shadowColor=`rgba(0,0,0,${.45-.15*f.tt})`;g.shadowBlur=(16+30*f.tt)*f.s;g.shadowOffsetX=(5+14*f.tt)*f.s;g.shadowOffsetY=(7+40*f.tt)*f.s;}
    g.translate(f.X,f.Y);g.rotate(f.r);g.drawImage(c.sp,-c.bw*K/2,-c.bh*K/2,c.bw*K,c.bh*K);g.restore();return;}
   c.shards.forEach(s=>{const sa=c.rv*(1-seg(p,ph.k0+s.thr*KD*.5,ph.k0+KD));if(sa<=.004)return;g.save();g.globalAlpha=sa;
    if(!c.ground){g.shadowColor="rgba(0,0,0,.4)";g.shadowBlur=10*f.s;g.shadowOffsetY=(10+30*f.tt)*f.s;}
    g.translate(f.X,f.Y);g.rotate(f.r);g.scale(K,K);g.translate(s.px,s.py);g.rotate(s.rs*ph.st);g.drawImage(s.sp,s.lx0-s.cx,s.ly0-s.cy,s.w,s.h);g.restore();});});g.globalAlpha=1;}
 PAPERS.forEach((pp,i)=>{const n=PAPERS.length,a0=T.stack[0]+(T.stack[1]-T.stack[0])*i/n,o=eo(seg(p,a0,a0+(T.stack[1]-T.stack[0])/n*1.6))*(1-seg(p,...T.papersOut));pp.el.style.opacity=o;pp.el.style.transform=`translate(${pp.cx-pp.w/2}px,${pp.cy-pp.h/2-(1-o)*60}px) rotate(${pp.rot}rad)`;});
 fades.forEach(f=>{const o=seg(p,f.a,f.a+FD)*(1-seg(p,f.b-FD,f.b));f.el.style.opacity=o;if(f.cap){f.el.style.transform=`translateY(${(1-o)*12}px)`;f.el.style.visibility=o>0?"visible":"hidden";}});
 // radial light burst from the bulb
 const gl=seg(p,...T.glow);
 if(CH.bulb){const[bx,by,bh]=CH.bulb;
  if(gl>0&&bp<1){const gr=g.createRadialGradient(bx,by,0,bx,by,bh*(.4+.25*gl));gr.addColorStop(0,`rgba(255,236,170,${.7*gl})`);gr.addColorStop(1,"rgba(255,236,170,0)");g.fillStyle=gr;g.fillRect(0,0,W,H);}
  if(bp>0&&bp<1){const maxR=Math.max(Math.hypot(bx,by),Math.hypot(W-bx,by),Math.hypot(bx,H-by),Math.hypot(W-bx,H-by))*1.05,rr=maxR*eo(bp);
   g.save();g.lineCap="round";RAYS.forEach(([a,l])=>{g.strokeStyle=`rgba(255,226,150,${.55*(1-bp)})`;g.lineWidth=2+6*(1-bp);g.beginPath();g.moveTo(bx+Math.cos(a)*rr*.6,by+Math.sin(a)*rr*.6);g.lineTo(bx+Math.cos(a)*rr*(1+.6*l),by+Math.sin(a)*rr*(1+.6*l));g.stroke();});g.restore();
   g.fillStyle=css(LT);g.beginPath();g.arc(bx,by,rr,0,7);g.fill();
   const ring=g.createRadialGradient(bx,by,rr*.82,bx,by,rr*1.08);ring.addColorStop(0,"rgba(255,244,200,0)");ring.addColorStop(.7,`rgba(255,226,140,${.8*(1-bp*.6)})`);ring.addColorStop(1,"rgba(255,226,140,0)");g.fillStyle=ring;g.fillRect(0,0,W,H);}}
 const tU=eio(seg(p,...T.U)),tK=eio(seg(p,...T.K)),tB=eio(seg(p,...T.B)),tV=eio(seg(p,...T.Ev)),tN=eio(seg(p,...T.Nw)),tM=eio(seg(p,...T.Mp)),tZ=eio(seg(p,...T.Z));
 const rotU=(t/1000)*.02*(1-tK),ucx=CH.ucx,ucy=CH.ucy,kOn=tK*(1-tB);
 // Barker dust beyond the mandala
 if(kOn>0){const tw=t/1000;DUST.forEach(([x,y,s,c,k])=>{g.globalAlpha=kOn*(.2+.5*k)*(.75+.25*Math.sin(tw*1.3+k*40));g.fillStyle=css(c);g.fillRect(x,y,s,s);});g.globalAlpha=1;}
 // underlays
 const ev=win(p,T.Evg);
 if(ev>0){const{ROWS,COLS,gx0,gy0,cw,chh}=CH;g.globalAlpha=ev;g.strokeStyle="#c3cdd6";g.lineWidth=1;g.font=(CH.narrow?"9px":"10px")+" 'Martian Mono',monospace";g.fillStyle="#4f5a74";
  for(let i=0;i<=ROWS.length;i++){g.beginPath();g.moveTo(gx0,gy0+i*chh);g.lineTo(gx0+cw*COLS.length,gy0+i*chh);g.stroke();}
  for(let j=0;j<=COLS.length;j++){g.beginPath();g.moveTo(gx0+j*cw,gy0);g.lineTo(gx0+j*cw,gy0+chh*ROWS.length);g.stroke();}
  g.textAlign="right";g.textBaseline="alphabetic";ROWS.forEach((r2,i)=>g.fillText(r2,gx0-8,gy0+i*chh+chh/2+3));g.textAlign="center";COLS.forEach((c2,j)=>g.fillText(c2,gx0+j*cw+cw/2,gy0-10));
  g.textAlign="right";g.fillText(CH.narrow?"illustrative counts":"worldwide; illustrative cell counts until the live counts are built",gx0+cw*COLS.length,gy0+chh*ROWS.length+18);g.globalAlpha=1;}
 const mu=win(p,T.Mpu);
 if(mu>0&&MAPU){const{mx0,my0,cell}=MAPU;g.globalAlpha=mu*.9;for(let r4=0;r4<RR;r4++){const row=RAS[r4];for(let cc=0;cc<RC;cc++){const ch=row[cc];if(ch===".")continue;g.fillStyle=css(MCOL[ch]);g.fillRect(mx0+cc*cell,my0+r4*cell,cell-1,cell-1);}}g.globalAlpha=1;}
 const zu=seg(p,...T.Zu);
 if(zu>0){const{zx0,zy0,cell}=ZU;g.globalAlpha=zu;for(let r4=0;r4<ZR.length;r4++){const row=ZR[r4];for(let cc=0;cc<row.length;cc++){const ch=row[cc];if(ch===".")continue;g.fillStyle=ch==="w"?"#e7f2f1":"#cfe9e6";g.fillRect(zx0+cc*cell,zy0+r4*cell,cell-1,cell-1);}}g.globalAlpha=1;}
 // bulb outline and filament: faint glass first, yellow once it turns on
 const bo=seg(p,T.B[0]+.3/TOT,T.B[1])*(1-seg(p,T.C[0]-.1/TOT,T.C[0]+.2/TOT));
 if(bo>0&&CH.bulbPaths){const[,,,bsc,bx0,by0]=CH.bulb;g.save();g.translate(bx0,by0);g.scale(bsc,bsc);g.lineWidth=1.3/bsc;g.lineJoin="round";g.lineCap="round";
  g.strokeStyle=css(mix([215,222,235],mix(YEL,GOLD,bp),Math.max(gl,bp)),.55*bo+.35*bo*gl);CH.bulbPaths.forEach(pa=>g.stroke(pa));g.restore();}
 // springy network: nodes chase their targets on damped springs; a community gets plucked now and then
 const spr=reduce?0:win(p,T.spring);
 if(spr>.5&&t-lastPluck>2300){lastPluck=t;const k=Math.floor(Math.random()*CH.coms.length),[kx,ky]=CH.coms[k];P.forEach(q=>{if(q.com===k&&q.sOn){q.vx+=(q.sx-kx)*.09+(Math.random()-.5)*2;q.vy+=(q.sy-ky)*.09+(Math.random()-.5)*2;}});}
 // crumbs: each shard sprays small pieces of its own colours, which swirl into the cloud and fade
 if(tU<1&&p>T.pop[0]&&DEB.length){for(const d of DEB){const c=d.c,ph=c.ph,a0=ph.k0+d.thr*KD*.8;if(p<a0)continue;const al=seg(p,a0,a0+.04/TOT)*(1-tU)*c.rv;if(al<=.01)continue;
   let[x,y]=shardPt(c,d.sh,d.lx,d.ly);const dm=eo(seg(p,a0,a0+.7/TOT));x+=d.dx*dm;y+=d.dy*dm;
   x+=(CH.ucx+Math.cos(d.ua)*d.ur*CH.uRX-x)*tU;y+=(CH.ucy+Math.sin(d.ua)*d.ur*CH.uRY-y)*tU;g.globalAlpha=al;g.fillStyle=d.rgb;g.fillRect(x,y,d.s,d.s);}g.globalAlpha=1;}
 const pos=new Map(),yel=Math.max(gl,bp);
 for(const q of P){
  if(!q.c)continue;
  const st=q.cj*(1.4/TOT);
  const ph=q.c.ph,a0=ph.k0+q.thr*KD*.7;let x,y;
  if(p>=ph.c0)[x,y]=shardPt(q.c,q.sh,q.lx,q.ly);else{const f=q.c.xf,K=f.k*f.s;x=f.X+(q.lx*f.co-q.ly*f.si)*K;y=f.Y+(q.lx*f.si+q.ly*f.co)*K;}
  const dm=eo(seg(p,a0,a0+.7/TOT))*.55;
  x+=q.eo[0]*dm;y+=q.eo[1]*dm;
  let ux=q.U[0]-ucx,uy=q.U[1]-ucy;const a2=rotU*(1+q.seed),cr=Math.cos(a2),sr=Math.sin(a2);
  x+=(ucx+ux*cr-uy*sr-x)*tU;y+=(ucy+ux*sr+uy*cr-y)*tU;
  x+=(q.K[0]-x)*tK;y+=(q.K[1]-y)*tK;
  x+=(q.B[0]-x)*tB;y+=(q.B[1]-y)*tB;
  const tC=eio(seg(p-st,...T.C));
  x+=(q.C[0]-x)*tC;y+=(q.C[1]-y)*tC;
  if(q.Ev){x+=(q.Ev[0]-x)*tV;y+=(q.Ev[1]-y)*tV;}
  x+=(q.Nw[0]-x)*tN;y+=(q.Nw[1]-y)*tN;
  if(spr>0){const tx=x+Math.sin(t/900+q.seed*20)*2.5,ty=y+Math.cos(t/1100+q.seed*30)*2.5;
   if(!q.sOn){q.sx=x;q.sy=y;q.vx=0;q.vy=0;q.sOn=true;}
   q.vx=(q.vx+(tx-q.sx)*.05)*.88;q.vy=(q.vy+(ty-q.sy)*.05)*.88;q.sx+=q.vx;q.sy+=q.vy;x+=(q.sx-x)*spr;y+=(q.sy-y)*spr;}else q.sOn=false;
  x+=(q.Mp[0]-x)*tM;y+=(q.Mp[1]-y)*tM;
  x+=(q.Z[0]-x)*tZ;y+=(q.Z[1]-y)*tZ;
  pos.set(q,[x,y]);
  const show=seg(p,a0,a0+.05/TOT);if(show<=0)continue;
  let rgb=q.rgb;
  rgb=mix(rgb,mix(YEL,GOLD,bp),yel*(1-tC));
  rgb=mix(rgb,TEAL,tC);
  rgb=mix(rgb,TEAL,tV);
  rgb=mix(rgb,q.com===2?MATCH:TEAL,tN);
  rgb=mix(rgb,MCOL[q.mch]||TEAL,tM);
  rgb=mix(rgb,q.zc,tZ);
  const alpha=show;
  if(tM>.5){g.globalAlpha=alpha;g.fillStyle=css(rgb);const cc=MAPU.cell+(ZU.cell-MAPU.cell)*tZ;g.fillRect(x-cc/2,y-cc/2,cc-1,cc-1);}
  else if(tC>.65){g.globalAlpha=alpha;g.fillStyle=css(rgb);g.beginPath();g.arc(x,y,tN>.5?2.6:tV>.5?Math.max(1.2,(q.evsp||4)*.34):Math.max(1.3,CH.gap*.38),0,7);g.fill();}
  else{let f=(1+.5*tU*(1-tK))*(1+1.2*(1-seg(p,a0,a0+.35/TOT)));f+=(q.ksz-f)*tK;f+=(q.bsz-f)*tB;const r0=q.rot+q.spin*(dm+tU);const ord=Math.max(kOn,tB*(1-tC));shape(q,x,y,q.size*f,r0+(q.kth-r0)*ord,rgb,alpha,ord>.5);}
 }
 g.globalAlpha=1;
 const kl=win(p,T.Kl);
 if(kl>0){g.lineWidth=.5;g.strokeStyle=`rgba(225,228,236,${.2*kl})`;g.beginPath();KL.forEach(([a,b])=>{const A=pos.get(a),B=pos.get(b);g.moveTo(A[0],A[1]);g.lineTo(B[0],B[1]);});g.stroke();}
 const ax=win(p,T.Cax);
 if(ax>0){const{x0,x1,base,stride}=CH;g.globalAlpha=ax;g.strokeStyle="#4f5a74";g.fillStyle="#4f5a74";g.lineWidth=1;g.beginPath();g.moveTo(x0,base+3);g.lineTo(x1,base+3);g.stroke();
  g.font="10px 'Martian Mono',monospace";g.textAlign="center";g.textBaseline="alphabetic";
  YEARS.forEach((y,i)=>{if(y%10===0||y===2026){const X=x0+i*stride+stride/2;g.beginPath();g.moveTo(X,base+3);g.lineTo(X,base+8);g.stroke();g.fillText(y,X,base+20);}});g.globalAlpha=1;
  const n=ANN.length,aw=(T.Ann[1]-T.Ann[0])/n,out=1-seg(p,T.Cax[2],T.Cax[3]);ANN.forEach((a,i)=>drawAnn(a,seg(p,T.Ann[0]+i*aw,T.Ann[0]+(i+1)*aw)*out));}
 const nl=win(p,T.Nwl);
 if(nl>0){g.lineWidth=.5;g.strokeStyle=`rgba(23,32,58,${.22*nl})`;g.beginPath();NL.forEach(([a,b])=>{const A=pos.get(a),B=pos.get(b);g.moveTo(A[0],A[1]);g.lineTo(B[0],B[1]);});g.stroke();}
 requestAnimationFrame(frame);
}
function fitContain(nw,nh,box){const s=Math.min(box.w/nw,box.h/nh),w=nw*s,h=nh*s;return{x:box.x+(box.w-w)/2,y:box.y+(box.h-h)/2,w,h};}
const stackEl=document.getElementById("stack");const PAPERS=[];
function placeStack(box){const imgs=[...stackEl.querySelectorAll("img")];const pr=rng(21);const n=imgs.length;const ph=Math.min(box.h*.62,box.w*.5),pw=ph*.773;PAPERS.length=0;
 const y=box.y+box.h/2;imgs.forEach((im,i)=>{const t=n>1?i/(n-1):.5;const cx=box.x+pw/2+12+t*(box.w-pw-24)+(pr()-.5)*16,cy=y+(pr()-.5)*box.h*.06,rot=(pr()-.5)*.3;
  im.style.width=pw+"px";im.style.height=ph+"px";PAPERS.push({el:im,cx,cy,w:pw,h:ph,rot});});}
async function start(){await Promise.all([...stackEl.querySelectorAll("img"),scene,itemsImg].map(i=>i.decode().catch(()=>{})));
 compose();layout();T0=performance.now();requestAnimationFrame(frame);}
if(document.fonts&&document.fonts.ready)document.fonts.ready.then(start);else addEventListener("load",start);
addEventListener("resize",()=>layout());
