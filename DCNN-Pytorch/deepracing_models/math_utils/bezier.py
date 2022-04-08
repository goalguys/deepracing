import numpy as np
import math
import torch, torch.nn
from scipy.special import comb as nChoosek
from deepracing_models.math_utils.fitting import pinv

def polynomialFormConversion(k : int, dtype=torch.float64, device=torch.device("cpu")):
    topolyform : torch.Tensor = torch.zeros((k+1,k+1), dtype=dtype, device=device)
    kfactorial : float = math.factorial(k)
    topolyform[0,0]=topolyform[-1,-1]=1.0
    for i in range(1, k+1):
        outerfactor = kfactorial/math.factorial(k-i)
        for j in range(0,i+1):
            topolyform[i,j]=outerfactor/(math.factorial(j)*math.factorial(i-j))
            if ((i+j)%2)!=0:
                topolyform[i,j]*=-1.0
            # else:
                # rtn[i,j]=1.0/(math.factorial(j)*math.factorial(i-j))
        # rtn[i]*=outerfactor
    tobezierform = torch.linalg.inv(topolyform)
    for i in range(0,k+1):
        for j in range(0,k+1):
            if j>i:
                tobezierform[i,j]=0.0
    return topolyform, tobezierform
def Mtk(k,n,t):
    return torch.pow(t,k)*torch.pow(1-t,(n-k))*nChoosek(n,k)
def bezierArcLength(control_points, d0=None, N=59, simpsonintervals=4 ):
    
    
    t=torch.stack([torch.linspace(0.0, 1.0, steps = simpsonintervals*N+1, dtype=control_points.dtype, device=control_points.device ) for i in range(control_points.shape[0])], dim=0)
    tsamp = t[:,[i*simpsonintervals for i in range(N+1)]]

    Mderiv, deriv = bezierDerivative(control_points, t=t, order=1)
    Mderivsamp = Mderiv[:,[i*simpsonintervals for i in range(N+1)],:]

    speeds = torch.norm(deriv,p=2,dim=2)
    

    #want [1.0, 4.0, 2.0, 4.0, 1.0] for simpsonintervals=4
    simpsonscale = torch.ones(speeds.shape[0], simpsonintervals+1, 1, dtype=speeds.dtype, device=speeds.device)
    simpsonscale[:,[i for i in range(1,simpsonintervals,2)]] = 4.0
    simpsonscale[:,[i for i in range(2,simpsonintervals,2)]] = 2.0
    Vmat = torch.stack([ torch.stack([speeds[i,simpsonintervals*j:simpsonintervals*(j+1)+1] for j in range(0, N)], dim=0)   for i in range(speeds.shape[0])], dim=0)

    relmoves = torch.matmul(Vmat, simpsonscale)[:,:,0]
    if d0 is None:
        d0_ = torch.zeros(speeds.shape[0], dtype=speeds.dtype, device=speeds.device).unsqueeze(1)
    else:
        d0_ = d0.unsqueeze(1)
    distances = torch.cat([d0_,d0_+torch.cumsum(relmoves,dim=1)/(3.0*simpsonintervals*N)],dim=1)
    
    speedsamp = speeds[:,[i*simpsonintervals for i in range(N+1)]]
    derivsamp = deriv[:,[i*simpsonintervals for i in range(N+1)]]
    return Mderivsamp, tsamp, derivsamp, speedsamp, distances
        

    
def bezierM(t,n):
    return torch.stack([Mtk(k,n,t) for k in range(n+1)],dim=2)
def evalBezier(M,control_points):
    return torch.matmul(M,control_points)
    
def bezierDerivative(control_points, t = None, M = None, order = 1 ):
    if (bool(t is not None) ^ bool(M is not None)):
        n = control_points.shape[1]-1
        if t is not None:
            Mderiv = bezierM(t,n-order)
        else:
            Mderiv = M
        pdiff =  control_points[:,1:] - control_points[:,:-1]
        for i in range(1,order):
            pdiff =  pdiff[:,1:] - pdiff[:,:-1]
        factor = torch.prod(torch.linspace(n,n-order+1,order))
        return Mderiv, factor*torch.matmul(Mderiv, pdiff)
    else:
        raise ValueError("One of t or M must be set, but not both")

def bezierLsqfit(points, n, t = None, M = None, built_in_lstq=False):
    if ((t is None) and (M is None)) or ((t is not None) and (M is not None)):
        raise ValueError("One of t or M must be set, but not both")
    if M is None:
        M_ = bezierM(t,n)
    else:
        M_ = M
    batch = M_.shape[0]
    if built_in_lstq:
        res = torch.linalg.lstsq(M_, points)
        return M_, res.solution
    else:
        return M_, torch.matmul(pinv(M_), points)

class BezierCurveModule(torch.nn.Module):
    def __init__(self, control_points, mask = None):
        super(BezierCurveModule, self).__init__()
        if mask is None:
            self.mask = [True for asdf in range(control_points.shape[0])]
        else:
            self.mask = mask
        self.control_points = torch.nn.ParameterList([ torch.nn.Parameter(control_points[i], requires_grad=self.mask[i]) for i in range(len(self.mask)) ])
    @staticmethod
    def lsqFit(s, pts, n, mask=None):
        assert(s.shape[0]==pts.shape[0])
        M, cntrlpoints = bezierLsqfit(pts, n, t=s)
        return M, BezierCurveModule(cntrlpoints[0], mask=mask)
    def allControlPoints(self):
        return torch.stack([p for p in self.control_points], dim=0).unsqueeze(0)
    def forward(self, M):
        points = self.allControlPoints()
        return torch.matmul(M, points)