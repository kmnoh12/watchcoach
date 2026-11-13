"""Geometry-only QA for topology repair; no changes to the original asset."""
import bpy,json,sys,numpy as np
from pathlib import Path
D=Path(__file__).resolve().parent;x=json.loads((D/'working_rest.json').read_text());V=np.array(x['verts']);T=np.array(x['tris']);bpy.ops.wm.read_factory_settings(use_empty=True)
me=bpy.data.meshes.new('V5_Working_Rest');me.from_pydata(V.tolist(),[],T.tolist());me.update();ob=bpy.data.objects.new('V5_Working_Rest',me);bpy.context.scene.collection.objects.link(ob);mat=bpy.data.materials.new('Diagnostic_Clay');mat.diffuse_color=(.6,.66,.69,1);me.materials.append(mat)
sys.path.insert(0,'/Users/kmnoh/.agents/skills/blender-asset-qa/scripts');import qa_check,review_shots
qa=qa_check.run(objects=[ob.name],profile='game',uv=False);qa['scope']='Geometry-only intermediary mesh. Original rest vertices/weights retained; no textured or posed delivery approval.';(D/'working_rest_qa.json').write_text(json.dumps(qa,indent=2));assert qa['pass'],qa['errors']
review_shots.run(objects=[ob.name],out=str(D/'working_rest_solid.png'),views=['front','right'],mode='solid',res=384);review_shots.run(objects=[ob.name],out=str(D/'working_rest_wire.png'),views=['front','right'],mode='wire',res=384)
print('GEOMETRY_QA',json.dumps(qa))
