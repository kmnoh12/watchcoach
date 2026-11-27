"""Regenerate the stage-one lat station style from the saved scene, read-only.

blender -b --factory-startup --disable-autoexec promo/scenes/scene_gym.blend \
  --python-exit-code 1 -P tools/viewer3d/scene_lat_extract.py
Only writes the sibling scene_lat_source.json; -- --check compares without writing.
No source builder, external font, survey fixture, scene save or render required.
"""
import json
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = 'P_lat_pulldown'
SEAT = 'Ddetail6_LP_Seat'
ROLL = 'Ddetail6_LP_ThighRollers'
PLATE = 'Selector plate.020'
CHASSIS = 'Ddetail6_LP_LowerChassis'
CHARS = '.0123456789'


def um(v):
    return np.rint(np.asarray(v) * 1e6).astype(int).tolist()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def extract():
    sc = bpy.context.scene
    check(bpy.app.background and sc.unit_settings.scale_length == 1 and sc.frame_current == 1,
          'Expected the saved metre-scale scene at frame one, in background mode')
    dg = bpy.context.evaluated_depsgraph_get()
    root = sc.objects[ROOT]
    descendants = set(root.children_recursive)
    inv = root.evaluated_get(dg).matrix_world.inverted()

    def mesh(o):
        check(o in descendants, o.name + ' is not in lat station')
        obj = o.evaluated_get(dg)
        xf = np.asarray(inv @ obj.matrix_world)
        me = obj.to_mesh()
        try:
            me.calc_loop_triangles()
            v = np.array([p.co[:] for p in me.vertices]) @ xf[:3, :3].T + xf[:3, 3]
            f = np.array([p.vertices[:] for p in me.loop_triangles])
            m = np.array([p.material_index for p in me.loop_triangles])
            return v, f, m, xf[:3, 3]
        finally:
            obj.to_mesh_clear()

    def slots(o):
        return [s.material.name for s in o.material_slots]

    seat, roll, plate, chassis = [sc.objects[n] for n in (SEAT, ROLL, PLATE, CHASSIS)]
    expected = {seat: ['Ddetail6_LP_Pad', 'E_stitch'], roll: ['Ddetail6_LP_Pad', 'Ddetail6_LP_Grip'],
                plate: ['Ddetail6_LP_Stack', 'Ddetail6_LP_Grip'],
                chassis: ['Ddetail6_LP_Frame', 'Ddetail6_LP_Silver', 'Ddetail6_LP_Grip', 'Ddetail6_LP_Steel']}
    for o, names in expected.items():
        check(o in descendants and slots(o) == names, 'Source material role changed: '+o.name)

    def normalized(v, t, m):
        center = (v.min(0)+v.max(0))/2
        return dict(verts=um(v-center), tri=t.tolist(), material=m.tolist())

    # Keep evaluated triangles, including all stitch/cuff rings and each source material boundary.
    v, t, m, _ = mesh(seat)
    check(len(v)==322 and np.bincount(m).tolist()==[512,128], 'Source cushion topology changed')
    seat_data = normalized(v,t,m)
    v, t, m, _ = mesh(roll)
    out = v[:,0] > 0
    keep = out[t].all(1)
    check(out.sum()==450 and len(v)==900 and not np.any(out[t].any(1)!=keep)
          and np.bincount(m[keep]).tolist()==[480,416], 'Source cuff topology changed')
    # The +X island points outward. (Y,Z,X) is a proper rotation into local axle-Z.
    # The equal mirrored assembly is obtained at runtime by reflecting local Z and winding.
    roll_data = normalized(v[out][:,[1,2,0]], np.cumsum(out)[t[keep]]-1, m[keep])

    v, faces, mi, _ = mesh(plate)
    check(len(v) == 128 and len(faces) == 220, 'Source selector topology changed')
    body = v[:96]; center = (body.max(0)+body.min(0))/2; v -= center
    front = v[80:96,1].mean()
    check(np.ptp(v[80:96,1])<1e-6 and front<0 and np.all(mi[faces.min(1)>=96]==1), 'Wrong service face')
    casting = faces.max(1)<96
    check(np.bincount(mi[casting]).tolist()==[160,32], 'Source bore materials changed')
    labels = []
    for i in (96,112):
        q = v[i:i+16]; c = (q.min(0)+q.max(0))/2
        labels.append(dict(center=um(c-[0,front,0]), outline=um(q[:,[0,2]]-c[[0,2]])))
    plate_data = dict(size=um(np.ptp(body, axis=0)), verts=um(body),
                      tri=faces[casting].tolist(), material=mi[casting].tolist(), labels=labels)

    # Read the saved font triangles. Segment along the print line, including a separate decimal mark.
    # Infer the source font's advances and sidebearings from all 40 centered numeric runs. No recreation
    # with a machine-installed font and no approximation by rectangular LED strokes.
    glyphs = {}; eq = []; rhs = []; ink_offsets = []; units = {}
    plates = sorted((o for o in descendants if o.data == plate.data), key=lambda o:o.name)
    check(len(plates)==20,'Expected 20 original selector castings')
    for p in plates:
        _, _, _, pc = mesh(p)
        for o in sorted(p.children,key=lambda o:o.name):
            check(o.type=='FONT' and slots(o)==['E_print'], 'Unknown plate child')
            s = o.data.body; vv, ff, _, pos = mesh(o); vv -= pos
            check(np.ptp(vv[:,1])<1e-6 and all(c in CHARS for c in s), 'Unsupported number geometry')
            ink_offsets.append(pos[1]-pc[1]-front)
            if p==plate:
                units['kg' if s=='2.5' else 'lb']=int(np.argmin([abs(label['center'][0]*1e-6-(pos[0]-pc[0])) for label in labels]))
            x = vv[ff, 0]; spans=[]
            for j in np.argsort(x.min(1)):
                lo,hi = x[j].min(),x[j].max()
                if not spans or lo>spans[-1][1]+1e-7: spans.append([lo, hi, [j]])
                else: spans[-1][1]=max(spans[-1][1],hi); spans[-1][2].append(j)
            check(len(spans)==len(s),'Overlapping glyphs: '+s)
            for i,(c,(lo,hi,ids)) in enumerate(zip(s,spans)):
                row=np.zeros(2*len(CHARS))
                for a in s: row[CHARS.index(a)]-=.5
                for a in s[:i]: row[CHARS.index(a)]+=1
                row[len(CHARS)+CHARS.index(c)]=1;eq.append(row);rhs.append(lo)
                if c not in glyphs:
                    used, ii = np.unique(ff[ids], return_inverse=True)
                    xy = vv[used][:,[0,2]]-[lo,0]; face=ii.reshape(-1,3)
                    # Positive XZ signed area faces the service side (-Y). Weld duplicate contour vertices.
                    clean, rev = np.unique(np.asarray(um(xy)),axis=0,return_inverse=True); face=rev[face]; pts=clean[face]
                    area=(pts[:,1,0]-pts[:,0,0])*(pts[:,2,1]-pts[:,0,1])-(pts[:,2,0]-pts[:,0,0])*(pts[:,1,1]-pts[:,0,1]);check(np.all(area!=0),'Degenerate character')
                    face[area<0]=face[area<0,::-1];glyphs[c]=dict(xz=clean.tolist(),tri=face.tolist())
    sol,_,rank,_=np.linalg.lstsq(eq,rhs,rcond=None)
    check(rank==len(sol) and np.max(np.abs(np.array(eq)@sol-rhs))<2e-6,'Font metrics do not match saved runs')
    for i,c in enumerate(CHARS):glyphs[c].update(advance=um(sol[i]), bearing=um(sol[i+len(CHARS)]))
    check(units=={'kg':0,'lb':1} and np.ptp(ink_offsets)<1e-6,'Number side/offset mismatch')
    plate_data.update(units=units, ink_offset_y=um(np.mean(ink_offsets)))
    names=dict(lower_red=slots(chassis)[0],silver=slots(chassis)[1],grip=slots(chassis)[2],steel=slots(chassis)[3],
               pad=slots(seat)[0],stitch=slots(seat)[1],casting=slots(plate)[0],ink='E_print')
    colors={k:[round(float(c),6) for c in bpy.data.materials[n].diffuse_color[:3]] for k,n in names.items()}
    return dict(schema=2, units='um', source=dict(scene=Path(bpy.data.filepath).name,root=ROOT,
                seat=SEAT,roller=ROLL,plate=PLATE,chassis=CHASSIS,material_names=names),
                palette=colors, seat=seat_data, roller=roll_data, plate=plate_data, glyphs=glyphs)


if __name__=='__main__':
    output=Path(__file__).with_name('scene_lat_source.json')
    data=json.dumps(extract(),sort_keys=True,separators=(',',':'))+chr(10)
    if '--check' in sys.argv:
        check(output.read_text()==data,'Regenerated geometry differs from checked-in data')
    else:
        output.write_text(data)
    print('Extracted seat, cuff, plate, 11 glyphs and lower-chassis palette;',len(data),'bytes')
