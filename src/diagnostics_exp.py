import os
import torch
import numpy as np
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader

from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d
from train_pinn import NormalizedPINN
from train_pinn_expB import ReparametrizedPINN
from train_expC import ReparametrizedFNO2d

def relative_l2_per_timestep(pred, target):
    diff_norms = torch.norm(pred - target, 2, dim=2)
    target_norms = torch.norm(target, 2, dim=2)
    rel_err = diff_norms / (target_norms + 1e-8)
    return rel_err, diff_norms

def evaluate_pinn(model, test_dataset, device, t_flat, x_flat):
    abs_errors = []
    with torch.no_grad():
        for idx in range(len(test_dataset)):
            y = test_dataset.u[idx].unsqueeze(0).to(device)
            alpha_raw = test_dataset.alphas[idx].item()
            a_flat = torch.full_like(t_flat, alpha_raw)
            pred_flat = model(x_flat, t_flat, a_flat)
            pred = pred_flat.view(1, 100, 50)
            _, abs_err = relative_l2_per_timestep(pred, y)
            abs_errors.append(abs_err[0, 0].item())
    return abs_errors

def evaluate_fno(model, ood_loader, device):
    abs_errors = []
    with torch.no_grad():
        for x, y in ood_loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            if out.dim() == 4:
                out = out.squeeze(1)
            if y.dim() == 4:
                y = y.squeeze(1)
            _, abs_err = relative_l2_per_timestep(out, y)
            abs_errors.extend(abs_err[:, 0].cpu().numpy())
    return abs_errors

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, 'data', 'interim')
    model_dir = os.path.join(base_dir, 'models')
    
    # Load dataset to get alphas
    checkpoint_pinn = torch.load(os.path.join(model_dir, 'pinn_heat.pt'), map_location=device)
    log_alpha_mean = checkpoint_pinn['log_alpha_mean']
    log_alpha_std = checkpoint_pinn['log_alpha_std']
    
    test_ood_dataset = HeatEquationDataset(os.path.join(data_dir, 'test_ood.npz'), 
                                           log_alpha_mean=log_alpha_mean, 
                                           log_alpha_std=log_alpha_std)
    ood_loader = DataLoader(test_ood_dataset, batch_size=20, shuffle=False)
    
    z_scored_alphas = test_ood_dataset.log_alpha_scaled.numpy()
    
    t_np = np.load(os.path.join(data_dir, 'test_interpolation.npz'))['t']
    x_np = np.load(os.path.join(data_dir, 'test_interpolation.npz'))['x']
    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
    t_flat = torch.tensor(t_mesh, dtype=torch.float32, device=device).view(-1, 1)
    x_flat = torch.tensor(x_mesh, dtype=torch.float32, device=device).view(-1, 1)
    
    # Baseline PINN
    pinn_base = NormalizedPINN(log_alpha_mean, log_alpha_std).to(device)
    pinn_base.load_state_dict(torch.load(os.path.join(model_dir, 'pinn_heat.pt'), map_location=device)['model_state_dict'])
    pinn_base.eval()
    pinn_base_err = evaluate_pinn(pinn_base, test_ood_dataset, device, t_flat, x_flat)
    
    # Exp A PINN (Loss weighted)
    pinn_expA = NormalizedPINN(log_alpha_mean, log_alpha_std).to(device)
    pinn_expA.load_state_dict(torch.load(os.path.join(model_dir, 'pinn_expA.pt'), map_location=device)['model_state_dict'])
    pinn_expA.eval()
    pinn_expA_err = evaluate_pinn(pinn_expA, test_ood_dataset, device, t_flat, x_flat)
    
    # Exp B PINN (Hard IC/BC)
    pinn_expB = ReparametrizedPINN(log_alpha_mean, log_alpha_std).to(device)
    pinn_expB.load_state_dict(torch.load(os.path.join(model_dir, 'pinn_expB.pt'), map_location=device)['model_state_dict'])
    pinn_expB.eval()
    pinn_expB_err = evaluate_pinn(pinn_expB, test_ood_dataset, device, t_flat, x_flat)
    
    # Baseline FNO
    fno_base = FNO2d(modes1=16, modes2=12, width=32).to(device)
    fno_base.load_state_dict(torch.load(os.path.join(model_dir, 'fno2d_heat.pt'), map_location=device)['model_state_dict'])
    fno_base.eval()
    fno_base_err = evaluate_fno(fno_base, ood_loader, device)
    
    # Exp C FNO (Hard IC/BC)
    fno_expC = ReparametrizedFNO2d(modes1=16, modes2=12, width=32).to(device)
    fno_expC.load_state_dict(torch.load(os.path.join(model_dir, 'fno2d_expC.pt'), map_location=device)['model_state_dict'])
    fno_expC.eval()
    fno_expC_err = evaluate_fno(fno_expC, ood_loader, device)
    
    # Plots
    plt.figure(figsize=(15, 6))
    
    # Plot 1: PINN Comparisons
    plt.subplot(1, 2, 1)
    plt.scatter(z_scored_alphas, pinn_base_err, label='Baseline PINN', alpha=0.6)
    plt.scatter(z_scored_alphas, pinn_expA_err, label='Exp A: Normalized PDE Loss', alpha=0.6)
    plt.scatter(z_scored_alphas, pinn_expB_err, label='Exp B: Hard IC/BC Reparam', alpha=0.6)
    plt.xlabel('Z-scored log(Alpha)')
    plt.ylabel('Absolute Error at t=0')
    plt.title('PINN: t=0 Error vs Alpha (OOD Tails)')
    plt.legend()
    plt.grid(True)
    
    # Plot 2: FNO Comparisons
    plt.subplot(1, 2, 2)
    plt.scatter(z_scored_alphas, fno_base_err, label='Baseline FNO', alpha=0.6)
    plt.scatter(z_scored_alphas, fno_expC_err, label='Exp C: Hard IC/BC Reparam', alpha=0.6)
    plt.xlabel('Z-scored log(Alpha)')
    plt.ylabel('Absolute Error at t=0')
    plt.title('FNO: t=0 Error vs Alpha (OOD Tails)')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plot_path = os.path.join(base_dir, 'plots', 't0_error_experiments.png')
    plt.savefig(plot_path, dpi=300)
    print(f"Plot saved to {plot_path}")

if __name__ == '__main__':
    main()
