"""Read the phone plate overlay back. Compare the actual triangles, UVs and rigid tracks,
and sample the new-hand skin against original/replacement solids at keys and midpoints.
Usage: python3 tools/check_app3d_plates.py [viewer3d] [--report output.json]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation, Slerp

import check_app3d_stage1 as wire
from scene_plates import HERE, fit
from part_registry import MAT_CHROME, MAT_PLATE_FACE


class Solid:
    """Parity in a non-axial ray direction; exact nearest triangle distance for interior probes."""
    def __init__(self, verts, triangles):
        self.lo, self.hi = verts.min(0), verts.max(0)
        a,b,c = verts[triangles].transpose(1,0,2)
        edge = np.stack([b-a,c-b,a-c]); n = np.cross(edge[0], -edge[2]); area = np.linalg.norm(n,axis=1)
        valid = area > 1e-14
        self.a = a[valid]; self.origins = np.stack([a,b,c])[:,valid]; self.edges = edge[:,valid]
        self.n = n[valid]/area[valid,None]; self.crosses = np.cross(self.n, self.edges)
        self.denom = (self.edges**2).sum(2)
        ray = np.array([.721351,.368928,.586807]); dot = np.einsum('ij,j->i',self.n,ray)
        self.ray = ray; self.inverse = np.divide(1.,dot,out=np.zeros_like(dot),where=abs(dot)>1e-10)

    def depth(self, pts):
        assert np.isfinite(pts).all()
        out = np.zeros(len(pts)); ix, = np.where(((pts>=self.lo)&(pts<=self.hi)).all(1))
        # Work in bounded batches, even if the skin lies flat against a face.
        for batch in np.array_split(ix, max(1,(len(ix)+63)//64)):
            if not len(batch): continue
            x = pts[batch]; d = np.einsum('ptc,tc->pt',x[:,None,:]-self.a,self.n)
            travel = -d*self.inverse
            hit = x[:,None,:] + travel[:,:,None]*self.ray
            inside = (travel>0)
            for o,cross in zip(self.origins,self.crosses):
                inside &= np.einsum('ptc,tc->pt',hit-o,cross)>=0
            k, = np.where(inside.sum(1)%2)
            if not len(k): continue
            x = x[k,None,:]; in_face = np.ones((len(k),len(self.a)),bool); edge2 = np.full(in_face.shape,np.inf)
            for o,e,cross,den in zip(self.origins,self.edges,self.crosses,self.denom):
                delta=x-o; in_face &= np.einsum('ptc,tc->pt',delta,cross)>=0
                t=(np.einsum('ptc,tc->pt',delta,e)/den).clip(0,1)
                edge2=np.minimum(edge2, ((delta-t[:,:,None]*e)**2).sum(2))
            out[batch[k]]=np.sqrt(np.where(in_face,d[k]**2,edge2).min(1))
        return out


def tracks(pos,q,grid,times):
    if len(pos)==1:
        return np.broadcast_to(pos,(len(times),3)), np.broadcast_to(Rotation.from_quat(q[0]).as_matrix(),(len(times),3,3))
    tt=times.clip(grid[0],grid[-1]);return (np.column_stack([np.interp(tt,grid,c) for c in pos.T]),
                                           Slerp(grid,Rotation.from_quat(q))(tt).as_matrix())


def check(view):
    data=view/'data'; human=view/'human_v5'; manifest=json.loads((data/'wgm_manifest.json').read_text())
    targets=json.loads((HERE/'plate_targets.json').read_text()); source=json.loads((HERE/'scene_plate_source.json').read_text())
    assert manifest['plateOverlays']==targets and set(manifest['clips'])-set(manifest.get('machineOverlays', {}))==set(targets)|set(wire.build.STAGE1)
    with Image.open(data/'plate_faces.webp') as texture, Image.open(HERE.parents[1]/'promo/parts/detail_gym_freeweight/plate_faces.png') as ref:
        assert texture.size==ref.size and np.array_equal(np.asarray(ref),np.asarray(texture))
    base=json.loads((human/'base.json').read_text());faces=np.asarray(base['triangles']).reshape(-1,3);assert base['vertices']==1401
    uv=[]; parts=wire.read_parts(data/'parts.bin',uvs=uv);seen=set(); counts=Counter(); report=[]
    for model, targets_by_index in targets.items():
        raw=json.loads((data/f'{model}.json').read_text());acts,rows=wire.read_clip(data/f'{model}.wgm',parts)
        assert np.array_equal(acts,np.asarray(raw['acts'],'<f4')) and len(rows)==2*len(targets_by_index)
        path=human/f'{model}.bin';h=wire.build.load_wgp2_human_frames(path);ht=np.frombuffer(path.read_bytes(),'<f4',len(h),40)
        keys=np.unique(np.r_[acts, ht]);t=np.unique(np.r_[keys,(keys[:-1]+keys[1:])/2]);j=np.searchsorted(ht,t,side='right').clip(1,len(ht)-1);w=((t-ht[j-1])/(ht[j]-ht[j-1])).clip(0,1)
        skin=h[j-1]+w[:,None,None]*(h[j]-h[j-1]);center=skin[:,faces].mean(2); edges=np.unique(np.sort(np.vstack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
        samples=np.concatenate((skin,center,(skin[:,edges[:,0]]+skin[:,edges[:,1]])/2),axis=1)
        for i,(idx,name) in enumerate(targets_by_index.items()):
            o=raw['objects'][int(idx)];assert o['name']==name
            body,hub=rows[2*i:2*i+2]; key,_,_,_=fit(o,source);counts[key]+=1
            for slot,r in enumerate((body,hub)):
                v,tri=parts[r['pid']]; ref=source[key][slot]
                assert np.array_equal(tri.flatten(),ref['t']) and np.max(abs(v-ref['v']))<.000006
                assert r['mat']==(MAT_CHROME if slot else MAT_PLATE_FACE)
                if slot==0: assert np.array_equal(uv[r['pid']],np.rint(np.asarray(ref['uv'])*65535))
                seen.add(r['pid'])
            for field in ('pos','quat','scale'):assert np.array_equal(body[field],hub[field])
            s=body['scale'];assert np.all(s>0) and np.allclose(s,s[0,0])
            m=wire.build.strip_fake_animation(o['m']);assert len(m)==body['nf'];oldpos,oldq,ss=wire.build.decompose_frames(m)
            v=np.asarray(o['verts']).reshape(-1,3);ctr=(v.min(0)+v.max(0))/2; world=np.asarray(m).reshape(-1,4,4); expected=ctr @ world[:,:3,:3]+world[:,3,:3]
            err=np.linalg.norm(body['pos']-expected,axis=1).max();assert err<.00012
            dims=np.ptp(v,axis=0)*ss[0];ax=dims.argmin(); axis=world[:,ax,:3]/ss[:,ax,None]
            got=Rotation.from_quat(body['quat']).as_matrix()[:,:,2]; assert np.linalg.norm(got-axis,axis=1).max()<.00011
            orig=Solid((v-ctr)*ss[0],np.asarray(o['tris']).reshape(-1,3)); solids=[Solid(parts[r['pid']][0]*s[0],parts[r['pid']][1]) for r in (body,hub)]
            grid=acts if len(m)==len(acts) else np.linspace(0,1,len(m));op,orr=tracks(oldpos,oldq,grid,t); np_,nr=tracks(body['pos'],body['quat'],grid,t)
            op=op+(orr@(ctr*ss[0]))
            radius=max(np.linalg.norm((v-ctr)*ss[0],axis=1).max(),*(np.linalg.norm(parts[r['pid']][0]*s[0],axis=1).max() for r in (body,hub)))+.001
            prev=after=increase=0.
            for f,pts in enumerate(samples):
                x=pts[(abs(pts-np_[f])<radius).all(1)]
                if not len(x):continue
                old=orig.depth(np.einsum('ij,jk->ik',x-op[f],orr[f]));local=np.einsum('ij,jk->ik',x-np_[f],nr[f]);new=np.maximum(solids[0].depth(local),solids[1].depth(local))
                prev=max(prev,old.max());after=max(after,new.max());increase=max(increase,(new-old).max())
            report.append(dict(clip=model,name=name,type=key,n=body['nf'],samples=len(t),center_mm=err*1000,old_mm=prev*1000,new_mm=after*1000,added_mm=increase*1000,old_tris=len(o['tris'])//3))
    print(f'{len(report)} plates, {len(targets)} clips, {len(seen)} catalogue parts, {dict(counts)}')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('view',type=Path);p.add_argument('--report',type=Path);a=p.parse_args();result=check(a.view)
    if a.report:a.report.write_text(json.dumps(result,indent=2)+'\n')
    for field in ['center_mm','old_mm','new_mm','added_mm']:
        row=max(result,key=lambda r:r[field]);print(field,round(row[field],4),row['clip'],row['name'])
