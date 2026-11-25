"""Material and geometry pass for the two shop-fixture collections. Call apply() after loading the scene."""
import math
import bpy
import bmesh
from mathutils import Vector

C = "Dgym_counter_"
F = "Dgym_freeweight_"
TAG = "AstraFixtures_"


def bsdf(mat):
    return next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def node(mat, kind, label):
    nodes = mat.node_tree.nodes
    n = nodes.get(TAG + label) or nodes.new(kind)
    n.name = TAG + label
    return n


def finish(name, rough, spread, pitch, height, metal=0):
    """Object-space coordinates are metres in these scale-applied fixture meshes."""
    mat = bpy.data.materials[name]
    tree = mat.node_tree
    p = bsdf(mat)
    p.inputs['Metallic'].default_value = metal
    tex = node(mat, 'ShaderNodeTexCoord', 'Coordinates')
    grain = node(mat, 'ShaderNodeTexNoise', 'Surface grain')
    grain.inputs['Scale'].default_value = 1 / pitch
    grain.inputs['Detail'].default_value = 1.8
    tree.links.new(tex.outputs['Object'], grain.inputs['Vector'])
    remap = node(mat, 'ShaderNodeMapRange', 'Roughness range')
    remap.inputs['To Min'].default_value = rough-spread
    remap.inputs['To Max'].default_value = rough+spread
    tree.links.new(grain.outputs['Fac'], remap.inputs['Value'])
    tree.links.new(remap.outputs['Result'], p.inputs['Roughness'])
    relief = node(mat, 'ShaderNodeBump', 'Surface relief')
    relief.inputs['Distance'].default_value = height
    relief.inputs['Strength'].default_value = .32
    tree.links.new(grain.outputs['Fac'], relief.inputs['Height'])
    tree.links.new(relief.outputs[0], p.inputs['Normal'])


def mesh(name, verts, faces, materials, smooth=True):
    name = TAG + name
    existing = bpy.data.meshes.get(name)
    if existing:
        return existing
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    for m in materials:
        me.materials.append(m)
    if smooth:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(40))
    me.update()
    return me


def shell_faces(n, levels):
    faces = [list(reversed(range(n)))]
    for i in range(levels-1):
        for j in range(n):
            k = (j+1) % n
            faces.append((i*n+j, i*n+k, (i+1)*n+k, (i+1)*n+j))
    faces.append(list(range((levels-1)*n, levels*n)))
    return faces


def cloth(material, variant):
    # Three layers connected by alternating turns, with the open hem visible from the aisle.
    path = [(-.097, -.011), (.092, -.011)]
    for i in range(1,9):
        a = -math.pi/2 + i*math.pi/8
        path.append((.092 + .0055*math.cos(a), -.0055 + .0055*math.sin(a)))
    path.append((-.095, 0))
    for i in range(1,9):
        a = -math.pi/2 - i*math.pi/8
        path.append((-.095 + .0055*math.cos(a), .0055 + .0055*math.sin(a)))
    path.append((.083 - .004*variant, .011))
    upper, lower = [], []
    for i,(y,z) in enumerate(path):
        a = Vector(path[max(0,i-1)])
        b = Vector(path[min(len(path)-1,i+1)])
        dy,dz = (b-a).normalized()
        upper.append((y-.0047*dz,z+.0047*dy))
        lower.append((y+.0047*dz,z-.0047*dy))
    profile = upper+lower[::-1]
    verts = []
    for i in range(9):
        u = i/8
        for y,z in profile:
            ripple = .0012*math.sin(u*8+variant)*math.cos(8*y)
            verts.append(((u-.5)*.235, y + .0025*math.sin(7*u+variant), z+ripple))
    return mesh('Hanfold '+material.name+str(variant), verts, shell_faces(len(profile),9), [material])


