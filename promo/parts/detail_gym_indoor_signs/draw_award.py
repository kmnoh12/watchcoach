"""Original printed artwork. Coordinates in a 1500 by 1000 trim box, all outlines drawn locally."""
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
W,H=1500,1000
u,v=np.meshgrid(np.linspace(0,1,W),np.linspace(0,1,H))
FONT=ROOT/"promo/parts/fonts/NanumGothic-Bold.ttf"
APPLE=Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")


def gradient(t, stops):
    colors=[list(bytes.fromhex(c)) for _,c in stops]
    a=np.stack([np.interp(t,[s for s,_ in stops],[c[i] for c in colors]) for i in range(3)],axis=-1)
    return Image.fromarray(np.uint8(a))


def bezier(a,b,c,d,count=60):
    return [tuple((1-t)**3*a[i]+3*t*(1-t)**2*b[i]+3*t*t*(1-t)*c[i]+t**3*d[i] for i in (0,1))
            for t in np.linspace(0,1,count)]


def foil_wedge(image,edge,upper,fill):
    mask=Image.new("L",(W,H))
    outside=[(-1,-1)] if upper else [(W+1,H+1)]
    ImageDraw.Draw(mask).polygon([*edge,*outside],fill=255)
    image.paste(fill,(0,0),mask)


def star(cx,cy,r):
    return [(cx+math.sin(i*math.pi/5)*r*(.43 if i%2 else 1),
             cy-math.cos(i*math.pi/5)*r*(.43 if i%2 else 1)) for i in range(10)]


def laurel(image):
    d=ImageDraw.Draw(image)
    for side in (-1,1):
        def stem(t):
            return np.array([750+side*(435+100*math.sin(math.pi*t)-18*t+11*math.sin(2*math.pi*t)),800-482*t])
        d.line([tuple(stem(t)) for t in np.linspace(0,1,100)],fill="#9f7943",width=2)
        for j,t in enumerate(np.linspace(.085,.94,6)):
            for inward,delta in [(False,0),(True,.045)]:
                base=stem(t+delta)
                direction=np.array([side*(-1 if inward else 1)*(.74 if inward else .72),
                                    -.65 if inward else -1.0])
                direction=direction/np.linalg.norm(direction)
                length=(92-37*t)*(1.05 if inward else 1.13)
                tip=base+length*direction
                perp=np.array([-direction[1],direction[0]])
                width=length*.29
                mid=base+direction*length*.51
                left=bezier(base,mid+width*perp,mid+1.13*width*perp,tip,21)
                right=bezier(tip,mid-width*perp*.82,mid-perp*width,base,21)
                shade=['#c79a58','#c08b48','#d2aa6e','#bb8747'][(j+inward)%4]
                d.polygon(left+right,fill=shade)
                d.polygon(right+[tuple(mid+perp*1.6)],fill='#c99b5c')
                d.line(bezier(base,mid+perp*2,mid+direction*length*.10,tip,17)[:-4],fill='#b58c53',width=1)


