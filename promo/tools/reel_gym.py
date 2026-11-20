"""Set dressing and optional selfie cast for the reel gym."""
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
import wc_lib as W

ART = Path(W.PARTS) / "reel_screens"


def rod(name, start, end, radius, material, collection, parent=None):
    a, b = Vector(start), Vector(end)
    obj = W.cyl(name, radius, (b-a).length, material, collection, (a+b)/2, parent=parent, seg=12)
    obj.rotation_euler = (b-a).to_track_quat("Z", "Y").to_euler()
    return obj


def oval(name, center, radii, material, collection, parent):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1)
    bmesh.ops.scale(bm, vec=Vector(radii), verts=bm.verts)
    return W.mesh_obj(name, bm, material, collection, center, parent=parent)


def band(name, points, width, depth, material, collection, parent, closed=False):
    """Sweep a rectangular ribbon along a planar XY loop or an XZ arch."""
    bm = bmesh.new()
    rings = []
    for i, pt in enumerate(points):
        prev = points[(i-1) % len(points)] if closed or i else points[i]
        nxt = points[(i+1) % len(points)] if closed or i+1 < len(points) else points[i]
        tangent = (Vector(nxt)-Vector(prev)).normalized()
        axis = Vector((0,0,1) if closed else (0,1,0))
        normal = tangent.cross(axis).normalized()
        rings.append([bm.verts.new(Vector(pt)+axis*w*width/2+normal*d*depth/2)
                      for w,d in ((-1,-1), (1,-1), (1,1), (-1,1))])
    for i in range(len(points) if closed else len(points)-1):
        a,b = rings[i],rings[(i+1)%len(points)]
        for j in range(4):
            k=(j+1)%4
            bm.faces.new((a[j],a[k],b[k],b[j]))
    if not closed:
        bm.faces.new(rings[0])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return W.mesh_obj(name,bm,material,collection,parent=parent)


def control(target, key, value, maximum, description):
    target[key]=value
    target.id_properties_ui(key).update(min=0,max=maximum,description=description)


def driven(curve, target, key, expression):
    driver=curve.driver
    variable=driver.variables.new()
    variable.name="v"
    variable.targets[0].id=target
    variable.targets[0].data_path='["'+key+'"]'
    driver.expression=expression


def scene_timebase(curve):
    for name,path in (("fps","render.fps"),("base","render.fps_base")):
        var=curve.driver.variables.new()
        var.name=name
        var.targets[0].id_type="SCENE"
        var.targets[0].id=bpy.context.scene
        var.targets[0].data_path=path


def molded(name, size, material, collection, xyz, parent, radius=.009):
    obj = W.box(name, size, material, collection, xyz, parent=parent)
    bevel = obj.modifiers.new("Formed edges", "BEVEL")
    bevel.width = min(radius, min(size)*.44)
    bevel.segments = 3
    obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
    return obj


def printed_face(name, filename, width, height, xyz, root, collection, emissive=False):
    opt = Path(W.PARTS) / "gym_wall_opt" / (Path(filename).stem + ".jpg")
    path = opt if opt.exists() else (Path(W.PARTS) / "gym_print" / filename)
    material = W.mat(name, (.6,.62,.6), rough=.59)
    shader = next(n for n in material.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    tex = next((n for n in material.node_tree.nodes if n.type=="TEX_IMAGE"),None) or material.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(path), check_existing=True)
    if not tex.image.packed_file: tex.image.pack()
    material.node_tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
    if emissive:
        material.node_tree.links.new(tex.outputs["Color"],shader.inputs["Emission Color"])
        shader.inputs["Emission Strength"].default_value=.57
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([(-width/2,0,-height/2),(width/2,0,-height/2),
                      (width/2,0,height/2),(-width/2,0,height/2)],[],[(0,1,2,3)])
    uv=mesh.uv_layers.new()
    for loop,coord in zip(uv.data,((0,0),(1,0),(1,1),(0,1))): loop.uv=coord
    mesh.materials.append(material)
    obj=bpy.data.objects.new(name,mesh)
    collection.objects.link(obj)
    obj.parent=root
    obj.location=xyz
    return obj


def appliance_shell(name, profile, material, collection, parent, center=(0,0)):
    """Horizontal rounded-rectangle sections, given as height, width, depth and corner radius."""
    bm=bmesh.new()
    rings=[]
    for z,width,depth,radius in profile:
        ring=[]
        for corner,(sx,sy) in enumerate(((1,1),(-1,1),(-1,-1),(1,-1))):
            for step in range(9):
                angle=(corner+step/8)*math.pi/2
                x=sx*(width/2-radius)+radius*math.cos(angle)
                y=sy*(depth/2-radius)+radius*math.sin(angle)
                ring.append(bm.verts.new((center[0]+x,center[1]+y,z)))
        rings.append(ring)
    for a,b in zip(rings,rings[1:]):
        for i in range(len(a)):
            bm.faces.new((a[i-1],a[i],b[i],b[i-1])).smooth=True
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    obj=W.mesh_obj(name,bm,material,collection,parent=parent)
    for face in obj.data.polygons:
        face.use_smooth=len(face.vertices)==4
    return obj


def appliance_label(name, string, xyz, size, material, collection, parent):
    data=bpy.data.curves.new(name,"FONT")
    data.font=W.load_font(W.KFONT)
    data.body=string
    data.size=size
    data.align_x="CENTER"
    data.align_y="CENTER"
    data.materials.append(material)
    obj=bpy.data.objects.new(name,data)
    collection.objects.link(obj)
    obj.parent=parent
    obj.location=xyz
    obj.rotation_euler.x=math.pi/2
    return obj


def water_purifier(c,root):
    # Frontal product photograph: Coway Core CHP-671R.
    white=W.mat("Purifier pearl ABS",(.76,.78,.77),rough=.35)
    silver=W.mat("Purifier silver well",(.44,.47,.48),rough=.36,metal=.21)
    black=W.mat("Core smoked glass",(.009,.012,.014),rough=.22)
    chrome=W.mat("Brushed alloy",(.46,.5,.51),rough=.27,metal=.8)
    light=W.shadeless("Core panel backlight",(.77,.87,.90),strength=.87)
    def body(name,profile,material,center=(0,0)):
        return appliance_shell(name,profile,material,c,root,center)
    def panel(name,size,mat,loc,r=.008):
        return molded(name,size,mat,c,loc,root,r)
    body("Core lower door",[(.009,.345,.418,.045),(.025,.37,.44,.052),
                             (.564,.37,.44,.052),(.575,.366,.435,.05)],white)
    body("Door reveal",[(.570,.363,.430,.05),(.582,.363,.430,.05)],silver)
    body("Tray fascia",[(.579,.367,.436,.051),(.59,.37,.44,.052),
                        (.73,.37,.44,.052),(.747,.369,.438,.05)],white)
    panel("Service access",(.061,.006,.085),silver,(0,-.221,.477))
    panel("Drain hatch",(.055,.004,.078),white,(0,-.225,.477))
    # The serving recess extends across the full front of the machine.
    body("Recess liner",[(.743,.366,.286,.049),(.983,.366,.286,.049)],silver,(0,.076))
    body("Upper cabinet",[(.979,.365,.431,.049),(.997,.37,.44,.052),
                          (1.222,.37,.44,.052),(1.238,.36,.43,.05)],white)
    panel("Dark indicator fascia",(.208,.009,.226),black,(0,-.219,1.111))
    appliance_label("Purifier mark","coway",(0,-.224,1.195),.016,light,c,root)
    for x,title in ((-.064,"온수"),(.064,"냉수")):
        for j in range(7):
            panel("Status light",(.0025,.001,.009),light,(x,-.2245,1.069+j*.013))
        appliance_label("Temperature",title,(x,-.225,1.03),.011,light,c,root)
        panel("Tap escutcheon",(.038,.020,.032),white,(x,-.205,.974))
        W.cyl("Steel nozzle",.011,.030,chrome,c,(x,-.185,.952),parent=root,seg=20)
        rod("Paddle hinge",(x,-.194,.973),(x,-.154,.946),.008,silver,c,root)
        panel("Cup push lever",(.042,.013,.067),silver,(x,-.154,.918))
    panel("Tray surround",(.331,.155,.009),silver,(0,-.135,.748))
    for i in range(15):
        panel("Tray drain slot",(.008,.103,.0015),black,((i-7)*.019,-.136,.753))


def inbody_270(c,root):
    # Distinctive folding column and pendant electrodes from the 270 front photograph.
    white=W.mat("270 pearl enclosure",(.79,.80,.78),rough=.37)
    dark=W.mat("270 anthracite",(.022,.024,.026),rough=.39)
    keys=W.mat("270 rubber keys",(.052,.054,.058),rough=.62)
    chrome=W.mat("Brushed alloy",(.46,.5,.51),rough=.27,metal=.8)
    ink=W.mat("270 printed lettering",(.018,.021,.024),rough=.68)
    pale=W.mat("270 key legends",(.81,.83,.82))
    def body(name,profile,material,center=(0,0)):
        return appliance_shell(name,profile,material,c,root,center)
    for x in (-.20,.20):
        for y in (-.21,.21):
            W.cyl("Leveling foot",.036,.024,chrome,c,(x,y,.012),parent=root,seg=20)
    body("270 scale base",[(.023,.491,.528,.039),(.047,.504,.54,.045),
                          (.108,.479,.51,.041)],dark)
    body("270 beveled deck",[(.10,.492,.527,.04),(.124,.512,.546,.041),
                             (.147,.493,.530,.043)],keys)
    for x in (-.158,.158):
        for y,w,d in ((-.154,.091,.069),(.020,.103,.143)):
            body("Bare metal contact",[(.146,w-.006,d-.006,.024),(.150,w,d,.027),
                                       (.152,w-.004,d-.004,.026)],chrome,(x,y))
    # Folding pivot is exposed between deck and wide oval upright.
    rod("270 hinge axle",(-.080,.142,.194),(.080,.142,.194),.043,dark,c,root)
    molded("270 pedestal shoe",(.151,.106,.06),dark,c,(0,.147,.175),root)
    body("Pearl folding column",[(.212,.139,.102,.044),(.252,.151,.108,.047),
                                 (1.24,.152,.112,.05),(1.29,.143,.109,.048)],white,(0,.146))
    mark=appliance_label("270 column mark","InBody 270",(0,.088,1.035),.044,ink,c,root)
    mark.rotation_euler.y=math.pi/2
    for side in (-1,1):
        x=side*.16
        rod("Electrode shoulder",(side*.057,.141,1.283),(x,.140,1.283),.022,dark,c,root)
        smooth_mesh(oval("Swivel end",(x,.14,1.28),(.026,.027,.036),dark,c,root))
        rod("Hanging black lead",(x,.14,1.271),(side*.164,.12,.938),.009,dark,c,root)
        body("Pendant electrode grip",[(.698,.018,.024,.008),(.72,.026,.031,.011),
                                      (.825,.043,.044,.020),(.884,.040,.04,.017),
                                      (.935,.021,.026,.009),(.945,.019,.023,.008)],white,(side*.164,.12))
        smooth_mesh(oval("Pendant thumb contact",(side*.164,.100,.836),(.012,.004,.032),
                         chrome,c,root))
    console=W.empty("270 keypad console",c,(0,.135,1.364),parent=root)
    console.rotation_euler.x=math.radians(-13)
    appliance_shell("270 console housing",[
        (-.146,.130,.075,.032),(-.126,.189,.090,.040),(-.083,.210,.098,.041),
        (.082,.202,.098,.040),(.132,.182,.092,.039),(.146,.165,.085,.035)],white,c,console)
    molded("Inset control face",(.157,.009,.227),dark,c,(0,-.05,.010),console,.004)
    printed_face("Analyzer result LCD","composition.png",.138,.101,(0,-.055,.046),console,c,True)
    appliance_label("Control panel mark","InBody",(0,-.055,.110),.010,pale,c,console)
    for row,line in enumerate(("123▲","456▼","789C","·0↵E")):
        for col,letter in enumerate(line):
            x=(col-1.5)*.034
            z=-.017-row*.020
            molded("Membrane key",(.029,.003,.016),keys,c,(x,-.0553,z),console,.001)
            appliance_label("Key legend",letter,(x,-.057,z),.009,pale,c,console)


