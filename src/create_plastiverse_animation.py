#!/usr/bin/env python3
"""Animate the supplied Plastiverse Live raster logo without redrawing its artwork.

Outputs: a full-resolution H.264 MP4, optimized GIF, animated WebP and a six-frame storyboard.
Dependencies: numpy, opencv-python, Pillow, ffmpeg on PATH.
Usage:
    python create_plastiverse_animation.py --input logo.png --output-dir .
"""
import argparse
import math
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS=24
DURATION=7.0
SEED=92187

def smooth(a):
    a = np.clip(a,0.0,1.0)
    return a*a*(3.-2.*a)

def interval(t, t0, t1):
    return float(smooth((t-t0)/(t1-t0)))

def shape_mask(w,h,points):
    out=Image.new('L',(w,h),0)
    ImageDraw.Draw(out).polygon(points,fill=255)
    return np.array(out)>0

def circle_mask(w,h,cx,cy,r):
    yy,xx=np.ogrid[:h,:w]
    return (xx-cx)**2+(yy-cy)**2<=r*r

def load_layers(path):
    src=np.array(Image.open(path).convert('RGB'))
    h,w=src.shape[:2]
    assert h==w, 'This composition assumes a square logo'
    k=w/1254.
    # Defining broad spatial masks from the exact original image preserves all the edges/text.
    scale=lambda p: (round(p[0]*k),round(p[1]*k))
    left=shape_mask(w,h,[scale(p) for p in [(0,0),(755,0),(730,140),(690,220),(645,350),(625,430),(610,500),(610,650),(600,888),(0,888)]])
    flow=shape_mask(w,h,[scale(p) for p in [(454,555),(514,498),(680,471),(785,458),(831,452),(867,469),(870,508),(785,524),(660,553),(528,619),(454,618)]])
    hub=circle_mask(w,h,round(855*k),round(478*k),round(117*k))
    illustration=np.zeros((h,w),bool); illustration[:round(898*k),:]=True
    # The crossfading pieces are mutually exclusive, avoiding double-bright pixels.
    hub &= illustration
    flow &= illustration & ~hub
    left &= illustration & ~flow & ~hub
    # Keep the entire database badge in the later knowledge-network reveal,
    # rather than revealing a clipped yellow crescent during the debris phase.
    left &= ~circle_mask(w,h,round(697*k),round(297*k),round(85*k))
    network=illustration & ~left & ~flow & ~hub
    colored=src.max(axis=2)>11
    left &=colored; flow &=colored; hub &=colored; network &=colored

    # Component segmentation distinguishes existing pictograms from free debris.
    n,labels,stats,cent=cv2.connectedComponentsWithStats(left.astype(np.uint8),8)
    rng=np.random.default_rng(SEED)
    debris=[]; icons=[]
    for i in range(1,n):
        x,y,ww,hh,area=map(int,stats[i]);
        if area<6: continue
        center=(x+ww*.5,y+hh*.5)
        # Recognize pictograms by original position without altering their geometry.
        is_icon=(
            (191*k<center[0]<349*k and 330*k<center[1]<455*k and area>600*k*k) or
            (418*k<center[0]<555*k and 221*k<center[1]<352*k and area>850*k*k) or
            (191*k<center[0]<304*k and 546*k<center[1]<701*k and area>700*k*k) or
            (433*k<center[0]<554*k and 691*k<center[1]<853*k and area>700*k*k) or
            (506*k<center[0]<646*k and 299*k<center[1]<448*k and area>750*k*k)
        )
        # Crop exact pixel colors of the source and component alpha mask.
        m=(labels[y:y+hh,x:x+ww]==i)
        patch=src[y:y+hh,x:x+ww].copy()
        obj={"x":x,"y":y,"w":ww,"h":hh,"patch":patch,"mask":m,
             "dx":float(rng.uniform(-70,70)*k),"dy":float(rng.uniform(-55,55)*k),
             "angle":float(rng.uniform(0,math.pi*2)), "jitter":float(rng.uniform(.0,.55)),
             "delay":float(rng.uniform(.22,1.12))}
        if is_icon:
            obj['delay']=float(rng.uniform(1.18,1.70))
            icons.append(obj)
        else:
            debris.append(obj)
    return src,flow,hub,network,debris,icons