def shelf_mesh(original):
    """Face wires run under the bottles; two transverse structural rails under the wires."""
    bm = bmesh.new()
    def wire(a,b,r):
        a,b = Vector(a),Vector(b)
        vs=bmesh.ops.create_cone(bm,cap_ends=True,segments=8,radius1=r,radius2=r,depth=(b-a).length)['verts']
        mx=(b-a).to_track_quat('Z','Y').to_matrix()
        for v in vs:
            v.co=mx@v.co+(a+b)*.5
    for i in range(18):
        x=-.220+i*.440/17
        wire((x,-.226,.002),(x,.226,.002),.002)
    for y in (-.225,0,.225):
        wire((-.225,y,-.0026),(.225,y,-.0026),.0028)
    data=bpy.data.meshes.new(TAG+'Shelf wire')
    bm.to_mesh(data)
    bm.free()
    data.materials.append(original.materials[0])
    return data


def leaf_mesh(small):
    length, width = (.068,.033) if small else (.157,.075)
    # Asymmetric, cupped blade narrowing to the petiole and a drip tip.
    verts=[]
    for i in range(11):
        t=i/10
        w=width*(.009+.491*math.sin(math.pi*t)**.82)
        z=length*(.13*math.sin(math.pi*t)-.13*t*t)
        ring=[(-w,.10*w),(-.12*w,0),(0,.034*w),(.12*w,0),(w,.12*w),
              (.95*w,.12*w-.0006),(.08*w,-.0007),(-.95*w,.10*w-.0006)]
        for x,dz in ring:
            verts.append((x+.025*length*t*t,(t-.5)*length,z+dz))
    return mesh('Desk leaf' if small else 'Ficus blade',verts,shell_faces(8,11),
                [bpy.data.materials[C+'RubberPlantLeaf']])


def drink_wraps(col):
    from pathlib import Path
    key=TAG+'Club drink wraps'
    image=bpy.data.images.get(key)
    if image is None:
        image=bpy.data.images.load(str(Path(__file__).with_name('drink_wraps.png')),check_existing=False)
        image.name=key
        image.pack()
    for me in {o.data for o in col.objects if o.name.startswith(C+'Protein drink')}:
        if me.get('astra_wrap'):
            continue
        orig=me.materials[1]
        flavours=['Choco','Vanilla','Banana','Blue']
        row=next(i for i,s in enumerate(flavours) if orig.name.endswith(s))
        mat=orig.copy()
        mat.name=TAG+'Printed '+flavours[row]
        # Caps keep their material even when the original reused the same label swatch.
        me.materials[1]=mat
        uv=me.uv_layers.new(name='Bottle wrap')
        tex=node(mat,'ShaderNodeTexImage','Club graphics')
        tex.image=image
        mat.node_tree.links.new(tex.outputs['Color'],bsdf(mat).inputs['Base Color'])
        print_faces=[p for p in me.polygons if p.material_index==1]
        low=min(me.vertices[j].co.z for p in print_faces for j in p.vertices)
        high=max(me.vertices[j].co.z for p in print_faces for j in p.vertices)
        for p in print_faces:
            us=[]
            for j in p.loop_indices:
                x,y,z=me.vertices[me.loops[j].vertex_index].co
                us.append((math.atan2(y,x)/math.tau % 1,z))
            seam=max(u for u,z in us)-min(u for u,z in us)>.5
            for j,(u,z) in zip(p.loop_indices,us):
                uv.data[j].uv=(u+(1 if seam and u<.5 else 0),(3-row+.006+.988*(z-low)/(high-low))/4)
        me['astra_wrap']=True


