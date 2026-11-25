"""Meter-based material and fit corrections to the three pass-one gym shell packages."""
import math
import random

import bpy
from mathutils import Vector

PREFIX = "GS_Real_"


class Surface:
    def __init__(self, name, color, metal=0):
        name = PREFIX + name
        self.mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        self.mat.diffuse_color = (*color, 1)
        tree = self.mat.node_tree
        self.nodes, self.links = tree.nodes, tree.links
        self.nodes.clear()
        self.bsdf = self.node("BsdfPrincipled")
        self.bsdf.inputs["Base Color"].default_value = (*color, 1)
        self.bsdf.inputs["Metallic"].default_value = metal
        self.link(self.bsdf.outputs[0], self.node("OutputMaterial"), "Surface")
        self.pos = self.node("NewGeometry").outputs["Position"]

    def node(self, kind):
        return self.nodes.new("ShaderNode" + kind)

    def link(self, source, dest, socket):
        self.links.new(source, dest.inputs[socket])

    def noise(self, scale, detail=2, vector=None):
        n = self.node("TexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        self.link(vector or self.pos, n, "Vector")
        return n.outputs["Fac"]

    def ramp(self, source, stops):
        n = self.node("ValToRGB")
        self.link(source, n, 0)
        for i,(pos,col) in enumerate(stops):
            elem = n.color_ramp.elements[i] if i < 2 else n.color_ramp.elements.new(pos)
            elem.position = pos
            elem.color = (*col, 1)
        return n.outputs["Color"]

    def rough(self, source, lo, hi):
        n = self.node("MapRange")
        n.inputs["To Min"].default_value = lo
        n.inputs["To Max"].default_value = hi
        self.link(source,n,"Value")
        self.link(n.outputs[0],self.bsdf,"Roughness")

    def relief(self, source, depth, strength):
        n = self.node("Bump")
        n.inputs["Distance"].default_value = depth
        n.inputs["Strength"].default_value = strength
        self.link(source,n,"Height")
        self.link(n.outputs[0],self.bsdf,"Normal")


def assign(obj, mat):
    slot = obj.material_slots[0]
    slot.link = "OBJECT"
    slot.material = mat


def pigmented(name, base, grain_scale, depth, rough, metal=0, axis=None):
    s = Surface(name, base, metal)
    vec = s.pos
    if axis:
        stretch = s.node("VectorMath")
        stretch.operation = "MULTIPLY"
        stretch.inputs[1].default_value = axis
        s.link(vec,stretch,0)
        vec = stretch.outputs[0]
    grain = s.noise(grain_scale, 3, vec)
    col = s.ramp(grain,[(0.20,tuple(v*0.78 for v in base)),(0.80,tuple(v*1.12 for v in base))])
    s.link(col,s.bsdf,"Base Color")
    s.rough(grain,*rough)
    s.relief(grain,depth,0.24)
    return s.mat


def rubber(name, base, tint):
    s = Surface(name,base)
    # Dual-scale cut rubber fragments so EPDM speckle reads cleanly at both 1m and 5m (refs 207/209/212).
    chip_med = s.node("TexVoronoi")
    chip_med.voronoi_dimensions = "2D"
    chip_med.distance = "MANHATTAN"
    chip_med.inputs["Scale"].default_value = 115
    s.link(s.pos,chip_med,"Vector")
    chip_fine = s.node("TexVoronoi")
    chip_fine.voronoi_dimensions = "2D"
    chip_fine.distance = "MANHATTAN"
    chip_fine.inputs["Scale"].default_value = 285
    s.link(s.pos,chip_fine,"Vector")
    binder = s.ramp(s.noise(45, 3),[(0.2,tuple(v*.75 for v in base)),(.8,tuple(v*1.18 for v in base))])
    facets_med = s.ramp(chip_med.outputs["Color"],[(.22,(.026,.027,.028)),(.68,(.062,.064,.065)),(.90,tint)])
    facets_fine = s.ramp(chip_fine.outputs["Color"],[(.25,(.032,.033,.034)),(.72,(.085,.087,.086)),(.92,tint)])
    blend1 = s.node("MixRGB")
    mask1 = s.ramp(chip_med.outputs["Distance"],[(.14,(1,1,1)),(.30,(0,0,0))])
    s.link(mask1,blend1,0)
    s.link(binder,blend1,1)
    s.link(facets_med,blend1,2)
    blend2 = s.node("MixRGB")
    mask2 = s.ramp(chip_fine.outputs["Distance"],[(.12,(0.45,0.45,0.45)),(.26,(0,0,0))])
    s.link(mask2,blend2,0)
    s.link(blend1.outputs[0],blend2,1)
    s.link(facets_fine,blend2,2)
    s.link(blend2.outputs[0],s.bsdf,"Base Color")
    # Subtle macro foot-traffic roughness variation so overhead LEDs cast soft dark-satin reflections (ref 229).
    s.rough(s.noise(1.1, 3),.44,.72)
    s.relief(s.noise(240, 3),.00042,.26)
    return s.mat


def floor():
    machine = bpy.data.objects["RubberFloorTiles"]
    # Keep the array pitch and footprint centers. 598 mm mats on 600 mm centers.
    for v in machine.data.vertices:
        for axis in (0,1):
            v.co[axis] = math.copysign(.299, v.co[axis])
    machine.data.update()
    assign(machine,rubber("MachineEPDM",(.018,.018,.019),(.145,.150,.152)))
    heavy = rubber("ImpactEPDM",(.015,.015,.016),(.095,.128,.155))
    for key in ("Dgym_floor_FreeWeight_Tiles","Platform_Base"):
        assign(bpy.data.objects[key],heavy)
    # Retain canonical stagger, emboss and decorative planks. Richer warm-oak satin LVT (refs 159/252).
    mat = bpy.data.materials["Dgym_floor_DecoTile_Oak"]
    brick = next(n for n in mat.node_tree.nodes if n.type=="TEX_BRICK")
    for key, rgb in (("Color1",(.235,.150,.084)),("Color2",(.160,.100,.054)),("Mortar",(.092,.056,.030))):
        brick.inputs[key].default_value = (*rgb,1)
    brick.inputs["Mortar Size"].default_value = .0009
    bsdf = next((n for n in mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED"), None)
    if bsdf:
        if not bsdf.inputs["Roughness"].is_linked:
            bsdf.inputs["Roughness"].default_value = .32
        bsdf.inputs["Coat Weight"].default_value = .25
        bsdf.inputs["Coat Roughness"].default_value = .16
    mat.diffuse_color = (.200,.126,.070,1)


def mesh_object(name,verts,faces,collection,mats,indices=None):
    name = PREFIX+name
    obj = bpy.data.objects.get(name)
    if obj:
        return obj
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj = bpy.data.objects.new(name,mesh)
    collection.objects.link(obj)
    for mat in mats:
        mesh.materials.append(mat)
    if indices:
        for poly,idx in zip(mesh.polygons,indices):
            poly.material_index=idx
    return obj


def outlet_louvres(duct, coll):
    """Dark angled vanes bridging each existing side-branch rim, in its local outlet plane."""
    verts,faces=[],[]
    vertices=[(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
              (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
    cube=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    for x in (-4,.5,4.5,7.5,10.5):
        for side in (-1,1):
            axis=Vector((0,side*math.sin(math.radians(50)),-math.cos(math.radians(50))))
            horizontal=Vector((1,0,0))
            vertical=axis.cross(horizontal)
            center=Vector((x,-2.20,3.365))+axis*.182
            for offset in (-.031,-.0155,0,.0155,.031):
                half=math.sqrt(.049**2-(abs(offset)+.002)**2)
                first=len(verts)
                for a,b,c in vertices:
                    verts.append(center+horizontal*(a*half)+vertical*(offset+b*.0018+c*.0007)+axis*(c*.0014))
                faces.extend(tuple(first+i for i in f) for f in cube)
    return mesh_object("DiffuserVanes",verts,faces,coll,[duct])


def ceiling():
    slab = pigmented("Slab",(.034,.033,.032),18,.0015,(.66,.9))
    assign(bpy.data.objects["Ceiling"],slab)
    duct = pigmented("FactoryDuct",(.039,.040,.041),120,.00015,(.28,.49))
    for key in ("SpiralDuct2","SpiralDuct2Fittings"):
        assign(bpy.data.objects["Dgym_ceiling_"+key],duct)
    # Standing lock seam on 220 mm spiral pipe. Segment at existing sleeve joints.
    verts,faces=[],[]
    y,z,r=-2.20,3.365,.1096
    centers=[-6.566]+[-5.1+3*i for i in range(6)]+[12.566]
    for idx,(a,b) in enumerate(zip(centers,centers[1:])):
        start=a+(.020 if idx else 0)
        end=b-(.020 if idx<len(centers)-2 else 0)
        steps=math.ceil((end-start)/.20*28)
        first=len(verts)
        for j in range(steps+1):
            x=start+(end-start)*j/steps
            angle=(x-start)*math.tau/.20
            for ax,rad in ((-.0023,r-.0015),(.0023,r-.0015),(.0015,r+.0028),(-.0015,r+.0028)):
                verts.append((x+ax,y+rad*math.cos(angle),z+rad*math.sin(angle)))
        faces.append(tuple(first+i for i in range(3,-1,-1)))
        for j in range(steps):
            for k in range(4):
                p=first+j*4
                faces.append((p+k,p+(k+1)%4,p+4+(k+1)%4,p+4+k))
        faces.append(tuple(first+steps*4+i for i in range(4)))
    coll=bpy.data.collections["DETAIL_gym_ceiling"]
    mesh_object("RolledSeam",verts,faces,coll,[duct])
    outlet_louvres(duct,coll)
    lens=pigmented("OpalExtrusion",(.79,.78,.74),140,.00008,(.33,.45))
    shader=next(n for n in lens.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    shader.inputs["Emission Strength"].default_value=4.5
    shader.inputs["Emission Color"].default_value=(1,.948,.855,1)
    for obj in coll.objects:
        if any(s.name in ("Dgym_ceiling_LEDOpalDiffuser",lens.name) for s in obj.material_slots):
            assign(obj,lens)


def wall():
    # Individually split charcoal slips, laid above Wainscot_Left (z=0.85) to ceiling with a
    # true 3 mm shadow joint. Surface rises 5–14 mm from wall, behind the sign standoffs.
    coll=bpy.data.collections["DETAIL_gym_wall_graphics"]
    colors=[(.028,.027,.027),(.044,.042,.040),(.035,.036,.037),(.022,.022,.021)]
    mats=[pigmented("Slate"+str(i),col,14,.0026,(.52,.84),axis=(1,3,12))
          for i,col in enumerate(colors)]
    verts,faces,slots=[],[],[]
    rng=random.Random(276)
    z=.855
    while z<3.389:
        top=min(z+rng.choice((.066,.082,.095,.115)),3.39)
        y=1.16
        while y<4.979:
            end=min(y+rng.uniform(.215,.52),4.98)
            if 4.98-end<.12: end=4.98
            base=len(verts)
            front=-7.489+rng.uniform(-.002,.003)
            # Walls are nominally x=-7.496; slightly embed the rear of every slip.
            corners=[(y,z),(end,z),(end,top),(y,top)]
            verts.extend([(-7.501,yy,zz) for yy,zz in corners])
            verts.extend([(front+rng.uniform(-.001,.001),yy,zz) for yy,zz in corners])
            verts.append((front+.002,y+(end-y)*rng.uniform(.35,.65),(z+top)*.5))
            f=[(3,2,1,0)]
            for j in range(4):
                k=(j+1)%4
                f+= [(j,k,k+4,j+4),(4+j,4+k,8)]
            faces.extend([tuple(base+k for k in face) for face in f])
            slots.extend([rng.randrange(4)]*len(f))
            y=end+.003
        z=top+.003
    mesh_object("SplitSlateBay",verts,faces,coll,mats,slots)
    # Fix milky translucent acrylic sign plates -> EEVEE-clean crystal-clear optical acrylic (zero dither noise).
    acrylic = bpy.data.materials.get("Dgym_wall_graphics_ClearAcrylic")
    if acrylic and acrylic.use_nodes:
        if hasattr(acrylic, "surface_render_method"):
            acrylic.surface_render_method = "BLENDED"
        if hasattr(acrylic, "use_transparency_overlap"):
            acrylic.use_transparency_overlap = False
        bsdf = next((n for n in acrylic.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.94, 0.98, 1.0, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.03
            bsdf.inputs["IOR"].default_value = 1.49
            bsdf.inputs["Transmission Weight"].default_value = 0.0
            bsdf.inputs["Alpha"].default_value = 0.14
            bsdf.inputs["Specular IOR Level"].default_value = 0.70
            bsdf.inputs["Coat Weight"].default_value = 1.0
            bsdf.inputs["Coat Roughness"].default_value = 0.02
    # Eliminate giant floating cyan/pink orb reflections of point lights in the gym mirrors.
    for lname in ("Dgym_wall_graphics_NameSign_Glow", "Dgym_wall_graphics_StretchSign_Glow",
                  "NeonGlow_Blue", "NeonGlow_PinkLeft", "NeonGlow_PinkRight"):
        lo = bpy.data.objects.get(lname)
        if lo and lo.type == "LIGHT":
            lo.visible_glossy = False
            lo.visible_camera = False
            if lname == "Dgym_wall_graphics_NameSign_Glow":
                if "gs_orig_energy" not in lo:
                    lo["gs_orig_energy"] = lo.data.energy
                lo.data.energy = lo["gs_orig_energy"] * 0.45
    # Cable bends must emerge from the new finish. Keep the lead seated in the rail.
    for tag in ("NameSign","StretchSign"):
        lead=bpy.data.objects["Dgym_wall_graphics_"+tag+"_Lead"]
        # Cables are baked in anchor-local coordinates. Displace only the wall-hugging tail.
        for v in lead.data.vertices:
            if v.co.y>-.018:
                v.co.y=min(v.co.y,-.0165+(v.co.y+.006)*.18)
        # Baseline local coordinates are kept for idempotence in apply() below.
    steel=pigmented("BrushedLetter",(.67,.69,.70),170,.00012,(.22,.43),1,axis=(1,1,30))
    assign(bpy.data.objects["Dgym_wall_graphics_Lettering_EN"],steel)


def mirrors_and_shadows():
    """Upgrade Gym_Mirror to bright silvered metal, add planar probe for Stretch mirror, and clear EEVEE shadow pool overflow."""
    gm = bpy.data.materials.get("Gym_Mirror")
    if gm and gm.node_tree:
        bsdf = next((n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.93, 0.94, 0.94, 1.0)
            bsdf.inputs["Metallic"].default_value = 1.0
            bsdf.inputs["Roughness"].default_value = 0.01
            bsdf.inputs["Coat Weight"].default_value = 0.0

    # Planar reflection probe for the stretching-zone mirror (faces +X at x=-7.442).
    stretch = bpy.data.objects.get("Stretch mirror glass")
    if stretch is not None:
        bpy.context.view_layer.update()
        pts = [stretch.matrix_world @ Vector(c) for c in stretch.bound_box]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        probe_name = PREFIX + "StretchMirrorProbe"
        coll = bpy.data.collections["DETAIL_gym_wall_graphics"]
        ob = bpy.data.objects.get(probe_name)
        if ob is not None and ob.type != "LIGHT_PROBE":
            bpy.data.objects.remove(ob, do_unlink=True)
            ob = None
        if ob is None:
            lp = bpy.data.lightprobes.new(probe_name, "PLANE")
            ob = bpy.data.objects.new(probe_name, lp)
            coll.objects.link(ob)
        else:
            lp = ob.data
            if coll not in ob.users_collection:
                coll.objects.link(ob)
        lp.influence_distance = 0.12
        lp.clip_start = 0.001
        ob.parent = None
        ob.location = (hi[0] + 0.010, 0.5 * (lo[1] + hi[1]), 0.5 * (lo[2] + hi[2]))
        # Local +Z -> +X, local +X -> -Z (half-height), local +Y -> +Y (half-width)
        ob.rotation_euler = (0.0, math.radians(90.0), 0.0)
        ob.scale = (0.5 * (hi[2] - lo[2]) + 0.05, 0.5 * (hi[1] - lo[1]) + 0.05, 1.0)

    # Prevent EEVEE shadow buffer full warnings: raise shadow pool to 1024 MB (1 GB) and disable shadows
    # on fill/bounce lights + the 0.16W outdoor Sun fill ("Key") whose clipmaps consume ~1500+ shadow pages.
    sc = bpy.context.scene
    if hasattr(sc.eevee, "shadow_pool_size"):
        sc.eevee.shadow_pool_size = "1024"
    for lo in sc.objects:
        if lo.type != "LIGHT":
            continue
        nl = lo.name
        if (nl.startswith("Dhall_surfaces_FloorBounce")
                or nl == "Warm neon fill"
                or nl == "Key"
                or nl.startswith("Dgym_counter_LED wash")
                or nl.startswith("Dgym_posing_Mirror LED bar")
                or nl == "Dhall_props_Stair_LightPit"
                or (nl.startswith("Dgym_ceiling_LEDFrame") and nl.endswith(("_2", "_3")))):
            lo.data.use_shadow = False


def apply():
    floor()
    ceiling()
    leads=[bpy.data.objects["Dgym_wall_graphics_"+tag+"_Lead"] for tag in ("NameSign","StretchSign")]
    for lead in leads:
        if "gs_original_y" not in lead:
            lead["gs_original_y"]=[v.co.y for v in lead.data.vertices]
        for v,y in zip(lead.data.vertices,lead["gs_original_y"]):
            v.co.y=y
    wall()
    mirrors_and_shadows()
    bpy.context.view_layer.update()
    owned=[bpy.data.objects[PREFIX+name] for name in ("RolledSeam","SplitSlateBay","DiffuserVanes")]
    for obj in owned:
        obj.data.calc_loop_triangles()
    return {"objects":[o.name for o in owned],"triangles":{o.name:len(o.data.loop_triangles) for o in owned}}
