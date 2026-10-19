try:
    from paths import DATASETS, MODELS, PLOTS
except ImportError:
    from src.paths import DATASETS, MODELS, PLOTS
import numpy as np
import torch
import scipy.optimize as opt
import matplotlib.pyplot as plt
import os
import time

from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d

def solve_heat_1d_exact(x, t, alpha):
    return np.exp(-alpha * np.pi**2 * t) * np.sin(np.pi * x)

def get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid):
    layouts = []
    for _ in range(num_replications):
        t_log = np.logspace(np.log10(0.01), np.log10(1.0), num_sensors)
        t_idx = [np.argmin(np.abs(t_grid - t)) for t in t_log]
        t_sensors = t_grid[t_idx]
        
        x_candidates = x_grid[(x_grid >= 0.2) & (x_grid <= 0.8)]
        x_sensors = np.random.choice(x_candidates, size=num_sensors, replace=True)
        layouts.append((t_sensors, x_sensors, t_idx, [np.argmin(np.abs(x_grid - x)) for x in x_sensors]))
    return layouts

def cramer_rao_bound(alpha, t_sensors, x_sensors, sigma):
    grads = -np.pi**2 * t_sensors * np.exp(-alpha * np.pi**2 * t_sensors) * np.sin(np.pi * x_sensors)
    fisher_info = np.sum(grads**2) / (sigma**2 + 1e-12)
    if fisher_info == 0:
        return np.inf
    return 1.0 / fisher_info

