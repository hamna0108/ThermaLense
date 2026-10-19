import sys, os
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_dir = os.path.join(base_dir, "src")
exp_dir = os.path.abspath(os.path.dirname(__file__))
for p in [base_dir, src_dir, exp_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from paths import DATASETS, MODELS, EXP_MODELS, PLOTS
import torch
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt

from models.pinn import PINN

def compute_pde_loss(model, x, t, alpha, alpha_raw):
    x.requires_grad_(True)
    t.requires_grad_(True)
    
    u = model(x, t, alpha)
    
    u_t = torch.autograd.grad(u, t, grad_outputs=torch.ones_like(u), create_graph=True)[0]
    u_x = torch.autograd.grad(u, x, grad_outputs=torch.ones_like(u), create_graph=True)[0]
    u_xx = torch.autograd.grad(u_x, x, grad_outputs=torch.ones_like(u_x), create_graph=True)[0]
    
    # Note: t is scaled from [0, 1] to [-1, 1], so dt_scaled = 2 * dt_raw => dt_raw = dt_scaled / 2.
    # Therefore, d/dt_raw = 2 * d/dt_scaled. Same for x.
    # Actually, if x, t are raw in [0, 1], no scaling is needed for autograd! 
    # But if the network expects scaled inputs, we must be careful with chain rule.
    # It is easier to input raw x, t, alpha to a wrapper, then scale inside, and autograd w.r.t raw!
    
    # Let's assume x, t are raw in [0, 1]. The model will handle scaling internally if we want, or we just pass raw.
    # Let's just pass raw and let the network learn without scaling coordinates (it's in [0,1], very friendly).
    # Wait, the FNO used scaled alpha. We'll pass scaled alpha. 
    # PDE is u_t - alpha_raw * u_xx = 0
    f = (u_t - alpha_raw * u_xx) / alpha_raw
    return torch.mean(f**2)

class NormalizedPINN(nn.Module):
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
        return self.pinn(x_scaled, t_scaled, alpha_scaled)

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    fno_path = str(MODELS / 'fno2d_heat.pt')
    
    checkpoint = torch.load(fno_path, map_location=device)
    log_alpha_mean = checkpoint['log_alpha_mean']
    log_alpha_std = checkpoint['log_alpha_std']
    
    model = NormalizedPINN(log_alpha_mean, log_alpha_std).to(device)
    
    # ---------------- Sampling ----------------
    N_f = 20000  # Collocation points
    N_bc = 2000  # Boundary points
    N_ic = 2000  # Initial points
    
    def sample_raw_points(N, ic=False, bc=False):
        x = torch.rand(N, 1, device=device)
        t = torch.rand(N, 1, device=device)
        # Log-uniform alpha in [0.01, 1.0]
        log_alpha = torch.rand(N, 1, device=device) * (-2.0)
        alpha_raw = 10**log_alpha
        
        if ic:
            t = torch.zeros_like(t)
        if bc:
            # 50% x=0, 50% x=1
            x = torch.where(torch.rand(N, 1, device=device) > 0.5, torch.ones_like(x), torch.zeros_like(x))
            
        return x, t, alpha_raw
        
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    epochs = 1000
    print(f"Training Parametric PINN on {device}...")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        
        # PDE Collocation
        x_f, t_f, alpha_f = sample_raw_points(N_f)
        loss_f = compute_pde_loss(model, x_f, t_f, alpha_f, alpha_f)
        
        # Initial Condition: u(x, 0) = sin(pi*x)
        x_ic, t_ic, alpha_ic = sample_raw_points(N_ic, ic=True)
        u_ic_pred = model(x_ic, t_ic, alpha_ic)
        u_ic_true = torch.sin(np.pi * x_ic)
        loss_ic = torch.mean((u_ic_pred - u_ic_true)**2)
        
        # Boundary Condition: u(0, t) = u(1, t) = 0
        x_bc, t_bc, alpha_bc = sample_raw_points(N_bc, bc=True)
        u_bc_pred = model(x_bc, t_bc, alpha_bc)
        loss_bc = torch.mean(u_bc_pred**2)
        
        loss = loss_f + loss_ic + loss_bc
        loss.backward()
        optimizer.step()
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch:5d} | Loss: {loss.item():.4e} (PDE: {loss_f.item():.4e}, IC: {loss_ic.item():.4e}, BC: {loss_bc.item():.4e})", flush=True)
            
    # L-BFGS
    optimizer_lbfgs = torch.optim.LBFGS(model.parameters(), max_iter=500, line_search_fn="strong_wolfe")
    
    def closure():
        optimizer_lbfgs.zero_grad()
        x_f, t_f, alpha_f = sample_raw_points(N_f)
        loss_f = compute_pde_loss(model, x_f, t_f, alpha_f, alpha_f)
        
        x_ic, t_ic, alpha_ic = sample_raw_points(N_ic, ic=True)
        loss_ic = torch.mean((model(x_ic, t_ic, alpha_ic) - torch.sin(np.pi * x_ic))**2)
        
        x_bc, t_bc, alpha_bc = sample_raw_points(N_bc, bc=True)
        loss_bc = torch.mean(model(x_bc, t_bc, alpha_bc)**2)
        
        loss = loss_f + loss_ic + loss_bc
        loss.backward()
        return loss

    print("Starting L-BFGS phase...", flush=True)
    optimizer_lbfgs.step(closure)
    print("L-BFGS finished.")
    
    # Save Model
    os.makedirs(str(EXP_MODELS), exist_ok=True)
    torch.save({
        'model_state_dict': model.state_dict(),
        'log_alpha_mean': log_alpha_mean,
        'log_alpha_std': log_alpha_std
    }, str(EXP_MODELS / 'pinn_expA.pt'))
    print("PINN ExpA model saved.")
    
if __name__ == '__main__':
    main()
