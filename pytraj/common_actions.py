from __future__ import absolute_import
import os
import numpy as np

from pytraj.action_dict import ActionDict
adict = ActionDict()

from pytraj.analysis_dict import AnalysisDict
analdict = AnalysisDict()

from pytraj.api import Trajectory
from ._get_common_objects import _get_topology, _get_data_from_dtype, _get_list_of_commands
from ._get_common_objects import _get_matrix_from_dataset
from ._get_common_objects import _get_reference_from_traj, _get_fiterator
from pytraj.core.ActionList import ActionList
from .utils import is_array, ensure_not_none_or_string
from .utils import is_int
from .utils.context import goto_temp_folder
from .utils.convert import array_to_cpptraj_atommask as array_to_cpptraj_atommask
from .externals.six import string_types
from .Frame import Frame
from .Topology import Topology
from .datasets.DatasetList import DatasetList as CpptrajDatasetList
from .datafiles import DataFileList
from .datasetlist import DatasetList
from .hbonds import search_hbonds, search_hbonds_nointramol
from .dssp_analysis import calc_dssp
from ._nastruct import nastruct
from ._shared_methods import iterframe_master
from .externals.get_pysander_energies import get_pysander_energies
from .decorators import noparallel, _register_pmap, _register_openmp
from .actions import CpptrajActions
from .analyses import CpptrajAnalyses
from .core.ActionList import ActionList

list_of_cal = ['calc_distance',
               'calc_dihedral',
               'calc_radgyr',
               'calc_angle',
               'calc_molsurf',
               'calc_volume',
               'calc_dssp',
               'calc_matrix',
               'calc_jcoupling',
               'calc_watershell',
               'calc_vector',
               'calc_multivector',
               'calc_volmap',
               'calc_rdf',
               'calc_pairdist',
               'calc_multidihedral',
               'calc_atomicfluct',
               'calc_COM',
               'calc_center_of_mass',
               'calc_center_of_geometry',
               'calc_pairwise_rmsd',
               'calc_density',
               'calc_grid',
               'calc_temperatures',
               'calc_linear_interaction_energy', ]

list_of_do = ['do_translation',
              'do_rotation',
              'do_autoimage',
              'do_clustering', ]

list_of_get = ['get_average_frame']

list_of_the_rest = ['search_hbonds', 'search_hbonds_nointramol',
                    'align_principal_axis', 'principal_axes', 'closest',
                    'native_contacts', 'nastruct']

__all__ = list_of_do + list_of_cal + list_of_get + list_of_the_rest

calc_energies = get_pysander_energies
energy_decomposition = get_pysander_energies


def _2darray_to_atommask_groups(seq):
    '''[[0, 3], [4, 7]] turns to ['@1 @4', '@5 @8']
    '''
    for arr in seq:
        # example: arr = [0, 3]; turns ot '@1 @4'
        yield '@' + str(arr[0] + 1) + ' @' + str(arr[1] + 1)


def _noaction_with_TrajectoryIterator(trajiter):
    from pytraj import TrajectoryIterator
    if isinstance(trajiter, TrajectoryIterator):
        raise ValueError(
            "This analysis does not support immutable object. Use `pytraj.Trajectory`")


@_register_pmap
def calc_distance(traj=None,
                  mask="",
                  frame_indices=None,
                  dtype='ndarray',
                  top=None,
                  n_frames=None):
    """calculate distance between two maskes

    Parameters
    ----------
    traj : Trajectory-like, list of Trajectory, list of Frames
    mask : str or a list of string or a 2D array-like of integers
    frame_indices : array-like, optional, default None
    top : Topology, optional
    dtype : return type, default 'ndarray'
    n_frames : int, optional, default None
        only need to provide n_frames if ``traj`` does not have this info

    Returns
    -------
    1D ndarray if mask is a string
    2D ndarray, shape (n_atom_pairs, n_frames) if mask is a list of strings or an array

    Examples
    --------
    >>> import pytraj as pt
    >>> # calculate distance for two atoms, using amber mask
    >>> pt.distance(traj, '@1 @3')

    >>> # calculate distance for two groups of atoms, using amber mask
    >>> pt.distance(traj, '@1,37,8 @2,4,6')

    >>> # calculate distance between two residues, using amber mask
    >>> pt.distance(traj, ':1 :10')

    >>> # calculate multiple distances between two residues, using amber mask
    >>> # distance between residue 1 and 10, distance between residue 3 and 20 
    >>> # (when using atom string mask, index starts from 1)
    >>> pt.distance(traj, [':1 :10', ':3 :20'])

    >>> # calculate distance for a series of atoms, using array for atom mask
    >>> # distance between atom 1 and 5, distance between atom 4 and 10 (index starts from 0)
    >>> pt.distance(traj, [[1, 5], [4, 10]])
    """
    ensure_not_none_or_string(traj)
    command = mask

    traj = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)

    cm_arr = np.asarray(command)

    if 'int' in cm_arr.dtype.name:
        from pytraj.datasetlist import from_dict

        int_2darr = cm_arr

        if int_2darr.ndim == 1:
            int_2darr = np.atleast_2d(cm_arr)

        if int_2darr.shape[1] != 2:
            raise ValueError("require int-array with shape=(n_atoms, 2)")

        if n_frames is None:
            try:
                n_frames = traj.n_frames
            except:
                raise ValueError("require specifying n_frames")

        arr = np.empty([n_frames, len(int_2darr)])

        for idx, frame in enumerate(iterframe_master(traj)):
            arr[idx] = frame.calc_distance(int_2darr)

        arr = arr.T
        if dtype == 'ndarray':
            return arr
        else:
            py_dslist = from_dict({'distance': arr})
            return _get_data_from_dtype(py_dslist, dtype)

    elif isinstance(command, (list, tuple, string_types, np.ndarray)):
        # create a list
        if not isinstance(command, np.ndarray):
            list_of_commands = _get_list_of_commands(command)
        else:
            list_of_commands = command

        dslist = CpptrajDatasetList()
        actlist = ActionList()

        for cm in list_of_commands:
            actlist.add_action(
                CpptrajActions.Action_Distance(), cm, _top,
                dslist=dslist)
        actlist.do_actions(traj)
        return _get_data_from_dtype(dslist, dtype)

    else:
        raise ValueError(
            "command must be a string, a list/tuple of strings, or "
            "a numpy 2D array")


def calc_pairwise_distance(traj=None,
                           mask_1='',
                           mask_2='',
                           top=None,
                           dtype='ndarray',
                           frame_indices=None):
    '''calculate pairwise distance between atoms in mask_1 and atoms in mask_2

    Parameters
    ----------
    traj : Trajectory-like or iterable that produces Frame
    mask_1: string or 1D array-like
    mask_2: string or 1D array-like
    ...

    Returns
    -------
    out_1 : numpy array, shape (n_frames, n_atom_1, n_atom_2)
    out_2 : atom pairs, shape=(n_atom_1, n_atom_2, 2)

    Notes
    -----
    This method is only fast for small number of atoms.
    '''
    from itertools import product

    _top = _get_topology(traj, top)
    indices_1 = _top.select(mask_1) if isinstance(mask_1,
                                                  string_types) else mask_1
    indices_2 = _top.select(mask_2) if isinstance(mask_2,
                                                  string_types) else mask_2
    arr = np.array(list(product(indices_1, indices_2)))
    mat = calc_distance(traj,
                         mask=arr,
                         dtype=dtype,
                         top=_top,
                         frame_indices=frame_indices)
    mat = mat.T
    return (mat.reshape(mat.shape[0], len(indices_1), len(indices_2)),
            arr.reshape(len(indices_1), len(indices_2), 2))

@_register_pmap
def calc_angle(traj=None,
               mask="",
               top=None,
               dtype='ndarray',
               frame_indices=None, *args, **kwd):
    """calculate angle between two maskes

    Parameters
    ----------
    traj : Trajectory-like, list of Trajectory, list of Frames
    mask : str or array
    top : Topology, optional
    dtype : return type, defaul 'ndarray'

    Returns
    -------
    1D ndarray if mask is a string
    2D ndarray, shape (n_atom_pairs, n_frames) if mask is a list of strings or an array

    Examples
    --------
    >>> import pytraj as pt
    >>> # calculate angle for three atoms, using amber mask
    >>> pt.angle(traj, '@1 @3 @10')

    >>> # calculate angle for three groups of atoms, using amber mask
    >>> pt.angle(traj, '@1,37,8 @2,4,6 @5,20')

    >>> # calculate angle between three residues, using amber mask
    >>> pt.angle(traj, ':1 :10 :20')

    >>> # calculate multiple angles between three residues, using amber mask
    >>> # angle between residue 1, 10, 20, angle between residue 3, 20, 30
    >>> # (when using atom string mask, index starts from 1)
    >>> pt.angle(traj, [':1 :10 :20', ':3 :20 :30'])

    >>> # calculate angle for a series of atoms, using array for atom mask
    >>> # angle between atom 1, 5, 8, distance between atom 4, 10, 20 (index starts from 0)
    >>> pt.angle(traj, [[1, 5, 8], [4, 10, 20]])
    """
    from pytraj.datasetlist import from_dict
    dslist = CpptrajDatasetList()
    act = CpptrajActions.Action_Angle()

    command = mask

    ensure_not_none_or_string(traj)

    traj = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)
    cm_arr = np.asarray(command)

    if 'int' not in cm_arr.dtype.name:
        if isinstance(command, string_types):
            # need to remove 'n_frames' keyword since Action._master does not use
            # it
            try:
                del kwd['n_frames']
            except:
                pass
            # cpptraj mask for action
            act(command, traj, top=_top, dslist=dslist, *args, **kwd)
            return _get_data_from_dtype(dslist, dtype)

        elif isinstance(command, (list, tuple)):
            list_of_commands = command
            from pytraj.core.ActionList import ActionList
            dslist = CpptrajDatasetList()
            actlist = ActionList()

            for cm in list_of_commands:
                actlist.add_action(
                    CpptrajActions.Action_Angle(), cm, _top,
                    dslist=dslist, *args, **kwd)
            actlist.do_actions(traj)
            return _get_data_from_dtype(dslist, dtype)

    else:
        # ndarray of integer
        int_2darr = cm_arr

        if int_2darr.ndim == 1:
            int_2darr = np.atleast_2d(int_2darr)

        if int_2darr.shape[1] != 3:
            raise ValueError("require int-array with shape=(n_atoms, 3)")

        if 'n_frames' not in kwd.keys():
            try:
                n_frames = traj.n_frames
            except:
                raise ValueError("require specifying n_frames")
        else:
            n_frames = kwd['n_frames']
        arr = np.empty([n_frames, len(int_2darr)])
        for idx, frame in enumerate(iterframe_master(traj)):
            arr[idx] = frame.calc_angle(int_2darr)

        arr = arr.T
        if dtype == 'ndarray':
            return arr
        else:
            py_dslist = from_dict({'angle': arr})
            return _get_data_from_dtype(py_dslist, dtype)


