try:
    from paths import RAW, RESULTS
except ImportError:
    from src.paths import RAW, RESULTS
"""Task B: Mode 1 (Frozen PINN Surrogate Inversion) Small Grid Evaluation

Grid:
  alpha in {0.02, 0.1, 2.5}
  N in {5, 20}
  sigma in {0.01, 0.05}
  20 replications per cell (240 total inversions)

Pairing:
  Uses the exact same layout and noise seeds as Mode 2 and Mode 3.
  Model: BoundedReparametrizedPINN from models/pinn_expD.pt (frozen forward surrogate).

Outputs:
  - data/raw/mode1_pinn_raw.csv: per-replication outputs (alpha_hat, layout_seed, noise_seed)
  - data/mode1_pinn_summary.csv: aggregated cell metrics (med rel err, spread/CRB, wall time)
"""

import os
import sys
import time
import csv
import torch
import numpy as np
import scipy.optimize as opt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from eval_final_all import BoundedReparametrizedPINN

def solve_heat_1d_exact(x, t, alpha):
    return np.exp(-alpha * (np.pi**2) * t) * np.sin(np.pi * x)

def cramer_rao_bound_log(alpha, t_sensors, x_sensors, sigma):
    """Theoretical Cramér-Rao standard deviation for log10(alpha)."""
    grads = -np.pi**2 * t_sensors * np.exp(-alpha * np.pi**2 * t_sensors) * np.sin(np.pi * x_sensors)
    fisher_info = np.sum(grads**2) / (sigma**2 + 1e-15)
    if fisher_info <= 0:
        return np.inf
    crb_var = 1.0 / fisher_info
    crb_std = np.sqrt(crb_var)
    return crb_std / (alpha * np.log(10))

