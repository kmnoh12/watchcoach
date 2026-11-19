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
    path = Path(W.PARTS) / "gym_print" / filename
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
    printed_face("Locker wall mural","locker_mural.png",18,3,(1.5,.020,2.09),wall,c)
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
    for x,filename in ((1.42,"plates.png"),(2.28,"training.png")):
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
    scan=W.empty("Body composition analyzer",c,(-4.05,-5.23,0))
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
    phone=next(o for o in dst.objects if o.name=="Galaxy_S25_Ultra")
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


def stage_reel():
    hero,phone,display,watch=stage()
    screen_switch(phone,display,("camera","reels","record"),0)
    screen_switch(hero,watch,("rest","reps","next_set"),0)
    for arc in W.watch_buzz(25,dur=12):
        arc.data.transform(Matrix.Rotation(math.pi/2,4,"X"))
    bpy.context.scene.frame_set(1)