def paper_cup_dispenser(c, root):
    """Wall-mounted vertical paper cup dispenser next to the water purifier."""
    dark = W.mat("Dispenser charcoal ABS", (.028, .031, .035), rough=.38)
    tube = W.mat("Dispenser frosted tube", (.76, .79, .80), rough=.26)
    cup_w = W.mat("Paper cup white", (.88, .88, .85), rough=.72)
    cup_rim = W.mat("Paper cup band", (.22, .48, .72), rough=.62)
    chrome = W.mat("Brushed alloy", (.46, .5, .51), rough=.27, metal=.8)
    # Wall plate & clamping collar (local -Y faces the room)
    molded("Cup dispenser plate", (.072, .014, .11), dark, c, (0, .052, .02), root, .004)
    molded("Cup dispenser collar", (.096, .085, .048), dark, c, (0, .012, .02), root, .008)
    # Main vertical sleeve (z = -0.18 .. +0.24)
    W.cyl("Cup dispenser tube", .041, .41, tube, c, (0, -.018, .035), parent=root, seg=28)
    # Top hinged cap
    W.cyl("Cup dispenser lid", .046, .024, dark, c, (0, -.018, .248), parent=root, seg=28)
    molded("Cup lid tab", (.022, .016, .010), dark, c, (0, -.062, .248), root, .003)
    # Bottom pull collar
    W.cyl("Cup dispenser nozzle", .045, .032, dark, c, (0, -.018, -.175), parent=root, seg=28)
    W.cyl("Cup nozzle ring", .039, .010, chrome, c, (0, -.018, -.192), parent=root, seg=24)
    # Ready-to-pull paper cup peeking out the bottom
    W.cyl("Bottom paper cup", .031, .068, cup_w, c, (0, -.018, -.215), r2=.024, parent=root, seg=24)
    W.cyl("Bottom cup stripe", .0285, .012, cup_rim, c, (0, -.018, -.218), r2=.027, parent=root, seg=24)


def gym_trash_bin(c, root):
    """Matte black commercial gym waste bin under the paper cup dispenser."""
    black = W.mat("Trash bin matte black", (.018, .020, .023), rough=.52)
    lid_m = W.mat("Trash bin satin lid", (.030, .033, .037), rough=.40)
    liner = W.mat("Trash bin dark interior", (.006, .007, .008), rough=.85)
    cup_w = W.mat("Paper cup white", (.88, .88, .85), rough=.72)
    # Tapered rounded-rect body (z = 0 .. 0.56)
    appliance_shell("Trash bin body", [
        (.004, .23, .19, .032), (.02, .25, .21, .036),
        (.52, .31, .25, .042), (.56, .32, .26, .044)
    ], black, c, root)
    # Rim collar + hooded top with front open chute (local -Y faces room)
    appliance_shell("Trash bin collar", [
        (.555, .332, .272, .046), (.595, .332, .272, .046)
    ], lid_m, c, root)
    appliance_shell("Trash bin hood", [
        (.592, .322, .262, .044), (.695, .300, .240, .042), (.728, .260, .200, .038)
    ], lid_m, c, root)
    molded("Trash bin chute", (.20, .05, .095), liner, c, (0, -.112, .645), root, .012)


def fire_extinguisher(c, root):
    """Korean 3.3 kg red ABC fire extinguisher on a floor stand."""
    red = W.mat("Extinguisher red enamel", (.68, .022, .020), rough=.24, metal=.28)
    stand_m = W.mat("Extinguisher stand", (.022, .024, .027), rough=.55)
    black = W.mat("Extinguisher hose rubber", (.014, .015, .017), rough=.68)
    brass = W.mat("Extinguisher brass valve", (.65, .50, .18), rough=.28, metal=.88)
    white = W.mat("Extinguisher label white", (.88, .88, .85), rough=.50)
    yellow = W.mat("Extinguisher label yellow", (.92, .72, .06), rough=.45)
    green = W.shadeless("Gauge green zone", (.15, .82, .25), strength=.7)
    # Floor stand tray
    W.cyl("Extinguisher stand base", .096, .024, stand_m, c, (0, 0, .012), parent=root, seg=28)
    W.cyl("Extinguisher stand rim", .096, .032, red, c, (0, 0, .034), r2=.090, parent=root, seg=28)
    # Main tank + domed shoulder
    W.cyl("Extinguisher tank", .068, .355, red, c, (0, 0, .205), parent=root, seg=32)
    smooth_mesh(oval("Extinguisher dome", (0, 0, .382), (.068, .068, .058), red, c, root))
    # Front instruction label band + Korean title (local -Y faces room)
    W.cyl("Extinguisher label", .0695, .155, white, c, (0, 0, .235), parent=root, seg=32)
    W.cyl("Extinguisher label band", .070, .028, yellow, c, (0, 0, .295), parent=root, seg=32)
    appliance_label("Extinguisher title", "소화기", (0, -.071, .255), .024, red, c, root)
    # Valve assembly, squeeze handle, safety pin & gauge
    W.cyl("Valve collar", .022, .042, brass, c, (0, 0, .448), parent=root, seg=20)
    molded("Valve block", (.034, .048, .036), brass, c, (0, .004, .476), root, .004)
    rod("Lower carry handle", (0, .012, .468), (0, .105, .448), .007, black, c, root)
    rod("Upper squeeze lever", (0, .008, .488), (0, .112, .518), .007, black, c, root)
    W.cyl("Pressure gauge body", .015, .012, brass, c, (.014, -.024, .478), (90, 0, 0), parent=root, seg=18)
    W.cyl("Pressure gauge dial", .012, .004, green, c, (.014, -.031, .478), (90, 0, 0), parent=root, seg=18)
    # Safety pin ring
    pin_pts = [(-.024, -.016 + .013 * math.cos(t * math.tau / 16), .484 + .013 * math.sin(t * math.tau / 16))
               for t in range(17)]
    piping("Safety pin ring", pin_pts, .0022, yellow, c, root)
    # Rubber hose looping down the +X side into a flare nozzle
    hose_pts = [(0, -.020, .476), (.052, -.026, .465), (.088, -.012, .410),
                (.092, .004, .300), (.088, .008, .175), (.084, .002, .125)]
    piping("Discharge hose", hose_pts, .0095, black, c, root)
    W.cyl("Discharge nozzle", .016, .062, black, c, (.084, .002, .095), r2=.010, parent=root, seg=18)
    molded("Hose clip", (.024, .018, .022), black, c, (.078, .006, .190), root, .003)


def ceiling_cassette_ac(c, root):
    """4-way commercial ceiling cassette air conditioner (0.95 x 0.95 m)."""
    body_m = W.mat("Cassette AC offwhite", (.74, .75, .74), rough=.38)
    vent_m = W.mat("Cassette AC dark vent", (.022, .024, .028), rough=.55)
    grille_m = W.mat("Cassette AC grille", (.56, .58, .59), rough=.46)
    led_m = W.shadeless("Cassette AC LED", (.18, .92, .38), strength=2.2)
    # Main outer fascia plate (top sits flush with ceiling at z = +0.025)
    molded("Cassette fascia", (.95, .95, .048), body_m, c, (0, 0, 0), root, .014)
    # Central recessed return-air grille
    molded("Cassette intake frame", (.48, .48, .012), grille_m, c, (0, 0, -.024), root, .004)
    for i in range(9):
        y = (i - 4) * .046
        W.box("Intake slat", (.42, .010, .006), vent_m, c, (0, y, -.030), parent=root)
    # 4 perimeter discharge vents + angled deflector louvers
    for angle in (0, 90, 180, 270):
        rad = math.radians(angle)
        cx, cy = .36 * math.sin(rad), .36 * math.cos(rad)
        sx, sy = (.62, .072) if angle in (0, 180) else (.072, .62)
        W.box("Discharge slot", (sx, sy, .010), vent_m, c, (cx, cy, -.024), parent=root)
        lx, ly = (.58, .036) if angle in (0, 180) else (.036, .58)
        louver = molded("Air louver", (lx, ly, .006), body_m, c, (cx, cy, -.031), root, .002)
        if angle == 0:
            louver.rotation_euler.x = math.radians(-22)
        elif angle == 180:
            louver.rotation_euler.x = math.radians(22)
        elif angle == 90:
            louver.rotation_euler.y = math.radians(22)
        else:
            louver.rotation_euler.y = math.radians(-22)
    # Corner IR receiver + tiny green power LED
    molded("AC IR window", (.065, .028, .006), vent_m, c, (.36, -.36, -.025), root, .002)
    W.cyl("AC status LED", .006, .004, led_m, c, (.34, -.36, -.028), parent=root, seg=12)


