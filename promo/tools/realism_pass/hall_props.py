"""Hall facilities overlay for b71c4024. Import and call apply() with scene loaded."""
import math
from pathlib import Path
import bpy
from mathutils import Vector

P = "Dhall_props_"
C = "DETAIL_hall_props"
TAG = "astra_hall_props_v1"


def old(name):
    o = bpy.data.objects[P + name]
    assert bpy.data.collections[C] in o.users_collection
    return o


def material(name, color, rough, metallic=0, grain=0):
    name = P + "HP_" + name
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    tree = m.node_tree
    shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs["Base Color"].default_value = m.diffuse_color
    shader.inputs["Roughness"].default_value = rough
    shader.inputs["Metallic"].default_value = metallic
    if grain:
        coord = tree.nodes.new("ShaderNodeTexCoord")
        noise = tree.nodes.new("ShaderNodeTexNoise")
        tree.links.new(coord.outputs["Object"], noise.inputs[0])
        noise.inputs["Scale"].default_value = grain
        noise.inputs["Detail"].default_value = 2
        bump = tree.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .14
        bump.inputs["Distance"].default_value = .00016
        tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return m


def assign(o, mat):
    o.material_slots[0].link = "OBJECT"
    o.material_slots[0].material = mat


def obj(name, mesh, parent, mat):
    o = bpy.data.objects.new(P+"HP_"+name, mesh)
    o[TAG] = True
    bpy.data.collections[C].objects.link(o)
    o.parent = parent
    mesh.materials.append(mat)
    return o


def rect(x, y, w, d, rad, z):
    rad = min(rad, .49*min(w,d))
    pts = []
    for cx, cy, start in [(1,1,0),(-1,1,90),(-1,-1,180),(1,-1,270)]:
        for k in range(9):
            a = math.radians(start + k*90/8)
            pts.append((x+cx*(w/2-rad)+rad*math.cos(a), y+cy*(d/2-rad)+rad*math.sin(a), z))
    return pts


def ellipse(x, y, w, d, z, n=36):
    return [(x+w/2*math.cos(k*math.tau/n),y+d/2*math.sin(k*math.tau/n),z) for k in range(n)]


def shell(name, parent, mat, rings, loop=False):
    """Successive CCW rings from outer bottom to lip to well bottom."""
    n = len(rings[0])
    faces = []
    for j in range(len(rings) if loop else len(rings)-1):
        k = (j+1)%len(rings)
        faces.extend((j*n+i,j*n+(i+1)%n,k*n+(i+1)%n,k*n+i) for i in range(n))
    if not loop:
        faces += [tuple(reversed(range(n))),tuple(range((len(rings)-1)*n,len(rings)*n))]
    mesh = bpy.data.meshes.new(P+"HP_"+name)
    mesh.from_pydata(sum(rings, []), [], faces)
    mesh.update()
    for p in list(mesh.polygons)[:len(faces) if loop else -2]:
        p.use_smooth = True
    return obj(name, mesh, parent, mat)


def rod(name, parent, mat, a, b, radius):
    v = Vector(b)-Vector(a)
    L = v.length
    o = shell(name,parent,mat,[ellipse(0,0,2*radius,2*radius,z,16) for z in (0,L)])
    o.location = a
    o.rotation_euler = v.to_track_quat("Z","Y").to_euler()
    return o


def cover(*names):
    for name in names:
        o = old(name)
        o.hide_viewport = o.hide_render = True


