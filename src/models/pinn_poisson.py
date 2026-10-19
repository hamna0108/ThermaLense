import torch
import torch.nn as nn
import numpy as np

class HardPINNPoisson(nn.Module):
    """
    Physics-Informed Neural Network for 2D Poisson with hard-constrained zero boundary conditions:
        u(x, y) = x * (1 - x) * y * (1 - y) * NN(x, y)
    Dirichlet boundary condition u = 0 on dOmega is identically zero for all network parameters.
    """
    def __init__(self, hidden_layers=[50, 50, 50, 50], activation=nn.Tanh()):
        super(HardPINNPoisson, self).__init__()
        dims = [2] + hidden_layers + [1]
        layers = []
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i+1]))
            if i < len(dims) - 2:
                layers.append(activation)
        self.net = nn.Sequential(*layers)
        
        # Xavier initialization
        for m in self.net.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, xy):
        """
        xy: (N, 2) tensor of (x, y) coordinates
        Returns: (N, 1) predicted field u
        """
        x = xy[:, 0:1]
        y = xy[:, 1:2]
        envelope = x * (1.0 - x) * y * (1.0 - y)
        nn_out = self.net(xy)
        return envelope * nn_out

    def compute_residual(self, xy, f_vals):
        """
        Computes PDE residual -nabla^2 u - f = -(u_xx + u_yy) - f using autograd.
        xy: (N, 2) with requires_grad=True
        f_vals: (N, 1) or callable
        """
        u = self.forward(xy)
        grad_u = torch.autograd.grad(
            u, xy,
            grad_outputs=torch.ones_like(u),
            create_graph=True,
            retain_graph=True
        )[0]
        
        u_x = grad_u[:, 0:1]
        u_y = grad_u[:, 1:2]
        
        u_xx = torch.autograd.grad(
            u_x, xy,
            grad_outputs=torch.ones_like(u_x),
            create_graph=True,
            retain_graph=True
        )[0][:, 0:1]
        
        u_yy = torch.autograd.grad(
            u_y, xy,
            grad_outputs=torch.ones_like(u_y),
            create_graph=True,
            retain_graph=True
        )[0][:, 1:2]
        
        neg_lap = -(u_xx + u_yy)
        residual = neg_lap - f_vals
        return residual, u
