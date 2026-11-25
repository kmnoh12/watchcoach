"""Hall surface and shopfront overlay for WatchCoach. Call apply() on the loaded scene."""
import math
import bpy
from mathutils import Vector

PREFIX = 'HallFinish_'
SHOP = 'Dhall_storefronts_'
SHELL = 'Dhall_surfaces_'


def material(label, color, roughness, metal=0):
    name = PREFIX + label
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Metallic'].default_value = metal
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(bs.outputs[0], out.inputs['Surface'])
    m.diffuse_color = (*color, 1)
    return m, nt, bs


def noise(nt, coord, scale, detail=2):
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    nt.links.new(coord, n.inputs['Vector'])
    return n.outputs['Fac']


def grade(nt, field, a, b):
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    for e,c in zip(ramp.color_ramp.elements,(a,b)):
        e.color = (*c,1)
    nt.links.new(field,ramp.inputs[0])
    return ramp.outputs[0]


def coord(nt, hall):
    t = nt.nodes.new('ShaderNodeTexCoord')
    t.object = hall
    return t.outputs['Object']


def bump(nt, field, strength, distance):
    n = nt.nodes.new('ShaderNodeBump')
    n.inputs['Distance'].default_value = distance
    n.inputs['Strength'].default_value = strength
    nt.links.new(field,n.inputs['Height'])
    return n.outputs[0]


def mix(nt, fac, a, b):
    n = nt.nodes.new('ShaderNodeMixRGB')
    for i, val in enumerate((fac,a,b)):
        if isinstance(val,bpy.types.NodeSocket):
            nt.links.new(val,n.inputs[i])
        else:
            n.inputs[i].default_value = val
    return n.outputs[0]


def ceramic(hall):
    m, nt, bs = material('LimestonePorcelain',(.35,.33,.29),.10)
    xyz = coord(nt,hall)
    slab = nt.nodes.new('ShaderNodeTexBrick')
    slab.offset = 0
    for key,value in [('Scale',1),('Brick Width',1.2),('Row Height',.6),('Mortar Size',.0026),('Mortar Smooth',.35)]:
        slab.inputs[key].default_value = value
    # Brick uses Z as a stack axis as well. Sample through the middle of a course.
    add = nt.nodes.new('ShaderNodeVectorMath')
    add.operation = 'ADD'
    add.inputs[1].default_value = (.15,.08,.31)
    nt.links.new(xyz,add.inputs[0])
    nt.links.new(add.outputs[0],slab.inputs['Vector'])
    # Subtle organic marble/limestone veining matching refs 70/72 (no regular stripes).
    vein = nt.nodes.new('ShaderNodeTexNoise')
    vein.inputs['Scale'].default_value = 2.4
    vein.inputs['Detail'].default_value = 6.0
    vein.inputs['Roughness'].default_value = 0.62
    vein.inputs['Distortion'].default_value = 1.6
    nt.links.new(xyz,vein.inputs['Vector'])
    vein_col = grade(nt,vein.outputs['Fac'],(.29,.28,.256),(.45,.438,.405))
    stone = grade(nt,noise(nt,xyz,3.6,5),(.26,.252,.232),(.46,.448,.416))
    mineral = grade(nt,noise(nt,xyz,42,3),(.285,.28,.258),(.50,.485,.448))
    color = mix(nt,.20,mix(nt,.18,stone,mineral),vein_col)
    nt.links.new(color,slab.inputs['Color1'])
    nt.links.new(mix(nt,.16,color,(.20,.192,.174,1)),slab.inputs['Color2'])
    slab.inputs['Mortar'].default_value = (.14,.135,.125,1)
    nt.links.new(slab.outputs['Color'],bs.inputs['Base Color'])
    gloss = grade(nt,noise(nt,xyz,4.8),(.055,)*3,(.125,)*3)
    nt.links.new(mix(nt,slab.outputs['Fac'],gloss,(.62,.62,.62,1)),bs.inputs['Roughness'])
    seam = nt.nodes.new('ShaderNodeBump')
    seam.invert = True
    seam.inputs['Strength'].default_value = .55
    seam.inputs['Distance'].default_value = .0014
    nt.links.new(slab.outputs['Fac'],seam.inputs['Height'])
    nt.links.new(seam.outputs[0],bs.inputs['Normal'])
    bs.inputs['IOR'].default_value = 1.54
    bs.inputs['Coat Weight'].default_value = .25
    bs.inputs['Coat Roughness'].default_value = .06
    return m