def _dihedral_res(traj, mask=(), resid=0, dtype='ndarray', top=None):
    '''calculate dihedral within a single residue. For internal use only.

    Parameters
    ----------
    traj
    mask : tuple of strings
    resid
    dtype
    '''

    if is_int(resid):
        resid = str(resid + 1)
    else:
        resid = resid
    m = ' :%s@' % resid
    command = m + m.join(mask)
    return calc_dihedral(traj=traj, mask=command, top=top, dtype=dtype)


@_register_pmap
def calc_dihedral(traj=None,
                  mask="",
                  top=None,
                  dtype='ndarray',
                  frame_indices=None, *args, **kwd):
    """calculate dihedral angle between two maskes

    Parameters
    ----------
    traj : Trajectory-like, list of Trajectory, list of Frames
    mask : str or array
    top : Topology, optional
    dtype : return type, defaul 'ndarray'

    Returns
    -------
    1D ndarray if mask is a string
    2D ndarray, shape (n_atom_pairs, n_frames) if mask is a list of strings or an array

    Examples
    --------
    >>> import pytraj as pt
    >>> # calculate dihedral angle for four atoms, using amber mask
    >>> pt.dihedral(traj, '@1 @3 @10 @20')

    >>> # calculate dihedral angle for four groups of atoms, using amber mask
    >>> pt.dihedral(traj, '@1,37,8 @2,4,6 @5,20 @21,22')

    >>> # calculate dihedral angle for four residues, using amber mask
    >>> pt.dihedral(traj, ':1 :10 :20 :22')

    >>> # calculate multiple dihedral angles for four residues, using amber mask
    >>> # angle for residue 1, 10, 20, 30; angle between residue 3, 20, 30, 40
    >>> # (when using atom string mask, index starts from 1)
    >>> pt.dihedral(traj, [':1 :10 :20 :30', ':3 :20 :30 :40'])

    >>> # calculate dihedral angle for a series of atoms, using array for atom mask
    >>> # dihedral angle for atom 1, 5, 8, 10, dihedral for atom 4, 10, 20, 30 (index starts from 0)
    >>> pt.dihedral(traj, [[1, 5, 8, 10], [4, 10, 20, 30]])
    """
    act = CpptrajActions.Action_Dihedral()
    dslist = CpptrajDatasetList()

    ensure_not_none_or_string(traj)
    command = mask

    traj = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)
    cm_arr = np.asarray(command)

    if 'int' not in cm_arr.dtype.name:
        if isinstance(command, string_types):
            # need to remove 'n_frames' keyword since Action._master does not use
            # it
            try:
                del kwd['n_frames']
            except:
                pass
            # cpptraj mask for action
            act(command, traj, top=_top, dslist=dslist)
            return _get_data_from_dtype(dslist, dtype)

        elif isinstance(command, (list, tuple)):
            list_of_commands = command
            from pytraj.core.ActionList import ActionList
            from pytraj.actions.CpptrajActions import Action_Dihedral
            dslist = CpptrajDatasetList()
            actlist = ActionList()

            for cm in list_of_commands:
                actlist.add_action(
                    Action_Dihedral(), cm, _top,
                    dslist=dslist, *args, **kwd)
            actlist.do_actions(traj)
            return _get_data_from_dtype(dslist, dtype)
    else:
        # ndarray
        int_2darr = cm_arr

        if int_2darr.ndim == 1:
            int_2darr = np.atleast_2d(int_2darr)

        if int_2darr.shape[1] != 4:
            raise ValueError("require int-array with shape=(n_atoms, 4)")

        if 'n_frames' not in kwd.keys():
            try:
                n_frames = traj.n_frames
            except:
                raise ValueError("require specifying n_frames")
        else:
            n_frames = kwd['n_frames']
        arr = np.empty([n_frames, len(int_2darr)])
        for idx, frame in enumerate(iterframe_master(traj)):
            arr[idx] = frame.calc_dihedral(int_2darr)

        arr = arr.T
        if dtype == 'ndarray':
            return arr
        else:
            from pytraj.datasetlist import from_dict
            py_dslist = from_dict({'dihedral': arr})
            return _get_data_from_dtype(py_dslist, dtype)


@_register_pmap
def calc_mindist(traj=None,
                 command="",
                 top=None,
                 dtype='ndarray',
                 frame_indices=None):
    '''
    Examples
    --------
    >>> import pytraj as pt
    >>> pt.mindist(traj, '@CA @H')
    '''
    from pytraj.actions.CpptrajActions import Action_NativeContacts
    from pytraj.utils.convert import array2d_to_cpptraj_maskgroup

    traj = _get_fiterator(traj, frame_indices)
    act = Action_NativeContacts()
    dslist = CpptrajDatasetList()

    if not isinstance(command, string_types):
        command = array2d_to_cpptraj_maskgroup(command)
    _command = "mindist " + command
    traj = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)
    act(_command, traj, top=_top, dslist=dslist)
    return _get_data_from_dtype(dslist, dtype=dtype)[-1]


def _calc_diffusion(traj=None,
                    mask="*",
                    dimension='xyz',
                    time=1.0,
                    mask2=None,
                    lower=0.01,
                    upper=3.5,
                    distance=False,
                    com=False,
                    frame_indices=None,
                    top=None,
                    dtype='ndarray'):
    '''calcualte diffusion for selected atoms

    Parameters
    ----------
    traj : Trajectory-like or iterable that produces Frame
    mask : str, defaul '*' (all atoms)
    mask2 : str, 2nd mask, optional
    time : time step (ps)
    ...
    '''
    traj = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)

    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)
    else:
        mask = mask

    _mask = 'mask ' + mask
    if mask2 is None:
        _mask2 = ''
    else:
        if not isinstance(mask2, string_types):
            mask2 = array_to_cpptraj_atommask(mask2)
        else:
            mask2 = mask2
        _mask2 = 'mask2 ' + mask2

    _time = 'time ' + str(time)
    _lower = 'lower ' + str(lower)
    _upper = 'upper ' + str(upper)
    _distances = 'distances' if distance else ''
    _com = 'com' if com else ''
    dirlist = ['x', 'y', 'z', 'xy', 'xz', 'yz', 'xyz']

    if dimension not in ['x', 'y', 'z', 'xy', 'xz', 'yz', 'xyz']:
        raise ValueError('direction must be in {0}'.format(str(dirlist)))
    else:
        _dimention = dimension

    act = CpptrajActions.Action_STFC_Diffusion()
    dslist = CpptrajDatasetList()

    command = ' '.join((_mask, _time, _mask2, _lower, _upper, _distances, _com,
                        _dimention))

    act(command, traj, top=_top, dslist=dslist)

    return _get_data_from_dtype(dslist, dtype=dtype)


@_register_pmap
@_register_openmp
def calc_watershell(traj=None,
                    solute_mask=None,
                    solvent_mask=':WAT',
                    lower=3.4,
                    upper=5.0,
                    image=True,
                    dtype='dataset',
                    frame_indices=None,
                    top=None):
    """(adapted from cpptraj doc): Calculate numbers of waters in 1st and 2nd solvation shells
    (defined by <lower cut> (default 3.4 Ang.) and <upper cut> (default 5.0 Ang.)

    Notes
    -----
    This method is not validated with cpptraj's output yet

    Parameters
    ----------
    traj : Trajectory-like
    solute_mask: solute mask
    solvent_mask: solvent mask
    lower : double, default 3.4
        lower cut distance
    upper : double, default 5.0
        upper cut distance
    image : bool, defaul True
        do autoimage if True
    dtype : return type, defaul 'dataset'
    top : Topology, optional

    Examples
    --------
    >>> pt.watershell(traj, solute_mask='!:WAT')
    >>> pt.watershell(traj, solute_mask='!:WAT', lower=5.0, upper=10.)
    """

    traj = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)
    _solutemask = solute_mask if solute_mask is not None else ''
    dslist = CpptrajDatasetList()

    act = CpptrajActions.Action_Watershell()

    if _solutemask in [None, '']:
        raise ValueError('must provide solute mask')

    _solventmask = solvent_mask if solvent_mask is not None else ''
    _noimage = 'noimage' if not image else ''

    _lower = 'lower ' + str(lower)
    _upper = 'upper ' + str(upper)
    command = ' '.join((_solutemask, _lower, _upper, _noimage, _solventmask))

    if not isinstance(command, string_types):
        command = array_to_cpptraj_atommask(command)

    act(command, traj, top=_top, dslist=dslist)
    return _get_data_from_dtype(dslist, dtype=dtype)

def calc_matrix(traj=None,
                command="",
                top=None,
                dtype='ndarray', *args, **kwd):
    from pytraj.actions.CpptrajActions import Action_Matrix
    if not isinstance(command, string_types):
        command = array_to_cpptraj_atommask(command)
    act = Action_Matrix()

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act(command, traj, top=_top, dslist=dslist, *args, **kwd)
    act.print_output()
    return _get_data_from_dtype(dslist, dtype)


@_register_pmap
def calc_radgyr(traj=None,
                mask="",
                top=None,
                nomax=True,
                frame_indices=None,
                dtype='ndarray', *args, **kwd):
    '''calc radgyr

    Examples
    --------
    >>> pt.radgyr(traj, '@CA')
    >>> pt.radgyr(traj, '!:WAT', nomax=False)
    >>> pt.radgyr(traj, '@CA', frame_indices=[2, 4, 6])
    '''
    _traj_iter = _get_fiterator(traj, frame_indices=frame_indices)

    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)

    _nomax = 'nomax' if nomax else ""
    command = " ".join((mask, _nomax))

    act = CpptrajActions.Action_Radgyr()

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act(command, _traj_iter, top=_top, dslist=dslist, *args, **kwd)
    return _get_data_from_dtype(dslist, dtype)


@_register_pmap
def calc_molsurf(traj=None,
                 mask="",
                 probe=1.4,
                 offset=0.0,
                 dtype='ndarray',
                 frame_indices=None,
                 top=None):
    '''calc molsurf

    Examples
    --------
    >>> pt.molsurf(traj, '@CA')
    >>> pt.molsurf(traj, '!:WAT')
    '''
    fi = _get_fiterator(traj, frame_indices)
    _probe = 'probe ' + str(probe)
    _offset = 'offset ' + str(offset) if offset != 0. else ''

    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)
    command = ' '.join((mask, _probe, _offset))

    act = CpptrajActions.Action_Molsurf()

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act(command, fi, top=_top, dslist=dslist)
    return _get_data_from_dtype(dslist, dtype)


