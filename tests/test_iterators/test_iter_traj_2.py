import unittest
import pytraj as pt
from pytraj.base import *
from pytraj import io as mdio
from pytraj.utils.check_and_assert import assert_almost_equal


class Test(unittest.TestCase):
    def test_0(self):
        traj = mdio.iterload("./data/md1_prod.Tc5b.x", "./data/Tc5b.top")

        start, stop, stride = 0, 8, 2
        indices = list(range(start, stop, stride))

        flist = []
        count = 0

        for i, frame in enumerate(traj[:stop + 1]):
            count += 1
            if i in indices:
                flist.append(frame)
            if i > stop:
                traj.end_traj()

        #print(traj[stop, 0])
        #print(traj[-1, 0])
        #print(count)

    def test_1(self):
        traj = mdio.iterload("./data/md1_prod.Tc5b.x", "./data/Tc5b.top")
        count = 0
        for farray in traj.iterchunk(chunksize=4):
            count += 1
            #print(farray)
            #print("count = %s" % count)

    def test_2(self):
        from pytraj import iterframe_master as frame_iter
        #print("test frame_iter for both pytraj/cpptraj Traj objects")
        traj = mdio.iterload("./data/md1_prod.Tc5b.x", "./data/Tc5b.top")
        farray = traj[:]
        #print(traj.n_frames)
        count = 0
        for frame in frame_iter(traj):
            count += 1
        #print("count = %s" % count)
        assert_almost_equal(frame.xyz, traj[-1].xyz)

        count = 0
        for frame in frame_iter(farray):
            count += 1
        #print("count = %s" % count)
        assert_almost_equal(frame.xyz, traj[-1].xyz)

    def test_3(self):
        from pytraj import iterframe_master as frame_iter
        #print("test frame_iter for both pytraj/cpptraj Traj objects")
        traj = mdio.iterload("./data/md1_prod.Tc5b.x", "./data/Tc5b.top")

        count = 0
        for frame in traj.iterframe():
            count += 1
        #print("count = %s" % count)
        assert_almost_equal(frame.xyz, traj[-1].xyz)

        count = 0
        for frame in traj.iterframe(2, 8, 2):
            count += 1
        #print("count = %s" % count)
        assert count == 3
        assert_almost_equal(frame.xyz, traj[6].xyz)

        count = 0
        for frame in traj[:].iterframe():
            count += 1
        #print("count = %s" % count)
        assert_almost_equal(frame.xyz, traj[-1].xyz)


if __name__ == "__main__":
    unittest.main()