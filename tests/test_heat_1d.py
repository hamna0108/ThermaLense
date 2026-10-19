import os
import numpy as np
import pytest
import matplotlib.pyplot as plt
from src.solvers.heat_1d import solve_heat_1d_exact, solve_heat_1d_numerical

def test_heat_1d_convergence():
    """
    Test that the numerical solution converges to the exact solution.
    We compute the Relative L2 field error at the final time step t=1.
    """
    Nx = 50
    Nt = 1000
    alpha = 0.1
    
    x, t, u_num = solve_heat_1d_numerical(Nx, Nt, alpha)
    
    # Get numerical solution at final time T=1
    u_num_final = u_num[-1, :]
    
    # Get exact solution at final time T=1
    u_exact_final = solve_heat_1d_exact(x, t[-1], alpha)
    
    # Calculate Relative L2 error
    l2_error = np.linalg.norm(u_num_final - u_exact_final) / np.linalg.norm(u_exact_final)
    
    # Calculate Maximum error
    max_error = np.max(np.abs(u_num_final - u_exact_final))
    
    print(f"\nRelative L2 error at T=1: {l2_error:.6e}")
    print(f"Maximum error at T=1: {max_error:.6e}")
    
    # Plotting
    os.makedirs('plots', exist_ok=True)
    plt.figure(figsize=(8, 6))
    plt.plot(x, u_exact_final, 'k-', label='Exact Solution')
    plt.plot(x, u_num_final, 'r--', label='Numerical Solution')
    plt.title('1D Heat Equation: Exact vs Numerical at T=1')
    plt.xlabel('x')
    plt.ylabel('u(x, T=1)')
    plt.legend()
    plt.grid(True)
    
    # Save the plot before showing
    plt.savefig(os.path.join('plots', 'heat_1d_convergence.png'), dpi=300)
    plt.close()

    
    # Error should be small (expected < 1e-3 for these Nx, Nt)
    assert l2_error < 1e-3, f"Relative L2 error too high: {l2_error}"

def test_heat_fno_accuracy():
    """
    Test that unmasked base FNO on test_interpolation has:
    - Median t=0 MAE < 1e-2 (actual ~0.0021)
    - Full-field relative L2 error < 1% (< 0.01, actual ~0.0045)
    """
    import torch
    from src.paths import DATASETS, MODELS
    from src.models.fno2d import FNO2d
    
    device = torch.device('cpu')
    ckpt = torch.load(MODELS / 'fno2d_heat.pt', map_location=device)
    assert ckpt.get('use_hard_mask', False) is False, "Heat FNO checkpoint must have use_hard_mask=False"
    
    model = FNO2d(modes1=16, modes2=12, width=32, use_hard_mask=False).to(device)
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()
    
    data = np.load(DATASETS / 'test_interpolation.npz')
    u_true = data['u']
    alphas = data['alpha']
    x_np, t_np = data['x'], data['t']
    
    lm, ls = ckpt['log_alpha_mean'].item(), ckpt['log_alpha_std'].item()
    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
    t_tensor = torch.tensor(2 * t_mesh - 1, dtype=torch.float32)
    x_tensor = torch.tensor(2 * x_mesh - 1, dtype=torch.float32)
    
    rel_l2_list, t0_mae_list = [], []
    with torch.no_grad():
        for i in range(len(alphas)):
            a = alphas[i]
            y = u_true[i]
            a_sc = (np.log10(a) - lm) / ls
            x_in = torch.stack([t_tensor, x_tensor, torch.full_like(t_tensor, a_sc)], dim=0).unsqueeze(0)
            pred = model(x_in).squeeze(1).squeeze(0).numpy()
            diff = pred - y
            rel_l2 = np.linalg.norm(diff) / np.linalg.norm(y)
            t0_mae = np.mean(np.abs(diff[0, :]))
            rel_l2_list.append(rel_l2)
            t0_mae_list.append(t0_mae)
            
    med_rel_l2 = np.median(rel_l2_list)
    med_t0_mae = np.median(t0_mae_list)
    
    print(f"\nHeat FNO Interpolation: Median Rel L2 = {med_rel_l2:.5f}, Median t=0 MAE = {med_t0_mae:.5f}")
    assert med_t0_mae < 1e-2, f"t=0 MAE too high: {med_t0_mae}"
    assert med_rel_l2 < 0.01, f"Full-field relative L2 too high: {med_rel_l2}"