@_register_pmap
def calc_rotation_matrix(traj=None,
                         ref=0,
                         mask="",
                         mass=False,
                         frame_indices=None,
                         top=None,
                         with_rmsd=False):
    '''
    Returns
    -------
    out : if with_rmsd=False, return numpy array, shape (n_frames, 3, 3)
          if with_rmsd=True, return a tuple (mat, rmsd)
    '''
    traj = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    ref = _get_reference_from_traj(traj, ref)

    _mass = 'mass' if mass else ''

    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)
    command = ' '.join(('tmp', mask, 'savematrices', _mass))

    act = CpptrajActions.Action_Rmsd()
    act(command, [ref, traj], top=_top, dslist=dslist)
    mat = dslist[-1].values
    # exclude data for reference
    if with_rmsd:
        return mat[1:], np.array(dslist[0].values[1:])
    else:
        return mat[1:]


def calc_volume(traj=None, mask="", top=None, dtype='ndarray', *args, **kwd):
    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)

    command = mask

    act = CpptrajActions.Action_Volume()

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act(command, traj, top=_top, dslist=dslist, *args, **kwd)
    return _get_data_from_dtype(dslist, dtype)


def calc_multivector(traj=None,
                     command="",
                     top=None,
                     dtype='ndarray', *args, **kwd):
    act = CpptrajActions.Action_MultiVector()

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act(command, traj, top=_top, dslist=dslist, *args, **kwd)
    return _get_data_from_dtype(dslist, dtype)


def calc_volmap(traj=None, mask="", top=None, dtype='ndarray', *args, **kwd):
    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)

    command = mask

    act = CpptrajActions.Action_Volmap()

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act(command, traj, top=_top, dslist=dslist, *args, **kwd)
    return _get_data_from_dtype(dslist, dtype)


def calc_linear_interaction_energy(traj=None,
                                   mask="",
                                   top=None,
                                   dtype='dataset',
                                   frame_indices=None, *args, **kwd):
    traj = _get_fiterator(traj, frame_indices)
    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)

    command = mask
    act = CpptrajActions.Action_LIE()

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act(command, traj, top=_top, dslist=dslist, *args, **kwd)
    return _get_data_from_dtype(dslist, dtype)

# alias
calc_LIE = calc_linear_interaction_energy


@_register_openmp
def calc_rdf(traj=None,
             solvent_mask=':WAT@O',
             solute_mask='',
             maximum=10.,
             bin_spacing=0.5,
             image=True,
             density=0.033456,
             center_solvent=False,
             center_solute=False,
             intramol=True,
             frame_indices=None,
             top=None):
    '''compute radial distribtion function. Doc was adapted lightly from cpptraj doc

    Returns
    -------
    a tuple of bin_centers, rdf values

    Parameters
    ----------
    traj : Trajectory-like, require
    solvent_mask : solvent mask, default None, required
    bin_spacing : float, default 0.5, optional
        bin spacing
    maximum : float, default 10., optional
        max bin value
    solute_mask: str, default None, optional
        if specified, calculate RDF of all atoms in solvent_mask to each atom in solute_mask
    image : bool, default True, optional
        if False, do not image distance
    density : float, default 0.033456 molecules / A^3, optional
    volume : determine density for normalization from average volume of input frames
    center_solvent : bool, default False, optional
        if True, calculate RDF from geometric center of atoms in solvent_mask to all atoms in solute_mask
    center_solute : bool, default False, optional
        if True, calculate RDF from geometric center of atoms in solute_mask to all atoms in solvent_mask
    intramol : bool, default True, optional
        if False, ignore intra-molecular distances
    frame_indices : array-like, default None, optional

    Examples
    --------
    >>> import pytraj as pt
    >>> traj = pt.datafiles.load_tz2_ortho()
    >>> data = pt.rdf(traj, solvent_mask=':WAT@O', bin_spacing=0.5, maximum=10.0, solute_mask=':WAT@O')
    >>> data[0]
    array([ 0.25,  0.75,  1.25, ...,  8.75,  9.25,  9.75])
    >>> data[1]
    array([ 0.        ,  0.        ,  0.        , ...,  0.95620052,
            0.95267934,  0.95135242])
    
    Notes
    -----
    - install ``pytraj`` and ``libcpptraj`` with openmp to speed up calculation
    - do not use this method with pytraj.pmap
    '''

    traj = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)

    act = CpptrajActions.Action_Radial()

    if not isinstance(solvent_mask, string_types):
        solvent_mask = array_to_cpptraj_atommask(solvent_mask)

    if not isinstance(solute_mask, string_types) and solute_mask is not None:
        solute_mask = array_to_cpptraj_atommask(solute_mask)

    _spacing = str(bin_spacing)
    _maximum = str(maximum)
    _solventmask = solvent_mask
    _solutemask = solute_mask
    _noimage = 'noimage' if not image else ''
    _density = 'density ' + str(density) if density is not None else ''
    _center1 = 'center1' if center_solvent else ''
    _center2 = 'center2' if center_solute else ''
    _nointramol = 'nointramol' if not intramol else ''

    # order does matters
    # the order between _solventmask and _solutemask is swapped compared
    # to cpptraj's doc (to get correct result)
    command = ' '.join(("pytraj_tmp_output.agr", _spacing, _maximum,
                        _solutemask, _solventmask, _noimage, _density,
                        _center1, _center2, _nointramol))

    dslist = CpptrajDatasetList()
    act(command, traj, top=_top, dslist=dslist)
    act.print_output()

    # make a copy sine dslist[-1].values return view of its data
    # dslist will be freed
    values = np.array(dslist[-1].values)
    # return (bin_centers, values)
    return (np.arange(bin_spacing / 2., maximum, bin_spacing), values)


@noparallel
def calc_pairdist(traj, mask="*", delta=0.1, dtype='ndarray', top=None):
    '''compute pair distribution function

    Parameters
    ----------
    traj : Trajectory-like
    mask : str, default all atoms
    delta : float, default 0.1
    dtype : str, default 'ndarray'
        dtype of return data
    top : Topology, optional
    '''
    with goto_temp_folder():
        _top = _get_topology(traj, top)
        dslist = CpptrajDatasetList()
        act = CpptrajActions.Action_PairDist()

        _mask = 'mask ' + mask
        _delta = 'delta ' + str(delta)
        command = ' '.join((_mask, _delta, 'out tmp_pytraj_out.txt'))

        act(command, traj, top=_top, dslist=dslist)
        act.print_output()

        return _get_data_from_dtype(dslist, dtype=dtype)


pairdist = calc_pairdist


def calc_jcoupling(traj=None,
                   mask="",
                   top=None,
                   kfile=None,
                   dtype='dataset', *args, **kwd):
    """
    Parameters
    ----------
    traj : any things that make `frame_iter_master` returning Frame object
    command : str, default ""
        cpptraj's command/mask
    kfile : str, default None, optional
        Dir for Karplus file. If "None", use $AMBERHOME dir 
    dtype : str, {'dataset', ...}, default 'dataset'
    *args, **kwd: optional
    """
    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)
    command = mask

    act = CpptrajActions.Action_Jcoupling()
    # add `radial` keyword to command (need to check `why`?)
    dslist = CpptrajDatasetList()
    _top = _get_topology(traj, top)

    if kfile is not None:
        command += " kfile %s" % kfile
    act(command, traj, dslist=dslist, top=_top, *args, **kwd)
    return _get_data_from_dtype(dslist, dtype)


def do_translation(traj=None, command="", frame_indices=None, top=None):
    '''
    Examples
    --------
    >>> import pytraj as pt
    >>> # load to mutable trajectory by `load` method
    >>> traj = pt.load('traj.nc', 'myparm.parm7')
    >>> pt.translate(traj, '@CA x 120.')
    '''
    _noaction_with_TrajectoryIterator(traj)

    _top = _get_topology(traj, top)
    fi = _get_fiterator(traj, frame_indices)

    if is_array(command):
        x, y, z = command
        _x = "x " + str(x)
        _y = "y " + str(y)
        _z = "z " + str(z)
        _command = " ".join((_x, _y, _z))
    else:
        _command = command
    CpptrajActions.Action_Translate()(_command, fi, top=_top)


translate = do_translation


def do_scaling(traj=None, command="", frame_indices=None, top=None):
    _noaction_with_TrajectoryIterator(traj)
    _top = _get_topology(traj, top)
    fi = _get_fiterator(traj, frame_indices)
    CpptrajActions.Action_Scale()(command, fi, top=_top)


scale = do_scaling


def do_rotation(traj=None, command="", frame_indices=None, top=None):
    _top = _get_topology(traj, top)
    _noaction_with_TrajectoryIterator(traj)
    fi = _get_fiterator(traj, frame_indices)
    CpptrajActions.Action_Rotate()(command, fi, top=_top)


rotate = do_rotation


def do_autoimage(traj=None, command="", frame_indices=None, top=None):
    '''perform autoimage and return the coordinate-updated traj
    '''
    _noaction_with_TrajectoryIterator(traj)
    _top = _get_topology(traj, top)
    fi = _get_fiterator(traj, frame_indices)

    CpptrajActions.Action_AutoImage()(command, fi, top=_top)
    return traj


autoimage = do_autoimage


@_register_pmap
def mean_structure(traj,
                   mask='',
                   frame_indices=None,
                   restype='frame',
                   autoimage=False,
                   rmsfit=None,
                   top=None):
    '''get mean structure for a given mask and given frame_indices

    Parameters
    ----------
    traj : Trajectory-like or iterable that produces Frame
    mask : None or str, default None (all atoms)
    frame_indices : iterable that produces integer, default None, optional
        frame indices
    restype: str, {'frame', 'traj'}, default 'frame'
        return type, either Frame (does not have Topology information) or 'traj'
    autoimage : bool, default False
        if True, performa autoimage
    rmsfit : object, {Frame, int, tuple, None}, default None
        if rmsfit is not None, perform rms fit to reference.

    Examples
    --------
    >>> import pytraj as pt
    >>> print('get average structure from whole traj, all atoms')
    >>> pt.mean_structure(traj)

    >>> print("get average structure from several frames, '@CA' atoms")
    >>> pt.mean_structure(traj, '@CA', frame_indices=range(2, 8, 2))

    >>> print('get average structure but do autoimage and rmsfit to 1st Frame.')
    >>> pt.mean_structure(traj(autoimage=True, rmsfit=0))

    >>> # get average structure but do autoimage and rmsfit to 1st Frame.
    >>> pt.mean_structure(traj(autoimage=True, rmsfit=0, frame_indices=[0, 5, 6]))

    Notes
    -----
    if autoimage=True and having rmsfit, perform autoimage first and do rmsfit
    '''
    _top = _get_topology(traj, top)
    try:
        fi = traj.iterframe(autoimage=autoimage,
                            rmsfit=rmsfit,
                            frame_indices=frame_indices)
    except AttributeError:
        fi = _get_fiterator(traj, frame_indices)

    dslist = CpptrajDatasetList()
    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)
    else:
        mask = mask

    # add "crdset s1" to trick cpptraj dump coords to DatSetList
    command = mask + " crdset s1"

    act = CpptrajActions.Action_Average()
    act(command, fi, _top, dslist=dslist)

    # need to call this method so cpptraj will write
    act.print_output()

    frame = dslist[0].get_frame()
    if restype.lower() == 'frame':
        return frame
    elif restype.lower() == 'traj':
        new_top = _top if mask is '' else _top[mask]
        return Trajectory(xyz=frame.as_3darray().copy(), top=new_top)


