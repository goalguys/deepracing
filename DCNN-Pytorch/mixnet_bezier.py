import argparse
import tempfile
import comet_ml
import deepracing_models.math_utils.bezier, deepracing_models.math_utils
from deepracing_models.nn_models.TrajectoryPrediction import BezierMixNet
from deepracing_models.data_loading import file_datasets as FD 
import torch, torch.optim, torch.nn.functional as F
from torch.optim.lr_scheduler import ExponentialLR
import torch.utils.data as torchdata
import yaml
import os
import io
import numpy as np
import pickle as pkl
import tqdm
import matplotlib.figure
import matplotlib.pyplot as plt
import json
from scipy.spatial.transform import Rotation
from mix_net.src.mix_net_dataset import MixNetDataset
import shutil
# k=3
# d = 2
# num = 1

parser = argparse.ArgumentParser(description="Train Bezier version of MixNet")
parser.add_argument("config_file", type=str,  help="Configuration file to load")
parser.add_argument("--tempdir", type=str, default=None, help="Temporary directory to save model files before uploading to comet. Default is to use tempfile module to generate one")

args = parser.parse_args()
argdict : dict = vars(args)
config_file = argdict["config_file"]
with open(config_file, "r") as f:
    allconfig : dict = yaml.load(f, Loader=yaml.SafeLoader)
dataconfig = allconfig["data"]
netconfig = allconfig["net"]
trainerconfig = allconfig["trainer"]



#bagsdir = "/media/trent/T7/bags/deepracingbags/offsetlines"
dsetfiles = dataconfig["filepaths"]
dsets = []
dsetconfigs = []
numsamples_prediction = None
for dsetmetadatafile in dsetfiles:
    with open(dsetmetadatafile, "r") as f:
        dsetconfig = yaml.load(f, Loader=yaml.SafeLoader)
    if numsamples_prediction is None:
        numsamples_prediction = dsetconfig["numsamples_prediction"]
    elif numsamples_prediction!=dsetconfig["numsamples_prediction"]:
        raise ValueError("All datasets must have the same number of prediction points. " + \
                         "Dataset at %s has prediction length %d, but previous dataset " + \
                         "has prediction length %d" % (dsetmetadatafile, dsetconfig["numsamples_prediction"], numsamples_prediction))
    dsetconfigs.append(dsetconfig)
    dsetdir = os.path.dirname(dsetmetadatafile)
    labelfile = dsetconfig["train_data"]
    with open(os.path.join(dsetdir, labelfile), "rb") as f:
        base, ext = os.path.splitext(labelfile)
        if ext==".pkl":
            data : dict = pkl.load(f)
        elif ext==".npz":
            datanp = np.load(f, allow_pickle=True)
            data : dict = {k : datanp[k].copy() for k in datanp.keys()}
            print(data.keys())
        else:
            raise ValueError("Unknown extension %s" % (ext,))
    dsets.append(MixNetDataset(data, 0.0, 31, dsetconfig["trackname"]))
batch_size = trainerconfig["batch_size"]
gpu_index=trainerconfig["gpu_index"]
cuda=gpu_index>=0
netconfig["gpu_index"]=gpu_index
dataloader = torchdata.DataLoader(torchdata.ConcatDataset(dsets), batch_size=batch_size, pin_memory=cuda, shuffle=True)#, collate_fn=dsets[0].collate_fn)
net : BezierMixNet = BezierMixNet(netconfig).double()
lossfunc = torch.nn.MSELoss().double()
if cuda:
    net = net.cuda(gpu_index)
    lossfunc = lossfunc.cuda(gpu_index)
firstparam = next(net.parameters())
dtype = firstparam.dtype
device = firstparam.device
nesterov = trainerconfig["nesterov"]
lr = float(trainerconfig["learning_rate"])
betas = tuple(trainerconfig["betas"])
weight_decay = trainerconfig["weight_decay"]
optimizername = trainerconfig["optimizer"]
if optimizername=="SGD":
    momentum = trainerconfig["momentum"]
    optimizer = torch.optim.SGD(net.parameters(), lr = lr, momentum = momentum, nesterov=(nesterov and (momentum>0.0)))
elif optimizername=="Adam":
    optimizer = torch.optim.Adam(net.parameters(), lr = lr, betas=betas, weight_decay = weight_decay)
else:
    raise ValueError("Unknown optimizer %s" % (optimizername,))
scheduler = ExponentialLR(optimizer, 0.9999)


