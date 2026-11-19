"""Commercial cardio machines for the gym reel set. Local -Y is forward."""
import math
import os

import bpy

import wc_lib as W
import reel_gym as R


def side_panel(name, yz, x, width, material, collection, parent, bevel=.016):
    count = len(yz)
    verts = [(xx,y,z) for xx in (x-width/2,x+width/2) for y,z in yz]
    faces = [tuple(reversed(range(count))),tuple(range(count,count*2))]
    faces.extend((i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name,mesh)
    collection.objects.link(obj)
    obj.parent = parent
    mod=obj.modifiers.new("Molded edge","BEVEL")
    mod.width=bevel
    mod.segments=3
    obj.modifiers.new("Surface normals","WEIGHTED_NORMAL")
    return obj


def bent_tube(name, points, radius, material, collection, parent):
    curve=bpy.data.curves.new(name,"CURVE")
    curve.dimensions="3D"
    curve.bevel_depth=radius
    curve.bevel_resolution=3
    curve.resolution_u=10
    curve.use_fill_caps=True
    path=curve.splines.new("BEZIER")
    path.bezier_points.add(len(points)-1)
    for knot,point in zip(path.bezier_points,points):
        knot.co=point
        knot.handle_left_type=knot.handle_right_type="AUTO"
    curve.materials.append(material)
    obj=bpy.data.objects.new(name,curve)
    collection.objects.link(obj)
    obj.parent=parent
    return obj


def display(name, c, root, loc, width, height, tilt, artwork, screen_fraction):
    pivot=W.empty(name,c,loc,parent=root)
    pivot.rotation_euler=(math.radians(-tilt),0,math.pi)
    shell=W.mat("Cardio console graphite",(.04,.043,.046),rough=.39)
    # The printed membrane and surrounding bezel share the same mesh boundary.
    # Rounded shoulders and a shallow arched top follow the New Redon housing.
    mesh=bpy.data.meshes.new(name+" case")
    ring=[]
    for cx,cz,start in ((.43,.42,0),(-.43,.42,90),(-.43,-.42,180),(.43,-.42,270)):
        for step in range(7):
            angle=math.radians(start+15*step)
            ring.append((cx+.07*math.cos(angle),cz+.08*math.sin(angle)))
            if step==6 and start==0:
                ring.extend([(u,.50+.024*(1-(u/.43)**2)) for u in (.32,.16,0,-.16,-.32)])
    count=len(ring)
    verts=[(u*width*scale,y,z*height*scale) for y,scale in
           ((.04,.96),(.031,1),(-.030,1),(-.038,.975),(-.038,screen_fraction))
           for u,z in ring]
    faces=[tuple(reversed(range(count)))]
    for row in range(4):
        for i in range(count):
            j=(i+1)%count
            faces.append((row*count+i,row*count+j,(row+1)*count+j,(row+1)*count+i))
    faces.append(tuple(range(4*count,5*count)))
    mesh.from_pydata(verts,[],faces)
    mesh.materials.append(shell)
    art=W.shadeless(name+" printed controls",image=os.path.join(W.PARTS,"gym_print",artwork),strength=.85)
    texture=next(n.image for n in art.node_tree.nodes if n.type=="TEX_IMAGE")
    if not texture.packed_file: texture.pack()
    mesh.materials.append(art)
    front=mesh.polygons[-1]
    front.material_index=1
    uv=mesh.uv_layers.new()
    for li,(u,z) in zip(front.loop_indices,ring):
        uv.data[li].uv=(u+.5,(z+.5)/1.024)
    obj=bpy.data.objects.new(name+" housing",mesh)
    c.objects.link(obj)
    obj.parent=pivot
    return pivot


def redon_console(machine,c):
    dark=W.mat("Cardio rubber",(.019,.023,.023),rough=.78)
    alloy=W.mat("Cardio satin shell",(.066,.073,.075),rough=.43,metal=.26)
    R.rod("Redon console bridge",(-.34,-.64,1.16),(.34,-.64,1.16),.043,alloy,c,machine)
    R.rod("Redon mounting neck",(0,-.64,1.15),(0,-.74,1.40),.056,alloy,c,machine)
    display("Runner controls",c,machine,(0,-.735,1.434),.638,.505,27,"new_redon_led.png",.928)
    for side in (-1,1):
        x=side*.34
        R.rod("Pulse contact",(x,-.415,1.011),(x,-.300,.996),.032,alloy,c,machine)
    red=W.mat("Emergency key vermilion",(.64,.055,.027),rough=.52)
    R.molded("Safety key",(.049,.037,.024),red,c,(0,-.603,1.188),machine)
    bent_tube("Safety lanyard",[(0,-.590,1.19),(.038,-.55,1.13),(.084,-.555,1.104),
                               (.13,-.59,1.14),(.14,-.619,1.163)],.0026,red,c,machine)
    R.molded("Shirt clip",(.034,.024,.015),dark,c,(.14,-.618,1.161),machine)


def stair_climber(c,loc):
    root=W.empty("Rotating stair climber",c,loc)
    root.rotation_euler.z=math.pi/2
    shell=W.mat("Climber charcoal",(.079,.084,.091),rough=.40,metal=.24)
    silver=W.mat("Cardio silver trim",(.46,.48,.50),rough=.37,metal=.52)
    rubber=W.mat("Cardio rubber",(.019,.023,.023),rough=.78)
    rail=W.mat("Graphite safety rails",(.036,.041,.046),rough=.32,metal=.48)
    # Counterclockwise profile as viewed from the positive X end.
    profile=[(-.74,.065),(.67,.065),(.77,.17),(.74,.38),(.59,.52),
             (-.34,1.16),(-.59,1.18),(-.73,1.04)]
    R.molded("Drive plinth",(.74,1.43,.14),rubber,c,(0,0,.072),root,.046)
    for sign in (-1,1):
        x=sign*.355
        side_panel("Stair drive fairing",profile,x,.105,shell,c,root)
        stripe=[(.68,.24),(.69,.33),(.56,.49),(-.36,1.12),(-.55,1.14),
                (-.48,1.073),(.53,.402)]
        side_panel("Swept silver insert",stripe,sign*.409,.009,silver,c,root,.003)
        railpath=[(x,.57,.45),(x,.68,.76),(x,.59,.95),(x,.05,1.39),
                  (x,-.34,1.70),(x,-.56,1.73),(x,-.65,1.62),(x,-.60,1.17)]
        bent_tube("Continuous side handrail",railpath,.029,rail,c,root)
        R.rod("Rail support",(x,-.49,1.11),(x,-.345,1.70),.022,rail,c,root)
        R.rod("Upper climbing grip",(x,-.34,1.69),(x,-.50,1.91),.030,rubber,c,root)
        R.molded("Boarding ledge",(.125,.24,.048),rubber,c,(sign*.33,.74,.18),root)
    for i in range(4):
        y=.52-.275*i
        z=.267+.196*i
        R.molded("Stair tread",(.618,.277,.047),rubber,c,(0,y,z),root,.012)
        R.molded("Step riser",(.61,.020,.181),shell,c,(0,y+.125,z-.105),root)
        for row in range(7):
            R.molded("Tread grip ridge",(.572,.008,.004),shell,c,(0,y-.09+row*.029,z+.024),root,.001)
    R.molded("Upper return cover",(.70,.28,.105),shell,c,(0,-.57,1.108),root,.034)
    R.rod("Climber console mast",(0,-.57,1.13),(0,-.67,1.93),.046,rail,c,root)
    display("Climber display",c,root,(0,-.67,1.94),.40,.294,22,"step_console.png",.84)
    return root


def upright_cycle(c,loc):
    root=W.empty("Upright exercise cycle",c,loc)
    root.rotation_euler.z=math.pi/2
    shell=W.mat("Cycle pearl silver",(.53,.56,.56),rough=.35,metal=.36)
    dark=W.mat("Graphite safety rails",(.036,.041,.046),rough=.32,metal=.48)
    rubber=W.mat("Cardio rubber",(.019,.023,.023),rough=.78)
    for y in (-.53,.44):
        R.molded("Cycle stabilizer",(.59,.112,.069),dark,c,(0,y,.043),root,.03)
        for x in (-.235,.235):
            W.cyl("Cycle leveling foot",.040,.022,rubber,c,(x,y,.011),parent=root,seg=16)
    R.molded("Low cycle backbone",(.138,1.00,.093),shell,c,(0,-.036,.112),root,.029)
    R.smooth_mesh(R.oval("Enclosed cycle drive",(0,.215,.340),(.143,.338,.265),
                         shell,c,root))
    for sign in (-1,1):
        x=sign*.112
        R.rod("Flywheel side cover",(x,.235,.34),(x+sign*.014,.235,.34),.201,dark,c,root)
    bent_tube("Cycle front frame",[(0,-.42,.126),(0,-.515,.207),(0,-.542,.48),(0,-.566,.73)],
              .065,shell,c,root)
    R.rod("Instrument upright",(0,-.566,.66),(0,-.603,1.249),.041,dark,c,root)
    R.rod("Seat post socket",(0,.22,.48),(0,.265,.69),.055,dark,c,root)
    R.rod("Adjustable seat post",(0,.264,.66),(0,.306,.895),.035,shell,c,root)
    R.rod("Height knob",(0,.26,.66),(.088,.26,.66),.022,rubber,c,root)
    R.smooth_mesh(R.oval("Saddle rear",(0,.336,.916),(.139,.116,.046),rubber,c,root))
    R.smooth_mesh(R.oval("Saddle nose",(0,.230,.92),(.075,.105,.034),rubber,c,root))
    for sign in (-1,1):
        x=.164*sign
        hub=(x,.23,.34); tip=(x,.23+sign*.113,.34+sign*.087)
        R.rod("Crank spindle",(sign*.105,.23,.34),hub,.024,shell,c,root)
        R.rod("Crank arm",hub,tip,.019,shell,c,root)
        R.rod("Pedal axle",tip,(x+sign*.069,tip[1],tip[2]),.009,dark,c,root)
        px=x+sign*.070
        R.molded("Platform pedal",(.106,.135,.027),rubber,c,(px,tip[1],tip[2]),root)
        bent_tube("Pedal strap",[(px-.047,tip[1],tip[2]),(px-.04,tip[1]-.022,tip[2]+.046),
                  (px+.04,tip[1]-.022,tip[2]+.046),(px+.047,tip[1],tip[2])],.009,rubber,c,root)
        bent_tube("Multi position cycle grip",[(0,-.58,1.15),(sign*.19,-.47,1.12),
                  (sign*.245,-.405,1.17),(sign*.226,-.495,1.34)],.022,rubber,c,root)
    display("Cycle monitor",c,root,(0,-.59,1.303),.31,.22,25,"bike_console.png",.83)
    return root


def add_cardio_pair(collection):
    return (stair_climber(collection,(12.20,-2.25,0)),upright_cycle(collection,(12.28,-3.63,0)))