get_average_frame = mean_structure


@_register_pmap
def get_velocity(traj, mask=None, frame_indices=None):
    '''get velocity for specify frames with given mask

    Parameters
    ----------
    traj : Trajectory-like or iterable that produces Frame
    mask : str, default None (use all atoms), optional
        atom mask
    frame_indices : iterable that produces integer, default None, optional
        if not None, only get velocity for given frame indices

    Return
    ------
    out : 3D numpy array, shape (n_frames, n_atoms, 3)
    '''
    if mask is None:
        atm_indices = None
    else:
        if not isinstance(mask, string_types):
            # array-like
            atm_indices = mask
        else:
            atm_indices = traj.top.select(mask)

    fi = traj.iterframe(frame_indices=frame_indices)
    n_atoms = traj.n_atoms if mask is None else len(atm_indices)
    n_frames = fi.n_frames

    data = np.empty((n_frames, n_atoms, 3), dtype='f8')
    for idx, frame in enumerate(fi):
        if not frame.has_velocity():
            raise ValueError('frame does not have velocity')
        data[idx
             ] = frame.velocity if mask is None else frame.velocity[atm_indices
                                                                    ]
    return data


def randomize_ions(traj=None, command="", top=None):
    """randomize_ions for given Frame with Topology

    Parameters
    ----------
    traj : Trajectory-like or a Frame
    top : Topology, optional (only needed if ``traj`` does not have it)

    Notes
    -----
    ``traj`` must be mutable since this method inplace update coordinate

    """
    if not isinstance(command, string_types):
        command = array_to_cpptraj_atommask(command)
    _noaction_with_TrajectoryIterator(traj)
    act = CpptrajActions.Action_RandomizeIons()
    act(command, traj, top)


def clustering_dataset(array_like, command=''):
    '''
    Returns
    -------
    cluster index for each data point

    Examples
    --------
    >>> import pytraj as pt
    >>> import numpy as np 
    >>> array_like = np.random.randint(0, 10, 1000)
    >>> data = pt.clustering_dataset(array_like, 'clusters 10 epsilon 3.0')
    >>> print(data)
    '''
    from pytraj.analyses.CpptrajAnalyses import Analysis_Clustering

    dslist = CpptrajDatasetList()
    dslist.add_set('double', '__array_like')
    dslist[0].resize(len(array_like))
    dslist[0].values[:] = array_like
    act = Analysis_Clustering()
    command = 'data __array_like ' + command
    act(command, dslist=dslist)

    return np.array(dslist[-1])


def do_clustering(traj=None,
                  command="",
                  top=None,
                  dtype='dataset',
                  dslist=None,
                  dflist=None):
    """perform clustering. (outdated)

    Parameters
    ----------
    traj : Trajectory-like | list of Trajectory-like | frame or chunk iterator
    command : cpptraj command
    top : Topology, optional
    dslist : CpptrajDatasetList, optional
    dflist : DataFileList, optional

    Notes:
    Supported algorithms: kmeans, hieragglo, and dbscan.

    Examples
    --------
    >>> do_clustering(traj, "kmeans clusters 50 @CA")

    Returns
    -------
    CpptrajDatasetList object

    """

    _top = _get_topology(traj, top)
    ana = analdict['clustering']
    # need to creat `dslist` here so that every time `do_clustering` is called,
    # we will get a fresh one (or will get segfault)
    if dslist is None:
        dslist = CpptrajDatasetList()
    else:
        dslist = dslist

    if traj is not None:
        dslist.add_set("coords", "__pytraj_cluster")
        #dslist[-1].top = _top
        dslist[0].top = _top
        for frame in traj:
            # dslist[-1].add_frame(frame)
            dslist[0].add_frame(frame)
        command += " crdset __pytraj_cluster"
    else:
        pass
    ana(command, _top, dslist, dflist)
    # remove frames in dslist to save memory
    dslist.remove_set(dslist['__pytraj_cluster'])
    return _get_data_from_dtype(dslist, dtype=dtype)


@_register_pmap
def calc_multidihedral(traj=None,
                       dhtypes=None,
                       resrange=None,
                       define_new_type=None,
                       range360=False,
                       dtype='dataset',
                       top=None, *args, **kwd):
    """perform dihedral search

    Parameters
    ----------
    traj : Trajectory-like object
    dhtypes : dihedral type, default None
        if None, calculate all supported dihedrals
    resrange : str | array-like
        residue range for searching. If `resrange` is string, use index starting with 1
        (cpptraj convertion)
        if `resrange` is array-like, use index starting from 0 (python convention)
    define_new_type : str
        define new type for searching
    range360 : bool, default False
        if True: use 0-360
    top : Topology | str, optional
        only need to have 'top' if can not find it in `traj`
    *arg and **kwd: additional arguments (for advanced users)


    Returns
    -------
    pytraj.DatasetList (use `values` attribute to get raw `numpy` array)

    Notes
    -----
        Dataset lables show residue number in 1-based index

    Examples
    --------
    >>> import pytraj as pt
    >>> pt.multidihedral(traj)
    >>> pt.multidihedral(traj, 'phi psi')
    >>> pt.multidihedral(traj, resrange=range(8))
    >>> pt.multidihedral(traj, range360=True)
    >>> pt.multidihedral(traj, resrange='1,3,5')
    >>> pt.multidihedral(traj, dhtypes='phi psi')
    >>> pt.multidihedral(traj, dhtypes='phi psi', resrange='3-7')
    >>> pt.multidihedral(traj, dhtypes='phi psi', resrange=[3, 4, 8])
    """
    if resrange:
        if is_int(resrange):
            resrange = [resrange, ]
        if isinstance(resrange, string_types):
            _resrange = "resrange " + str(resrange)
        else:
            from pytraj.utils import convert as cv
            _resrange = cv.array_to_cpptraj_range(resrange)
            _resrange = "resrange " + str(_resrange)
    else:
        _resrange = " "

    if dhtypes:
        d_types = str(dhtypes)
    else:
        d_types = " "

    if define_new_type:
        dh_types = ' '.join(('dihtype', str(define_new_type)))
    else:
        dh_types = ''

    if range360:
        _range360 = 'range360'
    else:
        _range360 = ''

    _command = " ".join((d_types, _resrange, dh_types, _range360))

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act = adict['multidihedral']
    act(_command, traj, _top, dslist=dslist, *args, **kwd)
    return _get_data_from_dtype(dslist, dtype=dtype)


def calc_atomicfluct(traj=None,
                     mask="",
                     top=None,
                     dtype='dataset', *args, **kwd):
    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)

    command = mask

    _top = _get_topology(traj, top)

    dslist = CpptrajDatasetList()
    act = adict['atomicfluct']
    act(command, traj, top=_top, dslist=dslist, *args, **kwd)
    # tag: print_output()
    act.print_output()  # need to have this. check cpptraj's code
    return _get_data_from_dtype(dslist, dtype=dtype)


@noparallel
def calc_bfactors(traj=None,
                  mask="",
                  byres=True,
                  top=None,
                  dtype='ndarray', *args, **kwd):
    """
    Returns
    -------
    if dtype is 'ndarray' (default), return a numpy array
    with shape=(n_atoms/n_residues, 2) ([atom_or_residue_idx, value])

    Examples
    --------
    >>> import pytraj as pt
    >>> pt.calc_bfactors(traj, byres=True)
    """
    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)

    byres_text = "byres" if byres else ""

    _command = " ".join((mask, byres_text, "bfactor"))
    return calc_atomicfluct(traj=traj,
                            mask=_command,
                            top=top,
                            dtype=dtype, *args, **kwd)


@_register_pmap
def calc_vector(traj=None,
                command="",
                frame_indices=None,
                dtype='ndarray',
                top=None):
    """perform vector calculation. See example below. Same as 'vector' command in cpptraj.

    Parameters
    ----------
    traj : Trajectory-like or iterable that produces :class:`pytraj.Frame`
    command : str or a list of strings, cpptraj command 
    frame_indices : array-like, optional, default None
        only perform calculation for given frame indices
    dtype : output's dtype, default 'ndarray'
    top : Topology, optional, default None

    Returns
    -------
    out : numpy ndarray, shape (n_frames, 3) if command is a string
          numpy ndarray, shape (n_vectors, n_frames, 3) if command is a list of strings

    Examples
    --------
    >>> import pytraj as pt
    >>> pt.calc_vector(traj, "@CA @CB")
    >>> pt.calc_vector(traj, [("@CA @CB"),])
    >>> pt.calc_vector(traj, "principal z")
    >>> pt.calc_vector(traj, "principal x")
    >>> pt.calc_vector(traj, "ucellx")
    >>> pt.calc_vector(traj, "boxcenter")
    >>> pt.calc_vector(traj, "box")

    Notes
    -----
    It's faster to calculate with a list of commands.
    For example, if you need to perform 3 calculations for 'ucellx', 'boxcenter', 'box'
    like below:

    >>> pt.calc_vector(traj, "ucellx")
    >>> pt.calc_vector(traj, "boxcenter")
    >>> pt.calc_vector(traj, "box")

    You should use a list of commands for faster calculation.

    >>> comlist = ['ucellx', 'boxcenter', 'box']
    >>> pt.calc_vector(traj, comlist)
    """
    from pytraj.core.ActionList import ActionList

    dslist = CpptrajDatasetList()
    _top = _get_topology(traj, top)
    list_of_commands = _get_list_of_commands(command)
    fi = _get_fiterator(traj, frame_indices)
    actlist = ActionList()

    for command in list_of_commands:
        act = CpptrajActions.Action_Vector()
        actlist.add_action(act, command, _top, dslist=dslist)
    actlist.do_actions(fi)

    return _get_data_from_dtype(dslist, dtype=dtype)


