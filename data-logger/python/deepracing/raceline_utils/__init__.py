import numpy as np
import scipy.interpolate
from scipy.interpolate import make_interp_spline, BSpline, CubicSpline
from scipy.spatial.transform import Rotation as Rot
import torch
import os
import json

def shiftRaceline(raceline: np.ndarray, reference_vec: np.ndarray, distance: float, s = None):
    diffs = raceline[1:] - raceline[0:-1]
    diffnorms = np.linalg.norm(diffs, axis=1, ord=2)
    if s is None:
        s_ = np.hstack([np.zeros(1), np.cumsum(diffnorms)])
    else:
        assert(s.shape[0]==raceline.shape[0])
        s_ = s.copy()
    nogood = diffnorms==0.0
    good = np.hstack([np.array([True]), ~nogood])
    s_ = s_[good]
    racelinegood = raceline[good].copy()
    racelinespl : CubicSpline = CubicSpline(s_, racelinegood)
    racelinetanspl = racelinespl.derivative()
    tangents = racelinetanspl(s_)
    tangent_norms = np.linalg.norm(tangents,axis=1,ord=2)
    unit_tangents = tangents/tangent_norms[:,np.newaxis]
    laterals = np.row_stack([np.cross(unit_tangents[i], reference_vec) for i in range(unit_tangents.shape[0])])
    lateral_norms = np.linalg.norm(laterals,axis=1,ord=2)
    unit_laterals = laterals/lateral_norms[:,np.newaxis]
    return s_, racelinegood + distance*unit_laterals

def loadRaceline(raceline_file : str, device : torch.device = torch.device("cpu")):
    racelinefile_ext = os.path.splitext(os.path.basename(raceline_file))[1].lower()
    if racelinefile_ext==".json":
        with open(raceline_file,"r") as f:
            raceline_dictionary = json.load(f)
        racelinenp = np.column_stack([raceline_dictionary["x"], raceline_dictionary["y"], raceline_dictionary["z"]])
        racelinedistsnp = np.array(raceline_dictionary["dist"])
    elif racelinefile_ext==".csv":
        racelinenp = np.loadtxt(raceline_file,dtype=float, skiprows=1,delimiter=",")
        diffnorms = np.linalg.norm(racelinenp[1:] - racelinenp[0:-1], axis=1, ord=2)
        racelinedistsnp = np.hstack([np.zeros(1), np.cumsum(diffnorms)])
    else:
        raise ValueError("Only .json and .csv extensions are supported")
    racelinedists = torch.from_numpy(racelinedistsnp).double().to(device)
    raceline = torch.stack( [ torch.from_numpy(racelinenp[:,0]),\
                                     torch.from_numpy(racelinenp[:,1]),\
                                     torch.from_numpy(racelinenp[:,2]),\
                                     torch.ones_like(torch.from_numpy(racelinenp[:,0]))], dim=0).double().to(device)

    return racelinedists, raceline