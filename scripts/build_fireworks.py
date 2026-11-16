"""Bake independent firework trajectories into the existing GitHub SVG banners.

Run: python scripts/build_fireworks.py
Check without writing: python scripts/build_fireworks.py --check
The traced artwork stays in the SVGs; no animation library or network is needed.
"""
from pathlib import Path
from collections import defaultdict
from copy import deepcopy
import argparse
import hashlib
import json
import math
import random
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
NS="http://www.w3.org/2000/svg"
ET.register_namespace("",NS)
LOOP=9.6
BLAST=1.32
PEAK=.65
Q=sorted(set([round(i*.1,3) for i in range(36)]+[PEAK,.85]))
def tag(x):return "{"+NS+"}"+x
def num(x):return f"{x:.5f}".rstrip("0").rstrip(".") or "0"
def fmt(v):return " ".join(num(x) for x in v) if isinstance(v,(tuple,list)) else num(v) if isinstance(v,(float,int)) else str(v)
def anim(parent,attribute,values,times,start,kind="animate",duration=LOOP,**extra):
    assert len(values)==len(times) and times[0]==0 and times[-1]==duration and times==sorted(times)
    attrs={"attributeName":attribute,"values":";".join(fmt(v) for v in values),
           "keyTimes":";".join(num(t/duration) for t in times),"dur":num(duration)+"s",
           "begin":num(start)+"s","repeatCount":"indefinite"}
    attrs.update(extra)
    return ET.SubElement(parent,tag(kind),attrs)
def trans(parent,kind,values,times,start):
    return anim(parent,"transform",values,times,start,"animateTransform",type=kind)
def points(path):
    return [tuple(map(float,p)) for p in re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)",path.attrib["d"])]
def art_paths(group):
    marked=[deepcopy(p) for p in group.iter(tag("path")) if p.attrib.get("data-artwork")=="true"]
    if marked:return marked
    burst=next(e for e in group if e.attrib.get("data-stage")=="burst")
    return [deepcopy(p) for p in burst.iter(tag("path"))]
def signature(paths):
    items=sorted((p.attrib["d"],p.attrib["fill"],p.attrib.get("fill-rule","")) for p in paths)
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()
def flight(q,px,py,k,g,delay=0):
    elapsed=max(0,q-delay)
    peak=PEAK-delay
    reach=(1-math.exp(-k*elapsed))/(1-math.exp(-k*peak))
    return px*reach,(py-.5*g*peak*peak)*reach+.5*g*elapsed*elapsed
def size(q,delay):
    if q<=delay:return .025
    if q<=PEAK:
        u=(q-delay)/(PEAK-delay)
        return .025+.975*(1-(1-u)**1.8)
    if q<=.85:return 1
    return max(.08,math.exp(-.7*(q-.85)))
def timeline(samples,initial=None):
    return [0,BLAST-.001]+[BLAST+q for q in Q]+[LOOP], [samples[0] if initial is None else initial]*2+samples+[samples[-1]]
def motion(parent,path,keys,times,start):
    assert len(keys)==len(times)
    return ET.SubElement(parent,tag("animateMotion"),{
        "path":path,"keyPoints":";".join(num(k) for k in keys),
        "keyTimes":";".join(num(t/LOOP) for t in times),"calcMode":"linear",
        "dur":num(LOOP)+"s","begin":num(start)+"s","repeatCount":"indefinite"})
def launch(group,defs,name,cy,scale,start,dark):
    warm="#ffdb9b" if dark else "#c39847"
    core="#fff2cd" if dark else "#dda947"
    gradient=ET.SubElement(defs,tag("linearGradient"),{"id":"comet-"+name,"gradientUnits":"userSpaceOnUse","x1":"0","y1":"0","x2":"0","y2":num(66/scale)})
    for offset,opacity in [("0","1"),(".3",".7"),("1","0")]:
        ET.SubElement(gradient,tag("stop"),{"offset":offset,"stop-color":warm,"stop-opacity":opacity})
    rocket=ET.SubElement(group,tag("g"),{"data-stage":"launch","opacity":"0"})
    anim(rocket,"opacity",[0,1,1,0,0],[0,.1,1.275,BLAST,LOOP],start)
    sy=(340-cy)/scale
    path=f"M{num(-20/scale)} {num(sy)} C{num(-10/scale)} {num(sy*.6)} {num(5/scale)} {num(sy*.1)} 0 0"
    motion(rocket,path,[0,.68,.91,1,1],[0,.66,1.07,1.29,LOOP],start)
    ET.SubElement(rocket,tag("path"),{"d":f"M0 0 Q{num(-2/scale)} {num(28/scale)} {num(-6/scale)} {num(66/scale)}",
        "fill":"none","stroke":"url(#comet-"+name+")","stroke-width":num(2.4/scale),"stroke-linecap":"round"})
    ET.SubElement(rocket,tag("circle"),{"r":num(5/scale),"fill":warm,"opacity":".16"})
    ET.SubElement(rocket,tag("circle"),{"r":num(2/scale),"fill":core})
    for i in range(4):
        ember=ET.SubElement(rocket,tag("circle"),{"cx":num((i%2*2-1)*1.3/scale),"cy":num((10+i*11)/scale),"r":num(.7/scale),"fill":warm})
        anim(ember,"opacity",[.15,.85,.15],[0,.19,.38],start+i*.08,duration=.38)
    flash=ET.SubElement(group,tag("circle"),{"data-stage":"flash","r":"0","fill":core,"opacity":"0"})
    anim(flash,"r",[0,0,13/scale,27/scale,27/scale],[0,BLAST-.02,BLAST+.055,BLAST+.21,LOOP],start)
    anim(flash,"opacity",[0,0,.85,0,0],[0,BLAST-.02,BLAST+.025,BLAST+.21,LOOP],start)