def _ired(iredvec, modes,
          NHbond=True,
          relax_freq=None,
          NHdist=1.02,
          order=2,
          tstep=1.0,
          tcorr=10000.,
          norm=False,
          drct=False,
          dtype='dataset'):
    '''perform isotropic reorientational Eigenmode dynamics analysis

    Parameters
    ----------
    iredvec : shape=(n_vectors, n_frames, 3)
    modes : tuple of (eigenvalues, eigenvectors) or DatasetModes (has attribute 'eigenvalues', 'eigenvectors')
        eigenvalues has shape of (n_modes, )
        eigenvectors has shape of (n_modes, vector_size), each vector correspond to each eigenvalue
    NHbond : bool, default True
        if True, relax_freq value will be used
        if False, NHdist and relax_freq will be ignored.
    relax_freq : float or None, default None
        be used with NHbond
    NHdist : N-H bond length, default 1.02
    order : int, default 2
    tstep : timestep between frames, default 1.0 ps
    tcorr: default 10000.
    norm : default False

    Returns
    -------
    CpptrajDatasetList
    '''

    _freq = 'relax freq ' + str(relax_freq) if relax_freq is not None else ''
    _NHdist = 'NHdist ' + str(NHdist) if NHbond else ''
    _order = 'order ' + str(order)
    _tstep = 'tstep ' + str(tstep)
    _tcorr = 'tcorr ' + str(tcorr)
    _norm = 'norm' if norm else ''
    _drct = 'drct' if drct else ''
    _modes = 'modes mymodes'
    if NHbond:
        command = ' '.join(
            (_freq, _NHdist, _modes, _order, _tstep, _tcorr, _norm, _drct))
    else:
        command = ' '.join((_modes, _order, _tstep, _tcorr, _norm, _drct))
    act = CpptrajAnalyses.Analysis_IRED()
    dslist = CpptrajDatasetList()
    # create DatasetVector
    for idx, dvec in enumerate(iredvec):
        name = 'ired_' + str(idx)
        dslist.add_set('vector', name)
        dslist[-1].scalar_type = 'iredvec'
        dslist[-1].data = np.asarray(dvec, dtype='f8')

    # add data to DatasetModes
    dslist.add_set('modes', 'mymodes')
    is_reduced = False  # ?
    if hasattr(modes, 'eigenvalues') and hasattr(modes, 'eigenvectors'):
        eigenvalues = modes.eigenvalues
        eigenvectors = modes.eigenvectors
    else:
        eigenvalues, eigenvectors = modes
    dslist[-1]._set_modes(is_reduced, len(eigenvalues), eigenvectors.shape[1],
                          eigenvalues, eigenvectors.flatten())

    act(command, dslist=dslist)
    # remove input datasets to free memory
    # all DatasetVectors + 1 DatasetModes
    #for d in dslist[:idx+2]:
    #    dslist.remove_set(d)
    #values = dslist.values.copy()
    #return values
    #return _get_data_from_dtype(dslist, dtype=dtype)
    return dslist


@_register_pmap
def ired_vector_and_matrix(traj=None,
                           mask="",
                           frame_indices=None,
                           order=2,
                           dtype='tuple',
                           top=None):
    """perform vector calculation and then calculate ired matrix

    Parameters
    ----------
    traj : Trajectory-like or iterable that produces :class:`pytraj.Frame`
    mask : str or a list of strings
    frame_indices : array-like, optional, default None
        only perform calculation for given frame indices
    order : default 2 
    dtype : output's dtype, {'dataset', 'tuple'} default 'dataset'
    top : Topology, optional, default None

    Returns
    -------
    out : if dtype is 'dataset', return pytraj.DatasetList with shape=(n_vectors+1,)
        last index is a matrix, otherwise n_vectors. If dtype is 'tuple', return a a tuple
        of vectors and matrix
    """
    dslist = CpptrajDatasetList()
    _top = _get_topology(traj, top)
    fi = _get_fiterator(traj, frame_indices)

    cm_arr = np.asarray(mask)

    if cm_arr.dtype.kind != 'i':
        list_of_commands = _get_list_of_commands(mask)
    else:
        if cm_arr.ndim != 2:
            raise ValueError(
                'if mask is a numpy.ndarray, it must have ndim = 2')
        list_of_commands = _2darray_to_atommask_groups(cm_arr)

    actlist = ActionList()

    for command in list_of_commands:
        # tag ired vector
        command += ' ired '
        act = CpptrajActions.Action_Vector()
        actlist.add_action(act, command, _top, dslist=dslist)

    act_matired = CpptrajActions.Action_Matrix()
    ired_cm = 'ired order ' + str(order)
    actlist.add_action(act_matired, ired_cm, _top, dslist=dslist)
    actlist.do_actions(fi)

    if dtype == 'tuple':
        mat = dslist[-1].values
        mat = mat / mat[0, 0]
        return dslist[:-1].values, mat
    else:
        out = _get_data_from_dtype(dslist, dtype=dtype)
        if dtype == 'dataset':
            out[-1].values = out[-1].values / out[-1].values[0, 0]
        return out

def _calc_vector_center(traj=None,
                        command="",
                        top=None,
                        mass=False,
                        dtype='ndarray'):
    _top = _get_topology(traj, top)

    dslist = CpptrajDatasetList()
    dslist.set__own_memory(False)  # need this to avoid segmentation fault
    act = CpptrajActions.Action_Vector()
    command = "center " + command

    if mass:
        command += " mass"

    act.read_input(command=command, top=_top, dslist=dslist)
    act.process(_top)

    for frame in iterframe_master(traj):
        # set Frame masses
        if mass:
            frame.set_frame_mass(_top)
        act.do_action(frame)
    return _get_data_from_dtype(dslist, dtype=dtype)


@_register_pmap
def calc_center_of_mass(traj=None,
                        mask='',
                        top=None,
                        dtype='ndarray', *args, **kwd):
    return _calc_vector_center(traj=traj,
                               command=mask,
                               top=top,
                               mass=True,
                               dtype=dtype)


calc_COM = calc_center_of_mass


@_register_pmap
def calc_center_of_geometry(traj=None, command="", top=None, dtype='ndarray'):
    _top = _get_topology(traj, top)

    if not isinstance(command, string_types):
        command = array_to_cpptraj_atommask(command)

    atom_mask_obj = _top(command)
    dslist = CpptrajDatasetList()
    dslist.add_set("vector")

    for frame in iterframe_master(traj):
        dslist[0].append(frame.center_of_geometry(atom_mask_obj))
    return _get_data_from_dtype(dslist, dtype=dtype)


calc_COG = calc_center_of_geometry

@_register_openmp
def calc_pairwise_rmsd(traj=None,
                       mask="",
                       metric='rms',
                       top=None,
                       dtype='ndarray',
                       mat_type='full'):
    """calculate pairwise rmsd with different metrics.

    Parameters
    ----------
    traj : Trajectory-like or iterable object
    mask : mask
        if mask is "", use all atoms
    metric : {'rms', 'dme', 'srmsd', 'nofit'}
        if 'rms', perform rms fit 
        if 'dme', use distance RMSD
        if 'srmsd', use symmetry-corrected RMSD 
        if 'nofit', perform rmsd without fitting
    top : Topology, optional, default=None
    dtype: ndarray
        return type
    mat_type : 2D or 1D ndarray, depending on value
        if 'full': return 2D array, shape=(n_frames, n_frames)
        if 'cpptraj': return 1D array, shape=(n_frames*(n_frames-1)/2, )
    *args, **kwd: optional (for advanced user)

    Examples
    --------
    >>> pt.pairwise_rmsd(traj(0, 1000, mask='@CA'))

    >>> # calculate pairwise rmsd for all frames using CA atoms, use `dme` (distance RMSD)
    >>> # convert to numpy array
    >>> arr_np = pt.pairwise_rmsd(traj, "@CA", metric="dme", dtype='ndarray')

    >>> # calculate pairwise rmsd for all frames using CA atoms, nofit for RMSD
    >>> # convert to numpy array
    >>> arr_np = pt.pairwise_rmsd(traj, "@CA", metric="nofit", dtype='ndarray')

    >>> # calculate pairwise rmsd for all frames using CA atoms
    >>> # use symmetry-corrected RMSD, convert to numpy array
    >>> arr_np = pt.pairwise_rmsd(traj, "@CA", metric="srmsd", dtype='ndarray')

    Notes
    -----
    This calculation is memory consumming. It's better to use out-of-core ``pytraj.TrajectoryIterator``

    It's better to use ``pytraj.pairwise_rmsd(traj(mask='@CA'))`` than ``pytraj.pairwise_rmsd(traj, mask='@CA')``

    Install ``libcpptraj`` with ``openmp`` to get benifit from parallel
    """
    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)

    from pytraj.analyses.CpptrajAnalyses import Analysis_Rms2d
    from pytraj import TrajectoryIterator, Trajectory

    act = Analysis_Rms2d()

    dslist = CpptrajDatasetList()
    dslist.add_set("coords", "_tmp")
    # need to set "rmsout" to trick cpptraj not giving error
    # need " " (space) before crdset too

    if isinstance(traj, (Trajectory, TrajectoryIterator)):
        fi = traj.iterframe(mask=mask)
        command = metric
        dslist[0].top = fi.top
        _top = fi.top
    else:
        fi = iterframe_master(traj)
        command = ' '.join((mask, metric))
        _top = _get_topology(traj, top)
        dslist[0].top = _top

    command = command + " crdset _tmp rmsout mycrazyoutput"

    for frame in fi:
        dslist[0].append(frame)

    act(command, _top, dslist=dslist)
    # remove dataset coords to free memory
    dslist.remove_set(dslist[0])

    if dtype == 'ndarray':
        return _get_matrix_from_dataset(dslist[0], mat_type)
    else:
        return _get_data_from_dtype(dslist, dtype)


def calc_density(traj=None,
                 command="",
                 top=None,
                 dtype='ndarray', *args, **kwd):
    # NOTE: trick cpptraj to write to file first and the reload

    with goto_temp_folder():

        def _calc_density(traj, command, *args, **kwd):
            # TODO: update this method if cpptraj save data to
            # CpptrajDatasetList
            _top = _get_topology(traj, top)
            dflist = DataFileList()

            tmp_filename = "tmp_pytraj_out.txt"
            command = "out " + tmp_filename + " " + command
            act = CpptrajActions.Action_Density()
            # with goto_temp_folder():
            act(command, traj, top=_top, dflist=dflist)
            act.print_output()
            dflist.write_all_datafiles()
            absolute_path_tmp = os.path.abspath(tmp_filename)
            return absolute_path_tmp

        dslist = CpptrajDatasetList()
        fname = _calc_density(traj, command, *args, **kwd)
        dslist.read_data(fname)
        return _get_data_from_dtype(dslist, dtype)


@_register_pmap
def calc_temperatures(traj=None,
                      command="",
                      frame_indices=None,
                      top=None,
                      dtype='ndarray'):
    """return 1D python array of temperatures (from velocity) in traj
    if `frame` keyword is specified cpptraj/pytraj will take existing T

    Default = array of 0.0
    """
    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()

    fi = _get_fiterator(traj, frame_indices)
    act = CpptrajActions.Action_Temperature()
    act(command, fi, dslist=dslist, top=_top)

    return _get_data_from_dtype(dslist, dtype)


