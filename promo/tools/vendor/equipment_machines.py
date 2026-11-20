"""Photo-referenced low-poly machines (design/equipment-reference). Same conventions as equipment_kit: metres, +Z up,
the lifter faces -Y, each machine is an empty P_<name> whose origin is on the floor under the seat/centre.
exec() after equipment_kit; build_machines() lays them out in a row for a showcase."""
import math
from mathutils import Vector
import equipment_kit as K
from equipment_kit import cyl, box, part, _obj
import bmesh

K.COL.update({"silver": (0.055, 0.060, 0.068, 1), "stack": (0.024, 0.027, 0.032, 1), "red": (0.72, 0.04, 0.05, 1),
              "wood": (0.45, 0.28, 0.14, 1), "frame": (0.68, 0.035, 0.040, 1), "pad": (0.022, 0.024, 0.028, 1), "plate": (0.018, 0.019, 0.023, 1),
              "grip": (0.014, 0.015, 0.018, 1), "accent": (0.95, 0.72, 0.04, 1)})
THICK = 1.55   # photo machines are built from fat tube; thin beams read as scaffolding


def beam(name, p, a, b, s=0.06, mat="frame", s2=None):
    """Beveled structural square tube from point a to point b."""
    a, b = Vector(a), Vector(b); d = b - a
    if d.length < 1e-4:
        return None
    s = s * THICK; s2 = s if s2 is None else s2 * THICK
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((d.length, s, s2)), verts=bm.verts)
    ob = _obj(name, bm, p, mat, tuple((a + b) / 2))
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = d.to_track_quat("X", "Z")
    K._add_bevel(ob, min(0.010, min(s, s2) * 0.24), segments=2)
    return ob


def rod(name, p, a, b, r=0.016, mat="steel", sides=20):
    a, b = Vector(a), Vector(b); d = b - a
    if d.length < 1e-4:
        return None
    seg = max(sides, 20)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d.length)
    ob = _obj(name, bm, p, mat, tuple((a + b) / 2))
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = d.to_track_quat("Z", "Y")
    return K._smooth_cyl(ob)


def _path(parent, name, points, radius, material, closed=False):
    """One beveled polyline, including curved wire returns and upholstery welts."""
    import bpy
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u, curve.bevel_resolution = 1, 0
    curve.bevel_depth, curve.use_fill_caps = radius, True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points)-1)
    for point, xyz in zip(spline.points, points):
        point.co = (*xyz, 1)
    spline.use_cyclic_u = closed
    obj = bpy.data.objects.new(name, curve)
    bpy.data.collections["Kit"].objects.link(obj)
    obj.parent = parent
    curve.materials.append(K.mat(material))
    return obj


def pad(name, p, size, loc, rot=(0, 0, 0), mat="pad"):
    """Loft a tapered cushion with a recessed welt around its edge."""
    thin = min(range(3), key=size.__getitem__)
    wide, long = [i for i in range(3) if i != thin]
    bm = bmesh.new()
    rings = []
    profile = ((-.50,.89),(-.355,.978),(-.345,.9803),(-.18,.99),(-.12,.965),
               (-.05,1.0),(.27,.985),(.455,.9217),(.465,.90125),(.50,.77))
    sew = bm.loops.layers.uv.new("Stitch pitch")
    for index, (depth, fullness) in enumerate(profile):
        ring = []
        for i in range(24):
            t = math.tau*i/24
            u, v = math.cos(t), math.sin(t)
            u = math.copysign(abs(u)**.40, u)
            v = math.copysign(abs(v)**.40, v)
            co = [0,0,0]
            co[wide] = .5*size[wide]*u*fullness*(1-.10*max(0,v))
            co[long] = .5*size[long]*v*fullness
            co[thin] = max(.085,size[thin])*depth
            ring.append(bm.verts.new(co))
        if rings:
            distance = 0.0
            for i in range(24):
                j = (i+1)%24
                face = bm.faces.new((rings[-1][i],rings[-1][j],ring[j],ring[i]))
                if index in (2, 8):
                    face.material_index = 1
                    end = distance + (ring[j].co-ring[i].co).length
                    for loop, u in zip(face.loops, (distance,end,end,distance)):
                        loop[sew].uv = (u, 0)
                    distance = end
        rings.append(ring)
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    ob = _obj(name,bm,p,mat,loc,rot)
    ob.data.materials.append(K.mat("stitch"))
    for face in ob.data.polygons:
        face.use_smooth = len(face.vertices)==4
    return ob


def _tray(p, x, y, top, w, d):
    """Single molded crown, with a round bottle well and a rounded phone well."""
    bm = bmesh.new()
    for side in (-1, 1):
        rings = []
        for level in ("bottom", "lip", "mouth", "floor"):
            ring = []
            for i in range(32):
                t = math.tau*i/32
                u, v = math.cos(t), math.sin(t)
                edge = max(abs(u), abs(v))
                cx = side*w/4
                if level in ("bottom", "lip"):
                    px, py = cx+w*.25*u/edge, d*.5*v/edge
                    # Roll the four outer corners. Keep the shared centre edge straight.
                    if abs(px) > w*.48 and abs(py) > d*.48:
                        px *= .975
                        py *= .975
                    z = -.0325 if level == "bottom" else .0325
                else:
                    taper = .86 if level == "floor" else 1
                    if side < 0:
                        r = min(.046, w*.19, d*.33)
                        px, py = cx+r*u*taper, r*v*taper
                    else:
                        px = cx + w*.17*math.copysign(abs(u)**.34,u)*taper
                        py = d*.29*math.copysign(abs(v)**.34,v)*taper
                    z = -.017 if level == "floor" else .0325
                ring.append(bm.verts.new((px, py, z)))
            if rings:
                for i, vtx in enumerate(ring):
                    j = (i+1)%len(ring)
                    if level == "lip" and max(abs(vtx.co.x),abs(ring[j].co.x)) < .00001:
                        continue
                    bm.faces.new((rings[-1][i], rings[-1][j], ring[j], vtx))
            rings.append(ring)
        bm.faces.new(rings[0])
        bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    crown = _obj("Molded accessory tray", bm, p, "silver", (x,y,top))
    K._add_bevel(crown, .0025, segments=2)


def _placard(p, x, y, z, w, rear=False):
    # Draw the setup figure in the panel's local XY plane. The hinge tips the
    # face upward; the icon, lettering and stripe follow that same plane.
    tilt = 82
    board = box("Exercise guide", p, (w,.129,.009), "grip", (x,y,z),
                (tilt,0,180 if rear else 0), bevel=.003)
    title = p.name.split(".")[0].removeprefix("P_").replace("_machine","").replace("_"," ").upper()
    K._lettering(board,title,(0,.043,.0048),min(.021,w*1.35/max(1,len(title))),(0,0,0))
    lower_body = any(word in title for word in ("LEG","HIP","CURL")) and "PREACHER" not in title
    overhead = any(word in title for word in ("SHOULDER","PULL","CABLE"))
    for step, start in enumerate((-.25,.23)):
        ox = w*start
        def stroke(name, xy, material):
            _path(board,name,[(ox+u,v,.006) for u,v in xy],.00155,material)
        stroke("Seat diagram",[(-.013,-.022),(-.013,-.035),(.006,-.035)],"silver")
        stroke("Torso",[(-.002,-.028),(-.009,-.005)],"print")
        cyl("Guide head",board,.0058,.0017,"Z","print",(ox-.010,.005,.0054))
        hand = (.020,.017 if overhead else -.003) if step else (.006,-.011)
        foot = (.024,-.030) if lower_body and step else (.010,-.045)
        stroke("Arm",[(-.009,-.007),(.002,-.016),hand],"print" if lower_body else "accent")
        stroke("Leg",[(-.002,-.028),(.012,-.029),foot],"accent" if lower_body else "print")
    return board