def paste_object(frame,obj,t,icon=False):
    x,y,ww,hh=obj['x'],obj['y'],obj['w'],obj['h']
    delay=obj['delay']
    start=interval(t,delay,delay+(.55 if icon else .40))
    if start <=0: return
    opacity=start
    move=1.-smooth((t-delay)/(.75 if icon else 1.04))
    dx=obj['dx']*move; dy=obj['dy']*move
    # A little rotational / diagonal easing gives visual life without changing the assets.
    dx+=math.sin(obj['angle']+t*4)*9*move
    dy+=math.cos(obj['angle']+t*3)*7*move
    xx=x+round(dx); yy=y+round(dy)
    H,W=frame.shape[:2]; x0=max(0,xx);y0=max(0,yy);x1=min(W,xx+ww);y1=min(H,yy+hh)
    if x1<=x0 or y1<=y0:return
    px0=x0-xx;py0=y0-yy;pw=x1-x0;ph=y1-y0
    mask=obj['mask'][py0:py0+ph,px0:px0+pw]
    patch=obj['patch'][py0:py0+ph,px0:px0+pw]
    dest=frame[y0:y1,x0:x1]
    if opacity>=.999:
        dest[mask]=patch[mask]
    else:
        dest[mask]=np.uint8(patch[mask]*opacity)

def partial_region(frame,source,mask,alpha):
    if isinstance(alpha,float):
        if alpha<=0:return
        if alpha>=.999: frame[mask]=source[mask]
        else: frame[mask]=np.uint8(source[mask]*alpha)
    else:
        valid=mask & (alpha>0)
        frame[valid]=np.uint8(source[valid]*alpha[valid,None])

def render(t,data):
    src,flow,hub,net,debris,icons=data
    h,w=src.shape[:2]; k=w/1254.
    out=np.zeros_like(src)
    # The publication deluge takes form, left intact after it resolves.
    for item in debris: paste_object(out,item,t)
    for item in icons: paste_object(out,item,t,icon=True)

    # Smooth reveal of existing source strokes, travelling left-to-right.
    # This is not a new redraw and retains the pixel-exact result at hold.
    if t>=2.0:
        front=475*k + 440*k*interval(t,2.08,3.22)
        feather=72*k
        xs=np.arange(w)[None,:]
        xalpha=np.clip((front-xs)/feather+.5,0,1).astype(np.float32)
        xalpha=smooth(xalpha)
        # Vectorized masked assignment only in local wedge.
        valid=flow & (xalpha>0)
        if np.any(valid):
            coeff=np.broadcast_to(xalpha,(h,w))[valid]
            out[valid]=np.uint8(src[valid]*coeff[:,None])

    # Compact yellow hub grows from the center, including its spoke/ray geometry.
    if t>=2.90:
        cx,cy=855*k,478*k
        radius=126*k*interval(t,2.94,3.49)
        yy,xx=np.ogrid[:h,:w]
        rr=(xx-cx)**2+(yy-cy)**2
        partial_region(out,src,hub,(rr <= radius*radius) if radius>0 else np.zeros((h,w),bool))

    # Network progressively grows along graph distance from central synthesis hub.
    if t>=3.38:
        cx,cy=855*k,478*k
        yy,xx=np.ogrid[:h,:w]
        distance=np.sqrt((xx-cx)**2+(yy-cy)**2)
        radius=(24+665*interval(t,3.38,4.88))*k
        radial=smooth(np.clip((radius-distance)/(46*k)+.5,0,1)).astype(np.float32)
        valid=net & (radial>.005)
        if np.any(valid):
            coeff=radial[valid]
            out[valid]=np.uint8(src[valid]*coeff[:,None])

    # Original exact typography appears only after the scientific system is organized.
    y0=round(912*k);y1=round(1021*k)
    header=interval(t,4.48,5.04)
    out[y0:y1]=np.uint8(src[y0:y1]*header)
    s0=round(1035*k);s1=round(1109*k)
    subtitle=interval(t,4.77,5.28)
    out[s0:s1]=np.uint8(src[s0:s1]*subtitle)

    # Switch to pixel-identical original at end of assembly. No generative drift.
    if t>=5.27:
        out=src.copy()

    # Gentle pulse at full resolution; no blur/glow or uncontrolled diffusion.
    if 5.37<=t<=5.99:
        progress=(t-5.37)/.62
        alpha=.29*math.sin(math.pi*progress)
        radius=(49+17*progress)*k
        center=(round(855*k),round(478*k))
        tmp=out.copy()
        cv2.circle(tmp,center,round(radius),(255,244,154),max(1,round(2.4*k)),cv2.LINE_AA)
        out=cv2.addWeighted(out,1-alpha,tmp,alpha,0)

    # Soft full-frame fade, producing a deliberate and seamless black-to-black loop.
    fade=1.-interval(t,6.22,6.96)
    if fade<1: out=np.uint8(out*fade)
    return out