@_register_pmap
def rmsd_perres(traj=None,
                ref=0,
                mask="",
                mass=False,
                resrange=None,
                perres_mask=None,
                perres_center=False,
                perres_invert=False,
                frame_indices=None,
                top=None,
                dtype='dataset'):
    """superpose ``traj`` to ``ref`` with `mask`, then calculate nofit rms for residues 
    in `resrange` with given `perresmask`

    Returns
    -------
    out : pytraj.DatasetList, shape=(1+n_residues, n_frames)
        out[0]: regular rmsd
        out[1:]: perres rmsd for all given residues
        `out.values` will return corresponding numpy array
    """
    if resrange is not None:
        if isinstance(resrange, string_types):
            _range = 'range %s ' % resrange
        else:
            raise ValueError("range must be a string")
    else:
        _range = ''
    _perresmask = 'perresmask ' + perres_mask if perres_mask is not None else ''
    _perrestcenter = 'perrescenter' if perres_center else ''
    _perrestinvert = 'perresinvert' if perres_invert else ''

    cm = " ".join(
        (mask, 'perres', _range, _perresmask, _perrestcenter, _perrestinvert))
    return calc_rmsd(traj=traj,
                     ref=ref,
                     mask=cm,
                     nofit=False,
                     mass=mass,
                     frame_indices=frame_indices,
                     top=top,
                     dtype=dtype)

@_register_pmap
def calc_rmsd_nofit(traj=None,
              ref=0,
              mask="",
              mass=False,
              frame_indices=None,
              top=None,
              dtype='ndarray'):
    '''
    See also
    --------
    calc_rmsd
    '''
    return calc_rmsd(traj=traj, ref=ref, mask=mask, mass=mass,
                     nofit=True, frame_indices=frame_indices,
                     top=top,
                     dtype=dtype)

@_register_pmap
def calc_rmsd(traj=None,
              ref=0,
              mask="",
              nofit=False,
              mass=False,
              frame_indices=None,
              top=None,
              dtype='ndarray'):
    """calculate rmsd

    Parameters
    ----------
    traj : Trajectory-like
    ref : {Frame, int}, default=0 (first frame)
        Reference frame or index.
    mask : str or 1D array-like of string or 1D or 2D array-like
        Atom mask/indices
    nofit : bool, default False
        if False, perform fitting (rotation and translation).
        if ``traj`` is mutable, its coordinates will be updated
        if True, not fitting.
    top : {Topology, str}, default None, optional
    dtype : return data type, default='ndarray'


    Examples
    --------
    >>> import pytraj as pt
    >>> # all atoms, do fitting, using ref=traj[-3]
    >>> pt.rmsd(traj, ref=-3)

    >>> # rmsd for 3 maskes, do fitting, using ref=traj[0] (defaul)
    >>> pt.rmsd(traj, mask=['@CA', '@C', ':3-18@CA'], dtype='dataset')

    >>> # rmsd to first frame, use mass ':3-13' but do not perorm fitting
    >>> pt.rmsd(traj, ref=traj[0], mask=':3-13', nofit=True)

    Notes
    -----
    if ``traj`` is mutable, its coordinates will be updated

    """

    _nofit = ' nofit ' if nofit else ''
    _mass = ' mass ' if mass else ''
    opt = _nofit + _mass

    if isinstance(mask, string_types):
        command = [mask, ]
    else:
        try:
            cmd = np.asarray(mask)
        except ValueError:
            raise ValueError("don't mix different types")
        dname = cmd.dtype.name
        if 'str' in dname:
            command = cmd
        elif 'int' in dname or 'object' in dname:
            if cmd.ndim == 1 and 'object' not in dname:
                command = [array_to_cpptraj_atommask(mask), ]
            elif cmd.ndim == 2 or 'object' in dname:
                command = [array_to_cpptraj_atommask(x) for x in mask]
            else:
                raise ValueError("only support array with ndim=1,2")
        else:
            raise ValueError("not supported")

    _top = _get_topology(traj, top)

    ref = _get_reference_from_traj(traj, ref)
    fi = _get_fiterator(traj, frame_indices)

    alist = ActionList()
    dslist = CpptrajDatasetList()

    for cm in command:
        _cm = cm + opt
        if 'savematrices' in _cm:
            if dtype not in ['dataset', 'cpptraj_dataset']:
                raise ValueError('if savematrices, dtype must be "dataset"')
            _cm = 'RMDSset ' + _cm
        alist.add_action(CpptrajActions.Action_Rmsd(), _cm,
                         top=_top,
                         dslist=dslist)

    alist.do_actions(ref)
    alist.do_actions(fi)

    dnew = DatasetList(dslist)
    for d in dnew:
        d.values = d.values[1:]
    return _get_data_from_dtype(dnew, dtype=dtype)

# alias for `calc_rmsd`
rmsd = calc_rmsd


@_register_pmap
def calc_distance_rmsd(traj=None, ref=0, mask='', top=None, dtype='ndarray'):
    '''compute distance rmsd between traj and reference

    Parameters
    ----------
    traj : Trajectory-like or iterator that produces Frame
    ref : {int, Frame}, default 0 (1st Frame) 
    mask : str
    top : Topology or str, optional, default None
    dtype : return dtype, default 'ndarray'

    Returns
    -------
    1D ndarray if dtype is 'ndarray' (default)

    Examples
    --------
    >>> import pytraj as pt
    >>> # compute distance_rmsd to last frame
    >>> pt.distance_rmsd(traj, ref=-1)

    >>> # compute distance_rmsd to first frame with mask = '@CA'
    >>> pt.distance_rmsd(traj, ref=0, mask='@CA')
    '''
    _top = _get_topology(traj, top)
    _ref = _get_reference_from_traj(traj, ref)
    dslist = CpptrajDatasetList()
    command = mask

    act = CpptrajActions.Action_DistRmsd()
    act(command, [_ref, traj], top=_top, dslist=dslist)

    # exclude ref value
    for d in dslist:
        d.data = d.data[1:]
    return _get_data_from_dtype(dslist, dtype=dtype)

# alias
distance_rmsd = calc_distance_rmsd


def align_principal_axis(traj=None, mask="*", top=None):
    # TODO : does not match with cpptraj output
    # rmsd_nofit ~ 0.5 for md1_prod.Tc5b.x, 1st frame
    """
    Notes
    -----
    apply for mutatble traj (Trajectory, Frame)
    """
    _noaction_with_TrajectoryIterator(traj)

    command = mask

    if not isinstance(command, string_types):
        command = array_to_cpptraj_atommask(command)
    _top = _get_topology(traj, top)
    act = CpptrajActions.Action_Principal()
    command += " dorotation"
    act(command, traj, top=_top)


def principal_axes(traj=None, mask='*', dorotation=False, mass=True, top=None):
    """calculate eigenvalues and eigenvectors

    Parameters
    ----------
    traj : Trajectory-like
    mask : str, default '*' (all atoms)
    mass: bool, defaul True
    if `dorotation`, the system will be aligned along principal axes (apply for mutable system)
    top : Topology, optional

    Returns
    -------
    out_0 : numpy array, shape=(n_frames, 3, 3), corresponding eigenvectors
    out_1: numpy array with shape=(n_frames, 3), eigenvalues
    """
    act = CpptrajActions.Action_Principal()
    command = mask

    _dorotation = 'dorotation' if dorotation else ''
    _mass = 'mass' if mass else ''

    if 'name' not in command:
        command += ' name pout'

    command = ' '.join((command, _dorotation, _mass))

    _top = _get_topology(traj, top)
    dslist = CpptrajDatasetList()
    act(command, traj, _top, dslist=dslist)
    return (dslist[0].values, dslist[1].values)


@_register_openmp
def atomiccorr(traj=None, mask="", top=None, dtype='ndarray', *args, **kwd):
    """
    """
    _top = _get_topology(traj, top)

    if not isinstance(mask, string_types):
        # [1, 3, 5] to "@1,3,5
        mask = array_to_cpptraj_atommask(mask)

    command = mask

    dslist = CpptrajDatasetList()
    act = CpptrajActions.Action_AtomicCorr()
    act("out mytempfile.out " + command, traj,
        top=_top,
        dslist=dslist, *args, **kwd)
    act.print_output()
    return _get_data_from_dtype(dslist, dtype=dtype)


def _closest_iter(act, traj):
    '''
    Parameters
    ----------
    act : Action object
    traj : Trajectory-like
    '''

    for frame in iterframe_master(traj):
        new_frame = act.do_action(frame, get_new_frame=True)
        #yield new_frame.copy()
        yield new_frame


@_register_openmp
def closest(traj=None,
            mask='*',
            solvent_mask=None,
            n_solvents=10,
            restype='trajectory',
            top=None):
    """return either a new Trajectory or a frame iterator. Keep only ``n_solvents`` closest to mask

    Parameters
    ----------
    traj : Trajectory-like | list of Trajectory-like/frames | frame iterator | chunk iterator
    mask: str, default '*' (all solute atoms)
    restype : str, {'trajectory', 'dataset', 'iterator'}, default 'trajectory'
        if restype == 'trajectory', return a new ``pytraj.Trajectory``
        if restype == 'dataset': return a tuple (new_traj, datasetlist)
        if restype == 'iterator': return a tuple of (Frame iterator, new Topology),  good for memory saving
        if restype == 'all': return (Trajectory, DatasetList)
    top : Topology-like object, default=None, optional

    Returns
    -------
    out : (check above)

    Examples
    --------
    >>> # obtain new traj, keeping only closest 100 waters 
    >>> # to residues 1 to 13 (index starts from 1) by distance to the first atom of water
    >>> t = pt.closest(traj, mask='@CA', n_solvents=10)

    >>> # only get meta data for frames, solvent without getting new Trajectory
    >>> # (such as Frame number, original solvent molecule number, ...) (from cpptraj manual)
    >>> dslist = pt.closest(traj, n_solvents=100, mask=':1-13', restype='dataset')

    >>> # getting a frame iterator for lazy evaluation
    >>> fiter = pt.closest(traj, n_solvents=20, restype='iterator')
    >>> for frame in fiter: print(frame) 
    """

    dslist = CpptrajDatasetList()

    if n_solvents == 0:
        raise ValueError('must specify the number of solvents')

    if not isinstance(mask, string_types):
        mask = array_to_cpptraj_atommask(mask)

    command = str(n_solvents) + ' ' + mask

    dtype = restype

    act = CpptrajActions.Action_Closest()

    _top = _get_topology(traj, top)

    if solvent_mask is not None:
        _top = _top.copy()
        _top.set_solvent(solvent_mask)

    if dtype not in ['trajectory', 'iterator']:
        # trick cpptraj to dump data to CpptrajDatasetList too
        command = command + " closestout tmp_pytraj_closestout.out"

    act.read_input(command, _top, dslist=dslist)
    new_top = act.process(_top, get_new_top=True)[0]

    fiter = _closest_iter(act, traj)

    if dtype == 'iterator':
        return (fiter, new_top.copy())
    else:
        if dtype in ['trajectory', 'all']:
            fa = Trajectory()
            fa.top = new_top.copy()
            for new_frame in fiter:
                fa.append(new_frame.copy())
            if dtype == 'trajectory':
                return fa
            elif dtype == 'all':
                return fa, dslist
        else:
            for new_frame in fiter:
                # just let cpptraj dump data to DatasetList
                pass
            new_dslist = _get_data_from_dtype(dslist, dtype=dtype)
            return new_dslist