def evaluate_mode3():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    checkpoint = torch.load('models/fno2d_heat.pt', map_location=device)
    model = FNO2d(modes1=16, modes2=12, width=32).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    log_alpha_mean = checkpoint['log_alpha_mean'].item()
    log_alpha_std = checkpoint['log_alpha_std'].item()
    
    data = np.load(str(DATASETS / 'test_interpolation.npz'))
    x_np = data['x']
    t_np = data['t']
    
    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
    t_scaled = 2 * t_mesh - 1
    x_scaled = 2 * x_mesh - 1
    t_tensor = torch.tensor(t_scaled, dtype=torch.float32).to(device)
    x_tensor = torch.tensor(x_scaled, dtype=torch.float32).to(device)
    
    # Define bounds
    bounds_train = [(np.log10(0.01), np.log10(1.0))]
    bounds_narrow = [(-3.0, np.log10(4.0))]
    bounds_wide = [(-3.0, np.log10(100.0))]
    
    grid_la_train = np.linspace(np.log10(0.01), np.log10(1.0), 100)
    grid_la_narrow = np.linspace(-3, np.log10(4.0), 100)
    grid_la_wide = np.linspace(-3, np.log10(100.0), 200)
    
    # Merge unique grid points for batched precompute
    all_grid_la = np.unique(np.concatenate([grid_la_train, grid_la_narrow, grid_la_wide]))
    
    def precompute_fno_grid(la_grid):
        print(f"Precomputing {len(la_grid)} FNO solutions for Mode 3...")
        out_list = []
        batch_size = 50
        for i in range(0, len(la_grid), batch_size):
            batch_la = la_grid[i:i+batch_size]
            x_inputs = []
            for la in batch_la:
                a_scaled = (la - log_alpha_mean) / log_alpha_std
                a_tensor = torch.full_like(t_tensor, a_scaled)
                x_inputs.append(torch.stack([t_tensor, x_tensor, a_tensor], dim=0))
            x_batch = torch.stack(x_inputs, dim=0)
            with torch.no_grad():
                out_batch = model(x_batch).squeeze(1).cpu().numpy()
            out_list.append(out_batch)
        return np.concatenate(out_list, axis=0)
    
    t0_pre = time.time()
    all_grid_outputs = precompute_fno_grid(all_grid_la)
    t1_pre = time.time()
    print(f"Precompute time: {t1_pre - t0_pre:.2f} s")
    
    # Map from all_grid_la back to specific grids
    idx_train = [np.argmin(np.abs(all_grid_la - la)) for la in grid_la_train]
    idx_narrow = [np.argmin(np.abs(all_grid_la - la)) for la in grid_la_narrow]
    idx_wide = [np.argmin(np.abs(all_grid_la - la)) for la in grid_la_wide]
    
    def get_objective(t_idx, x_idx, y_sensors):
        y_tensor = torch.tensor(y_sensors, dtype=torch.float32, device=device)
        def objective_fn(log_alpha_array):
            log_a_tensor = torch.tensor(log_alpha_array[0], dtype=torch.float32, device=device, requires_grad=True)
            a_scaled = (log_a_tensor - log_alpha_mean) / log_alpha_std
            a_tensor = a_scaled * torch.ones_like(t_tensor)
            x_input = torch.stack([t_tensor, x_tensor, a_tensor], dim=0).unsqueeze(0)
            out = model(x_input).squeeze()
            out_sensors = out[t_idx, x_idx]
            loss = torch.mean((out_sensors - y_tensor)**2)
            loss.backward()
            return loss.item(), np.array([log_a_tensor.grad.item()], dtype=np.float64)
        return objective_fn

    alphas_to_test = {
        'Interpolation': [0.1, 0.5],
        'Low-alpha OOD': [0.005],
        'High-alpha OOD': [2.5]
    }
    
    sensor_counts = [5, 10, 20]
    noise_levels = [0.0, 0.01, 0.05]
    num_replications = 200
    
    print(f"Local Refinement check: using opt.minimize L-BFGS-B with PyTorch autograd (jac=True).")
    
    print(f"{'Split':15s} | {'Alpha':5s} | {'Sensors':7s} | {'Sigma':5s} | {'MedRelErr (Train)':17s} | {'MedRelErr (Narrow)':18s} | {'MedRelErr (Wide)':16s} | {'FracWide>4':10s} | {'Sprd/CRB':8s} | {'Time(s)':7s}")
    print("-" * 135)
    
    global_total_time = 0
    global_num_inversions = 0
    
    for split, alphas in alphas_to_test.items():
        for alpha_true in alphas:
            for num_sensors in sensor_counts:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_np, t_np)
                for sigma in noise_levels:
                    
                    alpha_hats_train = []
                    alpha_hats_narrow = []
                    alpha_hats_wide = []
                    crbs_log = []
                    
                    wide_failures_plotted = 0
                    
                    cell_start_time = time.time()
                    
                    for i_rep, (t_s, x_s, t_idx, x_idx) in enumerate(layouts):
                        u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                        if sigma > 0:
                            noise = np.random.normal(0, sigma, size=num_sensors)
                            y_s = u_exact + noise
                        else:
                            y_s = u_exact
                            
                        crb = cramer_rao_bound(alpha_true, t_s, x_s, sigma)
                        crb_std_log = np.sqrt(crb) / (alpha_true * np.log(10)) if (crb != np.inf and crb != 0) else 0.0
                        crbs_log.append(crb_std_log)
                        
                        # Precomputed grid losses
                        grid_sensor_outs = all_grid_outputs[:, t_idx, x_idx] # (num_all_grid, num_sensors)
                        mse_all = np.mean((grid_sensor_outs - y_s)**2, axis=1)
                        
                        best_train_idx = idx_train[np.argmin(mse_all[idx_train])]
                        best_la_train = all_grid_la[best_train_idx]
                        
                        best_narrow_idx = idx_narrow[np.argmin(mse_all[idx_narrow])]
                        best_la_narrow = all_grid_la[best_narrow_idx]
                        
                        best_wide_idx = idx_wide[np.argmin(mse_all[idx_wide])]
                        best_la_wide = all_grid_la[best_wide_idx]
                        
                        obj_fn = get_objective(t_idx, x_idx, y_s)
                        
                        res_train = opt.minimize(obj_fn, x0=[best_la_train], bounds=bounds_train, method='L-BFGS-B', jac=True)
                        alpha_hats_train.append(10**res_train.x[0])
                        
                        res_narrow = opt.minimize(obj_fn, x0=[best_la_narrow], bounds=bounds_narrow, method='L-BFGS-B', jac=True)
                        alpha_hats_narrow.append(10**res_narrow.x[0])
                        
                        res_wide = opt.minimize(obj_fn, x0=[best_la_wide], bounds=bounds_wide, method='L-BFGS-B', jac=True)
                        hat_wide = 10**res_wide.x[0]
                        alpha_hats_wide.append(hat_wide)
                        
                        if hat_wide > 4.0 and wide_failures_plotted < 2:
                            plt.figure()
                            plt.plot(all_grid_la[idx_wide], mse_all[idx_wide])
                            plt.axvline(np.log10(alpha_true), color='r', linestyle='--', label='True')
                            plt.axvline(np.log10(hat_wide), color='g', linestyle='--', label='Est Wide')
                            plt.title(f'Mode 3 Spurious Minima (True={alpha_true:.3f}, Est={hat_wide:.1f})')
                            plt.xlabel('log10(alpha)')
                            plt.ylabel('MSE (FNO)')
                            plt.legend()
                            plt.savefig(f'plots/mode3_spurious_loss_alpha{alpha_true}_rep{i_rep}.png')
                            plt.close()
                            wide_failures_plotted += 1
                            
                    cell_end_time = time.time()
                    cell_time = cell_end_time - cell_start_time
                    global_total_time += cell_time
                    global_num_inversions += num_replications
                    
                    alpha_hats_train = np.array(alpha_hats_train)
                    alpha_hats_narrow = np.array(alpha_hats_narrow)
                    alpha_hats_wide = np.array(alpha_hats_wide)
                    
                    med_rel_err_train = np.median(np.abs(alpha_hats_train - alpha_true) / alpha_true)
                    med_rel_err_narrow = np.median(np.abs(alpha_hats_narrow - alpha_true) / alpha_true)
                    med_rel_err_wide = np.median(np.abs(alpha_hats_wide - alpha_true) / alpha_true)
                    
                    frac_wide_gt_4 = np.mean(alpha_hats_wide > 4.0)
                    
                    mean_crb = np.mean(crbs_log)
                    spread_narrow = np.std(np.log10(alpha_hats_narrow))
                    spread_crb_ratio = spread_narrow / mean_crb if mean_crb > 0 else 0.0
                    
                    mean_time = cell_time / num_replications
                    
                    print(f"{split:15s} | {alpha_true:5.3f} | {num_sensors:7d} | {sigma:5.2f} | "
                          f"{med_rel_err_train:17.4f} | {med_rel_err_narrow:18.4f} | {med_rel_err_wide:16.4f} | {frac_wide_gt_4:10.2f} | {spread_crb_ratio:8.2f} | {mean_time:7.4f}", flush=True)

    print(f"\nAverage wall-clock time per Mode 3 inversion (excluding precompute): {global_total_time / global_num_inversions:.4f} seconds")

if __name__ == '__main__':
    os.makedirs('plots', exist_ok=True)
    evaluate_mode3()
