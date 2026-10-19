import os
import torch
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt

try:
    from paths import MODELS
except ImportError:
    from src.paths import MODELS

from models.pinn import PINN

def compute_pde_loss(model, x, t, alpha, alpha_raw):
    x.requires_grad_(True)
    t.requires_grad_(True)
    
    u = model(x, t, alpha)
    
    u_t = torch.autograd.grad(u, t, grad_outputs=torch.ones_like(u), create_graph=True)[0]
    u_x = torch.autograd.grad(u, x, grad_outputs=torch.ones_like(u), create_graph=True)[0]
    u_xx = torch.autograd.grad(u_x, x, grad_outputs=torch.ones_like(u_x), create_graph=True)[0]
    
    f = u_t - alpha_raw * u_xx
    return torch.mean(f**2)

class BoundedReparametrizedPINN(nn.Module):
    def __init__(self, log_alpha_mean, log_alpha_std):
        super().__init__()
        self.pinn = PINN(layers=[3, 64, 64, 64, 64, 1])
        self.log_alpha_mean = log_alpha_mean
        self.log_alpha_std = log_alpha_std
        
    def forward(self, x, t, alpha_raw):
        x_scaled = 2 * x - 1
        t_scaled = 2 * t - 1
        log_alpha = torch.log10(alpha_raw)
        alpha_scaled = (log_alpha - self.log_alpha_mean) / self.log_alpha_std
        
        N = self.pinn(x_scaled, t_scaled, alpha_scaled)
        
        # Bounded multiplier: 1 - exp(-t * 5.0)
        bounded_t = 1.0 - torch.exp(-t * 5.0)
        
        out = torch.sin(np.pi * x) + x * (1.0 - x) * bounded_t * N
        return out

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    fno_path = str(MODELS / 'fno2d_heat.pt')
    
    checkpoint = torch.load(fno_path, map_location=device)
    log_alpha_mean = checkpoint['log_alpha_mean']
    log_alpha_std = checkpoint['log_alpha_std']
    
    model = BoundedReparametrizedPINN(log_alpha_mean, log_alpha_std).to(device)
    
    N_f = 20000
    
    def sample_raw_points(N):
        x = torch.rand(N, 1, device=device)
        t = torch.rand(N, 1, device=device)
        log_alpha = torch.rand(N, 1, device=device) * (-2.0)
        alpha_raw = 10**log_alpha
        return x, t, alpha_raw
        
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    epochs = 1000
    print(f"Training Parametric PINN ExpD on {device}...")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        
        x_f, t_f, alpha_f = sample_raw_points(N_f)
        loss_f = compute_pde_loss(model, x_f, t_f, alpha_f, alpha_f)
        
        loss = loss_f
        loss.backward()
        optimizer.step()
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch:5d} | Loss: {loss.item():.4e}", flush=True)
            
    optimizer_lbfgs = torch.optim.LBFGS(model.parameters(), max_iter=500, line_search_fn="strong_wolfe")
    
    def closure():
        optimizer_lbfgs.zero_grad()
        x_f, t_f, alpha_f = sample_raw_points(N_f)
        loss = compute_pde_loss(model, x_f, t_f, alpha_f, alpha_f)
        loss.backward()
        return loss

    print("Starting L-BFGS phase...", flush=True)
    optimizer_lbfgs.step(closure)
    print("L-BFGS finished.")
    
    torch.save({
        'model_state_dict': model.state_dict(),
        'log_alpha_mean': log_alpha_mean,
        'log_alpha_std': log_alpha_std
    }, str(MODELS / 'pinn_expD.pt'))
    print("PINN ExpD model saved.")
    
if __name__ == '__main__':
    main()
