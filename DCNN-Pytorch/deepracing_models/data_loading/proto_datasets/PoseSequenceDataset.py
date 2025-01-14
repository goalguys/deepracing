
import scipy
import scipy.linalg as la
import skimage
import PIL
from PIL import Image as PILImage
import TimestampedPacketMotionData_pb2
import PoseSequenceLabel_pb2
import TimestampedImage_pb2
import Vector3dStamped_pb2
import FrameId_pb2
import Pose3d_pb2
import argparse
import os
import google.protobuf.json_format
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import bisect
import scipy.interpolate
import deepracing.pose_utils
from deepracing.protobuf_utils import getAllImageFilePackets, getAllMotionPackets, getAllSequenceLabelPackets, labelPacketToNumpy
import numpy as np
import torch
from torch.utils.data import Dataset
import skimage
import skimage.io
import torchvision.transforms as transforms
from skimage.transform import resize
import time
import shutil
from tqdm import tqdm as tqdm
from deepracing.imutils import resizeImage as resizeImage
from deepracing.imutils import readImage as readImage
from deepracing.backend import MultiAgentLabelLMDBWrapper, ImageLMDBWrapper
import cv2
import random
from scipy.spatial.transform import Rotation as Rot
from scipy.spatial.transform import RotationSpline as RotSpline
from Pose3d_pb2 import Pose3d
from typing import List
import torchvision.transforms as T
import torchvision.transforms.functional as F
from deepracing_models.data_loading.image_transforms import IdentityTransform
import json
import scipy.interpolate
from scipy.interpolate import make_lsq_spline, BSpline

def sensibleKnots(t, degree):
    numsamples = t.shape[0]
    knots = [ t[int(numsamples/4)], t[int(numsamples/2)], t[int(3*numsamples/4)] ]
    knots = np.r_[(t[0],)*(degree+1),  knots,  (t[-1],)*(degree+1)]
    return knots

def LabelPacketSortKey(packet):
    return packet.car_pose.session_time
def pbPoseToTorch(posepb : Pose3d):
    position_pb = posepb.translation
    rotation_pb = posepb.rotation
    pose = torch.eye(4).double()
    pose[0:3,0:3] = torch.from_numpy( Rot.from_quat( np.array([ rotation_pb.x,rotation_pb.y,rotation_pb.z,rotation_pb.w ], dtype=np.float64 ) ).as_matrix() ).double()
    pose[0:3,3] = torch.from_numpy( np.array( [ position_pb.x, position_pb.y, position_pb.z], dtype=np.float64 )  ).double()

class PoseSequenceDataset(Dataset):
    def __init__(self, image_db_wrapper : ImageLMDBWrapper, label_db_wrapper : MultiAgentLabelLMDBWrapper, keyfile : str, context_length : int, image_size : np.ndarray,  position_indices : np.ndarray,  extra_transforms : list = []):
        super(PoseSequenceDataset, self).__init__()
        self.image_db_wrapper : ImageLMDBWrapper = image_db_wrapper
        self.label_db_wrapper : MultiAgentLabelLMDBWrapper = label_db_wrapper
        self.image_size = image_size
        self.context_length = context_length
        self.totensor = transforms.ToTensor()
        with open(keyfile,'r') as filehandle:
            keystrings = filehandle.readlines()
            self.db_keys = [keystring.replace('\n','') for keystring in keystrings]
        self.num_images = len(self.db_keys)
        self.position_indices = position_indices
        self.transforms = [IdentityTransform()] + extra_transforms
    def __len__(self):
        return (self.num_images - self.context_length - 1)*len(self.transforms)
    def __getitem__(self, input_index):
        index = int(input_index%self.num_images)
        label_key = self.db_keys[index]
        label_key_idx = int(label_key.split("_")[1])
        images_start = label_key_idx - self.context_length + 1
        images_end = label_key_idx + 1
        packetrange = range(images_start, images_end)
        keys = ["image_%d" % (i,) for i in packetrange]
        assert(keys[-1]==label_key)

        label = self.label_db_wrapper.getMultiAgentLabel(keys[-1])
        assert(keys[-1]+".jpg"==label.image_tag.image_file)
        posespb = label.ego_agent_trajectory.poses
        rtn_session_times = np.array([p.session_time for p in posespb], dtype=np.float64)
        egopose = np.eye(4,dtype=np.float64)
        egopose[0:3,3] = np.array([label.ego_agent_pose.translation.x, label.ego_agent_pose.translation.y, label.ego_agent_pose.translation.z], dtype=np.float64)
        egopose[0:3,0:3] = Rot.from_quat(np.array([label.ego_agent_pose.rotation.x, label.ego_agent_pose.rotation.y, label.ego_agent_pose.rotation.z, label.ego_agent_pose.rotation.w], dtype=np.float64)).as_matrix()

        egopositions = np.array([ [p.translation.x, p.translation.y, p.translation.z]  for p in posespb  ], dtype=np.float64)

                
        transform = self.transforms[int(input_index/self.num_images)]
        images_pil = [ transform( F.resize( PILImage.fromarray( self.image_db_wrapper.getImage(key) ), self.image_size, interpolation=PIL.Image.LANCZOS) ) for key in keys ]
        images_torch = torch.stack( [ self.totensor(img) for img in images_pil ] )



        return {"images": images_torch, "ego_pose": egopose, "session_times": rtn_session_times, "ego_future_positions": egopositions[:,self.position_indices], "image_index": packetrange[-1]}