def run_task_b():
    print("=" * 90)
    print("TASK B: MODE 1 (FROZEN PINN SURROGATE INVERSION) SMALL GRID EVALUATION")
    print("=" * 90)
    
    os.makedirs(str(RAW), exist_ok=True); os.makedirs(str(RESULTS), exist_ok=True)
    
    
    device = torch.device('cpu')
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fno_chk_path = os.path.join(base_dir, 'models', 'fno2d_heat.pt')
    pinn_chk_path = os.path.join(base_dir, 'models', 'pinn_expD.pt')
    
    checkpoint = torch.load(fno_chk_path, map_location=device)
    log_alpha_mean = checkpoint['log_alpha_mean']
    log_alpha_std = checkpoint['log_alpha_std']
    
    print("Loading BoundedReparametrizedPINN from models/pinn_expD.pt...")
    model = BoundedReparametrizedPINN(log_alpha_mean, log_alpha_std).to(device)
    model.load_state_dict(torch.load(pinn_chk_path, map_location=device)['model_state_dict'])
    model.eval()
    
    Nx, Nt = 50, 100
    x_grid = np.linspace(0, 1, Nx)
    t_grid = np.linspace(0, 1, Nt)
    
    alphas = [0.02, 0.1, 2.5]
    sensor_counts = [5, 20]
    sigmas = [0.01, 0.05]
    num_reps = 20
    
    raw_csv_path = str(RAW / "mode1_pinn_raw.csv")
    summary_csv_path = str(RESULTS / "mode1_pinn_summary.csv")
    
    raw_rows = []
    summary_rows = []
    
    total_fits = 0
    t0_all = time.time()
    
    header = f"{'Alpha':5s} | {'Sensors':7s} | {'Sigma':5s} | {'MedRelErr':10s} | {'SpreadLog':10s} | {'CRB(log)':9s} | {'Sprd/CRB':9s} | {'Time(ms)':8s}"
    print(header)
    print("-" * len(header))
    
    for alpha_true in alphas:
        for num_sensors in sensor_counts:
            # Deterministic sensor layout seed exactly matching canonical pipeline
            layout_seed = int(alpha_true * 1000) + num_sensors
            rng_layout = np.random.RandomState(layout_seed)
            
            t_log = np.logspace(np.log10(0.01), np.log10(1.0), num_sensors)
            t_idx = np.array([np.argmin(np.abs(t_grid - t)) for t in t_log])
            t_s = t_grid[t_idx]
            
            x_cand_indices = np.where((x_grid >= 0.2) & (x_grid <= 0.8))[0]
            
            # Pre-generate 20 layouts for this cell
            layouts = []
            for _ in range(num_reps):
                x_idx = rng_layout.choice(x_cand_indices, size=num_sensors, replace=True)
                x_s = x_grid[x_idx]
                layouts.append((t_s, x_s))
                
            for sigma in sigmas:
                # Deterministic noise seed exactly matching canonical pipeline
                base_noise_seed = int(alpha_true * 5000) + num_sensors * 10 + int(sigma * 100)
                rng_noise = np.random.RandomState(base_noise_seed)
                paired_noises = [rng_noise.normal(0, sigma, size=num_sensors) for _ in range(num_reps)]
                
                hats = []
                fit_times = []
                crbs_log = []
                
                for rep in range(num_reps):
                    t_sensors, x_sensors = layouts[rep]
                    noise = paired_noises[rep]
                    
                    u_exact = solve_heat_1d_exact(x_sensors, t_sensors, alpha_true)
                    y_sensors = u_exact + noise
                    
                    # Compute CRB for this specific replication layout
                    crb_log_rep = cramer_rao_bound_log(alpha_true, t_sensors, x_sensors, sigma)
                    crbs_log.append(crb_log_rep)
                    
                    # Prepare PyTorch sensor tensors
                    x_t = torch.tensor(x_sensors, dtype=torch.float32, device=device).view(-1, 1)
                    t_t = torch.tensor(t_sensors, dtype=torch.float32, device=device).view(-1, 1)
                    y_t = torch.tensor(y_sensors, dtype=torch.float32, device=device).view(-1, 1)
                    
                    def loss_fn(la):
                        with torch.no_grad():
                            a_val = torch.tensor([10**la], dtype=torch.float32, device=device).expand_as(x_t)
                            pred = model(x_t, t_t, a_val)
                            return torch.mean((pred - y_t)**2).item()
                            
                    t0_fit = time.perf_counter()
                    res = opt.minimize_scalar(loss_fn, bounds=(-3.0, 1.0), method='bounded')
                    dur_fit_ms = (time.perf_counter() - t0_fit) * 1000.0
                    
                    alpha_hat = 10**res.x
                    hats.append(alpha_hat)
                    fit_times.append(dur_fit_ms)
                    
                    rel_err = abs(alpha_hat - alpha_true) / alpha_true
                    rep_noise_seed = base_noise_seed + rep
                    
                    raw_rows.append({
                        'alpha_true': alpha_true,
                        'sensors': num_sensors,
                        'sigma': sigma,
                        'rep': rep,
                        'alpha_hat': alpha_hat,
                        'rel_err': rel_err,
                        'fit_time_ms': dur_fit_ms,
                        'layout_seed': layout_seed,
                        'noise_seed': rep_noise_seed
                    })
                    
                total_fits += num_reps
                hats = np.array(hats)
                med_rel_err = np.median(np.abs(hats - alpha_true) / alpha_true)
                mean_rel_err = np.mean(np.abs(hats - alpha_true) / alpha_true)
                spread_log = np.std(np.log10(hats))
                mean_crb_log = np.mean(crbs_log)
                sprd_crb = spread_log / mean_crb_log if mean_crb_log > 0 and mean_crb_log != np.inf else 0.0
                mean_fit_ms = np.mean(fit_times)
                
                summary_rows.append({
                    'alpha_true': alpha_true,
                    'sensors': num_sensors,
                    'sigma': sigma,
                    'med_rel_err': med_rel_err,
                    'mean_rel_err': mean_rel_err,
                    'spread_log': spread_log,
                    'crb_log': mean_crb_log,
                    'sprd_crb': sprd_crb,
                    'single_fit_time_ms': mean_fit_ms
                })
                
                print(f"{alpha_true:5.3f} | {num_sensors:7d} | {sigma:5.2f} | {med_rel_err:10.4f} | {spread_log:10.4f} | {mean_crb_log:9.4f} | {sprd_crb:9.2f} | {mean_fit_ms:8.2f}")

    # Write raw per-replication CSV
    print(f"\nWriting {len(raw_rows)} per-replication rows to {raw_csv_path}...")
    with open(raw_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'alpha_true', 'sensors', 'sigma', 'rep',
            'alpha_hat', 'rel_err', 'fit_time_ms',
            'layout_seed', 'noise_seed'
        ])
        writer.writeheader()
        writer.writerows(raw_rows)
        
    # Write summary CSV
    print(f"Writing {len(summary_rows)} cell summaries to {summary_csv_path}...")
    with open(summary_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'alpha_true', 'sensors', 'sigma',
            'med_rel_err', 'mean_rel_err', 'spread_log',
            'crb_log', 'sprd_crb', 'single_fit_time_ms'
        ])
        writer.writeheader()
        writer.writerows(summary_rows)
        
    total_time = time.time() - t0_all
    print(f"\nTask B complete: {total_fits} fits across 12 cells in {total_time:.2f} s.")

if __name__ == '__main__':
    run_task_b()
