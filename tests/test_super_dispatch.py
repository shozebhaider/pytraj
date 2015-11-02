#!/usr/bin/env python

from __future__ import print_function
import unittest
import pytraj as pt
from pytraj.utils import eq, aa_eq
from pytraj._get_common_objects import _super_dispatch
from pytraj.externals.six import string_types

class TestSuperDispatch(unittest.TestCase):
    def setUp(self):
        self.traj = pt.iterload("./data/tz2.nc", "./data/tz2.parm7")

    def test_naive(self):
        # make sure to convert int to Frame
        def func_convert_ref(traj, ref=0, top=None):
            assert isinstance(ref, pt.Frame)
        func = _super_dispatch(func_convert_ref)
        func(self.traj, ref=-2)

        # make sure to insert correct Topology
        def func_convert_top(traj, top=None):
            assert isinstance(top, pt.Topology)
        func = _super_dispatch(func_convert_top)
        func(self.traj, top=None)

        # make sure to convert array to Amber mask
        def func_convert_mask_array(traj, top=None, mask=None):
            assert isinstance(mask, string_types)
        func = _super_dispatch(func_convert_mask_array)
        func(self.traj, mask=[0, 3, 7])

    def test_super_dispatch(self):
        traj = pt.iterload("./data/tz2.nc", "./data/tz2.parm7")

        funclist = [pt.radgyr, pt.molsurf]
        for func in funclist:
            mask = '@CA'
            atom_indices = pt.select_atoms(traj.top, mask)
            # mask
            aa_eq(func(traj, mask=mask),
                  func(traj, mask=atom_indices))

            # frame_indices with mask
            frame_indices = [0, 5, 8]
            aa_eq(func(traj[frame_indices], mask=mask),
                  func(traj, mask=atom_indices, frame_indices=frame_indices))


if __name__ == "__main__":
    unittest.main()