def stone_panel(hall):
    m, nt, bs = material('HonedGranite',(.34,.326,.305),.28)
    xyz = coord(nt,hall)
    # Medium-scale granite mineral pattern + subtle 600mm architectural panel seams so it reads at 2-4m.
    coarse = noise(nt,xyz,26,4)
    fine = noise(nt,xyz,95,3)
    grit = mix(nt,.45,coarse,fine)
    ground = grade(nt,grit,(.16,.153,.142),(.43,.420,.398))
    flecks = nt.nodes.new('ShaderNodeTexVoronoi')
    flecks.inputs['Scale'].default_value = 72
    nt.links.new(xyz,flecks.inputs['Vector'])
    tint = nt.nodes.new('ShaderNodeValToRGB')
    for el,pos,col in zip(tint.color_ramp.elements,(.18,.42),((.075,.070,.064),(.42,.406,.382))):
        el.position = pos
        el.color = (*col,1)
    nt.links.new(flecks.outputs['Distance'],tint.inputs[0])
    panel_col = mix(nt,.30,ground,tint.outputs[0])
    # Subtle vertical stone panel joints every 0.60m along corridor X/Y.
    joints = nt.nodes.new('ShaderNodeTexBrick')
    joints.offset = 0
    for key,value in [('Scale',1),('Brick Width',.60),('Row Height',1.15),('Mortar Size',.0022),('Mortar Smooth',.3)]:
        joints.inputs[key].default_value = value
    nt.links.new(xyz,joints.inputs['Vector'])
    nt.links.new(panel_col,joints.inputs['Color1'])
    nt.links.new(mix(nt,.08,panel_col,(.22,.21,.195,1)),joints.inputs['Color2'])
    joints.inputs['Mortar'].default_value = (.11,.105,.098,1)
    nt.links.new(joints.outputs['Color'],bs.inputs['Base Color'])
    rough = grade(nt,coarse,(.22,)*3,(.34,)*3)
    nt.links.new(mix(nt,joints.outputs['Fac'],rough,(.65,.65,.65,1)),bs.inputs['Roughness'])
    grain_bump = bump(nt,grit,.16,.00035)
    seam_bump = nt.nodes.new('ShaderNodeBump')
    seam_bump.invert = True
    seam_bump.inputs['Strength'].default_value = .45
    seam_bump.inputs['Distance'].default_value = .0012
    nt.links.new(joints.outputs['Fac'],seam_bump.inputs['Height'])
    nt.links.new(grain_bump,seam_bump.inputs['Normal'])
    nt.links.new(seam_bump.outputs[0],bs.inputs['Normal'])
    return m


def replace(ob, mat):
    if ob.data.users > 1:
        ob.data = ob.data.copy()
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def trim_overlap(hall, name):
    ob = bpy.data.objects[name]
    transform = hall.matrix_world.inverted() @ ob.matrix_world
    if ob.data.users > 1:
        ob.data = ob.data.copy()
    for vert in ob.data.vertices:
        p = transform @ vert.co
        if p.x > -4.6999:
            p.x = -4.7
            vert.co = transform.inverted() @ p
    ob.data.update()