def font_path(bold=False):
    paths=(["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    return next((p for p in paths if os.path.exists(p)),None)

def make_storyboard(data,path):
    stamps=[.9,1.85,2.75,3.43,4.35,5.55]
    titles=["01  PUBLICATION DELUGE","02  FRAGMENTED EVIDENCE","03  SYNTHESIS STREAMS", "04  POINT OF INSIGHT","05  KNOWLEDGE GRAPH","06  PLASTIVERSE LIVE"]
    tile=500; margin=24; cap=68
    board=Image.new('RGB',(tile*3+margin*4,(tile+cap)*2+margin*3),(12,15,19))
    draw=ImageDraw.Draw(board)
    font=ImageFont.truetype(font_path(True),21)
    small=ImageFont.truetype(font_path(),15)
    for ix,(stamp,label) in enumerate(zip(stamps,titles)):
        img=Image.fromarray(render(stamp,data)).resize((tile,tile),Image.Resampling.LANCZOS)
        x=margin+(ix%3)*(tile+margin); y=margin+(ix//3)*(tile+cap+margin)
        board.paste(img,(x,y))
        draw.text((x+11,y+tile+12),label,fill=(240,239,230),font=font)
        draw.text((x+11,y+tile+39),f'{stamp:.1f} s  |  keyframe',fill=(170,211,204),font=small)
    board.save(path,optimize=True)

def generate(args):
    dest=Path(args.output_dir);dest.mkdir(parents=True,exist_ok=True)
    data=load_layers(args.input)
    src=data[0];H,W=src.shape[:2]
    print(f'Loaded {W}x{H} source; {len(data[-2])} fragments and {len(data[-1])} icon parts',flush=True)
    make_storyboard(data,dest/'plastiverse_live_storyboard.png')

    mp4=dest/'plastiverse_live_high_res.mp4'
    command=['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo',
             '-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),
             '-i','-','-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',
             '-movflags','+faststart',str(mp4)]
    writer=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        total=int(FPS*DURATION)
        for i in range(total):
            t=i/FPS
            frame=render(t,data)
            writer.stdin.write(frame.tobytes())
            if i%48==0:print(f'Rendered {i}/{total} video frames',flush=True)
    finally:
        writer.stdin.close()
    error=writer.stderr.read().decode(); status=writer.wait()
    if status!=0:raise RuntimeError('ffmpeg encoding error: '+error)
    print('MP4:',mp4,mp4.stat().st_size,flush=True)

    # Animated WebP is the better browser-native high-res looping asset.
    webp=dest/'plastiverse_live_loop.webp'
    cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(mp4),'-vf','fps=18,scale=1080:1080:flags=lanczos',
         '-loop','0','-c:v','libwebp_anim','-lossless','0','-quality','83','-compression_level','5','-an',str(webp)]
    subprocess.run(cmd,check=True)
    print('WebP:',webp,webp.stat().st_size,flush=True)
    # GIF cannot faithfully represent 24-bit colors; a generated adaptive palette reduces banding.
    gif=dest/'plastiverse_live_loop.gif'
    filtergraph='fps=12,scale=900:900:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff:max_colors=192[pal];[b][pal]paletteuse=dither=bayer:bayer_scale=3'
    cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(mp4),'-filter_complex',filtergraph,
         '-loop','0','-gifflags','+transdiff',str(gif)]
    subprocess.run(cmd,check=True)
    print('GIF:',gif,gif.stat().st_size,flush=True)
    return mp4,webp,gif

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',default='/mnt/data/image(20261118-183555).png')
    p.add_argument('--output-dir',default='/mnt/data')
    generate(p.parse_args())
