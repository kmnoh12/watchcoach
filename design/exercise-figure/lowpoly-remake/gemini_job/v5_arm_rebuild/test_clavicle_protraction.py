import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from clavicle_protraction import protract

class ClavicleProtractionTests(unittest.TestCase):
 def test_rest_is_exact_even_when_original_rest_arm_points_partly_forward(self):
  ref=np.array([.4,-.15,-1.]);c=np.array([0.,0,1.]);s=np.array([.15,.01,1.])
  out,a=protract(c,s,ref,ref,np.eye(3),10,'l');np.testing.assert_array_equal(out,s);self.assertEqual(a,0)
 def test_clavicle_length_and_attachment_are_preserved(self):
  c=np.array([0.,0,1.]);s=np.array([.15,0,1.]);out,a=protract(c,s,[0,-1,0],[0,0,-1],np.eye(3),10,'l')
  self.assertAlmostEqual(np.linalg.norm(out-c),np.linalg.norm(s-c),places=14);self.assertAlmostEqual(a,10);self.assertLess(out[1],0)
 def test_rigid_world_motion_is_covariant(self):
  c=np.array([0.,0,1.]);s=np.array([.15,0,1.]);upper=np.array([0.,-.8,-.6]);ref=np.array([0.,0,-1.]);r=Rotation.from_rotvec([.4,.8,-.2]).as_matrix();t=np.array([.3,-.4,.2])
  out,a=protract(c,s,upper,ref,np.eye(3),10,'l');moved,b=protract(r@c+t,r@s+t,r@upper,ref,r,10,'l');np.testing.assert_allclose(moved,r@out+t,atol=1e-14);self.assertAlmostEqual(a,b)
 def test_rigidly_rotated_rest_does_not_activate(self):
  ref=np.array([.4,-.15,-1.]);r=Rotation.from_rotvec([.4,.8,-.2]).as_matrix();s=np.array([.15,0,1.]);out,a=protract([0,0,0],r@s,r@ref,ref,r,10,'l');np.testing.assert_array_equal(out,r@s);self.assertEqual(a,0)
 def test_mirrored_shoulders_move_forward_symmetrically(self):
  l,a=protract([0,0,1],[.15,0,1],[0,-1,0],[0,0,-1],np.eye(3),10,'l');r,b=protract([0,0,1],[-.15,0,1],[0,-1,0],[0,0,-1],np.eye(3),10,'r');np.testing.assert_allclose(l*[-1,1,1],r,atol=1e-14);self.assertEqual(a,b)
 def test_backward_arm_and_zero_strength_leave_shoulder_exact(self):
  s=np.array([.15,0,1.])
  for upper,strength in [([0,1,0],10),([0,-1,0],0)]:
   out,a=protract([0,0,1],s,upper,[0,0,-1],np.eye(3),strength,'l');np.testing.assert_array_equal(out,s);self.assertEqual(a,0)

if __name__=='__main__':unittest.main()
