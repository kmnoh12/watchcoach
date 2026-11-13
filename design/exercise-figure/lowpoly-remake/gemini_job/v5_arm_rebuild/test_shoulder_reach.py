import unittest
import numpy as np
from kinematics import PoseError, shoulder_arm


class ShoulderReachTests(unittest.TestCase):
    def check_lengths(self, c, original, w, s, e, a=.325, b=.288):
        self.assertAlmostEqual(np.linalg.norm(s-c), np.linalg.norm(original-c), places=8)
        self.assertAlmostEqual(np.linalg.norm(e-s), a, places=8)
        self.assertAlmostEqual(np.linalg.norm(w-e), b, places=8)

    def test_feasible_shoulder_stays_exactly_fixed(self):
        c=np.zeros(3); original=np.array([.15,0,0]); w=np.array([.4,0,-.3])
        s,e,_=shoulder_arm(c,original,w,.325,.288,[0,1,0])
        np.testing.assert_array_equal(s,original)
        self.check_lengths(c,original,w,s,e)

    def test_extra_reach_rotates_clavicle_without_stretching(self):
        c=np.zeros(3); original=np.array([.15,0,0]); w=np.array([.15,0,-.64])
        s,e,_=shoulder_arm(c,original,w,.325,.288,[0,1,0])
        self.check_lengths(c,original,w,s,e)
        self.assertGreater(np.linalg.norm(s-original),.02)
        self.assertLess(np.linalg.norm(s-original),.04)

    def test_too_distant_grip_is_rejected(self):
        with self.assertRaises(PoseError):
            shoulder_arm([0,0,0],[.15,0,0],[0,0,-1],.325,.288,[0,1,0])

    def test_folded_inner_limit_can_move_shoulder(self):
        c=np.zeros(3); original=np.array([.15,0,0]); w=np.array([.15,0,0])
        s,e,_=shoulder_arm(c,original,w,.325,.288,[0,1,0])
        self.check_lengths(c,original,w,s,e)

    def test_axial_singularity_and_mirror_have_finite_solutions(self):
        for sign in [-1,1]:
            c=np.zeros(3); original=np.array([-.15*sign,0,0]);w=np.array([.5*sign,0,0])
            # Force reach beyond the fixed arm with a collinear shoulder.
            s,e,_=shoulder_arm(c,original,w,.3,.29,[sign,0,0])
            self.check_lengths(c,original,w,s,e,.3,.29)
            self.assertTrue(np.isfinite(s).all() and np.isfinite(e).all())

    def test_input_vectors_are_preserved(self):
        values=[np.array(v,dtype=float) for v in [[0,0,0],[.15,0,0],[.15,0,-.64],[0,1,0]]]
        copies=[x.copy() for x in values]
        shoulder_arm(*values[:3],.325,.288,values[3])
        for actual,expected in zip(values,copies):np.testing.assert_array_equal(actual,expected)


if __name__=='__main__':unittest.main()