num_accel_sections : int = netconfig["acc_decoder"]["num_acc_sections"]
ratio = int(numsamples_prediction/num_accel_sections)
prediction_timestep = dsetconfigs[0]["timestep_prediction"]
prediction_totaltime = dsetconfigs[0]["predictiontime"]
time_per_segment = prediction_totaltime/num_accel_sections
net.train()
averageloss = 1E9
averagepositionloss = 1E9
averagevelocityloss = 1E9
averagevelocityerror = 1E9
fignumber = 1

numsamples_prediction = dsetconfigs[0]["numsamples_prediction"]
tsamp = torch.linspace(0.0, prediction_totaltime, dtype=dtype, device=device, steps=numsamples_prediction)
tswitchingpoints = torch.linspace(0.0, prediction_totaltime, dtype=dtype, device=device, steps=num_accel_sections+1)
dt = tswitchingpoints[1:] - tswitchingpoints[:-1]
kbezier = 4
kbeziervel = 3
project_name="mixnet-bezier"
api_key = os.getenv("COMET_API_KEY")
if api_key is not None:
    print(api_key)
    experiment = comet_ml.Experiment(workspace="electric-turtle", project_name=project_name, api_key=api_key)
else:
    experiment = None
    
experiment.log_asset(config_file, "config.yaml")
tempdirobj = None
tempdir = argdict["tempdir"]
if tempdir is None:
    tempdirobj = tempfile.TemporaryDirectory()
    tempdir = tempdirobj.name
