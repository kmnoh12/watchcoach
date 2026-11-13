from pathlib import Path
import json,unittest
import numpy as np
from front_biceps_visual import correct
D=Path(__file__).resolve().parent

class FrontBicepsVisualTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  b=json.loads((D/'guide_suite/base.json').read_text());cls.V=np.array(b['rest']).reshape(-1,3);cls.J=np.array(b['joints']);cls.W=np.array(b['weights']);cls.names=b['bone_names'];cls.R=np.array(json.loads((D/'anatomical_rest.json').read_text())['rest_matrices']);cls.P=np.fromfile(D/'guide_suite/flat_bench_press.positions.bin',dtype='<f4').reshape(-1,len(cls.V),3);cls.S=np.fromfile(D/'guide_suite/flat_bench_press.skin.bin',dtype='<f4').reshape(-1,len(cls.names),4,4)
 def apply(self,frame=32):return correct(self.V,self.P[frame],self.J,self.W,self.names,self.R,self.S[frame])
 def test_rest_is_exact_and_folded_relief_preserves_belly(self):
  identity=np.tile(np.eye(4),(len(self.names),1,1));q,_,_=correct(self.V,self.V,self.J,self.W,self.names,self.R,identity);np.testing.assert_array_equal(q,self.V)
  q,_,_=self.apply(0);delta=np.linalg.norm(q-self.P[0],axis=1)
  self.assertGreater(delta[138],delta[142]*2)
  self.assertLess(delta[142],.007)
  self.assertLessEqual(np.count_nonzero(delta>1e-10),6)
 def test_axilla_relief_preserves_the_biceps_belly(self):
  q,_,_=self.apply();delta=np.linalg.norm(q-self.P[32],axis=1)
  self.assertGreater(delta[138],.040)
  self.assertGreater(delta[118],.010)
  self.assertGreater(delta[142],.025)
  self.assertLess(delta[142],.035)
  self.assertLess(delta[178],.003)
 def test_relief_presses_the_surface_inward_without_shifting_along_bone(self):
  q,_,_=self.apply();u=self.names.index('upperarm_l');l=self.names.index('lowerarm_l');axis=self.R[l,:3,3]-self.R[u,:3,3];axis/=np.linalg.norm(axis)
  delta=(q[142]-self.P[32,142])@self.S[32,u,:3,:3]
  radial=self.V[142]-self.R[u,:3,3];radial-=axis*(radial@axis)
  self.assertLess(delta@radial,0);self.assertGreater(delta[1],0);self.assertLess(abs(delta@axis),1e-7)
 def test_rest_of_body_and_rear_shoulder_are_exact(self):
  q,f,_=self.apply();np.testing.assert_array_equal(q[f==0],self.P[32,f==0]);self.assertLessEqual(np.count_nonzero(f),10)
  for v in [135,147,152]:np.testing.assert_array_equal(q[v],self.P[32,v])
 def test_input_is_not_mutated(self):
  p=self.P.copy();v=self.V.copy();self.apply();np.testing.assert_array_equal(p,self.P);np.testing.assert_array_equal(v,self.V)
 def test_overhead_extension_also_relaxes_the_biceps_peak(self):
  p=np.fromfile(D/'guide_overhead/barbell_overhead_press.positions.bin',dtype='<f4').reshape(-1,len(self.V),3)
  s=np.fromfile(D/'guide_overhead/barbell_overhead_press.skin.bin',dtype='<f4').reshape(-1,len(self.names),4,4)
  q,_,rows=correct(self.V,p[-1],self.J,self.W,self.names,self.R,s[-1])
  self.assertGreater(min(r['activation'] for r in rows),.9)
  self.assertGreater(np.linalg.norm(q[138]-p[-1,138]),.030)
  self.assertLess(np.linalg.norm(q[142]-p[-1,142]),np.linalg.norm(q[138]-p[-1,138]))

if __name__=='__main__':unittest.main()