def sparks(group,paths,name,scale,start):
    rng=random.Random(name+"-embers")
    radius=max(math.hypot(x,y) for p in paths for x,y in points(p))
    palette=list(dict.fromkeys(p.attrib["fill"] for p in paths))
    cloud=ET.SubElement(group,tag("g"),{"data-stage":"flying-embers","opacity":"0"})
    anim(cloud,"opacity",[0,0,1,1,.88,.48,0,0],
         [0,BLAST-.001,BLAST+.025,BLAST+.8,BLAST+1.7,BLAST+2.8,BLAST+3.5,LOOP],start)
    count=32 if name=="candy" else 22
    for i in range(count):
        angle=math.tau*i/count+rng.uniform(-.055,.055)
        r=radius*rng.uniform(.62,1.08)
        px,py=math.cos(angle)*r,math.sin(angle)*r
        k=rng.uniform(1.6,2.7);g=rng.uniform(15,24)/scale
        locations=[flight(q,px,py,k,g) for q in Q]
        lengths=[0]
        for a,b in zip(locations,locations[1:]):lengths.append(lengths[-1]+math.dist(a,b))
        fractions=[v/lengths[-1] for v in lengths]
        path="M"+" L".join(fmt(p) for p in locations)
        times,keypoints=timeline(fractions)
        color=palette[i%len(palette)]
        trail=ET.SubElement(cloud,tag("path"),{"d":path,"pathLength":"100","fill":"none","stroke":color,
            "stroke-width":num(rng.uniform(.75,1.15)/scale),"stroke-linecap":"round",
            "stroke-dasharray":"6 100","stroke-dashoffset":"6","opacity":".7"})
        anim(trail,"stroke-dashoffset",[6-v*100 for v in keypoints],times,start)
        head=ET.SubElement(cloud,tag("g"))
        motion(head,path,keypoints,times,start)
        ET.SubElement(head,tag("circle"),{"r":num(2.2/scale),"fill":color,"opacity":".15"})
        dot=ET.SubElement(head,tag("circle"),{"r":num(.95/scale),"fill":color})
        blink=rng.uniform(.38,.66)
        anim(dot,"opacity",[1,.25,1],[0,blink*.5,blink],start+rng.uniform(0,.3),duration=blink)
        # A smaller following ember gives every jet a visibly detached, fading tail.
        follower=ET.SubElement(cloud,tag("circle"),{"r":num(.55/scale),"fill":color,"opacity":".4"})
        lagged=[max(0,q-.13) for q in Q]
        lag_points=[]
        for q in lagged:
            j=max(i for i,t in enumerate(Q) if t<=q)
            if j==len(Q)-1:lag_points.append(1)
            else:
                f=(q-Q[j])/(Q[j+1]-Q[j])
                lag_points.append(fractions[j]+(fractions[j+1]-fractions[j])*f)
        _,lag_keys=timeline(lag_points)
        motion(follower,path,lag_keys,times,start)