for epoch in range(1, trainerconfig["epochs"]+1):
    totalloss = 0.0
    total_position_loss = 0.0
    total_velocity_loss = 0.0
    total_velocity_error = 0.0
    tq = tqdm.tqdm(enumerate(dataloader), desc="Yay")
    if epoch%10==0:
        
        netout = os.path.join(tempdir, "net.pt")
        torch.save(net.state_dict(), netout)
        experiment.log_asset(netout, "network_epoch_%d.pt" % (epoch,), copy_to_tmp=False)   

        optimizerout =  os.path.join(tempdir, "optimizer.pt")
        torch.save(optimizer.state_dict(), optimizerout)
        experiment.log_asset(optimizerout, "optimizer_epoch_%d.pt" % (epoch,), copy_to_tmp=False)
    for (i, datatuple) in tq:
        position_history, position_future, tangent_future, speed_future, angvel_future, fut_inds_batch, future_arclength, \
            left_bound_input, right_bound_input, \
                left_boundary_label, right_boundary_label, \
                    centerline_label, raceline_label, \
                        left_boundary_label_arclength, right_boundary_label_arclength, \
                            centerline_label_arclength, raceline_label_arclength, \
                                bcurves_r, tracknames = datatuple
        if cuda:
            position_history = position_history.cuda().type(dtype)
            position_future = position_future.cuda().type(dtype)
            speed_future = speed_future.cuda().type(dtype)
            angvel_future = angvel_future.cuda().type(dtype)
            future_arclength = future_arclength.cuda().type(dtype)
            left_bound_input = left_bound_input.cuda().type(dtype)
            right_bound_input = right_bound_input.cuda().type(dtype)
            left_boundary_label = left_boundary_label.cuda().type(dtype)
            right_boundary_label = right_boundary_label.cuda().type(dtype)
            centerline_label = centerline_label.cuda().type(dtype)
            raceline_label = raceline_label.cuda().type(dtype)
            left_boundary_label_arclength = left_boundary_label_arclength.cuda().type(dtype)
            right_boundary_label_arclength = right_boundary_label_arclength.cuda().type(dtype)
            centerline_label_arclength = centerline_label_arclength.cuda().type(dtype)
            raceline_label_arclength = raceline_label_arclength.cuda().type(dtype)
            bcurves_r = bcurves_r.cuda().type(dtype)
            tangent_future = tangent_future.cuda().type(dtype)
        else:
            position_history = position_history.cpu().type(dtype)
            position_future = position_future.cpu().type(dtype)
            speed_future = speed_future.cpu().type(dtype)
            angvel_future = angvel_future.cpu().type(dtype)
            left_bound_input = left_bound_input.cpu().type(dtype)
            future_arclength = future_arclength.cpu().type(dtype)
            right_bound_input = right_bound_input.cpu().type(dtype)
            left_boundary_label = left_boundary_label.cpu().type(dtype)
            right_boundary_label = right_boundary_label.cpu().type(dtype)
            centerline_label = centerline_label.cpu().type(dtype)
            raceline_label = raceline_label.cpu().type(dtype)
            left_boundary_label_arclength = left_boundary_label_arclength.cpu().type(dtype)
            right_boundary_label_arclength = right_boundary_label_arclength.cpu().type(dtype)
            centerline_label_arclength = centerline_label_arclength.cpu().type(dtype)
            raceline_label_arclength = raceline_label_arclength.cpu().type(dtype)
            bcurves_r = bcurves_r.cpu().type(dtype)
            tangent_future = tangent_future.cpu().type(dtype)
        currentbatchsize = int(position_history.shape[0])


        # print(tangent_future[:,0])
        (mix_out_, acc_out_) = net(position_history, left_bound_input, right_bound_input)
        one = torch.ones_like(speed_future[0,0])
        mix_out = torch.clamp(mix_out_, -0.5*one, 1.5*one)
        # + speed_future[:,0].unsqueeze(-1)
        acc_out = acc_out_ + speed_future[:,0].unsqueeze(-1)
        # acc_out = torch.clamp(acc_out_ + speed_future[:,0].unsqueeze(-1), 5.0*one, 110.0*one)
        

        coefs_inferred = torch.zeros(currentbatchsize, num_accel_sections, 4, dtype=acc_out.dtype, device=acc_out.device)
        coefs_inferred[:,0,0] = speed_future[:,0]
        coefs_inferred[:,0,[1,2]] = acc_out[:,[0,1]]
        coefs_inferred[:,1:,1] = acc_out[:,2:-1]
        coefs_inferred[:,-1,-1] = acc_out[:,-1]
        for j in range(coefs_inferred.shape[1]-1):
            coefs_inferred[:, j,-1] = coefs_inferred[:, j+1,0] = \
                0.5*(coefs_inferred[:, j,-2] + coefs_inferred[:, j+1,1])
            if kbeziervel>2:
                coefs_inferred[:, j+1,-2] = 2.0*coefs_inferred[:, j+1,1] - 2.0*coefs_inferred[:, j, -2] + coefs_inferred[:, j, -3]
        # coefs = coefs_inferred.view(currentbatchsize, -1).unsqueeze(-1)
        # speed_profile_out = torch.matmul(HugeMBatch, coefs).squeeze(-1)
        tstart_batch = tswitchingpoints[:-1].unsqueeze(0).expand(currentbatchsize, num_accel_sections)
        dt_batch = dt.unsqueeze(0).expand(currentbatchsize, num_accel_sections)
        teval_batch = tsamp.unsqueeze(0).expand(currentbatchsize, numsamples_prediction)
        speed_profile_out, idxbuckets = deepracing_models.math_utils.compositeBezerEval(tstart_batch, dt_batch, coefs_inferred.unsqueeze(-1), teval_batch)
        loss_velocity : torch.Tensor = (lossfunc(speed_profile_out, speed_future))*(prediction_timestep**2)
        experiment.log_metric("loss_velocity", loss_velocity.item())
        

        delta_r : torch.Tensor = future_arclength[:,-1] - future_arclength[:,0]
        future_arclength_rel : torch.Tensor = future_arclength - future_arclength[:,0,None]
        arclengths_out_s = future_arclength_rel/delta_r[:,None]
        known_control_points : torch.Tensor = torch.zeros_like(bcurves_r[:,0,:2])
        known_control_points[:,0] = position_future[:,0]
        known_control_points[:,1] = known_control_points[:,0] + (delta_r[:,None]/kbezier)*tangent_future[:,0]
        mixed_control_points = torch.sum(bcurves_r[:,:,2:]*mix_out[:,:,None,None], dim=1)
        predicted_bcurve = torch.cat([known_control_points, mixed_control_points], dim=1) 

        coefs_antiderivative = deepracing_models.math_utils.compositeBezierAntiderivative(coefs_inferred.unsqueeze(-1), dt_batch)
        arclengths_out, _ = deepracing_models.math_utils.compositeBezerEval(tstart_batch, dt_batch, coefs_antiderivative, teval_batch, idxbuckets=idxbuckets)
        loss_arclength = lossfunc(arclengths_out, future_arclength_rel)
        experiment.log_metric("loss_arclength", loss_arclength.item())

        Mbezierout = deepracing_models.math_utils.bezierM(arclengths_out_s, kbezier)
        predicted_position_future = torch.matmul(Mbezierout, predicted_bcurve)

        loss_position : torch.Tensor = lossfunc(predicted_position_future, position_future)
        experiment.log_metric("loss_position", loss_position.item())
        experiment.log_metric("velocity_error", loss_velocity.item()/(prediction_timestep**2))
        

        loss = loss_position + 2.0*loss_velocity #+ 10.0*loss_arclength #
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_position_loss += loss_position.item()
        total_velocity_loss += loss_velocity.item()
        total_velocity_error += loss_velocity.item()/(prediction_timestep**2)
        totalloss += loss.item()
        averageloss = totalloss/(i+1)
        averagepositionloss = total_position_loss/(i+1)
        averagevelocityloss = total_velocity_loss/(i+1)
        averagevelocityerror = total_velocity_error/(i+1)
        tq.set_postfix({"average position loss" : averagepositionloss, "average velocity error" : averagevelocityerror, "average velocity loss" : averagevelocityloss, "average loss" : averageloss, "epoch": epoch})

    if epoch%10==0:
        bcurves_r_cpu = bcurves_r[0].cpu()
        position_history_cpu = position_history[0].cpu()
        position_future_cpu = position_future[0].cpu()
        predicted_position_future_cpu = predicted_position_future[0].detach().cpu()
        left_bound_input_cpu = left_bound_input[0].cpu()
        right_bound_input_cpu = right_bound_input[0].cpu()
        left_bound_label_cpu = left_boundary_label[0].cpu()
        right_bound_label_cpu = right_boundary_label[0].cpu()
        centerline_label_cpu = centerline_label[0].cpu()
        raceline_label_cpu = raceline_label[0].cpu()
        predicted_bcurve_cpu = predicted_bcurve[0].detach().clone().cpu()
        fig : matplotlib.figure.Figure = plt.figure()
        scale_array = 5.0
        plt.plot(position_history_cpu[:,0], position_history_cpu[:,1], label="Position History")#, s=scale_array)
        plt.plot(position_history_cpu[0,0], position_history_cpu[0,1], "g*", label="Position History Start")
        plt.plot(position_history_cpu[-1,0], position_history_cpu[-1,1], "r*", label="Position History End")
        plt.scatter(position_future_cpu[:,0], position_future_cpu[:,1], label="Ground Truth Future", s=scale_array)
        plt.plot(predicted_position_future_cpu[:,0], predicted_position_future_cpu[:,1], label="Prediction")#, s=scale_array)
        plt.plot(centerline_label_cpu[:,0], centerline_label_cpu[:,1], label="Centerline Label")#, s=scale_array)
        plt.plot(raceline_label_cpu[:,0], raceline_label_cpu[:,1], label="Raceline Label")#, s=scale_array)
        plt.scatter(bcurves_r_cpu[0,:,0], bcurves_r_cpu[0,:,1], s=scale_array)
        plt.scatter(bcurves_r_cpu[1,:,0], bcurves_r_cpu[1,:,1], s=scale_array)
        plt.scatter(bcurves_r_cpu[2,:,0], bcurves_r_cpu[2,:,1], s=scale_array)
        plt.scatter(bcurves_r_cpu[3,:,0], bcurves_r_cpu[3,:,1], s=scale_array)
        plt.plot([],[], label="Boundaries", color="navy")#, s=scale_array)
        plt.legend()
        # plt.plot(left_bound_input_cpu[:,0], left_bound_input_cpu[:,1], label="Left Bound Input", color="navy")
        # plt.plot(right_bound_input_cpu[:,0], right_bound_input_cpu[:,1], label="Right Bound Input", color="navy")
        plt.plot(left_bound_label_cpu[:,0], left_bound_label_cpu[:,1], label="Left Bound Label", color="navy")#, s=scale_array)
        plt.plot(right_bound_label_cpu[:,0], right_bound_label_cpu[:,1], label="Right Bound Label", color="navy")#, s=scale_array)
        plt.axis("equal")
        # print(mix_out[0])
        # print(predicted_bcurve_cpu)
        # print(left_boundary_label_arclength[0].cpu())
        # print(right_boundary_label_arclength[0].cpu())
        # print(centerline_label_arclength[0].cpu())
        # print(raceline_label_arclength[0].cpu())
        # fig.savefig(os.path.join(tempdir, "plot.svg"))

        experiment.log_figure(figure_name="epoch_%d" % (epoch,), figure=fig)
        plt.close(fig=fig)
        # plt.show()
        # plt.show()
    # scheduler.step()