def _hex(p, name, loc, radius, length, axis="X"):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=radius,
                          radius2=radius, depth=length)
    return _obj(name,bm,p,"steel",loc,{"X":(0,90,0),"Z":(0,0,0),"Y":(90,0,0)}[axis])


def _dial(p,x,y,z,r=.095):
    cyl("range_sector",p,r,.028,"X","silver",(x,y,z))
    cyl("bearing",p,r*.44,.038,"X","steel",(x,y,z))
    _hex(p,"Range lock bolt",(x,y,z),r*.22,.043)
    for i in (0,1,3,4,5):
        t = math.radians(30+25*i)
        cyl("range_index",p,.008,.006,"X","steel",
            (x+.016,y+r*.72*math.cos(t),z+r*.72*math.sin(t)))
    cyl("pop_pin",p,.017,.034,"X","accent",(x+.028,y+r*.72*math.cos(math.radians(80)),z+r*.72*math.sin(math.radians(80))))


def _seat_lever(p,y,z):
    rod("seat_release",p,(0,y,z),(.16,y-.035,z+.014),.009,"steel")
    rod("yellow_paddle",p,(.13,y-.03,z+.012),(.19,y-.047,z+.019),.017,"accent")


def _stack_head(p, x, y, top, plate_z, stroke, travel):
    """Route from the top plate around the guarded head wheel to the take-off."""
    station = p.name.split(".")[0].removeprefix("P_")
    targets = {
        "chest_press_machine": (.32,.20,1.025),
        "shoulder_press_machine": (.45,.45,1.975),
        "lateral_raise_machine": (.28,.10,1.325),
        "pec_deck": (0,.60,1.50),
        "assisted_pullup": (.17,.35,.87),
        "lat_pulldown": (0,-.45,2.15),
        "functional_trainer": (math.copysign(.55,x),-.134,2.222),
        "cable_crossover": (x,-.134,2.222),
    }
    # Low take-offs run down inside the shroud and forward along the base,
    # keeping the seated user's shoulder and knees clear of the cable.
    low = {"dip_machine": (.385,.12,1.13), "preacher_machine": (.177,.05,1.08),
           "hip_abductor": (.19,-.03,.481), "seated_leg_curl": (.239,-.30,.527),
           "leg_extension": (.246,-.25,.403), "seated_cable_row": (0,-.55,.29)}
    end = Vector(targets.get(station,(x,y-.14,top-.32)))
    if station in low:
        cam = Vector(low[station])
        end = Vector((cam.x*.62,y-.1,.18))
    direction = Vector((end.x-x,end.y-y,0)).normalized()
    up = Vector((0,0,1))
    axis = direction.cross(up)
    radius = .058
    wheel = Vector((x,y,top)) + direction*radius
    root = part("Head sheave")
    root.parent, root.location = p, wheel
    root.rotation_euler.z = math.atan2(axis.y,axis.x)
    cyl("Cable groove",root,radius-.004,.017,"X","grip")
    for side in (-1,1):
        cyl("Pulley flange",root,radius+.004,.003,"X","silver",(side*.010,0,0))
        box("Pulley cheek",root,(.004,.066,.079),"silver",(side*.019,0,-.020),bevel=.0015)
    _hex(root,"Sheave axle",(0,0,0),.012,.045)
    beam("Bearing pedestal",p,(x,y-.014,top-.071),
         (wheel.x,wheel.y,top-.030),.026,"silver")
    delta = end-wheel
    lateral, vertical = delta.dot(direction), delta.z
    # Tangency point on the upper branch, measured from the incoming vertical.
    theta = math.atan2(lateral,vertical) + math.asin(radius/delta.length)
    theta = min(math.pi,max(.01,theta))
    line = [(x,y,plate_z)]
    for i in range(17):
        t = theta*i/16
        line.append(wheel-radius*math.cos(t)*direction+radius*math.sin(t)*up)
    line.append(end)
    if station in low:
        lead = Vector((cam.x,cam.y+.09,.18))
        for pt in (end,lead):
            cyl("Lower sheave",p,.033,.017,"X","silver",(pt.x,pt.y,pt.z+.026))
        beam("Idler bracket",p,(0,lead.y,.09),(lead.x,lead.y,lead.z+.026),
             .022,"silver")
        line.extend([lead,cam])
    cable = _path(p,"Coated load cable",line,.004,"grip")
    K._driver(cable.data.splines[0].points[0],"co",2,p,f"{plate_z!r}+{travel!r}*v",v=stroke)
    drum = part("Load pulley spindle")
    drum.parent = root
    for wheel_part in list(root.children):
        if wheel_part.name.startswith(("Cable groove","Pulley flange")):
            wheel_part.parent = drum
    K._stroke(drum,"rotation_euler",0,p,travel/radius,stroke)


def _drive(p, hub):
    cyl("drive_cam",p,.082,.042,"X","silver",hub)
    pivot_hub("axle",p,hub,.043,.055)


