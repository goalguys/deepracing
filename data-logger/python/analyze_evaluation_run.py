
import TimestampedPacketMotionData_pb2, TimestampedPacketCarTelemetryData_pb2
import argparse
import argcomplete
import os
import numpy as np
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
import matplotlib.pyplot as plt
import deepracing.protobuf_utils as proto_utils
import scipy
import scipy.spatial
import deepracing.evaluation_utils
def analyzedatasets(main_dir,subdirs,prefix):
    mtbf= np.zeros(runmax)
    mdbf= np.zeros(runmax)
    mean_failure_scores = np.zeros(runmax)
    num_failures = np.zeros(runmax)
    for (i, dset) in enumerate(subdirs):
        print("Running dataset %d for %s:"%(i+1, prefix), flush=True)
        dset_dir = os.path.join(main_dir, dset)
        failurescores, failuretimes, failuretimediffs, failuredistances, failuredistancediffs \
            = deepracing.evaluation_utils.evalDataset(dset_dir,\
            "../tracks/Australia_innerlimit.track", "../tracks/Australia_outerlimit.track", plot=plot)
        mtbf[i] = np.mean(failuretimediffs)
        mdbf[i] = np.mean(failuredistancediffs)
        mean_failure_scores[i] = np.mean(failurescores)
        num_failures[i] = float(failuredistances.shape[0])
        # print( "Number of failures: %d" % ( num_failures[i] ) )
        # print( "Mean time between failures: %f" % ( mtbf[i] ) )
        # print( "Mean failure distance: %f" % ( mean_failure_distances[i] ) )
    print("\n")
    print("Results for %s:"%(prefix))
    print( "Average Number of failures: %d" % ( np.mean(num_failures) ) , flush=True)
    print( "Overall Mean time between failures: %f" % ( np.mean(mtbf) ) , flush=True)
    print( "Overall Mean distance between failures: %f" % ( np.mean(mdbf) ) , flush=True)
    print( "Overall Mean failure score: %f" % (  np.mean(mean_failure_scores)  ) , flush=True)
    print("\n")
parser = argparse.ArgumentParser()
parser.add_argument("main_dir", help="Directory of the evaluation datasets",  type=str)
args = parser.parse_args()
main_dir = args.main_dir

runmax = 5
plot=False
bezier_dsets = ["bezier_predictor_run%d" % i for i in range(1,runmax+1)]
waypoint_dsets = ["waypoint_predictor_run%d" % i for i in range(1,runmax+1)]
cnnlstm_dsets = ["cnnlstm_run%d" % i for i in range(1,runmax+1)]
pilotnet_dsets = ["pilotnet_run%d" % i for i in range(1,runmax+1)]
print(bezier_dsets)
print(waypoint_dsets)
print(cnnlstm_dsets)
print(pilotnet_dsets)




analyzedatasets(main_dir,bezier_dsets,"Bezier Predictor")
analyzedatasets(main_dir,waypoint_dsets,"Waypoint Predictor")
analyzedatasets(main_dir,cnnlstm_dsets,"CNNLSTM")
analyzedatasets(main_dir,pilotnet_dsets,"PilotNet")