@_register_pmap
def native_contacts(traj=None,
                    mask="",
                    mask2="",
                    dtype='dataset',
                    ref=0,
                    distance=7.0,
                    image=True,
                    include_solvent=False,
                    byres=False,
                    frame_indices=None,
                    top=None):
    """
    Examples
    --------
    >>> # use 1st frame as reference, don't need specify ref Frame
    >>> pt.native_contacts(traj)

    >>> # explicitly specify reference, specify distance cutoff
    >>> pt.native_contacts(traj, ref=ref, distance=8.0)
    """
    _top = _get_topology(traj, top)
    ref = _get_reference_from_traj(traj, ref)
    fi = _get_fiterator(traj, frame_indices)
    act = CpptrajActions.Action_NativeContacts()
    dslist = CpptrajDatasetList()

    if not isinstance(mask, string_types):
        # [1, 3, 5] to "@1,3,5
        mask = array_to_cpptraj_atommask(mask)
    if not isinstance(mask2, string_types):
        # [1, 3, 5] to "@1,3,5
        mask2 = array_to_cpptraj_atommask(mask2)
    command = ' '.join((mask, mask2))

    _distance = str(distance)
    _noimage = "noimage" if not image else ""
    _includesolvent = "includesolvent" if include_solvent else ""
    _byres = "byresidue" if byres else ""

    _command = " ".join(('ref myframe', command, _distance, _noimage,
                         _includesolvent, _byres))
    dslist.add_set('ref_frame', 'myframe')
    dslist[0].add_frame(ref)
    dslist[0].top = _top
    act(_command, fi, top=_top, dslist=dslist)
    dslist._pop(0)

    return _get_data_from_dtype(dslist, dtype=dtype)


def calc_grid(traj=None, command="", top=None, dtype='dataset', *args, **kwd):
    """
    """
    # TODO: doc, rename method, move to seperate module?
    if not isinstance(command, string_types):
        command = array_to_cpptraj_atommask(command)
    act = CpptrajActions.Action_Grid()
    dslist = CpptrajDatasetList()

    # cpptraj require output
    command = "tmp_pytraj_grid_output.txt " + command
    _top = _get_topology(traj, top)
    with goto_temp_folder():
        act(command, traj, dslist=dslist, top=_top, *args, **kwd)
    return _get_data_from_dtype(dslist, dtype=dtype)


def check_structure(traj=None, command="", top=None, *args, **kwd):
    """
    Examples
    --------
    >>> check_structure(traj[0], top=traj.top)
    """
    act = CpptrajActions.Action_CheckStructure()

    # cpptraj require output
    _top = _get_topology(traj, top)
    act(command, traj, top=_top, *args, **kwd)


def timecorr(vec0, vec1,
             order=2,
             tstep=1.,
             tcorr=10000.,
             norm=False,
             dtype='ndarray'):
    """TODO: doc. not yet assert to cpptraj's output

    Parameters
    ----------
    vec0 : 2D array-like, shape=(n_frames, 3)
    vec1 : 2D array-like, shape=(n_frames, 3)
    order : int, default 2
    tstep : float, default 1.
    tcorr : float, default 10000.
    norm : bool, default False
    """
    act = analdict['timecorr']

    cdslist = CpptrajDatasetList()

    cdslist.add_set("vector", "_vec0")
    cdslist.add_set("vector", "_vec1")
    cdslist[0].data = np.asarray(vec0).astype('f8')
    cdslist[1].data = np.asarray(vec1).astype('f8')

    _order = "order " + str(order)
    _tstep = "tstep " + str(tstep)
    _tcorr = "tcorr " + str(tcorr)
    _norm = "norm" if norm else ""
    command = " ".join(
        ('vec1 _vec0 vec2 _vec1', _order, _tstep, _tcorr, _norm))
    act(command, dslist=cdslist)
    return _get_data_from_dtype(cdslist[2:], dtype=dtype)


def crank(data0, data1, mode='distance', dtype='ndarray'):
    """
    Parameters
    ----------
    data0 : array-like
    data1 : array-like
    mode : str, {'distance', 'angle'}
    dtype : str

    Notes
    -----
    Same as `crank` in cpptraj
    """
    from pytraj.analyses.CpptrajAnalyses import Analysis_CrankShaft

    cdslist = CpptrajDatasetList()
    cdslist.add_set("double", "d0")
    cdslist.add_set("double", "d1")

    cdslist[0].data = np.asarray(data0)
    cdslist[1].data = np.asarray(data1)

    act = Analysis_CrankShaft()
    command = ' '.join((mode, 'd0', 'd1'))
    act(command, dslist=cdslist)
    return _get_data_from_dtype(cdslist[2:], dtype=dtype)


def cross_correlation_function(data0, data1, dtype='ndarray'):
    """
    Notes
    -----
    Same as `corr` in cpptraj
    """

    cdslist = CpptrajDatasetList()
    cdslist.add_set("double", "d0")
    cdslist.add_set("double", "d1")

    cdslist[0].data = np.asarray(data0)
    cdslist[1].data = np.asarray(data1)

    act = analdict['corr']
    act("d0 d1 out _tmp.out", dslist=cdslist)
    return _get_data_from_dtype(cdslist[2:], dtype=dtype)


def auto_correlation_function(data, dtype='ndarray', covar=True):
    """
    Notes
    -----
    Same as `autocorr` in cpptraj
    """

    _nocovar = " " if covar else " nocovar"

    cdslist = CpptrajDatasetList()
    cdslist.add_set("double", "d0")

    cdslist[0].data = np.asarray(data)

    act = analdict['autocorr']
    command = "d0 out _tmp.out" + _nocovar
    act(command, dslist=cdslist)
    return _get_data_from_dtype(cdslist[1:], dtype=dtype)


def lifetime(data, cut=0.5, rawcurve=False,
             more_options='',
             dtype='ndarray'):
    """lifetime (adapted lightly from cpptraj doc)

    Parameters
    ----------
    data : 1D-array or 2D array-like
    cut : cutoff to use when determining if data is 'present', default 0.5
    more_options : str, more cpptraj's options. Check cpptraj's manual.
    """
    data = np.asarray(data)
    if data.ndim == 1:
        data_ = [data, ]
    else:
        data_ = data

    _outname = 'name lifetime_'
    _cut = 'cut ' + str(cut)
    _rawcurve = 'rawcurve' if rawcurve else ''
    # do not sorting dataset's names. We can accessing by indexing them.
    _nosort = 'nosort'

    namelist = []
    cdslist = CpptrajDatasetList()
    for idx, arr in enumerate(data_):
        # create datasetname so we can reference them
        name = 'data_' + str(idx) 
        if 'int' in arr.dtype.name:
            cdslist.add_set("integer", name)
        else:
            cdslist.add_set("double", name)
        cdslist[-1].data = np.asarray(arr)
        namelist.append(name)

    act = CpptrajAnalyses.Analysis_Lifetime()
    _cm = ' '.join(namelist)
    command = " ".join((_cm, _outname, _cut, _rawcurve, _nosort, more_options))
    act(command, dslist=cdslist)

    for name in namelist:
        cdslist.remove_set(cdslist[name])
    return _get_data_from_dtype(cdslist, dtype=dtype)


def search_neighbors(traj=None,
                     mask='',
                     frame_indices=None,
                     dtype='dataset',
                     top=None):
    """search neighbors

    Returns
    -------
    :ref:`pytraj.DatasetList`, is a list of atom index arrays for each frame.
    Those arrays might not have the same lenghth

    Note
    ----
    not validate yet

    Examples
    --------
    >>> pt.search_neighbors(traj, ':5<@5.0') # around residue 5 with 5.0 cutoff
    """
    dslist = DatasetList()

    _top = _get_topology(traj, top)
    fi = _get_fiterator(traj, frame_indices)

    for idx, frame in enumerate(iterframe_master(fi)):
        _top.set_distance_mask_reference(frame)
        dslist.append({str(idx): np.asarray(_top.select(mask))})
    return _get_data_from_dtype(dslist, dtype)


@_register_pmap
def pucker(traj=None,
           pucker_mask=("C1'", "C2'", "C3'", "C4'", "O4'"),
           resrange=None,
           top=None,
           dtype='dataset',
           range360=False,
           method='altona',
           use_com=True,
           amplitude=True,
           offset=None, *args, **kwd):
    """Note: not validate yet

    """
    from pytraj.compat import range

    _top = _get_topology(traj, top)
    if not resrange:
        resrange = range(_top.n_residues)

    _range360 = "range360" if range360 else ""
    geom = "geom" if not use_com else ""
    amp = "amplitude" if amplitude else ""
    _offset = "offset " + str(offset) if offset else ""

    cdslist = CpptrajDatasetList()
    for res in resrange:
        act = CpptrajActions.Action_Pucker()
        command = " ".join((":" + str(res + 1) + '@' + x for x in pucker_mask))
        name = "pucker_res" + str(res + 1)
        command = " ".join(
            (name, command, _range360, method, geom, amp, _offset))
        act(command, traj, top=_top, dslist=cdslist, *args, **kwd)
    return _get_data_from_dtype(cdslist, dtype)


def center(traj=None, mask="", center='box', mass=False, top=None):
    """center

    Parameters
    ----------
    traj : Trajectory-like or Frame iterator
    mask : str, mask
    center : str, {'box', 'origin'}
    mass : bool, default: False
        if True, use mass weighted
    top : Topology, optional, default: None

    Examples
    --------
    >>> traj = traj[:]
    >>> # all atoms, center to box center (x/2, y/2, z/2)
    >>> pt.center(traj)

    >>> # center at origin, use @CA 
    >>> pt.center(traj, '@CA', center='origin')

    >>> # center to box center, use mass weighted
    >>> pt.center(traj, mass=True)
    >>> pt.center(traj, ':1', mass=True)

    Returns
    -------
    updated traj

    See also
    --------
    pytraj.translate
    """
    if center.lower() not in ['box', 'origin']:
        raise ValueError('center must be box or origin')
    _center = '' if center == 'box' else center
    _mass = 'mass' if mass else ''
    command = ' '.join((mask, _center, _mass))
    _noaction_with_TrajectoryIterator(traj)
    _top = _get_topology(traj, top)

    act = CpptrajActions.Action_Center()
    act(command, traj, top=_top)
    return traj


def rotate_dihedral(traj=None, mask="", top=None):
    # change to pt.rotate_dihedral(traj, res=0,
    #              mask=("O4'", "C1'", "N9", "C4"), deg=120)?
    """
    Examples
    --------
    >>> import pytraj as pt
    >>> pt.rotate_dihedral(traj, "3:phi:120") # rotate phi of res 3 to 120 deg
    >>> pt.rotate_dihedral(traj, "1:O4':C1':N9:C4:120") # rotate dihedral with given mask

    Returns
    -------
    updated traj

    Notes
    -----
    Syntax and method's name might be changed
    """
    _noaction_with_TrajectoryIterator(traj)
    _top = _get_topology(traj, top)

    if "custom:" in mask:
        command = mask
    else:
        command = "custom:" + mask

    act = CpptrajActions.Action_MakeStructure()

    act(command, traj, top=_top)
    return traj