def ceiling_spiral_duct(c, parent_root):
    """Galvanized silver round HVAC spiral duct running along X across the ceiling."""
    galv = W.mat("Galvanized HVAC duct", (.52, .55, .57), rough=.30, metal=.86)
    band_m = W.mat("HVAC flange steel", (.36, .39, .41), rough=.36, metal=.82)
    dark = W.mat("HVAC vent interior", (.012, .014, .016), rough=.85)
    y, z, r = 3.20, 3.36, .145
    x0, x1 = -4.45, 13.45
    cx, length = (x0 + x1) / 2, x1 - x0
    duct = W.cyl("Spiral HVAC duct", r, length, galv, c, (cx, y, z), (0, 90, 0), seg=32, parent=parent_root)
    smooth_mesh(duct)
    # Flanged coupler rings every 1.8 m
    for i in range(10):
        x = -3.6 + i * 1.8
        ring = W.cyl("Duct coupler ring", r + .012, .036, band_m, c, (x, y, z), (0, 90, 0), seg=32, parent=parent_root)
        smooth_mesh(ring)
    # Ceiling hanger straps & threaded drop rods every 3.6 m
    for x in (-3.6, 0.0, 3.6, 7.2, 10.8):
        strap = W.cyl("Duct hanger strap", r + .006, .024, band_m, c, (x, y, z), (0, 90, 0), seg=24, parent=parent_root)
        smooth_mesh(strap)
        for dy in (-.145, .145):
            rod("Duct hanger rod", (x, y + dy, z + .04), (x, y + dy, 3.59), .006, band_m, c, parent_root)
    # 4 downward-angled side supply diffusers
    for x in (-1.8, 2.6, 7.0, 11.4):
        noz = W.empty("Duct air diffuser", c, (x, y - r * .72, z - r * .55), parent=parent_root)
        noz.rotation_euler = (math.radians(48), 0, 0)
        smooth_mesh(W.cyl("Diffuser collar", .072, .068, galv, c, (0, 0, 0), parent=noz, seg=24))
        W.cyl("Diffuser opening", .060, .012, dark, c, (0, 0, -.032), parent=noz, seg=24)


def wall_speaker(c, root):
    """Compact commercial black wall-mounted PA speaker with U-bracket (y=0 sits on wall, -Y faces room)."""
    cab = W.mat("PA speaker matte black", (.018, .020, .023), rough=.48)
    grille = W.mat("PA speaker grille", (.010, .011, .013), rough=.62, metal=.45)
    metal = W.mat("PA bracket steel", (.045, .048, .052), rough=.36, metal=.70)
    badge = W.mat("PA silver logo", (.62, .65, .66), rough=.28, metal=.85)
    # Wall plate at y = -0.007 + U-bracket extending into -Y
    molded("Speaker wall plate", (.085, .014, .16), metal, c, (0, -.007, 0), root, .003)
    rod("Speaker yoke stem", (0, -.012, 0), (0, -.072, 0), .012, metal, c, root)
    for sz in (-1, 1):
        rod("Speaker U-arm", (0, -.072, sz * .165), (0, -.160, sz * .165), .009, metal, c, root)
    # Tilted speaker enclosure
    head = W.empty("Speaker cabinet pivot", c, (0, -.160, 0), parent=root)
    head.rotation_euler.x = math.radians(-18)
    molded("Speaker cabinet", (.21, .185, .31), cab, c, (0, 0, 0), head, .014)
    molded("Speaker front grille", (.182, .016, .275), grille, c, (0, -.092, 0), head, .006)
    W.box("Speaker badge", (.036, .004, .014), badge, c, (0, -.102, -.112), parent=head)


def cctv_camera(c, root):
    """Compact white security CCTV bullet camera with wall arm (local -Y faces target)."""
    white = W.mat("CCTV satin white", (.78, .80, .81), rough=.34)
    dark = W.mat("CCTV matte black", (.015, .017, .020), rough=.44)
    glass = W.mat("CCTV lens glass", (.005, .008, .012), rough=.08, metal=.25)
    ir_led = W.shadeless("CCTV IR indicator", (.95, .08, .05), strength=2.6)
    # Wall mount base + articulated arm
    W.cyl("CCTV wall base", .042, .016, white, c, (0, .008, 0), (90, 0, 0), parent=root, seg=24)
    rod("CCTV mount arm", (0, 0, 0), (0, -.11, -.025), .011, white, c, root)
    smooth_mesh(oval("CCTV ball joint", (0, -.11, -.025), (.018, .018, .018), dark, c, root))
    # Tilted camera housing
    body = W.empty("CCTV head pivot", c, (0, -.12, -.032), parent=root)
    body.rotation_euler.x = math.radians(-22)
    smooth_mesh(W.cyl("CCTV housing", .038, .155, white, c, (0, -.055, 0), (90, 0, 0), parent=body, seg=24))
    molded("CCTV sun hood", (.082, .165, .016), white, c, (0, -.062, .038), body, .004)
    W.cyl("CCTV lens bezel", .036, .016, dark, c, (0, -.134, 0), (90, 0, 0), parent=body, seg=24)
    W.cyl("CCTV lens glass", .024, .006, glass, c, (0, -.142, 0), (90, 0, 0), parent=body, seg=24)
    W.cyl("CCTV IR LED", .0045, .004, ir_led, c, (.018, -.142, -.014), (90, 0, 0), parent=body, seg=12)