def block(label, bounds, mat, hall, collection, bevel=0):
    name = PREFIX + label
    ob = bpy.data.objects.get(name)
    if ob is None:
        me = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name,me)
        collection.objects.link(ob)
        ob.parent = hall
        lo,hi = bounds
        vertices = [(x,y,z) for z in (lo[2],hi[2]) for x,y in
                    ((lo[0],lo[1]),(hi[0],lo[1]),(hi[0],hi[1]),(lo[0],hi[1]))]
        me.from_pydata(vertices,[],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        me.update()
        if bevel:
            mod = ob.modifiers.new('Edge radius','BEVEL')
            mod.width = bevel
            mod.segments = 3
            mod.harden_normals = True
            ob.modifiers.new('Corner normals','WEIGHTED_NORMAL')
    replace(ob,mat)
    return ob


def fabric_detail(ob):
    # Keep the original apartment-size artwork and give only the pile an actual fibre response.
    old = ob.active_material
    name = PREFIX+ob.name.removeprefix(SHOP)
    if old.name == name:
        return
    m = old.copy()
    m.name = name
    replace(ob,m)
    nt = m.node_tree
    bs = next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    xyz = coord(nt,ob)
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.bands_direction = 'Y'
    wave.inputs['Scale'].default_value = 51
    wave.inputs['Distortion'].default_value = 2.3
    wave.inputs['Detail Scale'].default_value = 1.7
    nt.links.new(xyz,wave.inputs['Vector'])
    texture = mix(nt,.36,wave.outputs['Fac'],noise(nt,xyz,650))
    nt.links.new(bump(nt,texture,.65,.0019),bs.inputs['Normal'])
    bs.inputs['Sheen Weight'].default_value = .27


def apply():
    objects = bpy.data.objects
    hall = objects['Sangga_Hallway']
    col = objects[SHOP+'VacLeaseSheet'].users_collection[0]
    tile = ceramic(hall)
    granite = stone_panel(hall)
    for name in ('Hallway floor','HallExt floor'):
        replace(objects[name],tile)
    for name in ('HallExt floor','HallExt ceiling'):
        trim_overlap(hall,name)
    for name in (SHELL+'GymWall_Wainscot',SHELL+'GymSideInfill_Wainscot','HallExt wall L lower'):
        replace(objects[name],granite)
    board = objects['Hallway ceiling'].active_material
    nt = board.node_tree
    bs = next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    if not bs.inputs['Normal'].is_linked:
        img = next(n for n in nt.nodes if n.type=='TEX_IMAGE')
        nt.links.new(bump(nt,img.outputs['Color'],.26,.0012),bs.inputs['Normal'])
    for l in bpy.context.scene.objects:
        if l.type != 'LIGHT':
            continue
        if l.name.startswith(SHELL+'FloorBounce'):
            l.data.energy = 185.0 if l.name.endswith('Main') else 140.0
            l.data.specular_factor = 0
        elif l.name.startswith('HallwayLight_'):
            l.data.energy = 155.0
            l.data.specular_factor = 1.0
        elif l.name.startswith('HallExtLight_'):
            l.data.energy = 145.0
            l.data.specular_factor = 1.0
        elif l.name.startswith(SHELL+'DownlightSpot'):
            l.data.energy = 75.0
    m = bpy.data.materials[SHELL+'DownlightLens']
    for n in m.node_tree.nodes:
        if n.type=='EMISSION':
            n.inputs['Strength'].default_value = 35
        if n.type=='BSDF_PRINCIPLED':
            n.inputs['Emission Strength'].default_value = 35

    # The unit was pasted on the face of a continuous solid wall. Preserve the host
    # and its name and rebuild just its visible masonry returns around the opening.
    wall = objects['HallExt wall R']
    wall.hide_render = wall.hide_viewport = True
    wall_mat = wall.active_material
    def box(n,lo,hi,m,r=0):
        return block(n,(lo,hi),m,hall,col,r)
    box('WallLeft',(-11.57,2.86,0),(-7.48,2.94,2.8),wall_mat)
    box('WallRight',(-4.87,2.86,0),(-4.63,2.94,2.8),wall_mat)
    box('Lintel',(-7.48,2.86,2.68),(-4.87,2.94,2.8),wall_mat)
    paint = material('ShopPlaster',(.54,.526,.495),.77)[0]
    rubber = material('GlazingRubber',(.023,.025,.024),.54)[0]
    enamel = material('GraphiteJoinery',(.058,.063,.064),.34)[0]
    interior = material('VacancyFloor',(.25,.239,.215),.48)[0]
    box('UnitBack',(-7.49,5.62,0),(-4.865,5.68,2.72),paint)
    box('UnitLeft',(-7.53,2.93,0),(-7.49,5.62,2.72),paint)
    box('UnitRight',(-4.865,2.93,0),(-4.815,5.62,2.72),paint)
    box('UnitCeiling',(-7.49,2.94,2.72),(-4.865,5.62,2.76),paint)
    box('UnitFloor',(-7.49,2.855,.054),(-4.865,5.62,.095),interior)
    box('RearSkirt',(-7.489,5.605,.095),(-4.866,5.62,.17),enamel,.001)
    box('SocketPlate',(-6.84,5.594,.34),(-6.71,5.605,.415),paint,.003)
    for i,x in enumerate((-6.815,-6.751)):
        box('Socket'+str(i),(x,5.589,.357),(x+.038,5.594,.394),enamel,.0004)
    # Empty unit as in refs 128,135: read through the glazing. Keep a single
    # lease sign and a few taped management sheets; remove the repeated faux newspaper.
    for o in hall.children_recursive:
        if o.name.startswith((SHOP+'VacPaper_',SHOP+'VacTape_',SHOP+'VacLeaseSheet',SHOP+'VacNoticeMail')):
            o.hide_render = o.hide_viewport = True
        if o.name.startswith('Vacant_Mullion'):
            replace(o,enamel)
    glass = objects[SHOP+'OppGlass_0'].active_material
    if glass:
        if hasattr(glass, 'surface_render_method'):
            glass.surface_render_method = 'BLENDED'
        if glass.use_nodes:
            gbs = next((n for n in glass.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if gbs:
                gbs.inputs['Transmission Weight'].default_value = 0.0
                gbs.inputs['Alpha'].default_value = 0.22
                gbs.inputs['Roughness'].default_value = 0.04
                gbs.inputs['Coat Weight'].default_value = 0.8
    replace(objects['Vacant_Glass'],glass)
    box('MeetingGasket',(-5.514,2.831,.133),(-5.508,2.840,2.142),rubber,.001)
    for i,x in enumerate((-7.47,-6.211,-6.148,-4.883)):
        box('FrameSeal'+str(i),(x,2.836,.132),(x+.005,2.843,2.142),rubber,.001)
    for i,(x0,x1) in enumerate(((-7.465,-6.21),(-6.143,-5.516),(-5.505,-4.884))):
        box('GlassShoe'+str(i),(x0,2.82,.133),(x1,2.859,.185),enamel,.0015)
    for name in ('Mat_GymEntrance','Mat_Academy'):
        fabric_detail(objects[SHOP+name])
    umb = objects.get(SHOP+'Umbrella_StandBody')
    if umb and umb.type == 'MESH':
        umb.data.shade_smooth()
        umb.data.set_sharp_from_angle(angle=math.radians(38))
        umb_mat = umb.active_material
        if umb_mat and umb_mat.use_nodes:
            bs = next((n for n in umb_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bs:
                bs.inputs['Metallic'].default_value = .92
                bs.inputs['Roughness'].default_value = .24
    bpy.context.view_layer.update()
    return {'generated':len([o for o in col.objects if o.name.startswith(PREFIX)]),
            'floor_ends_at':-4.70,'vacant_depth_m':2.78}