def _rack_post(p,x,y,h,width,depth):
    """Continuous steel tube with modeled through-holes, tight spacing at bench height."""
    bm = bmesh.new()
    holes = []
    z = .20
    while z < h-.14:
        holes.append(z)
        z += .0254 if .63 <= z <= 1.09 else .0508
    hole_x = math.copysign(.031,x) if p.name.startswith("P_smith_machine") else 0
    width, depth = width-.003, depth-.003
    cuts = [0] + [(a+b)/2 for a,b in zip(holes,holes[1:])] + [h]
    verts = {}
    def vertex(co):
        key = tuple(round(v,7) for v in co)
        if key not in verts:
            verts[key] = bm.verts.new(co)
        return verts[key]
    for index, center in enumerate(holes):
        bottom, top = cuts[index:index+2]
        rings = []
        for sign in (-1,1):
            outer = []
            hole = []
            lip = []
            for k in range(8):
                angle = k*math.tau/8
                u,v = math.cos(angle),math.sin(angle)
                outer.append(vertex((width*.5*round(u),sign*depth/2,
                                     top if v>.1 else bottom if v<-.1 else center)))
                hole.append(vertex((hole_x+.010*u,sign*depth/2,center+.010*v)))
                lip.append(vertex((hole_x+.009*u,sign*(depth/2-.002),center+.009*v)))
            for k in range(8):
                j = (k+1)%8
                bm.faces.new((outer[k],outer[j],hole[j],hole[k]))
                bm.faces.new((hole[k],hole[j],lip[j],lip[k])).material_index = 1
            rings.append((outer,lip))
        for k in range(8):
            j = (k+1)%8
            a,l = rings[0]
            b,r = rings[1]
            bm.faces.new((l[k],l[j],r[j],r[k])).material_index = 1
            if k in (0,3,4,7) or (index==0 and k in (5,6)) or (index==len(holes)-1 and k in (1,2)):
                bm.faces.new((a[k],a[j],b[j],b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    ob = _obj("Perforated upright",bm,p,"frame",(x,y,0))
    ob.data.materials.append(K.mat("silver"))
    return ob


def _chin_grips(p,half,h,reach):
    for side in (-1,1):
        a = (side*half*.63,0,h-.023)
        b = (side*half*.52,-reach,h-.055)
        rod("Chin bracket",p,a,b,.019,"silver")
        grip_handle("Angled chin grip",p,b,(side*half*.27,-reach,h-.08),.018)


def _trolley(p,x,z):
    rod("guide",p,(x,-.115,.22),(x,-.115,2.24),.015)
    box("slider",p,(.105,.11,.15),"silver",(x,-.118,z))
    cyl("swivel",p,.05,.055,"X","steel",(x,-.17,z))
    cyl("lock_pin",p,.018,.040,"X","accent",(x+.059,-.119,z))
    for height in (.42,.67,.92,1.17,1.42,1.67,1.92):
        cyl("index",p,.008,.012,"Y","grip",(x,-.128,height))
    cyl("Trolley head pulley",p,.042,.020,"X","grip",(x,-.134,2.18))
    for side in (-1,1):
        box("Head pulley guard",p,(.006,.062,.068),"silver",
            (x+side*.017,-.134,2.18),bevel=.002)
    line = [(x,-.134-.042*math.sin(i*math.pi/20),
             2.18+.042*math.cos(i*math.pi/20)) for i in range(11)]
    return_wire = _path(p,"Trolley return",line+[(x,-.176,z)],.004,"grip")
    for side in (-1,1):
        rod("stirrup",p,(x,-.19,z),(x+side*.073,-.23,z-.13),.009)
    grip_handle("stirrup_grip",p,(x-.073,-.23,z-.13),(x+.073,-.23,z-.13),.016)
    side = -1 if x<0 else 1
    stroke = "Stroke L" if side<0 else "Stroke R"
    handle = _linkage(p,(x,-.19,z),("stirrup","stirrup_grip"),side)
    carriage = _linkage(p,(x,-.118,z),("slider","swivel","lock_pin"),side)
    adjustment = "Pulley height L" if side<0 else "Pulley height R"
    K._control(p,adjustment,0.0,-.62,.52,"Vertical offset of this cable carriage (metres)")
    K._driver(carriage,"location",2,p,f"{z!r}+v",v=adjustment)
    K._driver(return_wire.data.splines[0].points[-1],"co",2,p,f"{z!r}+v",v=adjustment)
    handle.parent = carriage
    handle.location -= carriage.location
    K._stroke(handle,"location",1,p,-.40,stroke)
    line = _path(carriage,"Grip lead",[(0,-.052,0),(0,-.072,0)],.004,"grip")
    K._driver(line.data.splines[0].points[-1],"co",1,p,"-.072-.40*v",v=stroke)



def pivot_hub(name, p, loc, r=0.052, width=0.06, axis="X"):
    """Machined chrome/charcoal bearing housing at machine pivot joints."""
    cyl(name + "_body", p, r, width, axis, "silver", loc, sides=24)
    cyl(name + "_cap", p, r*.62, width+.014, axis, "silver", loc, sides=24)
    _hex(p,name+"_bolt",loc,r*.32,width+.021,axis)


def grip_handle(name, p, a, b, r=0.022):
    """Rubberized ergonomic handle with chrome end-caps."""
    a, b = Vector(a), Vector(b); d = b - a
    if d.length < 1e-4:
        return
    u = d.normalized()
    rod(name, p, a, b, r, "grip", sides=20)
    rod(name + "_cap1", p, a - u * 0.008, a + u * 0.010, r * 1.12, "steel", sides=20)
    rod(name + "_cap2", p, b - u * 0.010, b + u * 0.008, r * 1.12, "steel", sides=20)


def _linkage(p, pivot, names, side=0):
    """Group only moving parts under a local bearing, preserving their rest pose."""
    group = part("Moving assembly")
    group.parent, group.location = p,pivot
    for ob in list(p.children):
        name = ob.name.split(".")[0]
        if not any(name == stem or name.startswith(stem+"_cap") for stem in names):
            continue
        if side and side*ob.location.x <= 0:
            continue
        ob.parent = group
        ob.location -= Vector(pivot)
    return group


def _hinge(p,pivot,names,axis,degrees,side=0):
    joint = _linkage(p,pivot,names,side)
    K._stroke(joint,"rotation_euler",axis,p,math.radians(degrees))
    return joint


def _selector_plate(p, width, depth, height, loc):
    """Perforated casting and two black label substrates on its service face."""
    bm = bmesh.new()
    rings = []
    for extent, y in (("rim",-depth/2),("lip",-depth/2),("bore",-depth/2+.0015),
                      ("bore",depth/2-.0015),("lip",depth/2),("rim",depth/2)):
        ring = []
        for i in range(16):
            angle = math.tau*i/16
            u,v = math.cos(angle),math.sin(angle)
            if extent == "rim":
                edge = max(abs(u),abs(v))
                x,z = width*.5*u/edge,height*.5*v/edge
            else:
                radius = .008 if extent == "bore" else .0095
                x,z = radius*u,radius*v
            ring.append(bm.verts.new((x,y,z)))
        if rings:
            for i in range(16):
                j=(i+1)%16
                face = bm.faces.new((rings[-1][i],rings[-1][j],ring[j],ring[i]))
                if len(rings)==3:
                    face.material_index = 1
        rings.append(ring)
    for i in range(16):
        j=(i+1)%16
        bm.faces.new((rings[0][i],rings[0][j],rings[-1][j],rings[-1][i]))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    # Slightly rounded sticker corners, on either side of the open bore.
    label_w = min(.053,width*.30)
    offset = label_w/2+.013
    for sign in (-1,1):
        ring = []
        for i in range(16):
            t = math.tau*i/16
            u,v = math.cos(t),math.sin(t)
            ring.append(bm.verts.new((sign*offset+label_w*.5*math.copysign(abs(u)**.30,u),
                        depth/2+.0005,height*.405*math.copysign(abs(v)**.30,v))))
        face = bm.faces.new(ring[::-1])
        face.material_index = 1
    plate = _obj("Selector plate",bm,p,"stack",loc)
    plate.data.materials.append(K.mat("grip"))
    return plate,offset


def _plate_stack(p,x,y,w,d,h,z0,stroke,side):
    import bpy
    n = 20
    selection = "Pin row"+side
    K._control(p,selection,6,1,n,"Selected row, counted from the lightest plate at the top")
    K._control(p,stroke)
    pitch = min(.040,(h-.40)/n)
    height = pitch-.0017
    width,depth = w-.074,d-.085
    base = z0+.055+height/2
    top = base+(n-1)*pitch
    travel = min(.28,z0+h-top-.15)
    for i in range(n):
        z = top-i*pitch
        if i == 0:
            plate,offset = _selector_plate(p,width,depth,height,(x,y,z))
            mesh = plate.data
        else:
            plate = bpy.data.objects.new("Selector plate",mesh)
            bpy.data.collections["Kit"].objects.link(plate)
            plate.parent,plate.location = p,(x,y,z)
        plate.rotation_euler.z = math.pi
        kg = 2.5+i*5
        # Labels use plate-local coordinates and turn with the selector face.
        for dx,number in ((offset,str(round(kg*2.20462262))),(-offset,f"{kg:g}")):
            K._lettering(plate,number,(dx,depth/2+.0008,0),
                         min(.020,height*.55,(offset-.013)*.84),(90,0,180))
        K._driver(plate,"location",2,p,f"{z!r}+({travel!r}*v if row>{i} else 0)",
                  v=stroke,row=selection)
    lift = part("Head plate assembly")
    lift.parent,lift.location = p,(x,y,top)
    lift.rotation_euler.z = math.pi
    K._stroke(lift,"location",2,p,travel,stroke)
    for sign in (-1,1):
        cyl("Guide bushing",lift,.017,.009,"Z","red",(sign*w*.26,0,height/2+.004))
    cyl("Cable terminal",lift,.012,.045,"Z","steel",(0,0,height/2+.019))
    _hex(lift,"Locknut",(0,0,height/2+.039),.019,.012,"Z")
    pin = part("Selector pin")
    pin.parent,pin.location = p,(x,y,top)
    pin.rotation_euler.z = math.pi
    K._driver(pin,"location",2,p,f"{top!r}-(row-1)*{pitch!r}+{travel!r}*v",row=selection,v=stroke)
    face = depth/2
    cyl("Pin shaft",pin,.0065,depth*.63,"Y","steel",(0,face-depth*.29,0))
    cyl("Selector knob",pin,.017,.035,"Y","grip",(0,face+.020,0))
    cyl("Pin end insert",pin,.009,.002,"Y","accent",(0,face+.038,0))
    # Keep the coil attached to the head plate and the knob at every selection.
    anchor_x = .014
    cyl("Tether anchor",lift,.006,.012,"Y","steel",(anchor_x,face+.004,.005))
    coil = []
    for i in range(101):
        u=i/100
        a=math.tau*18*u
        coil.append((anchor_x*(1-u)+.004*math.sin(a),
                     face+.008+.030*u+.004*(1-math.cos(a)),-u))
    tether = _path(lift,"Selector coiled lanyard",coil,.00125,"grip")
    # One morph keeps the wire gauge constant while the helix changes length.
    for i,pt in enumerate(tether.data.splines[0].points):
        pt.co.z = .005*(1-i/100)
    tether.shape_key_add(name="Top row")
    extended = tether.shape_key_add(name="Bottom row")
    for i,point in enumerate(extended.data):
        point.co.z -= (n-1)*pitch*i/100
    K._driver(extended,"value",-1,p,f"(row-1)/{n-1}",row=selection)
    return top+height/2+.04,travel


def stack_tower(p, x, y, w=0.46, d=0.40, h=1.55, z0=0.05, mat="silver"):
    """Commercial selectorised weight stack: beveled shroud, twin chrome guide rods, 14 plates, T-pin & top pulley."""
    # Base plinth + rubber feet
    box("housing", p, (w + 0.02, d + 0.02, 0.055), mat, (x, y, z0 + 0.027), bevel=0.008)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl("tower_foot", p, 0.032, z0+.008, "Z", "grip",
                (x + sx * (w * 0.42), y + sy * (d * 0.40), (z0+.008)/2), sides=16)
    # Beveled side shrouds & back panel
    for s in (-1, 1):
        for offset, span in ((-.25*d-.033, .5*d-.066), (.25*d+.001, .5*d-.002)):
            box("Side shroud", p, (.032,span,h-.012),mat,
                (x+s*(w/2-.023),y+offset,z0+h/2),bevel=.010)
    rear = y+d/2-.016
    for side in (-1,1):
        # Formed shoulders turn around the rear corners; three profile stations
        # narrow the cover at its crown without changing its mounting footprint.
        bm = bmesh.new()
        previous = None
        for height, inset in ((.018,.014),(.12,0),(.76,0),(.805,.006),(.93,.009),(.993,.024)):
            ring = []
            for u,v in ((.39,-.005),(.401,.014),(.425,.011),(.44,.010),
                        (.48,-.008),(.49,-.040),(.48,-.060),(.40,-.055),(.34,-.016)):
                ring.append(bm.verts.new((side*(w*u-inset),rear+v-(.030 if height>=.805 else .0),z0+h*height)))
            if previous:
                for i in range(len(ring)):
                    j = (i+1)%len(ring)
                    bm.faces.new((previous[i],previous[j],ring[j],ring[i]))
            else:
                bm.faces.new(ring)
            previous = ring
        bm.faces.new(previous)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        shell = _obj("Rolled tower shoulder",bm,p,mat,(x,0,0))
        K._add_bevel(shell,.004,segments=2)
        rail_x = x+side*(w*.50-.011)
        rod("Exposed tower tube",p,(rail_x,y-.035,z0+.02),
            (rail_x,y-.035,z0+h-.018),.019,"steel")
    box("Rear stack guard",p,(w*.78,.012,h*.738),mat,
        (x,rear-.017,z0+h*.38),bevel=.005)
    box("Service panel",p,(w*.43,.032,h*.248),mat,
        (x,rear-.029,z0+h*.876),bevel=.009)
    box("Guide mounting boss",p,(w*.29,.039,.066),"silver",
        (x,rear-.009,z0+h*.875),bevel=.004)
    _placard(p,x,rear+.010,z0+h*.875,w*.72,rear=True)
    # Twin front shroud wings leaving a clean vertical selector slot in the middle
    wing_w = w * 0.24
    for s in (-1, 1):
        box("hfront_wing", p, (wing_w, 0.024, h * 0.86), "grip",
            (x + s * (w / 2 - wing_w / 2 - 0.02), y - d / 2 + 0.014, z0 + h * 0.44), bevel=0.005)
    # Molded top cap + angled instructional placard
    # Separate the user's tray from the open cable bay. The load strand
    # enters the stack through the bay, never through either accessory pocket.
    cap_depth = d+.02
    _tray(p,x,y+cap_depth*.28,z0+h,w+.02,cap_depth*.44)
    for side in (-1,1):
        box("Cable bay side rail",p,(.024,cap_depth*.57,.039),"silver",
            (x+side*(w/2-.002),y-cap_depth*.22,z0+h-.011),bevel=.007)
    box("Head bearing mount",p,(w-.020,.033,.039),"silver",
        (x,y-.014,z0+h-.020),bevel=.004)
    box("cover",p,(w+.01,.033,h*.19),mat,(x,y-d/2+.007,z0+h*.894),bevel=.008)
    _placard(p,x,y-d/2-.018,z0+h*.90,w*.80)
    # Twin chrome vertical guide rods
    for s in (-1, 1):
        rod("guide_rod", p, (x + s * (w * 0.26), y, z0 + 0.05), (x + s * (w * 0.26), y, z0 + h - 0.03), 0.011, "steel", sides=16)
    dual = p.name.startswith(("P_cable_crossover","P_functional_trainer"))
    side = (" L" if x<0 else " R") if dual else ""
    stroke = "Stroke"+side
    cable_z,travel = _plate_stack(p,x,y,w,d,h,z0,stroke,side)
    _stack_head(p,x,y,z0+h+.055,cable_z,stroke,travel)



def floor_feet(p, w, d, y0=0.0, mat="frame", s=0.07):
    for sx in (-1, 1):
        beam("foot", p, (sx * w / 2, y0 - d / 2, s / 2), (sx * w / 2, y0 + d / 2, s / 2), s, mat, s)


# ---------------------------------------------------------------- free-weight stations
def power_rack():
    """Four-post power rack: top frame, J-hooks, safety bars, plate pegs, pull-up bar."""
    p = part("power_rack"); W, D, H = 1.25, 1.10, 2.30
    for sx in (-1, 1):
        for sy in (-1, 1):
            _rack_post(p,sx*W/2,sy*D/2,H,.07*THICK,.07*THICK)
        beam("side_top", p, (sx * W / 2, -D / 2, H), (sx * W / 2, D / 2, H), 0.07)
        beam("base", p, (sx * W / 2, -D / 2 - 0.35, 0.035), (sx * W / 2, D / 2 + 0.25, 0.035), 0.074, "frame", 0.07)
        beam("brace", p, (sx * W / 2, -D / 2, 0.35), (sx * W / 2, D / 2, 1.15), 0.04)
        x = sx * W/2
        box("cup_back",p,(.085,.045,.15),"silver",(x,-D/2-.066,1.40))
        box("cup_cradle",p,(.079,.091,.022),"grip",(x,-D/2-.091,1.35))
        box("cup_lip",p,(.083,.021,.046),"silver",(x,-D/2-.132,1.36))
        beam("safety",p,(x,-D/2,.62),(x,D/2,.62),.036,"silver")
        box("Urethane cup liner",p,(.073,.006,.098),"grip",(x,-D/2-.090,1.401))
        box("Safety landing strip",p,(.046,D-.06,.009),"grip",(x,0,.650))
        grip_handle("neutral_pull",p,(x*.57,-D/2,H-.035),(x*.55,-D/2-.22,H-.05),.017)
        cup = _linkage(p,(x,-D/2,1.35),
                       ("cup_back","cup_cradle","cup_lip","Urethane cup liner"),sx)
        K._control(p,"Cup holes",0,-7,7,"J-cup height in hole increments")
        K._driver(cup,"location",2,p,"1.35+.0508*v",v="Cup holes")
        catch = _linkage(p,(x,0,.62),("safety","Safety landing strip"),sx)
        K._control(p,"Safety holes",0,-5,8,"Safety height in hole increments")
        K._driver(catch,"location",2,p,".62+.0254*v",v="Safety holes")
    beam("front_top", p, (-W / 2, -D / 2, H), (W / 2, -D / 2, H), 0.07)
    beam("back_top", p, (-W / 2, D / 2, H), (W / 2, D / 2, H), 0.07)
    rod("pullup", p, (-W / 2, -D / 2 - 0.22, H - 0.05), (W / 2, -D / 2 - 0.22, H - 0.05), 0.017)
    for sx in (-1, 1): beam("pu_arm", p, (sx * W / 2, -D / 2, H - 0.05), (sx * W / 2, -D / 2 - 0.22, H - 0.05), 0.05)
    for sx in (-1, 1):
        for z in (0.5, 1.0): cyl("peg", p, 0.025, 0.22, "Y", "steel", (sx * (W / 2 + 0.05), D / 2 + 0.08, z), 6)
    return p


def smith_machine():
    """Smith: guide-rod uprights with long feet, top beam, counter-balanced bar with hooks, plate pegs, safety catches."""
    p = part("smith_machine"); H = 2.25
    for s in (-1, 1):
        _rack_post(p,s*.72,0,H,.09*THICK,.09*THICK)
        box("Smith safety stop",p,(.104,.13,.075),"grip",(s*.72,-.065,.53),bevel=.01)
        rod("rail", p, (s * 0.72, -0.07, 0.10), (s * 0.72, -0.07, H - 0.05), 0.016)
        beam("foot", p, (s * 0.72, -0.55, 0.04), (s * 0.72, 0.55, 0.04), 0.09, "frame", 0.08)
        beam("brace", p, (s * 0.72, 0.5, 0.06), (s * 0.72, 0.03, H - 0.4), 0.05)
        for i in range(8): box("catch", p, (0.05, 0.09, 0.03), "accent" if i == 1 else "steel", (s * 0.72, -0.08, 0.30 + i * 0.22))
        for z in (0.55, 1.0, 1.45): cyl("peg", p, 0.022, 0.25, "Y", "steel", (s * 0.72, 0.18, z), 6)
    beam("top", p, (-0.72, 0, H), (0.72, 0, H), 0.09)
    _chin_grips(p,.72,H,.20)
    sb = part("smith_bar"); sb.parent = p; sb.location = (0, -0.10, 1.30)
    cyl("bar", sb, 0.016, 2.0, "X", "steel", sides=8)
    for s in (-1, 1):
        cyl("linear_sleeve",sb,.040,.18,"Z","silver",(s*.72,.03,0))
        for z in (-.088,.088):
            cyl("wiper",sb,.042,.014,"Z","grip",(s*.72,.03,z))
        rod("safety_hook",sb,(s*.72,.03,0),(s*.68,.062,.071),.015)
        rod("hook_return",sb,(s*.68,.062,.071),(s*.68,.096,.052),.014)
        for i, r in enumerate((0.2, 0.2)): cyl("plate", sb, r, 0.03, "X", "plate", (s * (0.90 + i * 0.04), 0, 0), 12)

    K._stroke(sb,"location",2,p,.46)
    return p


# ---------------------------------------------------------------- benches
def _bench_transport(p,front,rear):
    for side in (-1,1):
        cyl("transport_wheel",p,.043,.026,"X","grip",(side*.17,rear,.047))
        cyl("axle_cap",p,.016,.034,"X","steel",(side*.17,rear,.047))
        rod("lift_bracket",p,(side*.078,front,.04),(side*.078,front-.045,.12),.012)
    grip_handle("lift_grip",p,(-.078,front-.045,.12),(.078,front-.045,.12),.016)


def flat_bench():
    p = part("flat_bench")
    _bench_transport(p,-.55,.55)
    pad("seat",p,(.30,.36,.085),(0,-.42,.43))
    pad("back",p,(.30,.828,.085),(0,.186,.43))
    box("trim", p, (0.28, 1.18, 0.03), "grip", (0, 0, 0.39))
    for s in (-1, 1):
        beam("leg", p, (0, s * 0.50, 0.38), (0, s * 0.56, 0.02), 0.07)
        box("foot", p, (0.46, 0.06, 0.04), "frame", (0, s * 0.56, 0.02))
    beam("spine", p, (0, -0.5, 0.36), (0, 0.5, 0.36), 0.06)
    return p


def adjustable_bench(angle=45):
    """Back pad hinged at the seat rear (child P_adj_back, rotation_euler.x = -angle)."""
    p = part("adjustable_bench")
    pad("seat", p, (0.30, 0.38, 0.08), (0, -0.10, 0.45)); box("seat_trim", p, (0.28, 0.36, 0.03), "grip", (0, -0.10, 0.405))
    beam("spine", p, (0, -0.28, 0.33), (0, 0.55, 0.33), 0.063)
    beam("leg_f", p, (0, -0.22, 0.40), (0, -0.28, 0.02), 0.07); box("foot_f", p, (0.50, 0.06, 0.04), "frame", (0, -0.28, 0.02))
    beam("leg_b", p, (0, 0.45, 0.33), (0, 0.55, 0.02), 0.07); box("foot_b", p, (0.50, 0.06, 0.04), "frame", (0, 0.55, 0.02))
    for side in (-1,1):
        beam("ladder_rail",p,(side*.061,.12,.34),(side*.061,.45,.62),.018,"silver")
    for i in range(6):
        cyl("ladder_rung",p,.013,.13,"X","steel",(0,.135+i*.06,.353+i*.051))
    _bench_transport(p,-.28,.55)
    pv = part("adj_back"); pv.parent = p; pv.location = (0, 0.12, 0.47)
    pad("back", pv, (0.30, 0.78, 0.08), (0, 0.39, 0)); box("back_trim", pv, (0.28, 0.76, 0.03), "grip", (0, 0.39, -0.045))
    beam("back_frame", pv, (0, 0.05, -0.07), (0, 0.72, -0.07), 0.06)
    pv.rotation_euler.x = -math.radians(angle)
    K._stroke(pv,"rotation_euler",0,p,math.radians(72),"Bench adjustment")
    tip = part("Stay joint")
    tip.parent,tip.location = pv,(0,.22,-.07)
    anchor = Vector((0,.255,.455))
    theta = pv.rotation_euler.x
    end = Vector((0,.12+.22*math.cos(theta)+.07*math.sin(theta),
                    .47+.22*math.sin(theta)-.07*math.cos(theta)))
    length = (end-anchor).length
    stay = box("locking_stay",p,(.041,length,.041),"silver",anchor)
    for vert in stay.data.vertices:
        vert.co.y += length/2
    track = stay.constraints.new("STRETCH_TO")
    track.target,track.rest_length,track.volume = tip,length,"NO_VOLUME"
    return p


def decline_bench():
    p = part("decline_bench")
    pad("seat", p, (0.30, 0.38, 0.08), (0, -0.28, 0.58), (-12, 0, 0)); pad("back", p, (0.30, 0.90, 0.08), (0, 0.38, 0.46), (-12, 0, 0))
    beam("spine", p, (0, -0.4, 0.45), (0, 0.75, 0.30), 0.07)
    beam("leg_f", p, (0, -0.36, 0.52), (0, -0.40, 0.02), 0.08); box("foot_f", p, (0.55, 0.06, 0.04), "frame", (0, -0.40, 0.02))
    beam("leg_b", p, (0, 0.75, 0.30), (0, 0.80, 0.02), 0.07); box("foot_b", p, (0.50, 0.06, 0.04), "frame", (0, 0.80, 0.02))
    beam("roller_arm", p, (0, -0.40, 0.55), (0, -0.62, 0.62), 0.05)
    for z in (0.60, 0.74): cyl("roller", p, 0.055, 0.40, "X", "pad", (0, -0.66, z), 8)
    return p


def preacher_bench():
    p = part("preacher_bench")
    pad("seat", p, (0.34, 0.30, 0.08), (0, 0.22, 0.46))
    pad("arm_pad", p, (0.40, 0.55, 0.08), (0, -0.20, 0.82), (-38, 0, 0))
    beam("post", p, (0, 0.2, 0.40), (0, 0.2, 0.02), 0.07); box("foot_b", p, (0.55, 0.06, 0.04), "frame", (0, 0.2, 0.02))
    beam("arm_post", p, (0, -0.05, 0.75), (0, -0.30, 0.05), 0.07); box("foot_f", p, (0.55, 0.06, 0.04), "frame", (0, -0.30, 0.02))
    beam("link", p, (0, -0.05, 0.60), (0, 0.2, 0.40), 0.05)
    return p


# ---------------------------------------------------------------- cable stations
def cable_crossover():
    """Two stack towers joined by a top beam; adjustable pulley carriages on slotted uprights."""
    p = part("cable_crossover"); W = 2.1; H = 2.3
    for s in (-1, 1):
        _rack_post(p,s*W/2,0,H,.10*THICK,.12*THICK)
        beam("post_b", p, (s * W / 2, 0.30, 0), (s * W / 2, 0.30, H * 0.78), 0.10, "silver", 0.10)
        beam("link", p, (s * W / 2, 0, H * 0.78), (s * W / 2, 0.30, H * 0.78), 0.084, "silver")
        stack_tower(p, s * W / 2, 0.58, 0.40, 0.34, 1.25, 0.05)
        beam("foot", p, (s * W / 2, -0.30, 0.04), (s * W / 2, 0.80, 0.04), 0.106, "frame", 0.083)
        _trolley(p,s*W/2,1.45)
        cyl("Storage pin",p,.021,.14,"X","steel",(s*(W/2+.105),.30,.62))
    _chin_grips(p,W/2,H,.18)
    beam("top", p, (-W / 2, 0, H), (W / 2, 0, H), 0.12, "silver", 0.10)
    return p


def lat_pulldown():
    p = part("lat_pulldown"); H = 2.20
    stack_tower(p, 0, 0.58, 0.46, 0.38, 1.3, 0.05)
    beam("mast", p, (0, 0.20, 0), (0, 0.20, H), 0.12, "silver", 0.10)
    beam("arm", p, (0, 0.20, H), (0, -0.55, H - 0.05), 0.10, "silver", 0.08)
    cyl("pulley", p, 0.08, 0.05, "X", "accent", (0, -0.45, H - 0.12), 10)
    box("seat", p, (0.36, 0.34, 0.08), "pad", (0, -0.18, 0.46)); beam("seat_post", p, (0, -0.18, 0.42), (0, -0.18, 0.05), 0.08)
    beam("roller_stay",p,(0,-.18,.31),(0,-.53,.65),.032,"silver")
    for side in (-1,1):
        beam("front_foot",p,(side*.28,-.54,.049),(side*.28,-.77,.049),.044,"silver")
        cyl("thigh_roller",p,.066,.21,"X","pad",(side*.12,-.53,.66))
        cyl("roller_end",p,.046,.016,"X","steel",(side*.23,-.53,.66))
    line = [(0,-.45-.074*math.sin(i*math.pi/20),
             H-.12+.074*math.cos(i*math.pi/20)) for i in range(11)]
    tail = _path(p,"Lat bar cable",line+[(0,-.524,1.92),(0,-.45,1.86)],.005,"grip")
    for i in (-1,-2):
        point = tail.data.splines[0].points[i]
        K._driver(point,"co",2,p,f"{point.co.z!r}-.48*v",v="Stroke")
    beam("base", p, (0, -0.55, 0.04), (0, 0.80, 0.04), 0.106, "frame", 0.083)
    box("foot", p, (0.80, 0.08, 0.06), "frame", (0, -0.55, 0.05))
    lb = part("lat_bar"); lb.parent = p; lb.location = (0, -0.45, H - 0.40)
    rod("bar", lb, (-0.55, 0, -0.02), (-0.30, 0, 0.06), 0.017, "steel"); rod("bar", lb, (-0.30, 0, 0.06), (0.30, 0, 0.06), 0.017, "steel")
    rod("bar", lb, (0.30, 0, 0.06), (0.55, 0, -0.02), 0.017, "steel")
    for side in (-1,1):
        grip_handle("outer_grip",lb,(side*.36,0,.041),(side*.54,0,-.017),.022)
    K._stroke(lb,"location",2,p,-.48)
    return p


def seated_cable_row():
    p = part("seated_cable_row")
    beam("base", p, (0, -0.65, 0.05), (0, 1.05, 0.05), 0.12, "silver", 0.08)
    stack_tower(p, 0, 0.95, 0.46, 0.38, 1.35, 0.08)
    pad("seat", p, (0.36, 0.34, 0.09), (0, 0.05, 0.42)); beam("seat_post", p, (0, 0.05, 0.38), (0, 0.05, 0.08), 0.08, "silver")
    pad("chest", p, (0.40, 0.10, 0.30), (0, -0.32, 0.78)); beam("chest_post", p, (0, -0.32, 0.60), (0, -0.40, 0.08), 0.08, "silver")
    beam("footboard_mount",p,(0,-.60,.06),(0,-.62,.20),.043,"silver")
    box("foot_plate", p, (0.50, 0.30, 0.04), "silver", (0, -0.62, 0.20), (35, 0, 0))
    h = part("row_handle"); h.parent = p; h.location = (0, -0.20, 0.82)
    for side in (-1,1):
        rod("v_handle",h,(0,-.18,.04),(side*.12,-.12,0),.014)
        grip_handle("row_grip",h,(side*.12,-.12,0),(side*.12,.02,0),.020)
    tail = _path(p,"Row cable",[(0,-.55,.29),(0,-.38,.86)],.005,"grip")
    K._driver(tail.data.splines[0].points[-1],"co",1,p,"-.38+.30*v",v="Stroke")
    K._stroke(h,"location",1,p,.30)
    for i in range(-2,3):
        t=i*.047
        box("foot_rib",p,(.47,.012,.008),"grip",(0,-.634+t*.819,.221+t*.574),(35,0,0))
    return p


# ---------------------------------------------------------------- selectorised / plate-loaded machines
def _seat_unit(p, back_y=0.20):
    pad("seat", p, (0.42, 0.40, 0.09), (0, back_y - 0.20, 0.45))
    beam("seat_post", p, (0, back_y - 0.2, 0.30), (0, back_y - 0.2, 0.06), 0.07, "silver")
    rod("seat_slide", p, (0, back_y - 0.2, 0.20), (0, back_y - 0.2, 0.44), 0.024, "steel")
    cyl("seat_pop_pin", p, 0.018, 0.045, "Y", "accent", (0, back_y - 0.260, 0.285), sides=16)
    _seat_lever(p,back_y-.20,.33)
    pad("lumbar",p,(.38,.105,.22),(0,back_y-.028,.619),(-8,0,0))
    pad("back",p,(.42,.10,.39),(0,back_y+.017,.937),(-8,0,0))
    beam("back_post", p, (0, back_y + 0.06, 0.44), (0, back_y + 0.11, 1.12), 0.065, "silver")
    cyl("back_pop_pin", p, 0.016, 0.04, "X", "accent", (0.06, back_y + 0.08, 0.60), sides=16)


def chest_press_machine():
    p = part("chest_press_machine")
    beam("base", p, (0, -0.85, 0.05), (0, 1.0, 0.05), 0.12, "silver", 0.07)
    for s in (-1, 1):
        beam("footbar", p, (s * 0.40, -0.85, 0.05), (s * 0.40, 0.4, 0.05), 0.06, "silver")
    stack_tower(p, 0, 0.82, 0.48, 0.40, 1.45, 0.07)
    _seat_unit(p, 0.15)
    _drive(p,(.32,.20,.95))
    # Foot assist pedal & overhead pivot bridge
    beam("pedal_stem",p,(0,-.51,.07),(0,-.58,.16),.023,"silver")
    beam("base_cross",p,(-.40,.20,.065),(.40,.20,.065),.044,"silver")
    rod("foot_pedal", p, (-0.28, -0.58, 0.16), (0.28, -0.58, 0.16), 0.018, "steel")
    beam("pivot_bridge", p, (-0.34, 0.20, 0.56), (0.34, 0.20, 0.56), 0.05, "silver")
    for s in (-1, 1):
        beam("lever_knuckle",p,(s*.32,.20,.95),(s*.41,-.065,1.035),.040,"frame")
        beam("press_forearm",p,(s*.41,-.065,1.035),(s*.40,-.30,.95),.039,"frame")
        beam("pivot_arm", p, (s * 0.32, 0.20, 0.95), (s * 0.32, 0.20, 0.55), 0.05, "silver")
        if s < 0:
            pivot_hub("press_hub", p, (s * 0.32, 0.20, 0.95), r=0.052, width=0.07, axis="X")
        # Dual horizontal + neutral press handles
        grip_handle("handle", p, (s * 0.40, -0.30, 0.95), (s * 0.40, -0.46, 0.95), 0.022)
        grip_handle("handle_v", p, (s * 0.40, -0.32, 0.86), (s * 0.40, -0.32, 1.04), 0.020)
    for side in (-1,1):
        _hinge(p,(side*.32,.20,.95),("lever_knuckle","press_forearm","handle","handle_v"),
               2,-side*26,side)
    return p


def pec_deck():
    p = part("pec_deck")
    beam("base", p, (0, -0.45, 0.05), (0, 0.9, 0.05), 0.12, "silver", 0.07)
    stack_tower(p, 0, 0.78, 0.48, 0.40, 1.45, 0.07)
    _seat_unit(p, 0.15)
    beam("overhead_spine",p,(0,.76,1.42),(0,.03,1.46),.065,"silver")
    for s in (-1,1):
        x = s*.19
        beam("crosshead",p,(0,.03,1.46),(x,.03,1.46),.045,"silver")
        pivot_hub("fly_hinge",p,(x,.03,1.47),.068,.068,"Z")
        rod("fly_cable",p,(x,.04,1.50),(0,.60,1.50),.005,"grip")
        beam("swing_arm",p,(x,.03,1.43),(s*.40,-.19,1.38),.038,"frame")
        beam("arm_drop",p,(s*.40,-.19,1.38),(s*.40,-.28,.82),.039,"silver")
        grip_handle("fly_outer",p,(s*.40,-.28,.85),(s*.34,-.34,.85),.018)
        pad("pad", p, (0.10, 0.12, 0.34), (s * 0.40, -0.28, 0.98))
        grip_handle("pec_grip", p, (s * 0.40, -0.28, 0.74), (s * 0.40, -0.28, 0.88), 0.020)
    for side in (-1,1):
        _hinge(p,(side*.19,.03,1.47),("swing_arm","arm_drop","pad","pec_grip","fly_outer"),
               2,-side*36,side)
    return p


def leg_extension():
    p = part("leg_extension")
    beam("base", p, (0, -0.65, 0.05), (0, 0.95, 0.05), 0.12, "silver", 0.07)
    stack_tower(p, 0, 0.80, 0.46, 0.38, 1.35, 0.07)
    pad("seat", p, (0.42, 0.44, 0.09), (0, 0.0, 0.44))
    beam("seat_post", p, (0, 0.0, 0.40), (0, 0.0, 0.06), 0.075, "silver")
    pad("back", p, (0.42, 0.10, 0.50), (0, 0.28, 0.76), (-12, 0, 0))
    beam("back_post", p, (0, 0.34, 0.5), (0, 0.38, 0.9), 0.06, "silver")
    for s in (-1, 1):
        grip_handle("side_grip", p, (s * 0.27, -0.14, 0.44), (s * 0.27, 0.06, 0.44), 0.020)
    lv = part("leg_lever"); lv.parent = p; lv.location = (0, -0.25, 0.30)
    pivot_hub("leg_pivot", lv, (0.22, 0, 0), r=0.058, width=0.06, axis="X")
    _dial(lv,.246,0,0,.11)
    for s in (-1, 1):
        beam("arm", lv, (s * 0.20, 0, 0), (s * 0.20, -0.30, -0.02), 0.045, "silver")
    cyl("roller", lv, 0.062, 0.42, "X", "pad", (0, -0.32, -0.02), sides=24)
    cyl("roller_cap_l", lv, 0.045, 0.016, "X", "steel", (-0.215, -0.32, -0.02), sides=20)
    cyl("roller_cap_r", lv, 0.045, 0.016, "X", "steel", (0.215, -0.32, -0.02), sides=20)
    beam("cam", p, (0.2, -0.25, 0.30), (0.2, 0.45, 0.50), 0.035, "silver")
    K._stroke(lv,"rotation_euler",0,p,-.96)
    return p


def leg_press_45():
    """Twin 45-degree guide rods with a captive sled and flip-up safety catches."""
    p = part("leg_press_45")
    sl = part("sled")
    sl.parent, sl.location = p,(0,-.60,.62)
    for side in (-1,1):
        x=side*.40
        beam("base_runner",p,(x,-1.30,.055),(x,.90,.055),.073,"silver")
        beam("rear_stay",p,(x,-1.25,.09),(x,-1.04,1.06),.066)
        beam("incline_stringer",p,(x,.18,.10),(x,-1.04,.99),.053,"silver")
        rod("chrome_guide",p,(x,-.10,.12),(x,-1.04,1.06),.028)
        for y,z in ((-.10,.12),(-1.04,1.06)):
            box("guide_socket",p,(.112,.095,.10),"frame",(x,y,z),(45,0,0))
        rod("linear_bearing",sl,(x,.093,-.093),(x,-.093,.093),.049,"silver")
        rod("dust_seal",sl,(x,-.096,.096),(x,-.11,.11),.05,"grip")
        beam("seat_cradle",p,(x,.76,.10),(side*.16,.71,.43),.045,"silver")
        rod("release_shaft",p,(x,-.46,.37),(x,.39,.39),.014)
        rod("lock_handle",p,(x,.39,.39),(x,.32,.54),.016)
        grip_handle("safety_grip",p,(x,.32,.54),(x,.17,.54),.02)
        rod("side_grip_mount",p,(x,.58,.10),(side*.29,.58,.29),.022)
        grip_handle("side_grip",p,(side*.29,.58,.29),(side*.29,.42,.29),.02)
        cyl("load_horn",sl,.025,.37,"X","steel",(side*.565,0,0))
        cyl("rubber_stop",sl,.063,.037,"X","grip",(side*.474,0,0))
        for i in range(2):
            K._plate(sl,.205,.043,(side*(.518+i*.052),0,0),grips=True)
    for y in (-1.15,.62):
        beam("cross_member",p,(-.4,y,.08),(.4,y,.08),.061,"silver")
    beam("seat_saddle",p,(0,.62,.083),(0,.62,.18),.12,"silver")
    beam("backbone",p,(0,.90,.15),(0,.67,.88),.070,"silver")
    pad("seat",p,(.46,.46,.10),(0,.62,.20))
    pad("back",p,(.46,.10,.51),(0,.805,.552),(30,0,0))
    pad("headrest",p,(.32,.105,.176),(0,.629,.851),(30,0,0))
    beam("sled_axle",sl,(-.43,0,0),(.43,0,0),.065,"silver")
    box("footplate",sl,(.91,.061,.61),"silver",(0,0,0),(45,0,0),.019)
    for i in range(-4,5):
        t=i*.059
        y=(.034-t)*math.sqrt(.5)
        z=(.034+t)*math.sqrt(.5)
        box("traction_rib",sl,(.82,.013,.019),"grip",(0,y,z),(45,0,0),.004)
    K._stroke(sl,"location",1,p,-.24)
    K._stroke(sl,"location",2,p,.24)
    return p


def hack_squat():
    p = part("hack_squat")
    for s in (-1, 1):
        beam("rail", p, (s * 0.35, 0.80, 0.10), (s * 0.35, -0.35, 1.65), 0.07)
        beam("foot", p, (s * 0.45, -0.85, 0.04), (s * 0.45, 1.00, 0.04), 0.09, "frame", 0.08)
        beam("brace", p, (s * 0.45, -0.55, 0.04), (s * 0.35, 0.15, 1.15), 0.05)
    box("foot_plate", p, (0.60, 0.50, 0.04), "silver", (0, -0.58, 0.14), (-25, 0, 0))
    pad("back", p, (0.46, 0.10, 0.90), (0, 0.55, 0.78), (-30, 0, 0))
    for s in (-1, 1):
        pad("shoulder", p, (0.16, 0.14, 0.20), (s * 0.20, 0.38, 1.20), (-30, 0, 0))
        cyl("peg", p, 0.025, 0.35, "X", "steel", (s * 0.58, 0.60, 0.30), 6)
    return p


def plate_row():
    """Plate-loaded iso row / chest-supported row: low frame, chest pad on a post, two long handles on arms with plate pegs."""
    p = part("plate_row")
    for side in (-1, 1):
        x = side * .40
        beam("foot", p, (side*.55, -.40, .04), (side*.55, 1.0, .04), .10, "frame", .08)
        beam("bearing_support", p, (side*.55, .42, .09), (x, .30, .79), .045, "silver")
        pivot_hub("iso_bearing", p, (x, .30, .80), .079, .12)
        lever = part("row_lever_L" if side < 0 else "row_lever_R")
        lever.parent, lever.location = p, (x, .30, .80)
        K._stroke(lever,"rotation_euler",0,p,.43,"Stroke L" if side<0 else "Stroke R")
        beam("pull_arm", lever, (0, 0, 0), (0, -.70, -.25), .060)
        beam("load_arm", lever, (0, 0, 0), (side*.05, .55, -.30), .060)
        cyl("balance_slug", lever, .078, .085, "X", "silver", (side*.05, .47, -.26))
        grip_handle("wide_grip", lever, (0, -.70, -.25), (-side*.16, -.70, -.25), .019)
        grip_handle("neutral_grip", lever, (0, -.70, -.25), (0, -.85, -.10), .022)
        cyl("peg", lever, .025, .30, "X", "steel", (side*.18, .55, -.30))
        for i in range(2):
            K._plate(lever, .22, .033, (side*(.24+i*.041), .55, -.30), grips=True)
        box("footboard", p, (.19,.28,.034), "silver", (side*.37,-.19,.19), (25,0,0))
        beam("footrest_stay", p, (side*.52,-.14,.06), (side*.37,-.19,.17), .028, "silver")
    box("cross", p, (1.10, 0.10, 0.10), "frame", (0, 0.30, 0.78))
    pad("chest", p, (0.40, 0.10, 0.46), (0, 0.0, 0.95), (-15, 0, 0)); beam("post", p, (0, 0.05, 0.92), (0, 0.10, 0.04), 0.09)
    pad("seat", p, (0.40, 0.34, 0.09), (0, 0.50, 0.44)); beam("seat_post", p, (0, 0.5, 0.4), (0, 0.5, 0.05), 0.08)
    return p


def pullup_dip_tower():
    """Captain's chair / VKR tower: two uprights, back pad, forearm pads with grips, dip handles, pull-up bars."""
    p = part("pullup_dip_tower"); H = 2.35
    for s in (-1, 1):
        beam("post", p, (s * 0.38, 0.35, 0), (s * 0.38, 0.35, H), 0.08)
        beam("foot", p, (s * 0.38, -0.35, 0.04), (s * 0.38, 0.75, 0.04), 0.09, "frame", 0.08)
        beam("front", p, (s * 0.38, 0.35, 1.05), (s * 0.38, -0.20, 1.05), 0.06)
        pad("forearm", p, (0.10, 0.34, 0.06), (s * 0.38, -0.02, 1.12))
        rod("grip", p, (s * 0.38, -0.20, 1.12), (s * 0.38, -0.20, 1.28), 0.02, "grip")
        beam("pu_arm", p, (s * 0.38, 0.35, H), (s * 0.38, 0.0, H), 0.07)
        rod("dip", p, (s * 0.38, 0.12, 1.60), (s * 0.38, -0.22, 1.60), 0.02, "grip")
        beam("dip_post", p, (s * 0.38, 0.35, 1.60), (s * 0.38, 0.12, 1.60), 0.06)
    pad("back", p, (0.46, 0.08, 0.70), (0, 0.38, 1.35)); beam("back_bar", p, (-0.38, 0.35, 1.30), (0.38, 0.35, 1.30), 0.06)
    rod("pullup", p, (-0.48, 0.0, H), (0.48, 0.0, H), 0.017)
    return p


def hyperextension():
    p = part("hyperextension")
    beam("frame_f", p, (0, -0.35, 0.05), (0, -0.25, 0.85), 0.08); beam("frame_b", p, (0, 0.55, 0.05), (0, 0.35, 0.68), 0.08)
    box("foot_f", p, (0.60, 0.06, 0.04), "frame", (0, -0.35, 0.02)); box("foot_b", p, (0.60, 0.06, 0.04), "frame", (0, 0.55, 0.02))
    pad("hip_pad", p, (0.30, 0.34, 0.09), (0, -0.20, 0.90), (-20, 0, 0)); pad("ankle", p, (0.34, 0.12, 0.10), (0, 0.38, 0.72))
    beam("link", p, (0, -0.35, 0.40), (0, 0.45, 0.40), 0.05)
    return p


BUILD = [("power_rack", power_rack), ("smith_machine", smith_machine), ("flat_bench", flat_bench),
         ("adjustable_bench", adjustable_bench), ("decline_bench", decline_bench), ("preacher_bench", preacher_bench),
         ("cable_crossover", cable_crossover), ("lat_pulldown", lat_pulldown), ("seated_cable_row", seated_cable_row),
         ("chest_press_machine", chest_press_machine), ("pec_deck", pec_deck), ("leg_extension", leg_extension),
         ("leg_press_45", leg_press_45), ("hack_squat", hack_squat), ("plate_row", plate_row),
         ("pullup_dip_tower", pullup_dip_tower), ("hyperextension", hyperextension)]


def build_machines(row=True):
    old = bpy_col()
    out = {}
    x = 0.0
    for n, f in BUILD:
        e = f(); out[n] = e
        if row:
            e.location.x = x; x += 2.6 if n in ("power_rack", "smith_machine", "cable_crossover", "plate_row", "leg_press_45") else 1.9
    return out


def bpy_col():
    import bpy
    old = bpy.data.collections.get("Kit")
    if old:
        for o in list(old.all_objects): bpy.data.objects.remove(o, do_unlink=True)
        for c in list(old.children_recursive): bpy.data.collections.remove(c)
        bpy.data.collections.remove(old)
    for ob in [o for o in bpy.data.objects if o.name.startswith("P_") and o.users_collection == ()]: bpy.data.objects.remove(ob, do_unlink=True)
    col = bpy.data.collections.new("Kit"); bpy.context.scene.collection.children.link(col)
    return col