def artwork(group,paths,name,scale,start):
    buckets=defaultdict(list)
    for p in paths:
        vertices=points(p)
        px=(min(x for x,y in vertices)+max(x for x,y in vertices))/2
        py=(min(y for x,y in vertices)+max(y for x,y in vertices))/2
        r=math.hypot(px,py)
        key=(-1,0) if r<24 else (int((math.atan2(py,px)%math.tau)/math.tau*24),int(r>120))
        p.set("data-artwork","true")
        buckets[key].append(p)
    layer=ET.SubElement(group,tag("g"),{"data-stage":"burst"})
    for key,items in sorted(buckets.items()):
        rng=random.Random(name+str(key))
        vertices=[v for p in items for v in points(p)]
        px=(min(x for x,y in vertices)+max(x for x,y in vertices))/2
        py=(min(y for x,y in vertices)+max(y for x,y in vertices))/2
        delay=rng.uniform(0,.065);k=rng.uniform(1.8,2.8);g=rng.uniform(15,23)/scale
        if key[0]==-1:delay=0
        piece=ET.SubElement(layer,tag("g"),{"data-stage":"independent-ray","opacity":"0"})
        end=rng.uniform(2.55,3.45)
        anim(piece,"opacity",[0,0,1,1,.8,.1,0,0],
             [0,BLAST+delay,BLAST+delay+.07,BLAST+.8,BLAST+1.3,BLAST+end-.15,BLAST+end,LOOP],start)
        moving=ET.SubElement(piece,tag("g"))
        locations=[flight(q,px,py,k,g,delay) for q in Q]
        times,values=timeline(locations)
        trans(moving,"translate",values,times,start)
        rotating=ET.SubElement(moving,tag("g"))
        spin=rng.uniform(-11,11)
        angles=[0 if q<.85 else spin*((q-.85)/(3.5-.85)) for q in Q]
        _,values=timeline(angles)
        trans(rotating,"rotate",values,times,start)
        shrinking=ET.SubElement(rotating,tag("g"))
        _,values=timeline([size(q,delay) for q in Q])
        trans(shrinking,"scale",values,times,start)
        centered=ET.SubElement(shrinking,tag("g"),{"transform":f"translate({num(-px)} {num(-py)})"})
        centered.extend(items)
        assert math.dist(flight(PEAK,px,py,k,g,delay),(px,py))<1e-7
        assert size(PEAK,delay)==1 and size(2.8,delay)<.3
    return len(buckets)
def check(root):
    ids=[e.attrib["id"] for e in root.iter() if "id" in e.attrib]
    assert len(ids)==len(set(ids))
    text=ET.tostring(root,encoding="unicode")
    assert set(re.findall(r"url\(#([^)]+)\)",text)).issubset(ids)
    assert len(root.findall(".//"+tag("rect")))==2
    for a in root.iter():
        if a.tag not in (tag("animate"),tag("animateTransform"),tag("animateMotion")):continue
        if "keyTimes" not in a.attrib:continue
        times=[float(x) for x in a.attrib["keyTimes"].split(";")]
        values=a.attrib.get("values",a.attrib.get("keyPoints","")).split(";")
        assert len(times)==len(values) and times==sorted(times) and times[0]==0 and times[-1]==1
    groups=[g for g in root if "data-reference" in g.attrib]
    assert len(groups)==4
    for g in groups:
        assert len(art_paths(g))>100
        for stage in ("launch","flash","flying-embers","burst"):
            assert any(e.attrib.get("data-stage")==stage for e in g)
        assert len([e for e in g.iter() if e.attrib.get("data-stage")=="independent-ray"])>=15
    for q in (0,.12,PEAK,1.4,2.8):
        assert all(math.isfinite(v) for v in flight(q,90,-140,2.2,40))
    assert flight(0,90,-140,2.2,40)==(0,0)
    assert math.dist(flight(PEAK,90,-140,2.2,40),(90,-140))<1e-8
    assert flight(2.8,90,-140,2.2,40)[1]>flight(1.8,90,-140,2.2,40)[1]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    for filename,dark in (("greeting.svg",False),("greeting-dark.svg",True)):
        file=ROOT/"assets"/filename
        root=ET.parse(file).getroot()
        if not args.check:
            defs=root.find(tag("defs"))
            for el in list(defs):
                if el.attrib.get("id","").startswith("comet-"):defs.remove(el)
            groups=[g for g in root if "data-reference" in g.attrib]
            for i,old in enumerate(groups):
                paths=art_paths(old);expected=signature(paths)
                new=ET.Element(tag("g"),dict(old.attrib))
                cy,scale=map(float,re.search(r"translate\([\d.]+ ([\d.]+)\) scale\(([\d.]+)\)",old.attrib["transform"]).groups())
                name=old.attrib["data-reference"];start=i*LOOP/4
                launch(new,defs,name,cy,scale,start,dark)
                sparks(new,paths,name,scale,start)
                count=artwork(new,paths,name,scale,start)
                assert signature(art_paths(new))==expected
                index=list(root).index(old);root.remove(old);root.insert(index,new)
                print(filename,name,count,"independent rays")
            root.find(tag("desc")).text="意外降临的美好里，迸发的那一束灵感与触动的火花。带火星尾迹升空后快速炸开，每束彩条沿独立轨迹减速、下坠，细碎余烬闪烁消失。"
        check(root)
        if not args.check:
            for e in root.iter():e.tail=None
            ET.indent(root,space="  ")
            file.write_bytes(ET.tostring(root,encoding="utf-8")+b"\n")
        print(filename,"motion checks passed")
if __name__=="__main__":main()