def apply():
    coll = bpy.data.collections[C]
    for o in list(coll.objects):
        if o.get(TAG):
            mesh = o.data
            bpy.data.objects.remove(o,do_unlink=True)
            if not mesh.users:
                bpy.data.meshes.remove(mesh)
    hall = old("Rack_Back").parent
    steel = material("BrushedNickel",(.55,.53,.49),.29,1)
    rubber = material("EPDM",(.027,.029,.028),.73,grain=900)
    enamel = material("WarmGreyEnamel",(.55,.55,.50),.39,grain=360)
    case = material("MouldedGrey",(.46,.49,.48),.43,grain=680)
    porcelain = material("VitreousChina",(.87,.88,.84),.115)
    dark = material("WasteInside",(.024,.028,.026),.62)
    for n in ("FireDoor_Leaf","FireFrame_Head","FireFrame_JambL","FireFrame_JambR"):
        assign(old(n),enamel)
    door=old("FireDoor")
    # Frame shoe is seated against the inside return of the head jamb.
    cover("FireDoor_CloserArm")
    shoe_x, shoe_y = .026,-.12
    shell("CloserShoe",door,steel,[rect(shoe_x,shoe_y,.042,.058,.005,z) for z in (2.048,2.056)])
    for i,(a,b) in enumerate([((-.21,-.089,1.988),(-.21,-.089,2.014)),
                               ((-.21,-.089,2.014),(-.107,-.202,2.026)),
                               ((-.107,-.202,2.034),(shoe_x,shoe_y,2.039)),
                               ((shoe_x,shoe_y,2.039),(shoe_x,shoe_y,2.050))]):
        rod("CloserLink"+str(i),door,steel,a,b,.0075)
    rod("ElbowRivet",door,steel,(-.107,-.202,2.018),(-.107,-.202,2.044),.012)
    rod("ReturnGrip",door,steel,(-.70,-.111, .995),(-.70,-.091,.993),.009)
    for x in (-.846,-.814):
        rod("RosePin"+str(x),door,steel,(x,-.0675,1.0),(x,-.070,1.0),.0026)
    # Real moulded containers, continuous rolled rims and recessed bag wells.
    for i,(key,col,shape) in enumerate([
        ("general",(.12,.13,.14),"wide"),("plastic",(.055,.20,.40),"round"),
        ("can",(.045,.27,.145),"round"),("paper",(.67,.34,.055),"slit")]):
        x=3.135+.285*i
        y=.35
        cover(*["Bin_"+key+"_"+part for part in ("Body","Lid","Slot")])
        profiles=[(.245,.328,.020,.003),(.248,.330,.020,.016),(.258,.346,.017,.14),
                  (.270,.360,.016,.616),(.270,.360,.016,.642),(.276,.366,.015,.645),
                  (.276,.366,.015,.654),(.266,.356,.014,.657),(.252,.342,.012,.652),
                  (.240,.330,.012,.18)]
        shell("Tub_"+key,hall,case,[rect(x,y,w,d,r,z) for w,d,r,z in profiles])
        lid=material("Cap_"+key,col,.39,grain=520)
        rings=[rect(x,y,w,d,r,z) for w,d,r,z in [
            (.274,.364,.018,.652),(.279,.369,.018,.658),(.279,.369,.018,.682),
            (.275,.365,.019,.692),(.261,.351,.019,.701)]]
        w,d = {"round":(.125,.125),"slit":(.204,.070),"wide":(.176,.151)}[shape]
        r=min(w,d)*(.48 if shape=="round" else .17)
        for delta,z in [(.009,.701),(0,.697),(-.003,.685),(-.003,.658)]:
            rings.append(rect(x,y,w+delta,d+delta,r,z))
        shell("Rim_"+key,hall,lid,rings,True)
        # Textile liner clipped beneath the cap, 95 mm of visible depth.
        liner=[rect(x,y,w+dw,d+dw,r*.91,z) for dw,z in [(-.023,.575),(.008,.658),(.008,.677),(.001,.678),(-.013,.635),(-.030,.581)]]
        shell("Liner_"+key,hall,dark,liner)
        # Flat face of tapered body sits slightly behind the old label.
        label = old("Bin_"+key+"_Label")
        label.location.y = .5282
        label.rotation_euler.x = math.atan(.007/.476)

    # Replace closed bucket lid by moulded lip and hollow, slatted wringer.
    root=old("MopBucket")
    cover("MopBucket_Rim","MopBucket_Wringer")
    bucket=old("MopBucket_Shell").active_material
    shell("BailRim",root,bucket,[ellipse(0,0,r*2,r*2,z) for r,z in
          [(.163,.316),(.170,.320),(.172,.328),(.168,.334),(.160,.334),(.156,.329),(.159,.318)]],True)
    for dx in (-.143,-.041):
        rod("WringerRail"+str(dx),root,case,(dx,-.078,.341),(dx,.078,.341),.006)
    for i in range(8):
        y=-.073+i*.021
        for j,(a,b) in enumerate([((-.143,y,.342),(-.122,y,.238)),
                                   ((-.122,y,.238),(-.061,y,.238)),
                                   ((-.061,y,.238),(-.041,y,.342))]):
            rod(f"WringerRib{i}_{j}",root,case,a,b,.004)
    rod("PressHinge",root,steel,(-.144,0,.345),(-.041,0,.345),.012)
    # Vitreous basin rolls over the edge and falls to a real waste fitting.
    cover("Rest_SinkBasin","Rest_SinkBowl")
    x,y=6.286,1.30
    profiles=[(.20,.18,.06,.702),(.30,.35,.095,.735),(.396,.426,.096,.796),
              (.408,.439,.092,.831),(.402,.436,.089,.839),(.388,.425,.085,.842)]
    rings=[rect(x,y,w,d,r,z) for w,d,r,z in profiles]
    for off,w,d,z in [(-.027,.310,.357,.841),(-.028,.297,.347,.831),
                       (-.030,.272,.320,.799),(-.033,.209,.245,.765),
                       (-.028,.12,.135,.750),(-.027,.042,.042,.747),(-.027,.024,.024,.746),(-.027,.023,.023,.737)]:
        angles = [math.atan2((py-y)/.425,(px-x)/.388) for px,py,_ in rings[5]]
        rings.append([(x+off+w/2*math.cos(a), y+d/2*math.sin(a),z) for a in angles])
    basin = shell("WashBasin",hall,porcelain,rings)
    basin.data.materials.append(dark)
    basin.data.polygons[-1].material_index = 1
    shell("WasteFlange",hall,steel,[ellipse(x-.027,y,w,w,z) for w,z in
          [(.041,.7472),(.044,.7486),(.040,.750),(.028,.750),(.026,.7474)]],True)
    rod("WasteGrate",hall,steel,(x-.040,y,.749),(x-.014,y,.749),.002)
    rod("MixerLever",hall,steel,(6.45,1.30,.957),(6.41,1.30,.966),.006)
    # True silvered glass mirror instead of dull metallic grey plate.
    mirror_mat = material("SilveredMirror",(.93,.95,.96),.012,1.0)
    m_bsdf = next(n for n in mirror_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    m_bsdf.inputs["Coat Weight"].default_value = .45
    m_bsdf.inputs["Coat Roughness"].default_value = .01
    assign(old("Rest_Mirror"), mirror_mat)
    # Dark walnut laminate with vertical grain on restroom doors + stainless lock escutcheon.
    walnut = material("WalnutLaminate",(.065,.038,.026),.34)
    w_tree = walnut.node_tree
    w_bsdf = next(n for n in w_tree.nodes if n.type == "BSDF_PRINCIPLED")
    w_coord = w_tree.nodes.new("ShaderNodeTexCoord")
    w_map = w_tree.nodes.new("ShaderNodeMapping")
    w_map.inputs["Scale"].default_value = (18.0, 18.0, 2.2)
    w_tree.links.new(w_coord.outputs["Object"], w_map.inputs["Vector"])
    w_noise = w_tree.nodes.new("ShaderNodeTexNoise")
    w_noise.inputs["Scale"].default_value = 4.5
    w_noise.inputs["Detail"].default_value = 5.0
    w_noise.inputs["Distortion"].default_value = 1.4
    w_tree.links.new(w_map.outputs["Vector"], w_noise.inputs["Vector"])
    w_ramp = w_tree.nodes.new("ShaderNodeValToRGB")
    w_ramp.color_ramp.elements[0].position = 0.25
    w_ramp.color_ramp.elements[0].color = (0.042, 0.024, 0.016, 1.0)
    w_ramp.color_ramp.elements[1].position = 0.78
    w_ramp.color_ramp.elements[1].color = (0.095, 0.056, 0.038, 1.0)
    w_tree.links.new(w_noise.outputs["Fac"], w_ramp.inputs[0])
    w_tree.links.new(w_ramp.outputs["Color"], w_bsdf.inputs["Base Color"])
    w_rough = w_tree.nodes.new("ShaderNodeMapRange")
    w_rough.inputs["To Min"].default_value = 0.28
    w_rough.inputs["To Max"].default_value = 0.42
    w_tree.links.new(w_noise.outputs["Fac"], w_rough.inputs["Value"])
    w_tree.links.new(w_rough.outputs["Result"], w_bsdf.inputs["Roughness"])
    w_bump = w_tree.nodes.new("ShaderNodeBump")
    w_bump.inputs["Strength"].default_value = 0.14
    w_bump.inputs["Distance"].default_value = 0.0003
    w_tree.links.new(w_noise.outputs["Fac"], w_bump.inputs["Height"])
    w_tree.links.new(w_bump.outputs["Normal"], w_bsdf.inputs["Normal"])
    for dname in ("Rest_DoorMen", "Rest_DoorWomen"):
        assign(old(dname), walnut)
    knob_men = old("Rest_DoorMenKnob")
    kx, ky, kz = knob_men.location
    rod("RestMenRose", hall, steel, (kx + .018, ky, kz), (kx + .026, ky, kz), .032)
    # Exposed screw caps on the projecting bracket and wall signs.
    for name,y,z,dy,dz,front in [("Floor",1.69,1.50,.090,.165,4.612),
                                 ("Restroom",.34,1.55,.097,.146,4.612)]:
        for i,(sy,sz) in enumerate([(-1,-1),(1,-1),(-1,1),(1,1)]):
            cy,cz=y+sy*dy,z+sz*dz
            rod(f"{name}Screw{i}",hall,steel,(front,cy,cz),(front-.002,cy,cz),.0036)
    # Two shallow document channels retain the A4 inspection sheet.
    for side,yy in enumerate((.512,.728)):
        shell("ChecklistChannel"+str(side),hall,steel,[rect(4.614,yy,.006,.005,.001,z) for z in (1.304,1.606)])
    for t,zb in enumerate((.60,.94,1.28)):
        for i,x in enumerate((3.226,3.425,3.63)):
            rod(f"PocketReturn{t}_{i}",hall,steel,(x,2.762,zb+.07),(x,2.762,zb+.17),.0025)
    for i in range(6):
        o=old("Flyer"+str(i))
        artwork = Path(__file__).resolve().parent / "print" / f"flyer_{i}.png"
        imname = P + f"HP_FlyerInk{i}"
        im = bpy.data.images.get(imname)
        if im is None:
            im = bpy.data.images.load(str(artwork), check_existing=False)
            im.name = imname
            im.pack()
        assert im.packed_file
        for node in o.active_material.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                node.image = im
        # Warp the existing printed UV face, preserving trim and registration.
        if "hp_paper_curve" not in o.data:
            import bmesh
            bm=bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=6,use_grid_fill=True)
            for v in bm.verts:
                u=v.co.x/.10
                h=(v.co.z+.1425)/.285
                v.co.y-=.0006+.005*(max(h,0)**2)*(0.35+0.65*(u*(-1)**i+1)/2)
            bm.to_mesh(o.data)
            bm.free()
            o.data["hp_paper_curve"]=True
    return {"package":"hall_props","objects_added":sum(bool(o.get(TAG)) for o in coll.objects)}
