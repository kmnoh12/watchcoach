"""Build the six L1 interior signs on the saved gym layout. See review/README.md."""
import argparse
import hashlib
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work/detail3/indoor_signs"
ART = ROOT / "promo/parts/detail_gym_indoor_signs"
SOURCE = ROOT / "promo/scenes/scene_gym.blend"
OUTPUT = WORK / "candidate.blend"
GROUP = "L1 Indoor Signs"
PREFIX = "L1."
SYSTEM = Path("/System/Library/Fonts/Supplemental")
SANS = SYSTEM / "Arial Bold.ttf"
KO = ROOT / "promo/parts/fonts/NanumGothic-Bold.ttf"
UP = Vector((0,0,1))


def obj(name,data,parent=None,loc=(0,0,0)):
    ob=bpy.data.objects.new(PREFIX+name,data)
    bpy.data.collections[GROUP].objects.link(ob)
    ob.parent=parent
    ob.location=loc
    return ob


def anchor(name,loc,normal):
    n=Vector(normal)
    right=UP.cross(n)
    ob=obj(name,None,loc=loc)
    ob.rotation_euler=Matrix((right,UP,n)).transposed().to_euler()
    ob.empty_display_size=.03
    return ob


def mat(name,color,rough=.5,metal=0,emission=0):
    m=bpy.data.materials.new(PREFIX+name)
    m.diffuse_color=(*color,1)
    bs=next(n for n in m.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    for socket,value in [("Base Color",(*color,1)),("Roughness",rough),("Metallic",metal),
                         ("Emission Color",(*color,1)),("Emission Strength",emission)]:
        bs.inputs[socket].default_value=value
    return m


def print_mat(name,path):
    m=mat(name,(.82,.8,.75),.67)
    im=bpy.data.images.load(str(path),check_existing=False)
    im.name=PREFIX+path.name
    im.pack()
    tex=m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image=im
    bs=next(n for n in m.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    m.node_tree.links.new(tex.outputs["Color"],bs.inputs["Base Color"])
    m.node_tree.nodes.active=tex
    return m


def mesh(name,vertices,faces,parent,loc,material):
    data=bpy.data.meshes.new(PREFIX+name)
    data.from_pydata(vertices,[],faces)
    data.update()
    o=obj(name,data,parent,loc)
    data.materials.append(material)
    return o


def box(name,parent,loc,dims,material,bevel=0):
    x,y,z=(v/2 for v in dims)
    verts=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
           (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    o=mesh(name,verts,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],parent,loc,material)
    if bevel:
        mod=o.modifiers.new("Soft cut edges","BEVEL")
        mod.width=bevel
        mod.segments=3
        mod.harden_normals=True
        o.modifiers.new("Flat faces","WEIGHTED_NORMAL")
    return o


def image_face(name,parent,loc,width,height,material,cols=1,rows=1,bend=None):
    verts=[]
    uv=[]
    for j in range(rows+1):
        for i in range(cols+1):
            u,v=i/cols,j/rows
            verts.append(((u-.5)*width,(v-.5)*height,bend(u,v) if bend else 0))
            uv.append((u,v))
    faces=[]
    for j in range(rows):
        for i in range(cols):
            a=j*(cols+1)+i
            faces.append((a,a+1,a+cols+2,a+cols+1))
    o=mesh(name,verts,faces,parent,loc,material)
    layer=o.data.uv_layers.new(name="Print")
    for loop in o.data.loops:
        layer.data[loop.index].uv=uv[loop.vertex_index]
    return o


def text_mesh(name,parent,center,body,font,width,depth,material,bevel=0,spacing=1):
    curve=bpy.data.curves.new(PREFIX+name,"FONT")
    curve.body=body
    curve.font=bpy.data.fonts.load(str(font),check_existing=True)
    curve.space_character=spacing
    curve.resolution_u=8
    temp=obj(name+".typeset",curve)
    # Size the ink bounds first, then set extrusion in physical metres.
    dg=bpy.context.evaluated_depsgraph_get()
    ev=temp.evaluated_get(dg)
    bb=ev.bound_box
    curve.size=width/(max(v[0] for v in bb)-min(v[0] for v in bb))
    curve.extrude=depth/2
    curve.bevel_depth=bevel
    curve.bevel_resolution=2
    dg.update()
    data=bpy.data.meshes.new_from_object(temp.evaluated_get(dg),depsgraph=dg)
    data.name=PREFIX+name
    bm=bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    bm.to_mesh(data)
    bm.free()
    data.update()
    for i in (0,1):
        midpoint=(min(v.co[i] for v in data.vertices)+max(v.co[i] for v in data.vertices))/2
        for v in data.vertices: v.co[i]-=midpoint
    bpy.data.objects.remove(temp,do_unlink=True)
    bpy.data.curves.remove(curve)
    o=obj(name,data,parent,center)
    o["lettering"]=body
    data.materials.append(material)
    return o


def rounded_path(width,height,r):
    pts=[]
    for x,y,a in [(width/2-r,height/2-r,0),(-width/2+r,height/2-r,90),
                  (-width/2+r,-height/2+r,180),(width/2-r,-height/2+r,270)]:
        for s in range(9):
            angle=math.radians(a+90*s/8)
            pts.append((x+r*math.cos(angle),y+r*math.sin(angle)))
    return pts


def inset_ring(name,parent,width,height,r,band,z,material):
    outer=rounded_path(width,height,r)
    inner=rounded_path(width-2*band,height-2*band,r-band)
    n=len(outer)
    verts=[(x,y,t) for path,t in [(outer,0),(inner,0),(outer,.0015),(inner,.0015)] for x,y in path]
    faces=[]
    for i in range(n):
        j=(i+1)%n
        faces.extend([(i,n+i,n+j,j),(2*n+i,2*n+j,3*n+j,3*n+i),(i,j,2*n+j,2*n+i),
                      (n+j,n+i,3*n+i,3*n+j)])
    return mesh(name,verts,faces,parent,(0,0,z),material)


def mirror_rules(m):
    printed=print_mat("Uncoated notice",ART/"A09_notice.jpg")
    tape=mat("Clear tape",(.82,.79,.68),.19)
    bs=next(n for n in tape.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    bs.inputs["Alpha"].default_value=.29
    tape.diffuse_color=(.76,.73,.64,.29)
    for tag,x,normal,tilt in [("Men",11.53,(-1,0,0),1.3),("Women",11.67,(1,0,0),-1.1)]:
        p=anchor("A09."+tag,(x,-10.51,1.64),normal)
        p.rotation_euler=(p.rotation_euler.to_matrix()@Matrix.Rotation(math.radians(tilt),3,"Z")).to_euler()
        def curl(u,v):
            return .0001+.0015*(1-v)**5*(.4+.6*math.cos(2*math.pi*u)**2)+.00045*math.sin(math.pi*u*3)**2*math.sin(math.pi*v)**2
        paper=image_face("A09."+tag+".Paper",p,(0,0,.00012),.297,.210,printed,20,12,curl)
        solid=paper.modifiers.new("Paper stock","SOLIDIFY")
        solid.thickness=.00017
        for side in (-1,1):
            tab=image_face(f"A09.{tag}.Tape{side}",p,(side*.102,.104,.00036),.059,.021,tape,4,3,
                           lambda u,v: .00012*(1-v)+.0001*math.sin(2*math.pi*u)**2)
            tab.rotation_euler.z=math.radians(side*8)
            tab.modifiers.new("Tape thickness","SOLIDIFY").thickness=.00005


def locker_boxes(m):
    diffuser=bpy.data.node_groups.new(PREFIX+"Locker white diffuser","ShaderNodeTree")
    diffuser.interface.new_socket(name="Surface",in_out="OUTPUT",socket_type="NodeSocketShader")
    bright=diffuser.nodes.new("ShaderNodeBsdfPrincipled")
    border=m["warm"]
    bs=next(n for n in border.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    for socket in ("Base Color","Emission Color","Emission Strength","Roughness"):
        bright.inputs[socket].default_value=bs.inputs[socket].default_value
    diffuser.links.new(bright.outputs[0],diffuser.nodes.new("NodeGroupOutput").inputs[0])
    border.node_tree.nodes.remove(bs)
    shader=border.node_tree.nodes.new("ShaderNodeGroup")
    shader.node_tree=diffuser
    border.node_tree.links.new(shader.outputs[0],next(n for n in border.node_tree.nodes if n.type=="OUTPUT_MATERIAL").inputs["Surface"])
    for label,x,hangul in [("MAN",10.95,"남자 탈의실"),("WOMAN",12.25,"여자 탈의실")]:
        tag="B03."+label
        p=anchor(tag,(x,-6.68,2.369),(0,1,0))
        box(tag+".Channel",p,(0,0,.028),(.67,.326,.056),m["metal"],.0015)
        box(tag+".Black gasket",p,(0,0,.0575),(.664,.320,.0028),m["black"],.0005)
        face=box(tag+".Mirror acrylic",p,(0,0,.0615),(.662,.318,.005),m["bronze"],.0012)
        # The lettering is a diffuser seen through reverse-engraved windows in the
        # mirrored coating. All three lines share the same emitter as the perimeter.
        front=print_mat(tag+" mirror swatch",ART/f"B03_{label}_face.jpg")
        face.data.materials.append(front)
        poly=next(f for f in face.data.polygons if f.normal.z>.99)
        poly.material_index=1
        uv=face.data.uv_layers.new(name="Engraved face")
        for li in poly.loop_indices:
            v=face.data.vertices[face.data.loops[li].vertex_index].co
            uv.data[li].uv=(v.x/.662+.5,v.y/.318+.5)
        nodes=front.node_tree.nodes
        links=front.node_tree.links
        preview=nodes.active
        mask=nodes.new("ShaderNodeTexImage")
        mask.image=bpy.data.images.load(str(ART/f"B03_{label}_inlay.png"),check_existing=False)
        mask.image.name=PREFIX+label+" engraving mask"
        mask.image.colorspace_settings.name="Non-Color"
        mask.image.pack()
        original=next(n for n in nodes if n.type=="BSDF_PRINCIPLED")
        links.remove(original.inputs["Base Color"].links[0])
        original.inputs["Base Color"].default_value=(.14,.10,.062,1)
        original.inputs["Metallic"].default_value=.88
        original.inputs["Roughness"].default_value=.075
        original.inputs["Specular IOR Level"].default_value=.25
        original.inputs["Coat Weight"].default_value=0.0
        emitter=nodes.new("ShaderNodeGroup")
        emitter.node_tree=diffuser
        mix=nodes.new("ShaderNodeMixShader")
        links.new(mask.outputs["Color"],mix.inputs[0])
        links.new(original.outputs[0],mix.inputs[1])
        links.new(emitter.outputs[0],mix.inputs[2])
        links.new(mix.outputs[0],next(n for n in nodes if n.type=="OUTPUT_MATERIAL").inputs["Surface"])
        nodes.active=preview
        face["lettering"]=f"{label} / Fitting Room / {hangul}"
        inset_ring(tag+".Light inlay",p,.615,.275,.023,.0055,.0641,m["warm"])


def stretching(m):
    p=anchor("B06.Stretch",(-7.496,-.20,2.655),(1,0,0))
    # Preserve individual channel depths and spacing across both custom E glyphs.
    word="STRETCHING ZONE"
    font=bpy.data.fonts.load(str(SANS),check_existing=True)
    widths=[]
    for char in word:
        if char==" ":
            widths.append(.070)
            continue
        c=bpy.data.curves.new(PREFIX+"measure","FONT")
        c.body=char
        c.font=font
        o=obj("measure",c)
        b=o.evaluated_get(bpy.context.evaluated_depsgraph_get()).bound_box
        widths.append(.143*(max(v[0] for v in b)-min(v[0] for v in b))/(max(v[1] for v in b)-min(v[1] for v in b)))
        bpy.data.objects.remove(o,do_unlink=True)
        bpy.data.curves.remove(c)
    gap=.020
    pos=-(sum(widths)+gap*(len(word)-1))/2
    for i,(char,w) in enumerate(zip(word,widths)):
        x=pos+w/2
        pos+=w+gap
        tag=f"B06.{i:02}.{char}"
        if char==" ": continue
        if char=="E":
            for j,h in enumerate([-.059,0,.059]):
                width=w*(.86 if j==1 else 1)
                px=x-(w-width)/2
                box(tag+f".Return{j}",p,(px,h,.014),(width,.025,.028),m["black"],.0008)
                box(tag+f".Lens{j}",p,(px,h,.0296),(width-.001,.024,.0032),m["white"],.00065)
        else:
            o=text_mesh(tag,p,(x,0,.0155),char,SANS,w,.031,m["black"],.00055)
            o.data.materials.append(m["white"])
            for f in o.data.polygons:
                if f.normal.z>.68: f.material_index=1
    # The separate concealed linear fixture follows the top of the mirror, not the lettering.
    box("B06.Mirror light channel",p,(0,-.2275,.018),(2.42,.014,.036),m["black"],.001)
    box("B06.Mirror amber lens",p,(0,-.2195,.024),(2.39,.002,.017),m["amber"],.0005)
    lamp=bpy.data.lights.new(PREFIX+"Mirror edge wash","AREA")
    lamp.shape="RECTANGLE"
    lamp.size=2.32
    lamp.size_y=.028
    lamp.energy=9.0
    lamp.color=(1,.68,.28)
    ob=obj("B06.Mirror graze",lamp,p,(0,-.214,.033))
    ob.rotation_euler=Vector((0,1,-.42)).to_track_quat("-Z","Y").to_euler()


def upper_slogan(m):
    p=anchor("C04.Weight",(-1.68,5,2.918),(0,-1,0))
    text_mesh("C04.Cream cut letters",p,(0,0,.0036),"SWEAT NOW. SHINE LATER.",SANS,1.94,.007,m["cream"],.0004,1.09)


def rod(name,parent,start,end,width,material):
    a,b=Vector(start),Vector(end)
    o=box(name,parent,(a+b)/2,(width,width,(b-a).length),material,.001)
    o.rotation_euler=(b-a).to_track_quat("Z","Y").to_euler()
    return o


def easel(m):
    p=anchor("D04.Easel",(-5.83,-4.99,.012),(-.30,.9539392014,0))
    board=obj("D04.Leaning board",None,p,(0,.871,0))
    board.rotation_euler.x=math.radians(-8)
    box("D04.Frame",board,(0,0,0),(.466,.672,.025),m["rail"],.005)
    printm=print_mat("Paint marker on slate",ART/"D04_marker.jpg")
    ink=next(n for n in printm.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    ink.inputs["Roughness"].default_value=.40
    image_face("D04.Handwritten event",board,(0,0,.0128),.437,.642,printm)
    for s in (-1,1):
        for name,dx,dy,w,h in [("horizontal",s*.195,.323,.054,.010),("vertical",s*.217,.300,.010,.042)]:
            box(f"D04.Corner {s} {name}",board,(dx,dy,.014),(w,h,.004),m["metal"],.001)
    box("D04.Tray",board,(0,-.327,.017),(.48,.016,.037),m["rail"],.002)
    # Each leg terminates in its own flat-bottom ferrule on the finished desk floor.
    for i,(x,depth,top) in enumerate([(-.258,.113,(-.155,1.084,-.057)),(.258,.113,(.155,1.084,-.057)),
                                      (0,-.255,(0,1.055,-.063))]):
        box(f"D04.Foot {i}",p,(x,.006,depth),(.026,.012,.032),m["rubber"],.002)
        rod(f"D04.Leg {i}",p,(x,.010,depth),top,.016,m["rail"])
    rod("D04.Back crosspiece",p,(-.17,1.04,-.053),(.17,1.04,-.053),.019,m["rail"])
    rod("D04.Rear stay",p,(0,.39,-.184),(.218,.39,.05),.006,m["metal"])


def gallery(m,paths):
    p=anchor("D06.Gallery",(-7.471,1.86,1.68),(1,0,0))
    # Fixings bear directly against the measured relief of the existing slate tiles.
    slate=bpy.data.objects["GS_Real_SplitSlateBay"]
    inv=slate.matrix_world.inverted()
    for row,z in enumerate((-.312,-.07,.29)):
        for side in (-1,1):
            horizontal=.50*side
            origin=Vector((-7.471,1.86+horizontal,1.68+z))
            hit,pos,_,_=slate.ray_cast(inv@origin,inv.to_3x3()@Vector((-1,0,0)))
            if not hit: raise ValueError("Missing slate support under picture fitting")
            gap=origin.x-(slate.matrix_world@pos).x
            box(f"D06.Spacer {row} {side}",p,(horizontal,z,-gap/2),(.035,.012,gap),m["metal"],.0004)

    panel=print_mat("Project offset print",ART/"D06_project.jpg")
    box("D06.Mounted print",p,(0,.112,.008),(1.19,.508,.016),m["navy"],.002)
    image_face("D06.Award print",p,(0,.112,.0162),1.184,.505,panel)
    box("D06.Picture ledge",p,(0,-.311,.053),(1.21,.016,.106),m["oak"],.002)
    box("D06.Ledge lip",p,(0,-.292,.103),(1.21,.024,.006),m["oak"],.001)
    for i in range(5):
        x=(i-2)*.221
        width,height=.163,.20375
        # Lean on the panel, just behind the front lip; outer mount has 3 mm margins.
        card=obj(f"D06.Card {i+1}",None,p,(x,-.303,.092))
        card.rotation_euler.x=math.radians(-21)
        box(f"D06.Photo mount {i+1}",card,(0,height/2+.003,0),(width+.006,height+.006,.004),m["cream"],.0006)
        if paths:
            ink=print_mat(f"Member {i+1:02}",paths[i])
            image_face(f"D06.Member {i+1:02}",card,(0,height/2+.003,.00215),width,height,ink)


def apply(paths=None):
    if paths is None:
        paths=member_images()
    group=bpy.data.collections.get(GROUP)
    if group:
        for ob in list(group.objects): bpy.data.objects.remove(ob,do_unlink=True)
        bpy.data.collections.remove(group)
    # Only remove unused IDs created by this module, in dependency order.
    for data in (bpy.data.meshes,bpy.data.curves,bpy.data.lights,bpy.data.materials,bpy.data.node_groups,bpy.data.images):
        for block in list(data):
            if block.name.startswith(PREFIX) and not block.users: data.remove(block)
    group=bpy.data.collections.new(GROUP)
    bpy.context.scene.collection.children.link(group)
    old=[f"{base}.{i:03}" for i in (1,2) for base in ("Room plaque","Room plaque strip")]
    old += [pre+sex+"Locker" for pre in ("Label_","Sublabel_") for sex in ("Men","Women")]
    old += ["Dgym_wall_graphics_Lettering_EN"]
    old += [o.name for o in bpy.context.scene.objects if o.name.startswith(("Dgym_wall_graphics_Zone_Stretching_","Dgym_wall_graphics_StretchSign_"))]
    for name in old:
        ob=bpy.data.objects[name]
        ob.hide_render=ob.hide_viewport=True
    m={
        "metal":mat("Satin machined alloy",(.60,.57,.49),.31,1),
        "bronze":mat("Smoke bronze mirrored face",(.14,.10,.062),.075,.88),
        "warm":mat("Warm white light inlay",(1.0,.94,.82),.33,0,4.8),
        "black":mat("Channel returns",(.031,.035,.035),.38),
        "white":mat("Opal white diffuser",(.98,.98,.96),.33,0,3.8),
        "amber":mat("Mirror edge amber",(1.0,.68,.28),.35,0,3.6),
        "cream":mat("Bone matte cut vinyl",(.85,.80,.67),.72),
        "rail":mat("Powder coated frame",(.032,.036,.036),.40),
        "rubber":mat("Ferrules",(.017,.018,.019),.82),
        "navy":mat("Navy mount",(.028,.044,.07),.65),
        "oak":mat("Warm satin ledge",(.32,.217,.136),.44),
    }
    brushed=next(n for n in m["metal"].node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    next(socket for socket in brushed.inputs if "Anisotrop" in socket.name and "Rotation" not in socket.name and socket.type=="VALUE").default_value=.55
    mirror_rules(m)
    locker_boxes(m)
    stretching(m)
    upper_slogan(m)
    easel(m)
    gallery(m,paths)
    bpy.context.view_layer.update()
    return sorted(old)


def member_images():
    return [ART/"members"/f"member_{i:02}.jpg" for i in range(1,6)]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    parser.add_argument("--review",action="store_true")
    parser.add_argument("--structure-only",action="store_true")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    if Path(bpy.data.filepath).resolve()!=SOURCE: raise ValueError("Open the saved gym base")
    allowed_outputs={OUTPUT.resolve(),(WORK/"candidate_v2.blend").resolve(),SOURCE.resolve()}
    if args.output and args.output.resolve() not in allowed_outputs: raise ValueError("Only authorized L1 outputs are valid")
    if args.output and args.structure_only: raise ValueError("Final portraits required for candidate")
    paths=[] if args.structure_only else member_images()
    hidden=apply(paths)
    for p in paths:
        im=bpy.data.images[PREFIX+p.name]
        assert hashlib.sha256(im.packed_file.data).digest()==hashlib.sha256(p.read_bytes()).digest()
    if args.review and args.output: raise ValueError("Run review and save in separate processes")
    if args.review:
        import runpy
        review=runpy.run_path(str(WORK/"review"/"inspect_signs.py"))
        review["review"](hidden)
    if args.output:
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()),compress=True,copy=True,relative_remap=False)
    print("Built indoor signs:",len(bpy.data.collections[GROUP].objects),"objects;",len(hidden),"replaced objects")


if __name__=="__main__":
    main()
