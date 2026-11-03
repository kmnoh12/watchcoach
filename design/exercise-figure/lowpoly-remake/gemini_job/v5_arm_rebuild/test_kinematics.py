import math,unittest
import numpy as np
from kinematics import PoseError,two_bone,swing,rigid_rotation,continuous_twist
class ArmBoundaryTests(unittest.TestCase):
 def assert_lengths(self,s,w,a,b,e):
  self.assertAlmostEqual(np.linalg.norm(e-s),a,places=8);self.assertAlmostEqual(np.linalg.norm(w-e),b,places=8)
 def test_normal_elbow_sweep_keeps_original_lengths(self):
  for d in np.linspace(.08,.609,150):
   s=np.array([.1,.2,.3]);w=s+[d,0,0];e,_=two_bone(s,w,.337,.273,[0,1,0]);self.assert_lengths(s,w,.337,.273,e)
 def test_fully_straight_overhead_is_valid(self):
  s=np.zeros(3);w=np.array([0,0,.61]);e,_=two_bone(s,w,.337,.273,[0,0,1],previous_pole=[1,0,0]);self.assert_lengths(s,w,.337,.273,e)
 def test_fully_folded_boundary_is_valid(self):
  s=np.zeros(3);w=np.array([.064,0,0]);e,_=two_bone(s,w,.337,.273,[0,1,0]);self.assert_lengths(s,w,.337,.273,e)
 def test_unreachable_grip_does_not_stretch(self):
  with self.assertRaises(PoseError):two_bone([0,0,0],[0,0,.8],.337,.273,[0,1,0])
 def test_caller_pole_is_not_mutated(self):
  pole=np.array([1.,1.,0.]);original=pole.copy();two_bone([0,0,0],[.5,0,0],.337,.273,pole);np.testing.assert_array_equal(pole,original)
 def test_parallel_pole_uses_previous_plane(self):
  e,p=two_bone([0,0,0],[.5,0,0],.337,.273,[1,0,0],[0,1,0]);self.assertGreater(e[1],0);np.testing.assert_allclose(p,[0,1,0],atol=1e-10)
 def test_antiparallel_swing_does_not_reflect_or_scale(self):
  r=swing([0,1,0],[0,-1,0],[1,0,0]);np.testing.assert_allclose(r@[0,1,0],[0,-1,0],atol=1e-9);self.assertAlmostEqual(np.linalg.det(r),1);np.testing.assert_allclose(r.T@r,np.eye(3),atol=1e-9)
 def test_twist_crosses_branch_and_reverses_without_flip(self):
  values=list(np.linspace(150,210,61))+list(np.linspace(210,150,61));previous=None;actual=[]
  for deg in values:
   angle,held=continuous_twist([0,0,1],[1,0,0],[math.cos(math.radians(deg)),math.sin(math.radians(deg)),0],previous);self.assertFalse(held);actual.append(math.degrees(angle));previous=angle
  np.testing.assert_allclose(actual,values,atol=1e-8)
 def test_singular_palm_holds_previous_and_flags(self):
  angle,held=continuous_twist([0,0,1],[1,0,0],[0,0,1],.7);self.assertTrue(held);self.assertEqual(angle,.7)
 def test_scale_and_reflection_are_rejected(self):
  for m in [np.diag([1,1.12,1]),np.diag([-1,1,1]),np.zeros((3,3))]:
   with self.assertRaises(PoseError):rigid_rotation(m)
 def test_nonfinite_pose_is_rejected(self):
  with self.assertRaises(PoseError):two_bone([0,0,0],[0,float('nan'),0],.3,.3,[1,0,0])
if __name__=='__main__':unittest.main()