def screens_and_counter():
    for nm in ('TowelWhite','TowelGrey'):
        finish(C+nm,.89,.08,.0014,.00055)
    for nm in ('SlipperEVAGrey','SlipperEVANavy','SlipperSole'):
        finish(C+nm,.69,.13,.0018,.00028)
    finish(C+'RackBlackPowder',.43,.12,.0013,.00013)
    finish(C+'RubberPlantLeaf',.36,.09,.0025,.00009)
    for nm in ('NoticePrice','NoticeHours','SignTowel','SignSlipper','KeyboxLabel','BizCard'):
        bsdf(bpy.data.materials[C+nm]).inputs['Emission Strength'].default_value=0
    bsdf(bpy.data.materials[C+'FridgeInteriorLit']).inputs['Emission Strength'].default_value=.65
    # EEVEE-clean translucent frosted glass for consultation dividers (zero dither static).
    frost = bpy.data.materials.get('InfoRef_FrostedGlass')
    if frost and frost.use_nodes:
        if hasattr(frost, 'surface_render_method'):
            frost.surface_render_method = 'BLENDED'
        if hasattr(frost, 'use_transparency_overlap'):
            frost.use_transparency_overlap = False
        p = bsdf(frost)
        p.inputs['Base Color'].default_value = (0.88, 0.92, 0.92, 1.0)
        p.inputs['Roughness'].default_value = 0.28
        p.inputs['IOR'].default_value = 1.50
        p.inputs['Transmission Weight'].default_value = 0.0
        p.inputs['Alpha'].default_value = 0.42
        p.inputs['Coat Weight'].default_value = 0.40
        p.inputs['Coat Roughness'].default_value = 0.06
    # EEVEE-clean translucent PET/gel for hand sanitiser pump bottle (zero dither static).
    gel = bpy.data.materials.get(C + 'SanitiserGel')
    if gel and gel.use_nodes:
        if hasattr(gel, 'surface_render_method'):
            gel.surface_render_method = 'BLENDED'
        if hasattr(gel, 'use_transparency_overlap'):
            gel.use_transparency_overlap = False
        p = bsdf(gel)
        p.inputs['Base Color'].default_value = (0.82, 0.93, 0.97, 1.0)
        p.inputs['Roughness'].default_value = 0.08
        p.inputs['IOR'].default_value = 1.46
        p.inputs['Transmission Weight'].default_value = 0.0
        p.inputs['Alpha'].default_value = 0.34
        p.inputs['Coat Weight'].default_value = 0.80
        p.inputs['Coat Roughness'].default_value = 0.04
    # Satin lacquer finish on the warm wood reception counter.
    wood = bpy.data.materials.get('InfoRef_WarmWood')
    if wood and wood.use_nodes:
        p = bsdf(wood)
        if not p.inputs['Roughness'].is_linked:
            p.inputs['Roughness'].default_value = 0.30
        p.inputs['Coat Weight'].default_value = 0.28
        p.inputs['Coat Roughness'].default_value = 0.14
    # Ground the stark white desk file box into a realistic matte dark-slate organiser.
    fbox = bpy.data.objects.get('Desk file box')
    if fbox and fbox.type == 'MESH':
        fmat = bpy.data.materials.get(TAG + 'FileBoxSlate') or bpy.data.materials.new(TAG + 'FileBoxSlate')
        fmat.use_nodes = True
        p = bsdf(fmat)
        p.inputs['Base Color'].default_value = (0.042, 0.044, 0.048, 1.0)
        p.inputs['Roughness'].default_value = 0.46
        fmat.diffuse_color = (0.042, 0.044, 0.048, 1.0)
        finish(fmat.name, 0.48, 0.08, 0.0022, 0.00018, 0)
        if fbox.material_slots:
            fbox.material_slots[0].link = 'OBJECT'
            fbox.material_slots[0].material = fmat
        if not fbox.modifiers.get(TAG + 'Bevel'):
            mod = fbox.modifiers.new(TAG + 'Bevel', 'BEVEL')
            mod.width = 0.004
            mod.segments = 2
    col=bpy.data.collections['DETAIL_gym_counter']
    drink_wraps(col)
    for i,o in enumerate(sorted(col.objects,key=lambda obj:obj.name)):
        nm=o.name.removeprefix(C)
        if nm.startswith('Folded towel'):
            o.data=cloth(o.data.materials[0],i%3)
        elif nm.startswith('Fridge wire shelf'):
            o.data=bpy.data.meshes.get(TAG+'Shelf wire') or shelf_mesh(o.data)
        elif nm.startswith(('Desk leaf ','Rubber leaf ')):
            small=nm.startswith('Desk')
            o.data=leaf_mesh(small)
            # Root the blade in the desk stem or on the actual tilted trunk axis.
            length=.068 if small else .157
            stem_name='Desk stem '+nm.split()[-1] if small else 'Plant trunk '+nm.split()[-1].split('_')[0]
            stem=bpy.data.objects[C+stem_name]
            up=stem.rotation_euler.to_matrix()@Vector((0,0,1))
            base=stem.location + up*((o.location.z-stem.location.z)/up.z)
            if small:
                base=stem.location+up*max(v.co.z for v in stem.data.vertices)
            offset=o.rotation_euler.to_matrix()@Vector((0,length/2,0))
            # Store placement once, so the height is never inferred from a previously moved leaf.
            if 'astra_leaf_base' not in o:
                o['astra_leaf_base']=list(base)
            o.location=Vector(o['astra_leaf_base'])+offset


