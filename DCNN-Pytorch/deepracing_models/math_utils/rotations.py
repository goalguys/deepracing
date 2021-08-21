import torch
import numpy as np

def pointDirectionToPose(positions : torch.Tensor, forward_vectors : torch.Tensor, right_vectors : torch.Tensor):
    if positions.ndim!=2 or positions.shape[1]!=3:
        raise ValueError("Invalid input shape for positions. positions must have shape [N x 3], but got shape: " + str(positions.shape))
    if forward_vectors.ndim!=2 or forward_vectors.shape[1]!=3:
        raise ValueError("Invalid input shape for forward_vectors. forward_vectors must have shape [N x 3], but got shape: " + str(forward_vectors.shape))
    if right_vectors.ndim!=2 or right_vectors.shape[1]!=3:
        raise ValueError("Invalid input shape for right_vectors. right_vectors must have shape [N x 3], but got shape: " + str(right_vectors.shape))
    npoints = positions.shape[0]
    poses = torch.eye(4, dtype=positions.dtype, device=positions.device).unsqueeze(0).repeat(npoints,1,1)
    z = forward_vectors
    x = -1.0*right_vectors
    y = torch.cross(z,x,dim=1)

    poses[:,0:3,0:3] = torch.stack([x,y,z],dim=1).transpose(1,2)
    poses[:,0:3,3] = positions

    return poses

def quaternionToMatrix(quaternions: torch.Tensor):
    if quaternions.ndim == 1:
        return quaternionToMatrix(quaternions.unsqueeze(0))[0]
    elif quaternions.ndim == 2:
        if quaternions.shape[1]!=4:
            raise ValueError("Invalid input shape. input must be eiter a single quaternion (size 4) or a batch of quaternions [N x 4]")
    else:
        raise ValueError("Invalid input shape. input must be eiter a single quaternion (size 4) or a batch of quaternions [N x 4]")

    Nquats = quaternions.shape[0]
    norms = torch.norm(quaternions, p=2, dim=1)
    if not torch.allclose(norms, torch.ones_like(norms)):
        print(quaternions)
        raise ValueError("input quaternions must be normalized")

    qi = quaternions[:,0]
    qj = quaternions[:,1]
    qk = quaternions[:,2]
    qw = quaternions[:,3]

    qtilde = quaternions[:,0:3]
    I3 = torch.eye(3, dtype=qtilde.dtype, device=qtilde.device).unsqueeze(0).expand(Nquats,3,3)
    Q = torch.zeros_like(I3)

    Q[:,0,1] = -qk
    Q[:,0,2] = qj

    Q[:,1,0] = qk
    Q[:,1,2] = -qi

    Q[:,2,0] = -qj
    Q[:,2,1] = qi


    qtilde_unsqueeze = qtilde.unsqueeze(2)


    dots =  torch.sum(qtilde*qtilde, dim=1)
    a = (torch.square(qw) - dots)[:,None,None]*I3

    b = 2.0*torch.matmul(qtilde_unsqueeze, qtilde_unsqueeze.transpose(1,2))

    c = 2*qw[:,None,None]*Q

    return a + b + c