@_register_openmp
def replicate_cell(traj=None, mask="", direction='all', top=None):
    '''create a trajectory where the unit cell is replicated in 1 or
    more direction (up to 27)

    Parameters
    ----------
    traj : Trajectory-like or Frame iterator
    mask : str, default: ""
        if default, using all atoms
        else: given mask
    direction: {'all', 'dir'} or list/tuple of <XYZ> (below)
        if 'all', replicate cell once in all possible directions
        if 'dir', need to specify the direction with format 'dir <XYZ>', where each X (Y, Z)
        is either 0, 1 or -1 (see example below)
    top : Topology, optional, default: None

    Returns
    -------
    traj : pytraj.Trajectory

    Examples
    --------
    >>> pt.replicate_cell(traj, direction='all')
    >>> pt.replicate_cell(traj, direction='dir 001 dir 111')
    >>> pt.replicate_cell(traj, direction='dir 001 dir 1-10')
    >>> pt.replicate_cell(traj, direction='dir 001 dir 1-10')
    >>> pt.replicate_cell(traj, direction=('001', '0-10'))
    '''
    _top = _get_topology(traj, top)
    if isinstance(direction, string_types):
        _direction = direction
    elif isinstance(direction, (list, tuple)):
        # example: direction = ('001, '0-10')
        _direction = 'dir ' + ' dir '.join(direction)
    else:
        raise ValueError(
            'only support ``direction`` as a string or list/tuple of strings')
    command = ' '.join(('name tmp_cell', _direction, mask))

    act = CpptrajActions.Action_ReplicateCell()
    dslist = CpptrajDatasetList()
    act(command, traj, top=_top, dslist=dslist)
    traj = Trajectory(xyz=dslist[0].xyz, top=dslist[0].top)

    return traj


def _rotate_dih(traj, resid='1', dihtype=None, deg=0, top=None):
    '''
    Examples
    >>> pt._rotate_dih(traj, resid='1', dihtype='delta')

    Returns
    -------
    updated traj
    '''
    _top = _get_topology(traj, top)

    if not isinstance(resid, string_types):
        resid = str(resid + 1)
    deg = str(deg)

    command = ':'.join((dihtype, resid, dihtype, deg))
    make_structure(traj, command, top=_top)
    return traj


set_dihedral = _rotate_dih


def make_structure(traj=None, mask="", top=None):
    _noaction_with_TrajectoryIterator(traj)
    _top = _get_topology(traj, top)

    command = mask
    act = CpptrajActions.Action_MakeStructure()
    act(command, traj, top=_top)


def _analyze_modes(data,
                   mode='',
                   beg=1,
                   end=50,
                   bose=False,
                   factor=1.0,
                   maskp=None,
                   trajout='',
                   pcmin=None,
                   pcmax=None,
                   tmode=None):
    # TODO: not finished yet
    '''Perform analysis on calculated Eigenmodes

    Parameters
    ----------
    data : 
    mode : str, {'fluct', 'displ', 'corr', 'eigenval', 'trajout', 'rmsip'}
        - fluct:    RMS fluctations from normal modes
        - displ:    Displacement of cartesian coordinates along normal mode directions
        - corr:     Calculate dipole-dipole correlation functions.
        - eigenval: Calculate eigenvalue fractions.
        - trajout:  Calculate pseudo-trajectory along given mode.
        - rmsip:    Root mean square inner product.
    beg : int
    end : int
    bose : bool, optional
    factor : optional 
    maskp : a string or list of strings, optional
    trajout : output filename, optional
    '''
    pass


def _projection(traj, mask, modes, scalar_type,
                frame_indices=None,
                dtype='dataset',
                top=None):
    # TODO: not done yet
    act = CpptrajActions.Action_Projection()
    dslist = CpptrajDatasetList()
    fi = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)

    dslist.add_set('modes', 'tmp_evecs')
    is_reduced = False
    eigenvalues, eigenvectors = modes
    dslist[-1]._set_modes(is_reduced, len(eigenvalues), eigenvectors.shape[1],
                          eigenvalues, eigenvectors.flatten())
    dslist[-1].scalar_type = scalar_type
    _mask = mask
    _evecs = 'evecs tmp_evecs'
    command = ' '.join((_evecs, _mask))
    act(command, fi, top=_top, dslist=dslist)
    return _get_data_from_dtype(dslist, dtype=dtype)


def calc_atomiccorr(traj, mask,
                    cut=None,
                    min_spacing=None,
                    byres=True,
                    frame_indices=None,
                    dtype='ndarray',
                    top=None):
    '''Calculate average correlations between the motion of atoms in mask. Doc is adapted from cpptraj doc.

    Parameters
    ----------
    traj : Trajectory-like
    mask : atom mask
    cut : {None, float}, default None
        if not None, only print correlations with absolute value greater than cut
    min_spacing : {None, float}, default None 
        if not None, only calculate correlations for motion vectors spaced min_spacing apart
    byres : bool, default False
        if False, compute atomic motion vetor
        if True, Calculate motion vectors for entire residues (selected atoms in residues only).
    '''
    fi = _get_fiterator(traj, frame_indices)
    _top = _get_topology(traj, top)

    _mask = 'out tmp.dat ' + mask
    _cut = 'cut ' + str(cut) if cut is not None else ''
    _min_spacing = 'min ' + str(min_spacing) if min_spacing is not None else ''
    _byres = 'byres' if byres else 'byatom'
    command = ' '.join((_mask, _cut, _min_spacing, _byres))

    act = CpptrajActions.Action_AtomicCorr()
    dslist = CpptrajDatasetList()

    with goto_temp_folder():
        act(command, fi, top=_top, dslist=dslist)
        # need to print_output for this Action
        act.print_output()

    return _get_data_from_dtype(dslist, dtype=dtype)


def _rotdif(arr,
            nvecs=1000,
            rvecin=None,
            rseed=80531,
            order=2,
            ncorr=-1,
            tol=1E-6,
            d0=0.03,
            nmesh=2,
            dt=0.002,
            ti=0.0,
            tf=-1,
            itmax=-1.,
            dtype='ndarray'):
    '''

    Parameters
    ----------
    arr : array-like, shape (n_frames, 3, 3) or (n_frames, 9)
    '''
    _nvecs = 'nvecs ' + str(nvecs)
    _rvecin = 'rvecin ' + rvecin if rvecin is not None else ''
    _rseed = 'rseed ' + str(rseed)
    _order = 'order ' + str(order)
    _ncorr = 'ncorr ' + str(ncorr) if ncorr > 0 else ''
    _tol = 'tol ' + str(tol)
    _d0 = 'd0 ' + str(d0)
    _nmesh = 'nmesh ' + str(nmesh)
    _dt = 'dt ' + str(dt)
    _ti = 'ti ' + str(ti)
    _tf = 'tf ' + str(tf)
    _itmax = 'itmax ' + str(itmax)
    _rmatrix = 'rmatrix mymat'

    act = CpptrajAnalyses.Analysis_Rotdif()
    dslist = CpptrajDatasetList()
    dslist.add_set('mat3x3', 'mymat')

    arr = np.asarray(arr, dtype='f8')
    msg = 'array must have shape=(n_frames, 9) or (n_frames, 3, 3)'
    shape = arr.shape
    if arr.ndim == 2:
        assert shape[1] == 9, msg
    elif arr.ndim == 3:
        assert shape[1:3] == (3, 3), msg
        # need to reshape to (n_frames, 9)
        arr = arr.reshape(shape[0], shape[1] * shape[2])
    else:
        raise ValueError(msg)

    dslist[0]._append_from_array(arr)

    command = ' '.join((_nvecs, _rvecin, _rseed, _order, _ncorr, _tol, _d0,
                        _nmesh, _dt, _ti, _tf, _itmax, _rmatrix))

    act(command, dslist=dslist)
    return _get_data_from_dtype(dslist, dtype=dtype)


def _grid(traj, mask, grid_spacing,
          offset=1,
          frame_indices=None,
          dtype='ndarray',
          top=None):
    # TODO: what's about calc_grid?
    '''make grid for atom in mask

    Parameters
    ----------
    traj : Trajectory-like
    mask : str, atom mask
    grid_spacing : array-like, shape=(3,)
        grid spacing in X/Y/Z directions
    offset : int, optional
        bin offset, number of bins to add to each direction to grid
    dtype : str, default 'ndarray'
        output data type
    '''
    if len(grid_spacing) != 3:
        raise ValueError('must have grid_spacing with len=3')

    _top = _get_topology(traj, top)
    fi = _get_fiterator(traj, frame_indices)
    act = CpptrajActions.Action_Bounds()
    dslist = CpptrajDatasetList()
    dx, dy, dz = grid_spacing
    _dx = 'dx ' + str(dx) if dx > 0. else ''
    _dy = 'dy ' + str(dy) if dy > 0. else ''
    _dz = 'dz ' + str(dz) if dz > 0. else ''
    _offset = 'offset ' + str(offset)
    command = ' '.join(
        (mask, 'out tmp_bounds.dat', _dx, _dy, _dz, 'name grid_', _offset))

    with goto_temp_folder():
        act(command, fi, top=_top, dslist=dslist)
    act.print_output()

    return _get_data_from_dtype(dslist, dtype=dtype)


def NH_order_parameters(traj, vector_pairs, order=2, tstep=1., tcorr=10000.):
    '''compute NH order parameters

    Parameters
    ----------
    traj : Trajectory-like
    vector_pairs : 2D array-like, shape (n_pairs, 2)
    order : default 2
    tstep : default 1.
    tcorr : default 10000.

    Returns
    -------
    S2 : 1D array, order parameters

    Examples
    --------
    >>> import pytraj as pt
    >>> h_indices = pt.select_atoms(traj.top, '@H')
    >>> n_indices = h_indices - 1
    >>> nh_pairs = list(zip(n_indices, h_indices))
    >>> data = pt.NH_order_parameters(traj, nh_pairs)
    >>> print(data)
    '''
    from pytraj import matrix

    # compute N-H vectors and ired matrix
    vecs_and_mat = ired_vector_and_matrix(traj, vector_pairs, order=order, dtype='tuple')
    state_vecs = vecs_and_mat[0]
    mat_ired = vecs_and_mat[1]

    # get eigenvalues and eigenvectors
    modes = matrix.diagonalize(mat_ired, n_vecs=len(state_vecs))[0]
    evals, evecs = modes.eigenvalues, modes.eigenvectors

    data = _ired(state_vecs,
                 modes=(evals, evecs),
                 NHbond=True,
                 tcorr=tcorr,
                 tstep=tstep)
    order = [d.values.copy() for d in data if 'S2' in d.key][0]
    return order