def grip(me):
    # Replace the open, straight tube by a closed lathed grip and smooth collar transitions.
    if me.get('astra_grip'):
        return
    bm=bmesh.new()
    bm.from_mesh(me)
    old={v for f in bm.faces if f.material_index==2 for v in f.verts}
    bmesh.ops.delete(bm,geom=list(old),context='VERTS')
    profile=[(-.058,.013),(-.055,.0142),(-.048,.0145),(-.046,.0142),
             (-.040,.0148),(-.022,.0164),(0,.0172),(.022,.0164),(.040,.0148),
             (.046,.0142),(.048,.0145),(.055,.0142),(.058,.013)]
    seg=24
    rings=[]
    for y,r in profile:
        rings.append([bm.verts.new((r*math.cos(j*math.tau/seg),y,r*math.sin(j*math.tau/seg))) for j in range(seg)])
    for idxs in shell_faces(seg,len(profile)):
        f=bm.faces.new([rings[i//seg][i%seg] for i in idxs])
        f.material_index=2 if len(idxs)==4 and abs(f.calc_center_median().y)<.045 else 1
        f.smooth=len(idxs)==4
    # Label-bearing end remains as-is; form an inset face in the rubber mould.
    bm.normal_update()
    ends=[f for f in bm.faces if f.material_index==0 and len(f.verts)>6 and abs(f.calc_center_median().y)>.07]
    for f in ends:
        y=f.calc_center_median().y
        bmesh.ops.inset_individual(bm,faces=[f],thickness=.003,depth=0)
        for v in f.verts:
            v.co.y-=math.copysign(.0016,y)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.update()
    me['astra_grip']=True


def knurl(col):
    # Pitch measured in metres; unwrap shaft onto axial/circumferential coordinates.
    name='AstraKnurlMeters'
    mat=bpy.data.materials[F+'Chrome_Knurl']
    for me in {o.data for o in col.objects if o.type=='MESH' and mat in o.data.materials[:]}:
        is_db=me.name.startswith(F+'DB_')
        if is_db:
            grip(me)
        if me.uv_layers.get(name):
            continue
        active=me.uv_layers.active
        layer=me.uv_layers.new(name=name)
        for p in me.polygons:
            if me.materials[p.material_index]!=mat:
                continue
            coords=[]
            for idx in p.loop_indices:
                x,y,z=me.vertices[me.loops[idx].vertex_index].co
                coords.append((math.atan2(z if is_db else y,x),y if is_db else z))
            wraps=max(a for a,v in coords)-min(a for a,v in coords)>math.pi
            for idx,(a,v) in zip(p.loop_indices,coords):
                if wraps and a<0:
                    a+=math.tau
                layer.data[idx].uv=(a*(.016 if is_db else .0145),v)
        if active:
            me.uv_layers.active=active
            active.active_render=True
    uv=node(mat,'ShaderNodeUVMap','Grip cylindrical UV')
    uv.uv_map=name
    link=mat.node_tree.links.new
    waves=[]
    for sign,suffix in [(1,'right'),(-1,'left')]:
        phase=node(mat,'ShaderNodeVectorMath','Diamond '+suffix)
        phase.operation='DOT_PRODUCT'
        phase.inputs[1].default_value=(4100,sign*4100,0)
        link(uv.outputs[0],phase.inputs[0])
        wave=node(mat,'ShaderNodeMath','Knurl '+suffix)
        wave.operation='COSINE'
        link(phase.outputs['Value'],wave.inputs[0])
        waves.append(wave)
    ridge=node(mat,'ShaderNodeMath','Intersections')
    ridge.operation='MINIMUM'
    for i,wave in enumerate(waves):
        link(wave.outputs[0],ridge.inputs[i])
    bump=node(mat,'ShaderNodeBump','Rolled knurl')
    bump.inputs['Strength'].default_value=.30
    bump.inputs['Distance'].default_value=.00016
    link(ridge.outputs[0],bump.inputs['Height'])
    link(bump.outputs[0],bsdf(mat).inputs['Normal'])


def cradles(col):
    """A moulded U saddle on each front and back beam captures the two hex heads."""
    rubber=bpy.data.materials.get(TAG+'Moulded saddles')
    if rubber is None:
        rubber=bpy.data.materials[F+'Rubber_Black'].copy()
        rubber.name=TAG+'Moulded saddles'
        rubber.diffuse_color=(.055,.058,.061,1)
        bsdf(rubber).inputs['Base Color'].default_value=rubber.diffuse_color
    records=[]
    for ob in col.objects:
        if not ob.name.startswith(F+'DB_') or 'floor' in ob.name:
            continue
        size=ob.name[len(F+'DB_'):].split('_')[0].replace('p','.')
        kg=float(size)
        records.append((kg,ob,'upper' if ob.location.z>.7 else 'lower'))
    theta=math.radians(15)
    for tier in ('upper','lower'):
        occupied=sorted([(o.location.x,kg) for kg,o,t in records if t==tier])
        if tier=='upper':
            left=max(x for x,kg in occupied if kg==12)
            right=min(x for x,kg in occupied if kg==16)
            occupied.extend([(left+(right-left)*k/3,14) for k in (1,2)])
        y0,z0=(4.655,.8) if tier=='upper' else (4.40,.36)
        for i,(x,kg) in enumerate(sorted(occupied)):
            f=.050+.023*math.sqrt(kg)
            w=.49*f
            # Actual rubber head has clipped corners. Keep 2 mm of side clearance.
            flat=.29*f+.002
            rise=(w-flat)*1.5
            profile=[(-w,-.003),(w,-.003),(w,rise),(w-.002,rise+.0006),
                     (flat,.003),(-flat,.003),(-w+.002,rise+.0006),(-w,rise)]
            verts=[(xx,y,zz) for y in [-.019,.019] for xx,zz in profile]
            data=mesh('Cradle '+str(kg), verts,shell_faces(len(profile),2),[rubber])
            for j,ly in enumerate([-.115,.115]):
                name=TAG+'Saddle %s %02d %d'%(tier,i,j)
                if name in bpy.data.objects:
                    continue
                o=bpy.data.objects.new(name,data)
                col.objects.link(o)
                o.parent=bpy.data.objects[F+'ROOT']
                o.location=(x,y0+ly*math.cos(theta)-.002*math.sin(theta),z0+ly*math.sin(theta)+.002*math.cos(theta))
                o.rotation_euler.x=theta


def weights():
    for nm,rough,spread,pitch,height,metal in [
        ('RackSteel_Black',.39,.11,.0012,.00018,0),
        ('RackSteel_Silver',.33,.08,.0014,.00006,1),
        ('Rubber_Black',.68,.13,.0017,.00030,0),
        ('DB_HeadRubber',.53,.13,.0014,.00023,0),
        ('PlateFaces',.58,.11,.0021,.00025,0),
        ('Chrome',.20,.05,.0009,.000025,1)]:
        finish(F+nm,rough,spread,pitch,height,metal)
    col=bpy.data.collections['DETAIL_gym_freeweight']
    for o in col.objects:
        if o.name.startswith(F+'Tree_horn_tip') and not o.data.get('astra_tip'):
            for v in o.data.vertices:
                v.co.x*=.024/.031
                v.co.y*=.024/.031
            o.data.update()
            o.data['astra_tip']=True
    knurl(col)
    cradles(col)


def apply():
    screens_and_counter()
    weights()
    bpy.context.view_layer.update()
