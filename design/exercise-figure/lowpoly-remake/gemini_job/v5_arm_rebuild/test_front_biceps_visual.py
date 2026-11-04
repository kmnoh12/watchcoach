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
 def test_rest_and_deep_bent_pose_are_exact(self):
  identity=np.tile(np.eye(4),(len(self.names),1,1));q,_,_=correct(self.V,self.V,self.J,self.W,self.names,self.R,identity);np.testing.assert_array_equal(q,self.V)
  q,_,_=self.apply(0);np.testing.assert_array_equal(q,self.P[0])
 def test_actual_visible_peak_moves_twenty_mm(self):
  q,_,_=self.apply();self.assertAlmostEqual(np.linalg.norm(q[142]-self.P[32,142]),.020,places=7)
 def test_relief_is_outward_from_chest_and_keeps_front_thickness(self):
  q,_,_=self.apply();u=self.names.index('upperarm_l');l=self.names.index('lowerarm_l');axis=self.R[l,:3,3]-self.R[u,:3,3];axis/=np.linalg.norm(axis)
  delta=(q[142]-self.P[32,142])@self.S[32,u,:3,:3]
  self.assertGreater(delta[0],0);self.assertLess(abs(delta[1]),.0005);self.assertLess(abs(delta@axis),1e-7)
 def test_rest_of_body_and_rear_shoulder_are_exact(self):
  q,f,_=self.apply();np.testing.assert_array_equal(q[f==0],self.P[32,f==0]);self.assertLessEqual(np.count_nonzero(f),10)
  for v in [135,147,152]:np.testing.assert_array_equal(q[v],self.P[32,v])
 def test_input_is_not_mutated(self):
  p=self.P.copy();v=self.V.copy();self.apply();np.testing.assert_array_equal(p,self.P);np.testing.assert_array_equal(v,self.V)

if __name__=='__main__':unittest.main()