def treadmill_wall_tv(c, root):
    """55-inch commercial TV on ceiling-drop mount in front of the treadmills (local -Y faces runners)."""
    import numpy as np
    bezel = W.mat("TV slim bezel", (.012, .013, .015), rough=.32)
    back_m = W.mat("TV rear shell", (.022, .024, .027), rough=.46)
    steel = W.mat("TV mount steel", (.028, .030, .034), rough=.38, metal=.65)
    led = W.shadeless("TV power LED", (.95, .15, .12), strength=1.5)
    # Ceiling-drop twin poles from z = 0 up to ceiling (root is at z = 2.58, ceiling at 3.59 -> dz = 1.01)
    pole_top = 1.01
    for sx in (-.26, .26):
        rod("TV ceiling pole", (sx, .075, -.14), (sx, .075, pole_top), .019, steel, c, root)
        molded("TV ceiling flange", (.11, .11, .014), steel, c, (sx, .075, pole_top - .007), root, .004)
    molded("TV VESA crossbar", (.66, .036, .065), steel, c, (0, .052, 0), root, .006)
    # Tilted TV screen assembly
    panel = W.empty("TV panel tilt", c, (0, 0, 0), parent=root)
    panel.rotation_euler.x = math.radians(-10)
    w, h = 1.24, .71
    molded("TV bezel frame", (w, .032, h), bezel, c, (0, 0, 0), panel, .006)
    molded("TV electronics hump", (w * .74, .028, h * .64), back_m, c, (0, .026, -.04), panel, .008)
    W.cyl("TV standby LED", .004, .003, led, c, (w / 2 - .04, -.017, -h / 2 + .009), (90, 0, 0), parent=panel, seg=12)
    # Procedural packed broadcast sports/fitness screen image (no external file dependency)
    img = bpy.data.images.get("Gym_TV_Broadcast")
    if img is None:
        tw, th = 512, 288
        px = np.zeros((th, tw, 4), dtype=np.float32)
        px[:, :, 3] = 1.0
        yy, xx = np.mgrid[0:th, 0:tw]
        # Sports arena / broadcast studio gradient backdrop
        grad = yy / float(th)
        px[:, :, 0] = 0.05 + 0.07 * (1.0 - grad)
        px[:, :, 1] = 0.14 + 0.24 * (1.0 - grad) * (1.0 - 0.35 * np.abs(xx / tw - 0.5))
        px[:, :, 2] = 0.28 + 0.36 * (1.0 - grad)
        # Bright stadium turf / court lower band
        turf = (yy >= 44) & (yy < 155)
        px[turf, 0] = 0.10 + 0.04 * ((xx[turf] // 28) % 2)
        px[turf, 1] = 0.34 + 0.06 * ((xx[turf] // 28) % 2)
        px[turf, 2] = 0.16 + 0.02 * ((xx[turf] // 28) % 2)
        # White court / pitch lines
        px[(yy >= 96) & (yy <= 99), :3] = (0.85, 0.88, 0.90)
        px[(yy >= 44) & (yy < 155) & (xx >= 254) & (xx <= 258), :3] = (0.85, 0.88, 0.90)
        # Bottom news/sports ticker bar
        px[0:44, :, :3] = (0.04, 0.07, 0.15)
        px[38:44, :, :3] = (0.88, 0.18, 0.14)
        px[10:30, 18:118, :3] = (0.90, 0.14, 0.12)   # LIVE / SPORTS badge
        px[14:26, 132:360, :3] = (0.88, 0.90, 0.94)  # Headline bar
        px[14:26, 376:488, :3] = (0.95, 0.78, 0.14)  # Score pill
        # Top-left scoreboard bug
        px[238:270, 22:170, :3] = (0.05, 0.08, 0.16)
        px[238:270, 22:62, :3] = (0.12, 0.42, 0.88)
        px[246:262, 72:156, :3] = (0.92, 0.94, 0.96)
        img = bpy.data.images.new("Gym_TV_Broadcast", tw, th, alpha=True, float_buffer=False)
        img.pixels.foreach_set(px.ravel())
        img.pack()
    tv_mat = W.mat("TV Broadcast Screen", (.8, .8, .8), rough=.18)
    nt = tv_mat.node_tree
    shader = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None) or nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], shader.inputs["Emission Color"])
    shader.inputs["Emission Strength"].default_value = .95
    sw, sh = w - .030, h - .030
    mesh = bpy.data.meshes.new("TV screen face")
    mesh.from_pydata([(-sw / 2, -.017, -sh / 2), (sw / 2, -.017, -sh / 2),
                      (sw / 2, -.017, sh / 2), (-sw / 2, -.017, sh / 2)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new()
    for loop, coord in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = coord
    mesh.materials.append(tv_mat)
    screen = bpy.data.objects.new("TV screen face", mesh)
    c.objects.link(screen)
    screen.parent = panel


def cable_grip_rack(c, root):
    """Free-weight zone vertical A-frame stand holding MAG grip, tricep rope, V-bar and D-handle."""
    steel = W.mat("Accessory rack steel", (.028, .031, .036), rough=.42, metal=.55)
    chrome = W.mat("Brushed alloy", (.46, .5, .51), rough=.27, metal=.8)
    rubber = W.mat("Accessory grip rubber", (.014, .016, .018), rough=.78)
    mag_m = W.mat("MAG grip textured black", (.020, .022, .025), rough=.62, metal=.25)
    rope_m = W.mat("Tricep braided rope", (.032, .034, .038), rough=.88)
    # Steel A-frame base & uprights
    for sx in (-.21, .21):
        molded("Rack foot rail", (.05, .48, .04), steel, c, (sx, 0, .02), root, .006)
        rod("Rack upright front", (sx, -.17, .03), (sx, -.04, 1.15), .020, steel, c, root)
        rod("Rack upright rear", (sx, .17, .03), (sx, .04, 1.15), .020, steel, c, root)
    for z in (.32, .72, 1.13):
        molded("Rack crossbar", (.48, .045, .045), steel, c, (0, 0, z), root, .005)
    # Top hook bar + 4 chrome hooks
    for x, z in ((-.15, 1.13), (.15, 1.13), (-.14, .72), (.14, .72)):
        rod("Attachment peg", (x, -.02, z), (x, -.12, z + .022), .008, chrome, c, root)
    # 1) MAG grip (wide neutral-grip ergonomic lat bar) hanging on top-left/center hook
    mag = W.empty("MAG grip attachment", c, (-.15, -.105, 1.13), parent=root)
    W.cyl("MAG eyelet", .016, .010, chrome, c, (0, 0, -.018), (90, 0, 0), parent=mag, seg=16)
    mag_pts = [(-.22, 0, -.12), (-.19, 0, -.055), (-.08, 0, -.045), (0, 0, -.035),
               (.08, 0, -.045), (.19, 0, -.055), (.22, 0, -.12)]
    piping("MAG grip frame", mag_pts, .016, mag_m, c, mag)
    for sx in (-1, 1):
        rod("MAG palm handle", (sx * .22, -.025, -.12), (sx * .22, .025, -.12), .019, rubber, c, mag)
    # 2) Tricep braided rope hanging on top-right hook
    rope = W.empty("Tricep rope attachment", c, (.15, -.105, 1.13), parent=root)
    W.cyl("Rope swivel collar", .018, .036, chrome, c, (0, 0, -.028), parent=rope, seg=18)
    for sx in (-1, 1):
        pts = [(0, 0, -.045), (sx * .022, -.006, -.15), (sx * .038, -.004, -.28), (sx * .048, 0, -.39)]
        piping("Tricep rope leg", pts, .015, rope_m, c, rope)
        W.cyl("Rope bell stop", .030, .048, rubber, c, (sx * .048, 0, -.415), r2=.020, parent=rope, seg=18)
    # 3) Chrome V-bar close-grip row handle on lower-left hook
    vbar = W.empty("V-bar row handle", c, (-.14, -.095, .72), parent=root)
    for sx in (-1, 1):
        rod("V-bar arm", (0, 0, -.02), (sx * .085, 0, -.145), .012, chrome, c, vbar)
        rod("V-bar grip", (sx * .085, -.068, -.145), (sx * .085, .068, -.145), .015, rubber, c, vbar)
    # 4) Single D-handle on lower-right hook
    dhand = W.empty("Single D-handle", c, (.14, -.095, .72), parent=root)
    d_pts = [(0, 0, -.018), (-.062, 0, -.082), (-.062, 0, -.145), (.062, 0, -.145), (.062, 0, -.082), (0, 0, -.018)]
    piping("D-handle stirrup", d_pts, .0065, chrome, c, dhand)
    rod("D-handle grip", (-.056, 0, -.145), (.056, 0, -.145), .015, rubber, c, dhand)


def squat_barbell_pad(c, root):
    """High-density black foam squat barbell pad with slit and straps."""
    foam = W.mat("Squat pad foam", (.018, .019, .022), rough=.82)
    slit = W.mat("Squat pad bore", (.005, .006, .007), rough=.92)
    strap = W.mat("Squat pad strap", (.035, .037, .042), rough=.74)
    # Horizontal cylinder resting at z = +0.044
    pad = W.cyl("Squat foam cylinder", .044, .43, foam, c, (0, 0, .044), (0, 90, 0), seg=28, parent=root)
    smooth_mesh(pad)
    # Longitudinal center bar bore & top slit
    W.cyl("Squat pad inner bore", .016, .434, slit, c, (0, 0, .044), (0, 90, 0), seg=16, parent=root)
    W.box("Squat pad top slit", (.432, .012, .026), slit, c, (0, 0, .074), parent=root)
    # Twin Velcro wrap straps
    for x in (-.135, .135):
        band_o = W.cyl("Squat pad strap", .0465, .028, strap, c, (x, 0, .044), (0, 90, 0), seg=28, parent=root)
        smooth_mesh(band_o)


def kettlebell(c, root, radius, band_color, label):
    """Cast-iron matte black kettlebell with flat base, arched handle and color band."""
    iron = W.mat("Kettlebell cast iron", (.022, .024, .027), rough=.52, metal=.45)
    band_m = W.mat("Kettlebell band " + label, band_color, rough=.40)
    # Spherical bell with flattened bottom sitting at z = 0
    center_z = radius * .84
    bell = smooth_mesh(oval("Kettlebell body " + label, (0, 0, center_z), (radius, radius, radius * .96), iron, c, root))
    # Flatten bottom vertices slightly below z = 0
    for v in bell.data.vertices:
        if v.co.z + center_z < 0:
            v.co.z = -center_z
    # Arched handle
    h_r = radius * .175
    span = radius * .72
    top_z = center_z + radius * 1.56
    base_z = center_z + radius * .62
    handle_pts = [
        (-span * .78, 0, base_z),
        (-span * .96, 0, base_z + radius * .55),
        (-span * .70, 0, top_z),
        (0, 0, top_z + radius * .06),
        (span * .70, 0, top_z),
        (span * .96, 0, base_z + radius * .55),
        (span * .78, 0, base_z),
    ]
    piping("Kettlebell handle " + label, handle_pts, h_r, iron, c, root)
    # Weight-code color bands at the base of both handle horns
    for sx in (-1, 1):
        ring = W.cyl("Kettlebell weight band " + label, h_r * 1.12, .016, band_m, c,
                     (sx * span * .86, 0, base_z + radius * .26), parent=root, seg=18)
        ring.rotation_euler.y = math.radians(sx * 16)


def ez_bar_rack(c, root):
    """5-tier vertical A-frame fixed-weight EZ-bar rack (10, 15, 20, 25, 30 kg top to bottom)."""
    steel = W.mat("EZ rack charcoal", (.028, .031, .036), rough=.38, metal=.58)
    red = W.mat("EZ rack accent red", (.68, .035, .040), rough=.32, metal=.35)
    chrome = W.mat("Brushed alloy", (.46, .5, .51), rough=.22, metal=.88)
    rubber = W.mat("EZ bar rubber head", (.018, .019, .022), rough=.52)
    yellow = W.mat("EZ bar yellow ring", (.95, .72, .04), rough=.32)
    # Twin A-frame uprights & base rails (width 0.64m between posts, total rack height 1.38m)
    for sx in (-.30, .30):
        molded("EZ rack foot", (.065, .64, .045), steel, c, (sx, 0, .0225), root, .006)
        rod("EZ rack rear post", (sx, .20, .04), (sx, .05, 1.36), .028, steel, c, root)
        rod("EZ rack front post", (sx, -.22, .04), (sx, -.02, 1.36), .028, steel, c, root)
    for z in (.22, .80, 1.34):
        molded("EZ rack crossbar", (.64, .045, .045), red if z == 1.34 else steel, c, (0, .04, z), root, .005)
    # 5 fixed-weight EZ bars: 10 kg (top) -> 30 kg (bottom) in 5 kg increments
    specs = (
        (10, 1.24, .062, .044),
        (15, 1.00, .072, .056),
        (20, 0.76, .082, .068),
        (25, 0.52, .092, .080),
        (30, 0.28, .102, .094),
    )
    for kg, z, head_r, head_len in specs:
        # Cradle hooks extending toward -Y (room side)
        y_hook = -.16 - (1.24 - z) * .12
        for sx in (-.30, .30):
            rod(f"EZ cradle {kg}kg", (sx, y_hook + .12, z - .02), (sx, y_hook - .04, z - .005), .012, steel, c, root)
            molded(f"EZ cradle lip {kg}kg", (.026, .016, .038), red, c, (sx, y_hook - .045, z + .005), root, .003)
        # Bent chrome EZ-bar shaft (W-shaped curl profile)
        pts = [(-.46, y_hook, z), (-.25, y_hook, z), (-.15, y_hook - .038, z),
               (0, y_hook, z), (.15, y_hook - .038, z), (.25, y_hook, z), (.46, y_hook, z)]
        piping(f"EZ bar shaft {kg}kg", pts, .0145, chrome, c, root)
        # Fixed rubber weight heads + yellow weight rings on both ends
        for sx in (-1, 1):
            hx = sx * (.46 + head_len / 2)
            smooth_mesh(W.cyl(f"EZ head {kg}kg", head_r, head_len, rubber, c, (hx, y_hook, z), (0, 90, 0), seg=24, parent=root))
            smooth_mesh(W.cyl(f"EZ ring {kg}kg", head_r * .78, head_len + .006, yellow, c, (hx, y_hook, z), (0, 90, 0), seg=24, parent=root))
            smooth_mesh(W.cyl(f"EZ cap {kg}kg", head_r * .52, head_len + .011, rubber, c, (hx, y_hook, z), (0, 90, 0), seg=24, parent=root))


def build_gym_details(c):
    """Lived-in Korean gym details: water area, fire extinguishers, ceiling HVAC/audio/CCTV, cardio TV, free-weight props."""
    # 1) Paper cup dispenser + black trash bin right next to the water dispenser (5.9, -6.34)
    disp = W.empty("Paper cup dispenser", c, (6.26, -6.62, 1.18))
    disp.rotation_euler.z = math.pi
    paper_cup_dispenser(c, disp)

    trash = W.empty("Gym trash bin", c, (6.30, -6.36, 0))
    trash.rotation_euler.z = math.pi
    gym_trash_bin(c, trash)

    # 2) Red fire extinguishers at pillar bases (Right pillar & Left pillar)
    for name, loc, rot_deg in (
        ("Fire extinguisher right", (10.04, -0.44, 0), -18),
        ("Fire extinguisher left", (-1.04, -0.44, 0), 15),
    ):
        ext = W.empty(name, c, loc)
        ext.rotation_euler.z = math.radians(rot_deg)
        fire_extinguisher(c, ext)

    # 3) Ceiling 4-way cassette ACs (3 units spaced cleanly between beams, strips, and downlights)
    for i, x in enumerate((3.95, 6.95, 9.95), 1):
        ac = W.empty(f"Ceiling cassette AC {i}", c, (x, 0.55, 3.568))
        ceiling_cassette_ac(c, ac)

    # 4) Galvanized silver spiral HVAC duct running along X near ceiling
    duct_root = W.empty("Ceiling spiral HVAC duct", c, (0, 0, 0))
    ceiling_spiral_duct(c, duct_root)

    # 5) Wall-mounted black PA speakers high on the pillars
    for label, loc, rot_deg in (
        ("Left", (-1.40, -0.625, 2.86), 0),
        ("Right", (10.40, -0.625, 2.86), 0),
    ):
        spk = W.empty(f"Pillar speaker {label}", c, loc)
        spk.rotation_euler.z = math.radians(rot_deg)
        wall_speaker(c, spk)

    # 6) Compact CCTV security cameras high on pillars
    for label, loc, rot_deg in (
        ("Left", (-1.175, -0.40, 3.16), 105),
        ("Right", (10.175, -0.40, 3.16), -75),
    ):
        cam = W.empty(f"Gym CCTV {label}", c, loc)
        cam.rotation_euler.z = math.radians(rot_deg)
        cctv_camera(c, cam)

    # 7) Wall/ceiling-mounted TV in front of the treadmills (no window blinds)
    tv = W.empty("Treadmill wall TV", c, (13.28, 0.60, 2.58))
    tv.rotation_euler.z = math.radians(-90)
    treadmill_wall_tv(c, tv)

    # 8) Free-weight & cable zone floor props: cable grip rack, 5-tier EZ-bar rack (10-30kg), squat pad, kettlebells
    grip_rack = W.empty("Cable grip rack", c, (-3.95, -0.95, 0))
    grip_rack.rotation_euler.z = math.radians(90)
    cable_grip_rack(c, grip_rack)

    ez_rack = W.empty("Fixed EZ-bar rack", c, (-3.05, 4.45, 0))
    ez_bar_rack(c, ez_rack)

    pad = W.empty("Squat barbell pad", c, (1.98, 2.55, 0.024))
    pad.rotation_euler.z = math.radians(28)
    squat_barbell_pad(c, pad)

    for label, loc, rot_deg, radius, color in (
        ("8kg", (1.82, 1.98, 0), 18, .072, (.10, .38, .85)),
        ("12kg", (2.05, 1.84, 0), -25, .084, (.92, .72, .06)),
        ("16kg", (2.28, 2.00, 0), 10, .096, (.76, .08, .08)),
    ):
        kb = W.empty(f"Kettlebell {label}", c, loc)
        kb.rotation_euler.z = math.radians(rot_deg)
        kettlebell(c, kb, radius, color, label)

    # 9) Lived-in personal workout props: shaker bottles/tumblers, folded gym towels, coiled lifting belt, locker duffel bag
    for name, loc, rot_deg, body_col, lid_col, accent_col, metal in (
        ("Shaker leg press", (6.18, -2.82, 0), 24, (.06, .07, .08), (.03, .03, .035), (.26, .82, .18), 0.08),
        ("Tumbler dumbbell bench", (-0.38, 2.65, 0), -35, (.62, .65, .68), (.04, .04, .045), (.18, .19, .21), 0.85),
        ("Shaker leg extension", (7.78, -2.55, 0), 115, (.14, .46, .82), (.88, .90, .92), (.08, .10, .12), 0.05),
        ("Shaker dip machine", (3.12, -2.58, 0), -60, (.10, .11, .13), (.03, .03, .035), (.78, .10, .12), 0.10),
    ):
        btl = W.empty(name, c, loc)
        btl.rotation_euler.z = math.radians(rot_deg)
        shaker_bottle(c, btl, body_col, lid_col, accent_col, metal=metal)

    for name, loc, rot_deg, col in (
        ("Gym towel bench", (-1.68, 2.72, 0), 22, (.24, .26, .29)),
        ("Gym towel leg press", (6.34, -2.52, 0), -18, (.08, .14, .28)),
        ("Gym towel locker", (-1.85, -5.95, 0), 8, (.16, .17, .19)),
    ):
        tw = W.empty(name, c, loc)
        tw.rotation_euler.z = math.radians(rot_deg)
        folded_gym_towel(c, tw, col)

    belt = W.empty("Lifting belt rack", c, (2.12, 3.32, 0))
    belt.rotation_euler.z = math.radians(-32)
    lifting_belt(c, belt)

    bag = W.empty("Locker gym duffel bag", c, (-3.10, -5.85, 0))
    bag.rotation_euler.z = math.radians(22)
    gym_duffel_bag(c, bag)

    # 10) Korean commercial gym architectural details: ceiling sprinklers, wall outlets/switches
    # (Emergency exit sign now lives directly above the Main Entrance door in gym_annex.py)
    for ix, sx in enumerate((-1.2, 2.0, 5.2, 8.4, 11.6), 1):
        for iy, sy in enumerate((-2.6, 1.8), 1):
            sp = W.empty(f"Ceiling sprinkler {ix}_{iy}", c, (sx, sy, 3.588))
            ceiling_sprinkler(c, sp)

    for name, loc, rot_deg, kind in (
        ("Wall outlet InBody", (-7.48, -3.55, 0.34), 90, "outlet"),
        ("Wall outlet water", (5.38, -6.68, 0.34), 180, "outlet"),
        ("Wall outlet left", (-7.48, 0.90, 0.34), 90, "outlet"),
        ("Pillar light switch", (-1.40, -0.635, 1.24), 0, "switch"),
    ):
        el = W.empty(name, c, loc)
        el.rotation_euler.z = math.radians(rot_deg)
        wall_electrical_plate(c, el, kind=kind)

    from gym_annex import build_gym_doors
    build_gym_doors(c)


def korean_exit_sign(c, root):
    """Korean fire-code standard medium emergency exit sign (중형 피난구유도등, ~290x230x44 mm, NFTC 303 / KS ISO 3864-3)."""
    import os
    housing = W.mat("ExitSign_Housing", (0.86, 0.88, 0.87), rough=0.38, metal=0.10)
    trim = W.mat("ExitSign_Trim", (0.74, 0.76, 0.75), rough=0.45, metal=0.15)
    led_g = W.shadeless("ExitSign_StatusLED", (0.08, 0.95, 0.22), strength=3.0)
    # Standard wall-mounted medium housing: 290 x 230 x 44 mm
    molded("Exit sign body", (0.290, 0.044, 0.230), housing, c, (0, 0.022, 0), root, radius=0.006)
    molded("Exit sign bezel", (0.278, 0.010, 0.218), trim, c, (0, 0.002, 0), root, radius=0.003)
    # Emissive textured face using Korean standard pictogram PNG (266 x 206 mm)
    img_path = os.path.join(W.PARTS, "korean_exit_sign.png")
    im = bpy.data.images.load(img_path, check_existing=True)
    if not im.packed_file:
        im.pack()
    face_m = W.shadeless("ExitSign_FaceMat", image=img_path, strength=2.6)
    hw, hh = 0.133, 0.103
    me = bpy.data.meshes.new("Exit sign face")
    me.from_pydata([(-hw, -0.004, -hh), (hw, -0.004, -hh), (hw, -0.004, hh), (-hw, -0.004, hh)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for loop, coord in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = coord
    me.materials.append(face_m)
    face_ob = bpy.data.objects.new("Exit sign face", me)
    face_ob.parent = root
    c.objects.link(face_ob)
    # Bottom inspection button + green power status LED (classic Korean exit light detail)
    W.cyl("Exit test button", 0.006, 0.005, trim, c, (-0.095, 0.020, -0.116), parent=root, seg=12)
    W.cyl("Exit status LED", 0.004, 0.004, led_g, c, (-0.072, 0.020, -0.116), parent=root, seg=12)
    # Subtle localized emerald bounce light
    ld = bpy.data.lights.new("ExitSignGlow", "POINT")
    ld.energy = 5.5
    ld.color = (0.10, 0.92, 0.40)
    ld.shadow_soft_size = 0.16
    ld.use_shadow = False
    ob = bpy.data.objects.new(ld.name, ld)
    ob.location = (0, -0.10, -0.02)
    ob.parent = root
    c.objects.link(ob)


def ceiling_sprinkler(c, root):
    """Recessed commercial fire sprinkler head with chrome escutcheon ring and brass deflector."""
    chrome = W.mat("Sprinkler_Chrome", (0.68, 0.70, 0.72), rough=0.22, metal=0.90)
    brass = W.mat("Sprinkler_Brass", (0.72, 0.56, 0.24), rough=0.32, metal=0.85)
    W.cyl("Sprinkler escutcheon", 0.034, 0.008, chrome, c, (0, 0, -0.004), parent=root, seg=18)
    W.cyl("Sprinkler stem", 0.009, 0.024, brass, c, (0, 0, -0.018), parent=root, seg=12)
    W.cyl("Sprinkler deflector", 0.017, 0.004, brass, c, (0, 0, -0.032), parent=root, seg=16)


def wall_electrical_plate(c, root, kind="outlet"):
    """Korean recessed 2-gang wall power outlet or 3-gang rocker light switch."""
    plate_m = W.mat("WallPlate_Dark", (0.08, 0.085, 0.095), rough=0.45, metal=0.08) if kind == "switch" else W.mat("WallPlate_White", (0.82, 0.83, 0.81), rough=0.42, metal=0.04)
    socket_m = W.mat("WallSocket_Recess", (0.04, 0.042, 0.048), rough=0.65, metal=0.05)
    molded("Electrical plate", (0.118, 0.010, 0.072), plate_m, c, (0, -0.005, 0), root, radius=0.003)
    if kind == "outlet":
        for x in (-0.026, 0.026):
            W.cyl("Outlet well", 0.019, 0.006, socket_m, c, (x, -0.009, 0), (90, 0, 0), parent=root, seg=18)
    else:
        for x in (-0.030, 0.0, 0.030):
            molded("Rocker switch", (0.024, 0.008, 0.044), plate_m, c, (x, -0.011, 0), root, radius=0.002)


def shaker_bottle(c, root, body_color, lid_color, accent_color, metal=0.08):
    """Tapered sports shaker bottle or insulated gym tumbler (~23 cm tall)."""
    body_m = W.mat(f"ShakerBody_{body_color}", body_color, rough=0.28 if metal > 0.5 else 0.36, metal=metal)
    lid_m = W.mat(f"ShakerLid_{lid_color}", lid_color, rough=0.42, metal=0.05)
    acc_m = W.mat(f"ShakerAccent_{accent_color}", accent_color, rough=0.35, metal=0.05)
    W.cyl("Shaker base", 0.036, 0.016, lid_m, c, (0, 0, 0.008), parent=root, seg=24)
    # Tapered cup body
    me = bpy.data.meshes.new("Shaker cup")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24, radius1=0.035, radius2=0.044, depth=0.175)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("Shaker cup", me)
    ob.data.materials.append(body_m)
    ob.location = (0, 0, 0.098)
    ob.parent = root
    c.objects.link(ob)
    smooth_mesh(ob)
    # Measurement / grip accent ring
    W.cyl("Shaker grip band", 0.0435, 0.018, acc_m, c, (0, 0, 0.145), parent=root, seg=24)
    # Threaded lid + spout + carry loop
    W.cyl("Shaker lid", 0.046, 0.032, lid_m, c, (0, 0, 0.198), parent=root, seg=24)
    W.cyl("Shaker spout", 0.013, 0.022, acc_m, c, (0.018, 0, 0.222), parent=root, seg=16)
    molded("Shaker flip cap", (0.034, 0.020, 0.012), acc_m, c, (0.014, 0, 0.234), root, radius=0.004)
    piping("Shaker carry loop", [(-0.028, 0, 0.212), (-0.042, 0, 0.236), (-0.018, 0, 0.244), (-0.006, 0, 0.214)], 0.004, lid_m, c, root)


def folded_gym_towel(c, root, color):
    """Softly rounded folded cotton gym towel (~32 x 20 x 3.4 cm) with two-layer fold."""
    towel_m = W.mat(f"GymTowel_{color}", color, rough=0.92, metal=0.0)
    trim_col = tuple(min(1.0, ch * 1.35 + 0.04) for ch in color)
    trim_m = W.mat(f"GymTowelTrim_{color}", trim_col, rough=0.88, metal=0.0)
    molded("Towel bottom fold", (0.31, 0.20, 0.016), towel_m, c, (0, 0, 0.008), root, radius=0.006)
    molded("Towel top fold", (0.295, 0.192, 0.016), towel_m, c, (0.004, -0.003, 0.024), root, radius=0.006)
    molded("Towel hem stripe", (0.296, 0.014, 0.003), trim_m, c, (0.004, 0.068, 0.032), root, radius=0.001)


def lifting_belt(c, root):
    """Coiled leather weightlifting belt resting upright beside a rack."""
    leather = W.mat("LiftingBelt_Leather", (0.025, 0.025, 0.028), rough=0.58, metal=0.05)
    stitch = W.mat("LiftingBelt_Stitch", (0.72, 0.06, 0.07), rough=0.65, metal=0.0)
    chrome = W.mat("Brushed alloy", (0.46, 0.50, 0.51), rough=0.27, metal=0.80)
    # Coiled cylinder ring (open top/bottom)
    pts = [(math.cos(a) * 0.145, math.sin(a) * 0.145, 0.054) for a in [math.radians(d) for d in range(0, 345, 18)]]
    band("Lifting belt strap", pts, 0.105, 0.012, leather, c, root, closed=False)
    for z_off in (0.012, 0.096):
        s_pts = [(math.cos(a) * 0.1515, math.sin(a) * 0.1515, z_off) for a in [math.radians(d) for d in range(0, 345, 18)]]
        piping("Belt trim", s_pts, 0.0022, stitch, c, root)
    molded("Belt buckle frame", (0.016, 0.058, 0.074), chrome, c, (0.150, 0.0, 0.054), root, radius=0.003)
    rod("Belt prong", (0.154, -0.022, 0.054), (0.154, 0.024, 0.054), 0.004, chrome, c, root)


def gym_duffel_bag(c, root):
    """Dark nylon gym duffel bag resting near the lockers."""
    nylon = W.mat("GymBag_Nylon", (0.035, 0.038, 0.044), rough=0.78, metal=0.0)
    webbing = W.mat("GymBag_Webbing", (0.018, 0.018, 0.022), rough=0.85, metal=0.0)
    accent = W.mat("GymBag_Accent", (0.68, 0.07, 0.08), rough=0.55, metal=0.1)
    chrome = W.mat("Brushed alloy", (0.46, 0.50, 0.51), rough=0.27, metal=0.80)
    molded("Duffel main body", (0.48, 0.25, 0.23), nylon, c, (0, 0, 0.118), root, radius=0.055)
    molded("Duffel front pocket", (0.26, 0.028, 0.14), nylon, c, (0, -0.128, 0.105), root, radius=0.012)
    molded("Duffel zip accent", (0.24, 0.008, 0.010), accent, c, (0, -0.142, 0.165), root, radius=0.002)
    for x in (-0.11, 0.11):
        molded("Duffel strap band", (0.034, 0.258, 0.234), webbing, c, (x, 0, 0.118), root, radius=0.005)
    for y_side in (-0.095, 0.095):
        piping("Duffel handle", [(-0.11, y_side, 0.228), (-0.06, y_side * 0.65, 0.305), (0.06, y_side * 0.65, 0.305), (0.11, y_side, 0.228)], 0.008, webbing, c, root)
    for x_end in (-0.242, 0.242):
        W.cyl("Duffel D-ring", 0.014, 0.006, chrome, c, (x_end, 0, 0.165), (0, 90, 0), parent=root, seg=12)


def build_set(parent):
    c=W.coll("Reel gym fixtures",parent)
    graphite=W.mat("Graphite enamel",(.048,.06,.065),rough=.38,metal=.45)
    ivory=W.mat("Warm ceramic",(.72,.75,.71),rough=.4)
    chrome=W.mat("Brushed alloy",(.46,.5,.51),rough=.27,metal=.8)
    dark=W.mat("Reel rubber",(.011,.016,.018))
    red=W.shadeless("Clock LED",(.98,.013,.005),strength=4)
    def block(name,size,material,xyz,root):
        return molded(name,size,material,c,xyz,root)
    def text(root, name, string, xyz, size, material):
        data=bpy.data.curves.new(name,"FONT")
        data.body=string
        data.font=W.load_font(W.KFONT)
        data.size=size
        data.align_x="CENTER"
        data.align_y="CENTER"
        data.fill_mode="FRONT"
        data.materials.append(material)
        obj=bpy.data.objects.new(name,data)
        c.objects.link(obj)
        obj.parent=root
        obj.location=xyz
        obj.rotation_euler.x=math.pi/2
    # Local -Y faces the room on every front-wall unit.
    wall=W.empty("Front wall fittings",c,(6,-6.66,0))
    wall.rotation_euler.z=math.pi
    printed_face("Locker wall mural","locker_mural.png",21.2,3,(3.0,.020,2.09),wall,c)
    for i in range(8):
        x=-4.1+i*.41
        block("Locker shell",(.407,.44,1.775),graphite,(x,-.22,.9725),wall)
        for j in range(2):
            z=.47+j*.92
            block("Locker door",(.383,.022,.846),ivory,(x,-.45,z+.019),wall)
            block("Finger pull",(.025,.018,.078),graphite,(x+.137,-.467,z),wall)
            for k in range(3):
                block("Air slot",(.14,.003,.009),dark,(x,-.462,z+.285+.022*k),wall)
            text(wall,"Locker number",f"{101+i+j*8}",(x-.12,-.464,z+.33),.037,graphite)
            block("Recessed latch",(.078,.012,.146),dark,(x+.133,-.463,z),wall)
            rod("Key barrel",(x+.132,-.475,z+.046),(x+.132,-.482,z+.046),.013,chrome,c,wall)
            for side in (-1,1):
                block("Door hinge",(.012,.013,.076),chrome,(x-.19,-.46,z+side*.31),wall)
    block("Locker kick plate",(3.29,.41,.09),graphite,(-2.665,-.21,.045),wall)
    for x,filename in ((1.42,"plates.png"),(2.28,"training.png"),(3.14,"student_discount.png")):
        block("Aluminum snap frame",(.73,.034,1.02),chrome,(x,-.017,1.68),wall)
        printed_face("Gym poster "+filename,filename,.704,.99,(x,-.0345,1.68),wall,c)
    cooler=W.empty("Water dispenser",c,(5.9,-6.34,0))
    cooler.rotation_euler.z=math.pi
    water_purifier(c,cooler)
    clock=W.empty("LED timer",c,(6.35,4.90,2.84))
    control(clock,"Seconds",90,5999,"Time shown at frame one, in seconds.")
    control(clock,"Playback rate",1,120,"Elapsed seconds per second of footage. Set to zero to freeze.")
    block("Timer housing",(1.48,.09,.5),graphite,(0,0,0),clock)
    block("Tinted timer lens",(1.42,.009,.45),dark,(0,-.049,0),clock)
    for side in (-1,1):
        block("Timer mounting ear",(.097,.13,.12),graphite,(side*.62,.077,.08),clock)
        for height in (-.20,.20):
            rod("Timer bezel screw",(side*.717,-.043,height),(side*.717,-.051,height),.010,chrome,c,clock)
    piping("Timer power lead",[(.70,.02,-.19),(.77,.03,-.22),(.83,.07,-.23),
                              (.88,.086,-.16),(.89,.09,.19),(.89,.09,.39)],.006,dark,c,clock)
    dim=W.mat("Dormant LED segments",(.055,.015,.013),rough=.49)
    digits=("abcdef","bc","abdeg","abcdg","bcfg","acdfg","acdefg","abc","abcdefg","abcdfg")
    segments=[("a",0,.158),("b",.081,.081),("c",.081,-.081),("d",0,-.158),
              ("e",-.081,-.081),("f",-.081,.081),("g",0,0)]
    for x,unit in zip((-.5,-.253,.253,.5),(600,60,10,1)):
        for name,dx,z in segments:
            horiz=name in "adg"
            # Tapered segment ends leave a narrow diagonal gap at the joints.
            points=[(-.074,0),(-.062,-.013),(.062,-.013),(.074,0),(.062,.013),(-.062,.013)]
            if not horiz: points=[(-h,w*.90) for w,h in points]
            def segment(label,material,depth):
                mesh=bpy.data.meshes.new(label)
                mesh.from_pydata([(u,0,v) for u,v in points],[],[tuple(range(6))])
                mesh.materials.append(material)
                obj=bpy.data.objects.new(label,mesh)
                c.objects.link(obj);obj.parent=clock;obj.location=(x+dx,depth,z)
                return obj
            segment("Unlit segment",dim,-.054)
            obj=segment("LED "+name,red,-.055)
            mask=sum(1<<n for n,segs in enumerate(digits) if name in segs)
            modulus=6 if unit==10 else 10
            # Park the inactive layer just behind its unlit segment, keeping its geometry intact.
            curve=obj.driver_add("location",1)
            elapsed="(v+floor(max(0,frame-1)*rate*base/fps))"
            lit=f"(floor({mask}/2**(floor({elapsed}/{unit})%{modulus}))%2)"
            driven(curve,clock,"Seconds",f"-.053-.002*{lit}")
            rate=curve.driver.variables.new()
            rate.name="rate"
            rate.targets[0].id=clock
            rate.targets[0].data_path='["Playback rate"]'
            scene_timebase(curve)
    for z in (-.075,.075):
        block("Timer colon",(.037,.006,.037),red,(0,-.058,z),clock)
    scan=W.empty("Body composition analyzer",c,(-7.05,-3.55,0))
    scan.rotation_euler.z=math.pi/2
    inbody_270(c,scan)
    # Align the head, recessed optic and actual light to one pivot.
    lamp=W.empty("Mirror portrait spot",c,(11.55,4.88,2.99))
    block("Spot wall plate",(.153,.033,.158),graphite,(0,.088,0),lamp)
    rod("Spot arm",(0,.084,0),(0,-.255,0),.022,graphite,c,lamp)
    for side in (-1,1):
        rod("Yoke arm",(0,-.255,0),(side*.095,-.255,-.075),.014,graphite,c,lamp)
    pivot=W.empty("Aimed spotlight head",c,(0,-.255,-.075),parent=lamp)
    direction=Vector((11.25,3.05,1.43))-(Vector(lamp.location)+pivot.location)
    pivot.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
    W.cyl("Spot housing",.079,.18,graphite,c,(0,0,0),parent=pivot,seg=32)
    for k in range(5):
        W.cyl("Cast cooling fin",.087,.007,graphite,c,(0,0,.020+k*.014),parent=pivot,seg=32)
    W.cyl("Optic rim",.082,.028,dark,c,(0,0,-.095),parent=pivot,seg=32)
    W.cyl("Reflector",.069,.006,chrome,c,(0,0,-.110),parent=pivot,seg=32)
    optic=W.shadeless("Warm spot optic",(1,.86,.68),strength=3)
    W.cyl("Recessed optic",.052,.003,optic,c,(0,0,-.114),parent=pivot,seg=32)
    light=bpy.data.lights.new("Portrait downlight","SPOT")
    light.energy=175; light.spot_size=math.radians(48); light.spot_blend=.52
    light.color=(1,.86,.70); light.shadow_soft_size=.052
    ob=bpy.data.objects.new(light.name,light); c.objects.link(ob)
    ob.parent=pivot;ob.location=(0,0,-.122)
    build_gym_details(c)


def piping(name, points, radius, material, collection, parent):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, xyz in zip(spline.points, points):
        point.co = (*xyz, 1)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj.parent = parent
    curve.materials.append(material)
    return obj


def smooth_mesh(obj):
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def cap(collection, head):
    twill = W.mat("Washed charcoal twill", (.029,.031,.030), rough=.9)
    thread = W.mat("Charcoal topstitch", (.048,.049,.046), rough=.9)
    under = W.mat("Charcoal underbill", (.021,.022,.021), rough=.94)
    rubber = W.mat("Graphite headset cushion", (.014,.015,.016), rough=.65)
    shell = W.mat("Satin graphite earcup", (.048,.049,.052), rough=.34, metal=.32)
    inset = W.mat("Dark anodized inset", (.028,.029,.031), rough=.36, metal=.48)

    nodes=twill.node_tree.nodes
    if not nodes.get("Woven grain"):
        coords=nodes.new("ShaderNodeTexCoord")
        grain=nodes.new("ShaderNodeTexNoise")
        grain.name="Woven grain"
        grain.inputs["Scale"].default_value=1750
        grain.inputs["Detail"].default_value=2
        bump=nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value=.18
        bump.inputs["Distance"].default_value=.00016
        links=twill.node_tree.links
        links.new(coords.outputs["Object"],grain.inputs["Vector"])
        links.new(grain.outputs["Fac"],bump.inputs["Height"])
        surface=next(node for node in nodes if node.type=="BSDF_PRINCIPLED")
        links.new(bump.outputs["Normal"],surface.inputs["Normal"])
        dye=nodes.new("ShaderNodeValToRGB")
        dye.color_ramp.elements[0].color=(.018,.019,.018,1)
        dye.color_ramp.elements[1].color=(.048,.049,.046,1)
        links.new(grain.outputs["Fac"],dye.inputs["Fac"])
        links.new(dye.outputs["Color"],surface.inputs["Base Color"])

    def crown(angle, elevation):
        r = math.cos(elevation)
        side = math.cos(angle)
        base = 1.683 - .018*side**2
        z = base + (1.768-base)*math.sin(elevation)
        # Shallow compressions where the sewn panels meet the sweatband.
        folds=math.sin(6*angle+.55*math.sin(3*angle))**8
        r*=1-.022*folds*math.exp(-((elevation-.24)/.24)**2)
        return Vector((.105*r*side, -.091 + .120*r*math.sin(angle), z))

    def loft(name, rings, materials, bottom_index=0):
        bm = bmesh.new()
        loops = [[bm.verts.new(point) for point in row] for row in rings]
        count = len(loops[0])
        for a,b in zip(loops,loops[1:]):
            for i in range(count):
                j = (i+1)%count
                bm.faces.new((a[i],a[j],b[j],b[i]))
        bm.faces.new(loops[0]).material_index=bottom_index
        bm.faces.new(loops[-1])
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        obj = W.mesh_obj(name,bm,materials[0],collection,parent=head)
        for mat in materials[1:]:
            obj.data.materials.append(mat)
        return smooth_mesh(obj)

    angles = [i*math.tau/96 for i in range(96)]
    elevations = [i*1.558/24 for i in range(25)]
    loft("Soft six panel cap", [[crown(a,e) for a in angles] for e in elevations],[twill])
    for i in range(6):
        a = math.pi/6 + i*math.pi/3
        piping("Felled panel seam",[crown(a,e) for e in elevations],.00048,thread,collection,head)
    piping("Bound lower edge",[crown(a,.016) for a in angles+[math.tau]],.00085,twill,collection,head)

    # The inner edge follows the crown itself. Both ends taper into the temples.
    def bill(u,v):
        angle = -math.pi/2 + u*1.19
        p = crown(angle,.094)
        extent = max(.012, math.cos(u*math.pi/2))**.67
        p.y += .005 - v*.081*extent
        p.x += u*.006*v*extent
        p.z -= v*(.011+.052*u*u)*extent
        return p

    bm=bmesh.new()
    grids=[]
    for layer in (0,1):
        grid=[]
        for j in range(17):
            row=[]
            for i in range(65):
                p=bill(i/32-1,j/16)
                p.z -= layer*.0032
                row.append(bm.verts.new(p))
            grid.append(row)
        for j in range(16):
            for i in range(64):
                bm.faces.new((grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i])).material_index=layer
        grids.append(grid)
    def rim(grid):
        return grid[0]+[row[-1] for row in grid[1:]]+grid[-1][-2::-1]+[row[0] for row in grid[-2:0:-1]]
    top,bottom=map(rim,grids)
    for i in range(len(top)):
        bm.faces.new((top[i-1],top[i],bottom[i],bottom[i-1])).material_index=1
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    brim=W.mesh_obj("Rolled crescent visor",bm,twill,collection,parent=head)
    brim.data.materials.append(under)
    bevel=brim.modifiers.new("Soft fabric edge","BEVEL")
    bevel.width=.001;bevel.segments=3
    smooth_mesh(brim)
    for v in (.81,.91):
        piping("Visor stitch",[bill(i/40,v)+Vector((0,0,.00014)) for i in range(-38,39)],
               .00037,thread,collection,head)
    coords=[crown(-math.pi/2+x,e) for x,e in
            ((.07,.43),(.13,.33),(.18,.42),(.23,.33),(.29,.45))]
    piping("Tonal embroidered W",coords,.00135,thread,collection,head)

    # The padded band's inner surface shares the meridian of the cap.
    path=[]
    for i in range(81):
        a=math.pi*i/80
        path.append((.108*math.cos(a),-.091,1.665+.106*math.sin(a)))
    holder=band("Padded over-ear headband",path,.024,.0085,rubber,collection,head)
    mod=holder.modifiers.new("Rounded pad edges","BEVEL")
    mod.width=.003;mod.segments=4
    smooth_mesh(holder)
    for sign in (-1,1):
        y,z=-.081,1.627
        def ear_part(name,profile,material):
            rings=[]
            for x,ry,rz in profile:
                row=[]
                for i in range(64):
                    a=math.tau*i/64
                    dy,dz=ry*math.cos(a),rz*math.sin(a)
                    row.append((sign*x,y+dy+.14*dz,z+dz))
                rings.append(row)
            return loft(name,rings,[material])
        ear_part("Memory foam earpad",[(.077,.031,.046),(.080,.042,.058),(.087,.047,.064),
                                      (.096,.047,.064),(.102,.043,.060)],rubber)
        ear_part("Enclosed earcup",[(.099,.042,.057),(.102,.046,.061),(.110,.046,.061),
                                    (.117,.043,.058),(.121,.036,.051),(.122,.020,.031)],shell)
        ear_part("Earcup face inset",[(.1216,.022,.033),(.1224,.021,.032),(.123,.015,.025)],inset)
        for side in (-1,1):
            coords=[(sign*.106,-.091,1.68),(sign*.110,y+side*.016,1.679),
                    (sign*.113,y+side*.032,1.665),(sign*.113,y+side*.042,1.641)]
            piping("Headphone swivel fork",coords,.0028,inset,collection,head)


def tripod(collection, stand):
    alloy = W.mat("Tripod anodized graphite", (.065,.078,.081), rough=.32,metal=.66)
    silver = W.mat("Tripod satin aluminum", (.39,.42,.43), rough=.30,metal=.8)
    grip = W.mat("Tripod molded rubber", (.019,.021,.022),rough=.84)
    orange = W.mat("Tripod safety orange", (.78,.17,.034), rough=.44)
    def post(name, radius, bottom, top, material):
        return W.cyl(name,radius,top-bottom,material,collection,(0,0,(top+bottom)/2),seg=24,parent=stand)
    def tube(name, a, b, radius, material):
        return rod(name,a,b,radius,material,collection,stand)
    def block(name,size,xyz,material):
        return W.box(name,size,material,collection,xyz,parent=stand)
    for i in range(3):
        azimuth=math.tau*(i+.15)/3
        radial=Vector((math.cos(azimuth),math.sin(azimuth),0))
        transverse=Vector((-radial.y,radial.x,0))
        def point(r,z):
            return radial*r + Vector((0,0,z))
        foot,hinge=point(.35,.022),point(.043,.67)
        def leg(t):
            return foot.lerp(hinge,t)
        tube("Sliding lower leg",leg(.032),leg(.48),.012,silver)
        tube("Upper leg tube",leg(.46),hinge,.018,alloy)
        tube("Leg lock sleeve",leg(.435),leg(.503),.022,grip)
        tube("Flip lock lever",leg(.457)+radial*.021,leg(.53)+radial*.023,.008,orange)
        tube("Rubber foot",foot,leg(.079),.021,grip)
        oval("Non slip sole",point(.35,.012),(.025,.024,.012),grip,collection,stand)
        tube("Folding brace",point(.019,.305),leg(.425),.008,alloy)
        for joint in (hinge,leg(.425)):
            tube("Pivot axle",joint-transverse*.023,joint+transverse*.023,.010,silver)
        tube("Shoulder lug",point(.015,.68),hinge,.026,alloy)
    post("Lower spider",.036,.285,.325,alloy)
    post("Center mast",.022,.288,.946,alloy)
    post("Shoulder casting",.054,.648,.698,alloy)
    post("Twist lock grip",.030,.916,.975,grip)
    post("Lock marker",.031,.954,.960,orange)
    post("Extension tube",.014,.97,1.295,silver)
    post("Head pan base",.033,1.285,1.307,alloy)
    post("Head index ring",.0335,1.308,1.313,orange)
    post("Ball socket",.032,1.314,1.347,alloy)
    oval("Ball joint",(0,0,1.349),(.024,.024,.024),silver,collection,stand)
    post("Ball neck",.010,1.364,1.388,silver)
    tube("Head locking screw",(.014,0,1.331),(.050,0,1.331),.008,silver)
    tube("Knurled tension wheel",(.042,0,1.331),(.056,0,1.331),.017,grip)
    block("Quick release receiver",(.067,.052,.015),(0,0,1.39),alloy)
    block("Quick release plate",(.061,.049,.008),(0,0,1.401),silver)
    block("Padded cradle",(.088,.019,.013),(0,.006,1.409),grip)
    block("Clamp rear bridge",(.087,.011,.031),(0,.011,1.423),alloy)
    for side in (-1,1):
        block("Spring jaw",(.006,.022,.035),(side*.042,.003,1.424),alloy)
        block("Jaw liner",(.003,.017,.032),(side*.0387,.001,1.424),grip)


def stage():
    c=W.coll("Selfie kit",W.coll("PROPS"))
    black=W.mat("Accessory charcoal",(.022,.028,.034),rough=.64)
    trim=W.mat("Accessory nickel",(.42,.47,.46),metal=.72,rough=.32)
    cloth=W.mat("Cap olive",(.17,.23,.105),rough=.92)
    leather=W.mat("Belt oxblood",(.17,.042,.028),rough=.59)
    hero=W.add_hero("Selfie Guy")
    head=W.empty("Cap and headphones",c)
    head.parent=hero; head.parent_type="BONE"; head.parent_bone="head"
    bpy.context.view_layer.update()
    head.matrix_parent_inverse=head.matrix_world.inverted()
    cap(c,head)
    hero.location=(11.25,3.05,0)
    hero.rotation_euler.z=math.radians(166)
    W.apply_pose(hero,"check_watch")
    rack=W.empty("Equipment stool",c,(10.8,2.75,0))
    W.box("Seat",(.54,.37,.045),black,c,(0,0,.45),parent=rack)
    for x in (-.22,.22):
        for y in (-.13,.13):
            rod("Stool leg",(x,y,0),(x,y,.437),.014,trim,c,rack)
    belt=[(.133*math.cos(t*math.tau/32)-.078,.126*math.sin(t*math.tau/32),.524) for t in range(32)]
    band("Lifting belt",belt,.10,.009,leather,c,rack,True)
    W.box("Belt clasp",(.074,.015,.05),trim,c,(-.078,-.13,.523),parent=rack)
    for j in range(2):
        loop=[(.037*math.cos(t*math.tau/20)+.13,.052*math.sin(t*math.tau/20)+.074-j*.14,.489) for t in range(20)]
        band("Wrist strap",loop,.032,.004,cloth,c,rack,True)
        W.box("Strap tail",(.083,.027,.006),cloth,c,(.17,.026-j*.14,.477),parent=rack)
    stand=W.empty("Selfie tripod",c,(11.46,3.91,0))
    tripod(c,stand)
    with bpy.data.libraries.load(str(Path(W.ROOT)/"models/galaxy_s25_ultra.blend")) as (src,dst):
        dst.objects=[n for n in src.objects if n=="Galaxy_S25_Ultra" or n.startswith("S25U_") and not n.endswith("_Copy")]
    phone=next(o for o in dst.objects if o.name.startswith("Galaxy_S25_Ultra"))
    for o in [phone]+list(phone.children_recursive): W.link(o,c)
    phone.parent=stand; phone.location=(0,0,1.48)
    display=next(o for o in phone.children_recursive if o.name.startswith("S25U_Display_Screen"))
    watch=next(o for o in hero.children_recursive if o.name.startswith("Watch_Display"))
    return hero,phone,display,watch


def screen_switch(owner, display, labels, default):
    control(owner,"Screen",default,2," / ".join(f"{i} {label}" for i,label in enumerate(labels)))
    mat=display.data.materials[0]
    nt=mat.node_tree
    shader=next(n for n in nt.nodes if n.type=="BSDF_PRINCIPLED")
    previous=None
    for i,label in enumerate(labels):
        image=bpy.data.images.load(str(ART/(label+".png")),check_existing=True)
        if not image.packed_file: image.pack()
        tex=(nt.nodes.get("Screen_Image") if i==0 else None) or nt.nodes.new("ShaderNodeTexImage")
        tex.image=image
        color=tex.outputs["Color"]
        if previous:
            mix=nt.nodes.new("ShaderNodeMixRGB")
            nt.links.new(previous,mix.inputs[1]); nt.links.new(color,mix.inputs[2])
            driven(mix.inputs[0].driver_add("default_value"),owner,"Screen",f"v=={i}")
            color=mix.outputs[0]
        previous=color
    for socket in ("Emission Color","Base Color"): nt.links.new(previous,shader.inputs[socket])
    shader.inputs["Emission Strength"].default_value=.85


def wall_framed_portrait(who, loc, height, c):
    """Mount a WatchCoach cameo portrait inside a sleek wall poster frame (facing -Y).
    Uses lightweight gym_wall_opt/<who>_wall.jpg when available while preserving high-res originals in W.CAMEOS."""
    import os
    opt_path = os.path.join(W.PARTS, "gym_wall_opt", f"{who}_wall.jpg")
    if os.path.exists(opt_path):
        img_path = opt_path
    else:
        fn, _, _ = W.CAMEOS[who]
        img_path = os.path.join(W.PARTS, fn)
    im = bpy.data.images.load(img_path, check_existing=True)
    if not im.packed_file:
        im.pack()
    ratio = im.size[0] / im.size[1] if im.size[1] else 1.0
    w = height * ratio
    root = W.empty("WallFrame_" + who, c, loc)
    frame_m = W.mat("Gallery frame graphite", (.035, .038, .042), rough=.34, metal=.55)
    mat_w = W.mat("Gallery mat offwhite", (.86, .87, .85), rough=.65)
    molded("Frame outer " + who, (w + .064, .028, height + .064), frame_m, c, (0, .014, 0), root, .004)
    molded("Frame mat " + who, (w + .028, .010, height + .028), mat_w, c, (0, -.001, 0), root, .002)
    art = W.shadeless("WallPortrait_" + who, image=img_path, strength=.95)
    mesh = bpy.data.meshes.new("PortraitFace_" + who)
    mesh.from_pydata([(-w / 2, -.008, -height / 2), (w / 2, -.008, -height / 2),
                      (w / 2, -.008, height / 2), (-w / 2, -.008, height / 2)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new()
    for loop, coord in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = coord
    mesh.materials.append(art)
    ob = bpy.data.objects.new("PortraitFace_" + who, mesh)
    c.objects.link(ob)
    ob.parent = root
    return root


def wall_ai_logo(who, loc, height, c):
    """Mount an AI logo plaque cleanly on the wall (facing -Y)."""
    import os
    fn, _, _ = W.CAMEOS[who]
    img_path = os.path.join(W.PARTS, fn)
    im = bpy.data.images.load(img_path, check_existing=True)
    if not im.packed_file:
        im.pack()
    ratio = im.size[0] / im.size[1] if im.size[1] else 1.0
    w = height * ratio
    root = W.empty("WallLogo_" + who, c, loc)
    plaque_m = W.mat("Logo plaque charcoal", (.022, .024, .028), rough=.35, metal=.45)
    molded("Logo plaque " + who, (w + .08, .016, height + .08), plaque_m, c, (0, .008, 0), root, .006)
    mat = W.shadeless("WallLogoMat_" + who, image=img_path, strength=1.15)
    try:
        mat.surface_render_method = "BLENDED"
    except AttributeError:
        pass
    mesh = bpy.data.meshes.new("LogoFace_" + who)
    mesh.from_pydata([(-w / 2, -.004, -height / 2), (w / 2, -.004, -height / 2),
                      (w / 2, -.004, height / 2), (-w / 2, -.004, height / 2)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new()
    for loop, coord in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = coord
    mesh.materials.append(mat)
    ob = bpy.data.objects.new("LogoFace_" + who, mesh)
    c.objects.link(ob)
    ob.parent = root
    return root


def _tweak_extra_bones(arm, tweaks):
    """Apply subtle Euler degree offsets to pose bones so extras feel natural rather than cloned."""
    from mathutils import Euler
    for bname, degs in tweaks.items():
        pb = arm.pose.bones.get(bname)
        if not pb:
            continue
        delta = Euler([math.radians(d) for d in degs], "XYZ").to_quaternion()
        if pb.rotation_mode == "QUATERNION":
            pb.rotation_quaternion = pb.rotation_quaternion @ delta
        else:
            pb.rotation_euler.rotate(delta)


def stage_easter_eggs():
    """Seat supporting WatchCoach extras on gym machines and hang cameo portraits & AI logos on the back wall."""
    # 1) 5 supporting characters across the gym with varied natural poses & head/torso angles
    for role, loc, face_deg, pose, tweaks in (
        ("gray",   (5.45,  0.97, 0), 180, "sit_phone",   {"head": (8, 0, -10), "neck": (4, 0, -4)}),       # chest press — scrolling phone
        ("red",    (2.65,  0.87, 0), 180, "sit",         {"head": (-5, 0, 14), "spine.002": (5, 0, 6)}),    # shoulder press — glancing toward mirror
        ("yellow", (-0.35, 3.65, 0), 172, "mirror_flex", {"head": (-4, 0, -8)}),                            # dumbbell mirror — flexing in mirror!
        ("blue",   (7.15, -2.30, 0), 180, "sit",         {"head": (3, 0, -18), "spine.002": (4, 0, -10)}),  # leg extension — resting & looking right
        ("green",  (3.75, -2.30, 0), 180, "sit_phone",   {"head": (6, 0, 11),  "spine.001": (4, 0, 5)}),    # dip machine — checking phone
    ):
        ex = W.add_extra(role, loc=loc, face_deg=face_deg)
        W.apply_pose(ex, pose)
        _tweak_extra_bones(ex, tweaks)

    # 2) Framed cameo portraits (samsung, altman, amodei, musk, hassabis) & AI logos (gpt, claude, gemini) on back wall above mirror
    c = W.coll("CAMEO")
    for who, x in (("samsung", 1.77), ("altman", 2.55), ("amodei", 3.33), ("musk", 4.11), ("hassabis", 4.89)):
        wall_framed_portrait(who, (x, 4.97, 2.82), 0.44, c)
    for who, x in (("gpt", 8.15), ("claude", 9.05), ("gemini", 9.95)):
        wall_ai_logo(who, (x, 4.97, 2.82), 0.38, c)


def stage_reel():
    hero,phone,display,watch=stage()
    screen_switch(phone,display,("camera","reels","record"),0)
    screen_switch(hero,watch,("rest","reps","next_set"),0)
    for arc in W.watch_buzz(25,dur=12):
        arc.data.transform(Matrix.Rotation(math.pi/2,4,"X"))
    stage_easter_eggs()
    bpy.context.scene.frame_set(1)
