
import torch
import torch.utils
import torch.utils.data
import numpy as np
import typing
import deepracing_models
import deepracing_models.math_utils
from deepracing_models.math_utils import SimplePathHelper
from path_server.smooth_path_helper import SmoothPathHelper
from tqdm import tqdm
import torch.jit

class TrajectoryPredictionDataset(torch.utils.data.Dataset):
    def __init__(self,\
                 target_vehicle_positions : np.ndarray,\
                 target_vehicle_velocities : np.ndarray,\
                 inner_boundary_helper : SmoothPathHelper,\
                 inner_boundary_corresponding_arclengths : np.ndarray,\
                 outer_boundary_helper : SmoothPathHelper,\
                 outer_boundary_corresponding_arclengths : np.ndarray,\
                 centerline_helper : SmoothPathHelper,\
                 centerline_corresponding_arclengths : np.ndarray,\
                 raceline_helper : SmoothPathHelper,\
                 raceline_corresponding_arclengths : np.ndarray,\
                 ego_vehicle_positions : np.ndarray = None,\
                 ego_vehicle_velocities : np.ndarray = None,\
                 ego_vehicle_accelerations : typing.Union[np.ndarray,None] = None,\
                 target_vehicle_accelerations : typing.Union[np.ndarray,None] = None,\
                 orient_to_inner_boundary : bool = False):
        self.target_vehicle_positions : np.ndarray = target_vehicle_positions.copy()
        self.target_vehicle_velocities : np.ndarray = target_vehicle_velocities.copy()
        self.inner_boundary_helper : SmoothPathHelper = inner_boundary_helper
        self.outer_boundary_helper : SmoothPathHelper = outer_boundary_helper
        self.centerline_helper : SmoothPathHelper = centerline_helper
        self.raceline_helper : SmoothPathHelper = raceline_helper
        self.inner_boundary_corresponding_arclengths = inner_boundary_corresponding_arclengths.copy()
        self.outer_boundary_corresponding_arclengths = outer_boundary_corresponding_arclengths.copy()
        self.centerline_corresponding_arclengths = centerline_corresponding_arclengths.copy()
        self.raceline_corresponding_arclengths = raceline_corresponding_arclengths.copy()
        if (ego_vehicle_accelerations is None) and (target_vehicle_accelerations is not None):
            raise ValueError("target_vehicle_accelerations was provided, but not ego_vehicle_accelerations. Must provide either both or neither")
        if (target_vehicle_accelerations is None) and (ego_vehicle_accelerations is not None):
            raise ValueError("ego_vehicle_accelerations was provided, but not target_vehicle_accelerations. Must provide either both or neither")
        if (ego_vehicle_accelerations is not None) and (target_vehicle_accelerations is not None):
            self.ego_vehicle_accelerations : np.ndarray = ego_vehicle_accelerations.copy()
            self.target_vehicle_accelerations : np.ndarray = target_vehicle_accelerations.copy()
        else:
            self.ego_vehicle_accelerations = None
            self.target_vehicle_accelerations = None

        if (ego_vehicle_velocities is None) and (ego_vehicle_positions is not None):
            raise ValueError("ego_vehicle_positions was provided, but not ego_vehicle_velocities. Must provide either both or neither")
        if (ego_vehicle_positions is None) and (ego_vehicle_velocities is not None):
            raise ValueError("ego_vehicle_velocities was provided, but not ego_vehicle_positions. Must provide either both or neither")
        if (ego_vehicle_positions is not None) and (ego_vehicle_velocities is not None):
            self.ego_vehicle_positions : np.ndarray = ego_vehicle_positions.copy()
            self.ego_vehicle_velocities : np.ndarray = ego_vehicle_velocities.copy()
        else:
            self.ego_vehicle_positions = None
            self.ego_vehicle_velocities = None
        self.orient_to_inner_boundary = orient_to_inner_boundary
        rforward = 400.0
        dr = 20.0
        self.rdelta : np.ndarray = np.arange(0.0, rforward+dr, step=dr, dtype=target_vehicle_positions.dtype)     
    def __len__(self):
        return self.target_vehicle_positions.shape[0]-100
    def __getitem__(self, index):
        idxnow = index + 50
        ihistorystart = idxnow - 30
        ihistoryend = idxnow + 1
        ifutureend = idxnow + 51

        target_position_history : np.ndarray = self.target_vehicle_positions[ihistorystart:ihistoryend]
        target_velocity_history : np.ndarray = self.target_vehicle_velocities[ihistorystart:ihistoryend]
        target_positions_future : np.ndarray = self.target_vehicle_positions[idxnow:ifutureend]
        p0 : np.ndarray = target_positions_future[0]

        r_ib : np.ndarray = self.rdelta + self.inner_boundary_corresponding_arclengths[idxnow]
        r_ob : np.ndarray = self.rdelta + self.outer_boundary_corresponding_arclengths[idxnow]

        inner_boundary_input : np.ndarray = self.inner_boundary_helper.point(r_ib)
        outer_boundary_input : np.ndarray = self.outer_boundary_helper.point(r_ob)

        raceline_label : np.ndarray = self.raceline_helper.point(self.raceline_corresponding_arclengths[idxnow:ifutureend])
        centerline_label : np.ndarray = self.centerline_helper.point(self.centerline_corresponding_arclengths[idxnow:ifutureend])
        inner_boundary_label : np.ndarray = self.inner_boundary_helper.point(self.inner_boundary_corresponding_arclengths[idxnow:ifutureend])
        outer_boundary_label : np.ndarray = self.outer_boundary_helper.point(self.outer_boundary_corresponding_arclengths[idxnow:ifutureend])
        
        
        if self.orient_to_inner_boundary:
            tangent0 : np.ndarray = self.inner_boundary_helper.direction(float(r_ib[0]))
        else:    
            vel0 : np.ndarray = target_velocity_history[-1]
            tangent0 : np.ndarray = vel0/np.linalg.norm(vel0, ord=2, axis=0)

        rotmat : np.ndarray = np.stack([tangent0, tangent0[[1,0]]*np.asarray([-1.0, 1.0], dtype=tangent0.dtype)], axis=1)

        rotmatinv : np.ndarray = np.transpose(rotmat)
        translationinv : np.ndarray = rotmatinv @ -p0


        outdict : dict = dict()
        outdict["target_position_history"] = (rotmatinv @ target_position_history.T).T + translationinv
        outdict["target_position_future"] = (rotmatinv @ target_positions_future.T).T + translationinv
        outdict["target_velocity_history"] = (rotmatinv @ target_velocity_history.T).T
        if self.ego_vehicle_positions is not None:
            ego_position_history : np.ndarray = self.ego_vehicle_positions[ihistorystart:ihistoryend]
            ego_velocity_history : np.ndarray = self.ego_vehicle_velocities[ihistorystart:ihistoryend]
            outdict["ego_position_history"] = (rotmatinv @ ego_position_history.T).T + translationinv
            outdict["ego_velocity_history"] = (rotmatinv @ ego_velocity_history.T).T
        outdict["inner_boundary_input"] = (rotmatinv @ inner_boundary_input.T).T + translationinv
        outdict["outer_boundary_input"] = (rotmatinv @ outer_boundary_input.T).T + translationinv
        outdict["raceline_label"] = (rotmatinv @ raceline_label.T).T + translationinv
        outdict["centerline_label"] = (rotmatinv @ centerline_label.T).T + translationinv
        outdict["inner_boundary_label"] = (rotmatinv @ inner_boundary_label.T).T + translationinv
        outdict["outer_boundary_label"] = (rotmatinv @ outer_boundary_label.T).T + translationinv
        if self.target_vehicle_accelerations is not None:
            ego_acceleration_history : np.ndarray = self.ego_vehicle_accelerations[ihistorystart:ihistoryend]
            target_acceleration_history : np.ndarray = self.target_vehicle_accelerations[ihistorystart:ihistoryend]
            outdict["ego_acceleration_history"] = (rotmatinv @ ego_acceleration_history.T).T
            outdict["target_acceleration_history"] = (rotmatinv @ target_acceleration_history.T).T
        # outdict["trackname"]=self.trackname
        return outdict
        
        