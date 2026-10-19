import os
import torch
import numpy as np
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader

from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d
from train_pinn import NormalizedPINN, compute_pde_loss

def relative_l2_per_timestep(pred, target):
    diff_norms = torch.norm(pred - target, 2, dim=2)
    target_norms = torch.norm(target, 2, dim=2)
    rel_err = diff_norms / (target_norms + 1e-8)
    return rel_err, diff_norms

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, 'data', 'interim')
    model_dir = os.path.join(base_dir, 'models')
    
    pinn_path = os.path.join(model_dir, 'pinn_heat.pt')
    fno_path = os.path.join(model_dir, 'fno2d_heat.pt')
    
    checkpoint_pinn = torch.load(pinn_path, map_location=device)
    checkpoint_fno = torch.load(fno_path, map_location=device)
    
    log_alpha_mean = checkpoint_pinn['log_alpha_mean']
    log_alpha_std = checkpoint_pinn['log_alpha_std']
    
    # 1. PINN's in-distribution (interpolation-test) t=0 error
    test_in_dataset = HeatEquationDataset(os.path.join(data_dir, 'test_interpolation.npz'), 
                                          log_alpha_mean=log_alpha_mean, 
                                          log_alpha_std=log_alpha_std)
    
    model_pinn = NormalizedPINN(log_alpha_mean, log_alpha_std).to(device)
    model_pinn.load_state_dict(checkpoint_pinn['model_state_dict'])
    model_pinn.eval()
    
    model_fno = FNO2d(modes1=16, modes2=12, width=32).to(device)
    model_fno.load_state_dict(checkpoint_fno['model_state_dict'])
    model_fno.eval()
    
    t_np = np.load(os.path.join(data_dir, 'test_interpolation.npz'))['t']
    x_np = np.load(os.path.join(data_dir, 'test_interpolation.npz'))['x']
    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
    t_flat = torch.tensor(t_mesh, dtype=torch.float32, device=device).view(-1, 1)
    x_flat = torch.tensor(x_mesh, dtype=torch.float32, device=device).view(-1, 1)
    
    interp_rel = []
    interp_abs = []
    
    with torch.no_grad():
        for idx in range(len(test_in_dataset)):
            y = test_in_dataset.u[idx].unsqueeze(0).to(device)
            alpha_raw = test_in_dataset.alphas[idx].item()
            a_flat = torch.full_like(t_flat, alpha_raw)
            pred_flat = model_pinn(x_flat, t_flat, a_flat)
            pred = pred_flat.view(1, 100, 50)
            rel_err_t, abs_err_t = relative_l2_per_timestep(pred, y)
            interp_rel.append(rel_err_t.cpu().numpy()[0, 0])
            interp_abs.append(abs_err_t.cpu().numpy()[0, 0])
            
    print("1. PINN Interpolation-test t=0 Error:")
    print(f"Mean Rel: {np.mean(interp_rel):.4f}, Mean Abs: {np.mean(interp_abs):.4f}")
    
    # 2. t=0 absolute error vs. z-scored alpha input value for OOD
    test_ood_dataset = HeatEquationDataset(os.path.join(data_dir, 'test_ood.npz'), 
                                           log_alpha_mean=log_alpha_mean, 
                                           log_alpha_std=log_alpha_std)
    
    ood_loader = DataLoader(test_ood_dataset, batch_size=20, shuffle=False)
    
    fno_t0_abs = []
    pinn_t0_abs = []
    z_scored_alphas = []
    
    with torch.no_grad():
        # FNO eval
        for x, y in ood_loader:
            x, y = x.to(device), y.to(device)
            out = model_fno(x)
            if out.dim() == 4:
                out = out.squeeze(1)
            if y.dim() == 4:
                y = y.squeeze(1)
            _, abs_err = relative_l2_per_timestep(out, y)
            fno_t0_abs.extend(abs_err[:, 0].cpu().numpy())
            
        # PINN eval
        for idx in range(len(test_ood_dataset)):
            y = test_ood_dataset.u[idx].unsqueeze(0).to(device)
            alpha_raw = test_ood_dataset.alphas[idx].item()
            z_scored = test_ood_dataset.log_alpha_scaled[idx].item()
            z_scored_alphas.append(z_scored)
            
            a_flat = torch.full_like(t_flat, alpha_raw)
            pred_flat = model_pinn(x_flat, t_flat, a_flat)
            pred = pred_flat.view(1, 100, 50)
            _, abs_err = relative_l2_per_timestep(pred, y)
            pinn_t0_abs.append(abs_err[0, 0].item())
            
    plt.figure(figsize=(10, 6))
    plt.scatter(z_scored_alphas, fno_t0_abs, label='FNO t=0 Abs Error', alpha=0.6)
    plt.scatter(z_scored_alphas, pinn_t0_abs, label='PINN t=0 Abs Error', alpha=0.6)
    plt.xlabel('Z-scored log(Alpha)')
    plt.ylabel('Absolute Error at t=0')
    plt.title('t=0 Absolute Error vs Z-scored Alpha (OOD Tails)')
    plt.legend()
    plt.grid(True)
    plot_path = os.path.join(base_dir, 'plots', 't0_error_vs_alpha.png')
    plt.savefig(plot_path, dpi=300)
    print(f"\n2. Plot saved to {plot_path}")
    
    # 3. PINN PDE residual bucketed by alpha range
    N_f = 20000
    x_f = torch.rand(N_f, 1, device=device)
    t_f = torch.rand(N_f, 1, device=device)
    log_alpha = torch.rand(N_f, 1, device=device) * (-2.0)
    alpha_f = 10**log_alpha
    
    x_f.requires_grad_(True)
    t_f.requires_grad_(True)
    
    u = model_pinn(x_f, t_f, alpha_f)
    u_t = torch.autograd.grad(u, t_f, grad_outputs=torch.ones_like(u), create_graph=True)[0]
    u_x = torch.autograd.grad(u, x_f, grad_outputs=torch.ones_like(u), create_graph=True)[0]
    u_xx = torch.autograd.grad(u_x, x_f, grad_outputs=torch.ones_like(u_x), create_graph=True)[0]
    
    res = (u_t - alpha_f * u_xx)**2
    res_np = res.detach().cpu().numpy().flatten()
    log_alpha_np = log_alpha.detach().cpu().numpy().flatten()
    
    # Terciles based on log_alpha in [-2, 0]
    # Low: [-2, -1.33], Mid: [-1.33, -0.66], High: [-0.66, 0]
    low_mask = log_alpha_np < -1.33
    mid_mask = (log_alpha_np >= -1.33) & (log_alpha_np < -0.66)
    high_mask = log_alpha_np >= -0.66
    
    print("\n3. PINN PDE Residual Loss by Alpha Range (Over [0.01, 1.0]):")
    print(f"Low Alpha:  {np.mean(res_np[low_mask]):.4e}")
    print(f"Mid Alpha:  {np.mean(res_np[mid_mask]):.4e}")
    print(f"High Alpha: {np.mean(res_np[high_mask]):.4e}")

if __name__ == '__main__':
    main()
