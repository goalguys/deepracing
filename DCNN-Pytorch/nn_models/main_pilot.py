import cv2
import numpy as np
import nn_models
import data_loading.image_loading as il
import nn_models.Models as models
import data_loading.data_loaders as loaders
import numpy.random
import torch, random
import torch.nn as nn 
import torch.optim as optim
from tqdm import tqdm as tqdm
import pickle
from datetime import datetime
import os
import string
import argparse
import torchvision.transforms as transforms
def run_epoch(network, criterion, optimizer, trainLoader, use_gpu):
    network.train()  # This is important to call before training!
    cum_loss = 0.0
    batch_size = trainLoader.batch_size
    num_samples=0
    t = tqdm(enumerate(trainLoader))
    for (i, (inputs, labels)) in t:
        optimizer.zero_grad()
        labels = labels[:,0]
        if use_gpu>=0:
            inputs = inputs.cuda(use_gpu)
            labels = labels.cuda(use_gpu)
        # Forward pass:
        outputs = network(inputs)
        loss = criterion(outputs, labels)

        # Backward pass:
        loss.backward() 

        # Weight and bias updates.
        optimizer.step()

        # logging information
        loss_ = loss.item()
        cum_loss += loss_
        num_samples += batch_size
        t.set_postfix(cum_loss = cum_loss/num_samples)
 

def train_model(network, criterion, optimizer, trainLoader, directory, n_epochs = 10, use_gpu = False):
    if use_gpu>=0:
        criterion = criterion.cuda(use_gpu)
    # Training loop.
    if(not os.path.isdir(directory)):
        os.makedirs(directory)
    for epoch in range(n_epochs):
        print("Epoch %d of %d" %((epoch+1),n_epochs) )
        run_epoch(network, criterion, optimizer, trainLoader, use_gpu)
        log_path = os.path.join(directory,"_epoch"+str(epoch+1)+ ".model")
        torch.save(network.state_dict(), log_path)
def load_config(filepath):
    rtn = dict()
    rtn['batch_size']='1'
    rtn['gpu']='-1'
    rtn['epochs']='10'
    rtn['momentum']='0.0'
    rtn['file_prefix']=''
    rtn['load_files']=''
    rtn['use_float32']=''
    rtn['label_scale']='100.0'
    rtn['num_workers']='0'
    rtn['checkpoint_file']=''
    rtn['load_pickles']=''

    config_file = open(filepath)
    lines = config_file.readlines()
    vals = []
    for line in lines:
        key, value = line.split(",")
        key = key.replace("\n","")
        value = value.replace("\n","")
        rtn[key]=value
    return rtn
def main():
    parser = argparse.ArgumentParser(description="Steering prediction with PilotNet")
    parser.add_argument("--config_file", type=str, required=True, help="Config file to use")
    args = parser.parse_args()
    config_fp = args.config_file
    config = load_config(config_fp)
    #mandatory parameters
    learning_rate = float(config['learning_rate'])
    annotation_file = config['annotation_file']
    dataset_dir = os.path.dirname(annotation_file)
    dataset_file = os.path.basename(annotation_file)
    prefix, _ = dataset_file.split(".")

    #optional parameters
    file_prefix = config['file_prefix']

    load_files = bool(config['load_files'])
    load_pickles = int(config['load_pickles'])

    momentum = float(config['momentum'])

    batch_size = int(config['batch_size'])
    gpu = int(config['gpu'])
    
    epochs = int(config['epochs'])
    num_workers = int(config['num_workers'])

    
    

    config_file = os.path.basename(config_fp)
    print(config_file)
    config_file_name, _ = config_file.split(".")
    output_dir = config_file_name.replace("\n","")
    if(not os.path.isdir(output_dir)):
        os.mkdir(output_dir)
    network = models.PilotNet()
    if(gpu>=0):
        network = network.cuda(gpu)
    print(network)
    size=(66,200)
    trainset = loaders.F1ImageDataset(annotation_file, size)

    
   # trainset.read_files()
    
    if(load_files):
        trainset.loadFiles()
        trainset.writePickles()
    elif():  
        trainset.loadPickles()
    '''
    mean,stdev = trainset.statistics()
    print(mean)
    print(stdev)
    img_transformation = transforms.Compose([transforms.Normalize(mean,stdev)])
    trainset.img_transformation = img_transformation
    '''
    trainLoader = torch.utils.data.DataLoader(trainset, batch_size = batch_size, shuffle = True, num_workers = num_workers)
    print(trainLoader)
    #Definition of our loss.
    criterion = nn.MSELoss()

    # Definition of optimization strategy.
    optimizer = optim.SGD(network.parameters(), lr = learning_rate, momentum=momentum)
    config['image_transformation'] = None
    config_dump = open(os.path.join(output_dir,"config.pkl"), 'w+b')
    pickle.dump(config,config_dump)
    config_dump.close()
    train_model(network, criterion, optimizer, trainLoader, output_dir, n_epochs = epochs, use_gpu = gpu)

if __name__ == '__main__':
    main()