def badge(image,year,quarter):
    d=ImageDraw.Draw(image)
    cx,cy,r=1590,143,116
    image_width=image.width
    offset=cx-1335
    def ribbon(points,color):
        d.polygon([(x+offset,y+9) for x,y in points], fill=color)
    ribbon([(1268,192),(1323,208),(1290,290),(1272,262),(1233,273)],"#8b3835")
    ribbon([(1342,211),(1400,191),(1430,271),(1391,262),(1375,293)],"#a54940")
    ribbon([(1268,192),(1290,260),(1301,231)],"#692d31")
    ribbon([(1381,223),(1400,191),(1405,255)],"#803332")
    pts=[]
    for t in np.linspace(0,2*math.pi,640):
        rad=r+4.0*math.cos(16*t)
        pts.append((cx+rad*math.cos(t),cy+rad*math.sin(t)))
    seal=Image.new("L",image.size)
    ImageDraw.Draw(seal).polygon(pts,fill=255)
    foil=gradient(((np.arange(image_width)[None,:]-cx)/r+(np.arange(H)[:,None]-cy)/r+2)/4,
                  [(0,"ae7639"),(.34,"dbb364"),(.49,"f0ce85"),(.69,"a6773e"),(1,"d9ab64")])
    image.paste(foil,(0,0),seal)
    d.ellipse((cx-85,cy-85,cx+85,cy+85),fill="#26232b",outline="#b68e4e",width=4)
    d.ellipse((cx-78,cy-78,cx+78,cy+78),outline="#4a3a31",width=1)
    for k in (-1,0,1):
        for sy in (-1,1):
            d.polygon(star(cx+k*21,cy+sy*52,7 if k else 10),fill="#e7c181")
    for text,dy,size in [(year,-14,35),(quarter,20,32)]:
        d.text((cx,cy+dy),text,font=ImageFont.truetype(str(FONT),size),anchor="mm",fill="#e7c78c")


def make(header,headline,subhead,year,quarter):
    image=gradient(.50*u+.50*(1-v),[(0,"f2e5cd"),(.48,"faf1df"),(1,"f7f1e6")])
    navy=gradient(.80*u+.20*v,[(0,"24273e"),(.20,"383b64"),(.65,"232741"),(1,"292b46")])
    dot=ImageDraw.Draw(navy)
    for y in range(0,H,11):
        for x in range((y//11%2)*5,W,11):
            dot.ellipse((x,y,x+1,y+1),fill="#414265")
    for top in (True,False):
        for dx,dy,fill in [
            (0,0,'#c9beb0'),
            (15,6,'#c79c61'),(39,16,'#ebc580'),
            (85,32,'#b9874b'),(126,49,'#d7aa69'),(166,66,navy)]:
            if top:
                edge=bezier((0,617-dy),(91,327-dy),(299,47),(914-dx*2.45,0))
            else:
                edge=bezier((1500,418+dy),(1410,664+dy),(1220,910),(907+dx*1.9,1000))
            if isinstance(fill,str) and dx:
                tint=np.array(list(bytes.fromhex(fill[1:])))
                def hex_tone(factor):
                    return bytes(np.clip(tint*factor,0,255).astype(np.uint8)).hex()
                fill=gradient(.68*u+.32*v,[(0,hex_tone(.74)),(.18,hex_tone(1.08)),(.45,hex_tone(.87)),
                                             (.71,hex_tone(1.12)),(1,hex_tone(.81))])
            foil_wedge(image,edge,top,fill)
    laurel(image)
    image=image.resize((1800,1000),Image.Resampling.LANCZOS)
    badge(image,year,quarter)
    d=ImageDraw.Draw(image)
    def lettering(text,cx,y,width,height,heavy=False):
        font=ImageFont.truetype(str(APPLE if APPLE.exists() else FONT),200,index=6 if APPLE.exists() else 0)
        ink=Image.new("L",(math.ceil(font.getlength(text))+50,280))
        ImageDraw.Draw(ink).text((20,8),text,font=font,fill=255,stroke_width=4 if heavy else 1,stroke_fill=255)
        ink=ink.crop(ink.getbbox()).resize((width,height),Image.Resampling.LANCZOS)
        image.paste("#232435" if heavy else "#25242a",(cx-width//2,y),ink)
    lettering(header,895,208,884,82)
    lettering(headline,902,376,976,142,True)
    lettering(subhead,904,565,484,81,True)
    for x in [616,1191]:
        d.polygon(star(x,608,16),fill="#bf9151")
    image.save(HERE/"D06_project.jpg",quality=94,subsampling=0,optimize=True)


def achievement():
    make("바디프로필 프로젝트","회원 성과 전시","워치코치 짐","2026","4분기")


if __name__=="__main__":
    achievement()
