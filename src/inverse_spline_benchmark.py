import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.interpolate import CubicSpline
import scipy.optimize as opt
import torch
import time
import os
import sys

# Ensure src is on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from models.fno2d import FNO2d

def solve_heat_1d_exact(x, t, alpha):
    """Exact analytic Fourier series solution."""
    return np.exp(-alpha * (np.pi**2) * t) * np.sin(np.pi * x)

def solve_heat_1d_cn(Nx, Nt, alpha):
    """Second-order Crank-Nicolson finite-difference solver."""
    x = np.linspace(0, 1, Nx)
    t = np.linspace(0, 1, Nt)
    dx = x[1] - x[0]
    dt = t[1] - t[0]
    r = alpha * dt / (2 * dx**2)
    main_diag_A = (1 + 2*r) * np.ones(Nx-2)
    off_diag_A = -r * np.ones(Nx-3)
    main_diag_B = (1 - 2*r) * np.ones(Nx-2)
    off_diag_B = r * np.ones(Nx-3)
    A = sp.diags([off_diag_A, main_diag_A, off_diag_A], offsets=[-1, 0, 1], format='csr')
    B = sp.diags([off_diag_B, main_diag_B, off_diag_B], offsets=[-1, 0, 1], format='csr')
    u = np.zeros((Nt, Nx))
    u[0, :] = np.sin(np.pi * x)
    for n in range(0, Nt - 1):
        rhs = B.dot(u[n, 1:-1])
        u[n+1, 1:-1] = spla.spsolve(A, rhs)
        u[n+1, 0] = 0.0
        u[n+1, -1] = 0.0
    return x, t, u

def cramer_rao_bound(alpha, t_sensors, x_sensors, sigma):
    """Scalar CRB on log10(alpha)."""
    grads = -np.pi**2 * t_sensors * np.exp(-alpha * np.pi**2 * t_sensors) * np.sin(np.pi * x_sensors)
    fisher_info = np.sum(grads**2) / (sigma**2 + 1e-12)
    if fisher_info == 0:
        return np.inf
    return 1.0 / fisher_info

def get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid, seed=42):
    rng = np.random.RandomState(seed)
    layouts = []
    for _ in range(num_replications):
        t_log = np.logspace(np.log10(0.01), np.log10(1.0), num_sensors)
        t_idx = np.array([np.argmin(np.abs(t_grid - t)) for t in t_log])
        t_sensors = t_grid[t_idx]
        x_candidates_mask = (x_grid >= 0.2) & (x_grid <= 0.8)
        x_cand_indices = np.where(x_candidates_mask)[0]
        x_idx = rng.choice(x_cand_indices, size=num_sensors, replace=True)
        x_sensors = x_grid[x_idx]
        layouts.append((t_sensors, x_sensors, t_idx, x_idx))
    return layouts

def run_spline_pipeline():
    print("=" * 100)
    print("INVERSE PIPELINE BENCHMARK: SPLINE REFACTOR, BIAS SWEEPS & IDENTIFIABILITY")
    print("=" * 100)

    # -------------------------------------------------------------
    # 1. BIAS TEST: FULL sigma=0 SWEEP OVER alpha from 0.003 to 4.0
    # -------------------------------------------------------------
    print("\n[PART 1] Running sigma=0 bias sweep over alpha from 0.003 to 4.0 at both resolutions...")
    print("Test data is generated directly from solve_heat_1d_exact(x, t, alpha).")
    
    res1_Nx, res1_Nt = 50, 100
    res2_Nx, res2_Nt = 100, 200
    
    grid_log_alphas_sweep = np.linspace(np.log10(0.002), np.log10(5.0), 300)
    
    # Precompute Mode 2 CN for Res 1
    t0 = time.time()
    U_res1 = np.array([solve_heat_1d_cn(res1_Nx, res1_Nt, 10**la)[2] for la in grid_log_alphas_sweep])
    t_pre_m2_res1 = time.time() - t0
    
    # Precompute Mode 2 CN for Res 2
    t0 = time.time()
    U_res2 = np.array([solve_heat_1d_cn(res2_Nx, res2_Nt, 10**la)[2] for la in grid_log_alphas_sweep])
    t_pre_m2_res2 = time.time() - t0
    
    print(f"Precompute Res 1 (50x100, 300 grid solves): {t_pre_m2_res1:.2f} s")
    print(f"Precompute Res 2 (100x200, 300 grid solves): {t_pre_m2_res2:.2f} s")
    
    x_grid_res1 = np.linspace(0, 1, res1_Nx)
    t_grid_res1 = np.linspace(0, 1, res1_Nt)
    x_grid_res2 = np.linspace(0, 1, res2_Nx)
    t_grid_res2 = np.linspace(0, 1, res2_Nt)
    
    alphas_sweep_targets = [0.003, 0.005, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    
    print(f"\n{'Alpha':8s} | {'RelErr (50x100)':17s} | {'RelErr (100x200)':17s} | {'Conv Ratio (Err1/Err2)':24s}")
    print("-" * 75)
    
    # Use 20 sensors layout for sweep
    t_log_s = np.logspace(np.log10(0.01), np.log10(1.0), 20)
    t_idx1 = [np.argmin(np.abs(t_grid_res1 - t)) for t in t_log_s]
    x_idx1 = [int(0.5 * res1_Nx)] * 20
    t_idx2 = [np.argmin(np.abs(t_grid_res2 - t)) for t in t_log_s]
    x_idx2 = [int(0.5 * res2_Nx)] * 20
    
    cs_res1 = CubicSpline(grid_log_alphas_sweep, U_res1[:, t_idx1, x_idx1], axis=0)
    cs_res2 = CubicSpline(grid_log_alphas_sweep, U_res2[:, t_idx2, x_idx2], axis=0)
    
    sweep_results = []
    for a_val in alphas_sweep_targets:
        y1 = solve_heat_1d_exact(x_grid_res1[x_idx1], t_grid_res1[t_idx1], a_val)
        y2 = solve_heat_1d_exact(x_grid_res2[x_idx2], t_grid_res2[t_idx2], a_val)
        
        # Invert Res 1
        res_opt1 = opt.minimize_scalar(lambda la: np.mean((cs_res1(la) - y1)**2), 
                                       bounds=(grid_log_alphas_sweep[0], grid_log_alphas_sweep[-1]), 
                                       method='bounded')
        hat1 = 10**res_opt1.x
        err1 = abs(hat1 - a_val) / a_val
        
        # Invert Res 2
        res_opt2 = opt.minimize_scalar(lambda la: np.mean((cs_res2(la) - y2)**2), 
                                       bounds=(grid_log_alphas_sweep[0], grid_log_alphas_sweep[-1]), 
                                       method='bounded')
        hat2 = 10**res_opt2.x
        err2 = abs(hat2 - a_val) / a_val
        
        ratio = err1 / (err2 + 1e-12)
        sweep_results.append((a_val, hat1, err1, hat2, err2, ratio))
        print(f"{a_val:8.4f} | {err1:17.6f} | {err2:17.6f} | {ratio:24.2f}x")
        
    # -------------------------------------------------------------
    # 2. SENSOR-LAYOUT CHECK AT alpha=0.005
    # -------------------------------------------------------------
    print("\n[PART 2] Sensor-layout check at alpha=0.005 across 200 random layouts...")
    print("Testing if error depends on layout or discrete grid step...")
    for n_sens in [2, 5, 10, 20]:
        layouts = get_sensor_layouts(n_sens, 200, x_grid_res1, t_grid_res1, seed=123)
        errs = []
        for t_s, x_s, t_i, x_i in layouts:
            y = solve_heat_1d_exact(x_s, t_s, 0.005)
            cs = CubicSpline(grid_log_alphas_sweep, U_res1[:, t_i, x_i], axis=0)
            res = opt.minimize_scalar(lambda la: np.mean((cs(la) - y)**2), 
                                      bounds=(grid_log_alphas_sweep[0], grid_log_alphas_sweep[-1]), 
                                      method='bounded')
            hat = 10**res.x
            errs.append(abs(hat - 0.005) / 0.005)
        med_err = np.median(errs)
        std_err = np.std(errs)
        print(f"Sensors: {n_sens:2d} | MedRelErr: {med_err:.6f} | StdRelErr: {std_err:.6f} | Min: {min(errs):.6f} | Max: {max(errs):.6f}")

    # -------------------------------------------------------------
    # 3. MODE 3 (FNO) PRECOMPUTE & SPLINE SETUP
    # -------------------------------------------------------------
    print("\n[PART 3] Mode 3 (FNO) Precomputation and Evaluation...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"PyTorch device: {device}")
    checkpoint = torch.load('models/fno2d_heat.pt', map_location=device)
    model = FNO2d(modes1=16, modes2=12, width=32).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    log_alpha_mean = checkpoint['log_alpha_mean'].item()
    log_alpha_std = checkpoint['log_alpha_std'].item()

    data = np.load('data/interim/test_interpolation.npz')
    x_np = data['x']
    t_np = data['t']

    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
    t_scaled = 2 * t_mesh - 1
    x_scaled = 2 * x_mesh - 1
    t_tensor = torch.tensor(t_scaled, dtype=torch.float32).to(device)
    x_tensor = torch.tensor(x_scaled, dtype=torch.float32).to(device)

    # Bounds
    bounds_train = (np.log10(0.01), np.log10(1.0))
    bounds_narrow = (-3.0, np.log10(4.0))
    bounds_wide = (-3.0, np.log10(100.0))

    # Precompute FNO across wide grid
    grid_la_fno = np.linspace(-3.0, np.log10(100.0), 300)
    t0 = time.time()
    out_list = []
    batch_size = 50
    for i in range(0, len(grid_la_fno), batch_size):
        batch_la = grid_la_fno[i:i+batch_size]
        x_inputs = []
        for la in batch_la:
            a_scaled = (la - log_alpha_mean) / log_alpha_std
            a_tensor = torch.full_like(t_tensor, a_scaled)
            x_inputs.append(torch.stack([t_tensor, x_tensor, a_tensor], dim=0))
        x_batch = torch.stack(x_inputs, dim=0)
        with torch.no_grad():
            out_batch = model(x_batch).squeeze(1).cpu().numpy()
        out_list.append(out_batch)
    fno_grid_all = np.concatenate(out_list, axis=0) # shape (300, Nt, Nx)
    t_pre_fno = time.time() - t0
    print(f"FNO Precompute time (300 grid points): {t_pre_fno:.2f} s")

    # -------------------------------------------------------------
    # 4. FULL MODE 2 & MODE 3 EVALUATION TABLES (WITH SPLINE)
    # -------------------------------------------------------------
    splits_dict = {
        'Interpolation': [0.1, 0.5],
        'Low-alpha OOD': [0.005],
        'High-alpha OOD': [2.5]
    }
    
    sensor_counts_m2 = [2, 5, 10, 20]
    sensor_counts_m3 = [5, 10, 20]
    noise_levels = [0.0, 0.01, 0.05]
    num_replications = 200
    
    # ----------------- MODE 2 BENCHMARK -----------------
    print("\n" + "=" * 115)
    print("MODE 2 COMPLETE TABLE (Crank-Nicolson Spline Refactor)")
    print("=" * 115)
    print(f"{'Split':15s} | {'Alpha':5s} | {'Sensors':7s} | {'Sigma':5s} | {'MedRelErr':10s} | {'Spread(log)':11s} | {'Cov95':6s} | {'Time(ms)':8s} | {'Notes':20s}")
    print("-" * 115)

    # Grid for Mode 2 evaluations
    grid_la_m2 = np.linspace(-3.0, np.log10(4.0), 300)
    t0 = time.time()
    U_m2 = np.array([solve_heat_1d_cn(res1_Nx, res1_Nt, 10**la)[2] for la in grid_la_m2])
    t_pre_m2 = time.time() - t0
    
    m2_total_time = 0.0
    m2_total_inversions = 0
    m2_rows = []

    for split, alphas in splits_dict.items():
        for alpha_true in alphas:
            for num_sensors in sensor_counts_m2:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_grid_res1, t_grid_res1, seed=42 + int(alpha_true*100) + num_sensors)
                for sigma in noise_levels:
                    alpha_hats = []
                    crbs_log = []
                    cov_count = 0
                    
                    t_cell_start = time.time()
                    for t_s, x_s, t_idx, x_idx in layouts:
                        u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                        if sigma > 0:
                            y_s = u_exact + np.random.normal(0, sigma, size=num_sensors)
                        else:
                            y_s = u_exact
                            
                        crb_val = cramer_rao_bound(alpha_true, t_s, x_s, sigma)
                        crb_std_log = np.sqrt(crb_val) / (alpha_true * np.log(10)) if (crb_val != np.inf and crb_val != 0) else 0.0
                        crbs_log.append(crb_std_log)
                        
                        # Spline evaluation
                        cs = CubicSpline(grid_la_m2, U_m2[:, t_idx, x_idx], axis=0)
                        res = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                                                 bounds=(grid_la_m2[0], grid_la_m2[-1]),
                                                 method='bounded')
                        hat = 10**res.x
                        alpha_hats.append(hat)
                        
                        if sigma > 0:
                            crb_hat = cramer_rao_bound(hat, t_s, x_s, sigma)
                            if crb_hat != np.inf and crb_hat != 0:
                                crb_hat_log_std = np.sqrt(crb_hat) / (hat * np.log(10))
                                lower = np.log10(hat) - 1.96 * crb_hat_log_std
                                upper = np.log10(hat) + 1.96 * crb_hat_log_std
                                if lower <= np.log10(alpha_true) <= upper:
                                    cov_count += 1
                                    
                    t_cell_end = time.time()
                    cell_dur = t_cell_end - t_cell_start
                    m2_total_time += cell_dur
                    m2_total_inversions += num_replications
                    
                    alpha_hats = np.array(alpha_hats)
                    log_hats = np.log10(alpha_hats)
                    med_rel_err = np.median(np.abs(alpha_hats - alpha_true) / alpha_true)
                    spread_log = np.std(log_hats)
                    mean_crb = np.mean(crbs_log)
                    
                    bound_low = 10**grid_la_m2[0]
                    bound_high = 10**grid_la_m2[-1]
                    frac_clamped = np.mean((np.abs(alpha_hats - bound_low) < 1e-4) | (np.abs(alpha_hats - bound_high) < 1e-4))
                    
                    cov_str = "N/A" if sigma == 0 else f"{100.0 * cov_count / num_replications:4.1f}%"
                    per_inv_ms = (cell_dur / num_replications) * 1000.0
                    
                    is_not_identifiable = (frac_clamped > 0.5) or (sigma > 0 and spread_log < 0.5 * mean_crb)
                    tag = "**Not Identifiable**" if is_not_identifiable else (f"CRB: {mean_crb:.4f}" if sigma > 0 else "sigma=0 floor")
                    
                    row_info = {
                        'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                        'med_rel_err': med_rel_err, 'spread_log': spread_log, 'cov_str': cov_str,
                        'per_inv_ms': per_inv_ms, 'tag': tag, 'mean_crb': mean_crb
                    }
                    m2_rows.append(row_info)
                    
                    print(f"{split:15s} | {alpha_true:5.3f} | {num_sensors:7d} | {sigma:5.2f} | "
                          f"{med_rel_err:10.4f} | {spread_log:11.4f} | {cov_str:6s} | {per_inv_ms:8.3f} | {tag}")

    m2_mean_per_inversion_ms = (m2_total_time / m2_total_inversions) * 1000.0
    print(f"\nMode 2 Precompute Time: {t_pre_m2:.2f} s")
    print(f"Mode 2 Mean Time per Inversion: {m2_mean_per_inversion_ms:.3f} ms ({m2_mean_per_inversion_ms/1000.0:.6f} s)")

    # ----------------- MODE 3 BENCHMARK -----------------
    print("\n" + "=" * 135)
    print("MODE 3 COMPLETE TABLE (FNO Spline Refactor)")
    print("=" * 135)
    print(f"{'Split':15s} | {'Alpha':5s} | {'Sensors':7s} | {'Sigma':5s} | {'MedRelErr (Train)':17s} | {'MedRelErr (Narrow)':18s} | {'MedRelErr (Wide)':16s} | {'FracWide>4':10s} | {'Sprd/CRB':8s} | {'Time(ms)':8s}")
    print("-" * 135)

    m3_total_time = 0.0
    m3_total_inversions = 0
    m3_rows = []

    for split, alphas in splits_dict.items():
        for alpha_true in alphas:
            for num_sensors in sensor_counts_m3:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_np, t_np, seed=100 + int(alpha_true*100) + num_sensors)
                for sigma in noise_levels:
                    alpha_hats_train = []
                    alpha_hats_narrow = []
                    alpha_hats_wide = []
                    crbs_log = []
                    
                    t_cell_start = time.time()
                    for t_s, x_s, t_idx, x_idx in layouts:
                        u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                        if sigma > 0:
                            y_s = u_exact + np.random.normal(0, sigma, size=num_sensors)
                        else:
                            y_s = u_exact
                            
                        crb_val = cramer_rao_bound(alpha_true, t_s, x_s, sigma)
                        crb_std_log = np.sqrt(crb_val) / (alpha_true * np.log(10)) if (crb_val != np.inf and crb_val != 0) else 0.0
                        crbs_log.append(crb_std_log)
                        
                        # Spline on precomputed FNO outputs
                        cs_fno = CubicSpline(grid_la_fno, fno_grid_all[:, t_idx, x_idx], axis=0)
                        
                        # Train bounds
                        res_train = opt.minimize_scalar(lambda la: np.mean((cs_fno(la) - y_s)**2),
                                                       bounds=bounds_train, method='bounded')
                        alpha_hats_train.append(10**res_train.x)
                        
                        # Narrow bounds
                        res_narrow = opt.minimize_scalar(lambda la: np.mean((cs_fno(la) - y_s)**2),
                                                        bounds=bounds_narrow, method='bounded')
                        alpha_hats_narrow.append(10**res_narrow.x)
                        
                        # Wide bounds
                        res_wide = opt.minimize_scalar(lambda la: np.mean((cs_fno(la) - y_s)**2),
                                                      bounds=bounds_wide, method='bounded')
                        alpha_hats_wide.append(10**res_wide.x)
                        
                    t_cell_end = time.time()
                    cell_dur = t_cell_end - t_cell_start
                    m3_total_time += cell_dur
                    m3_total_inversions += num_replications
                    
                    alpha_hats_train = np.array(alpha_hats_train)
                    alpha_hats_narrow = np.array(alpha_hats_narrow)
                    alpha_hats_wide = np.array(alpha_hats_wide)
                    
                    med_train = np.median(np.abs(alpha_hats_train - alpha_true) / alpha_true)
                    med_narrow = np.median(np.abs(alpha_hats_narrow - alpha_true) / alpha_true)
                    med_wide = np.median(np.abs(alpha_hats_wide - alpha_true) / alpha_true)
                    frac_wide_gt_4 = np.mean(alpha_hats_wide > 4.0)
                    
                    mean_crb = np.mean(crbs_log)
                    spread_narrow = np.std(np.log10(alpha_hats_narrow))
                    
                    if sigma == 0:
                        sprd_crb_str = "N/A (bias)"
                    else:
                        sprd_crb_ratio = spread_narrow / mean_crb if mean_crb > 0 else 0.0
                        sprd_crb_str = f"{sprd_crb_ratio:8.2f}"
                        
                    per_inv_ms = (cell_dur / num_replications) * 1000.0
                    
                    row_info = {
                        'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                        'med_train': med_train, 'med_narrow': med_narrow, 'med_wide': med_wide,
                        'frac_wide_gt_4': frac_wide_gt_4, 'sprd_crb_str': sprd_crb_str, 'per_inv_ms': per_inv_ms
                    }
                    m3_rows.append(row_info)
                    
                    print(f"{split:15s} | {alpha_true:5.3f} | {num_sensors:7d} | {sigma:5.2f} | "
                          f"{med_train:17.4f} | {med_narrow:18.4f} | {med_wide:16.4f} | {frac_wide_gt_4:10.2f} | {sprd_crb_str:8s} | {per_inv_ms:8.3f}")

    m3_mean_per_inversion_ms = (m3_total_time / m3_total_inversions) * 1000.0
    print(f"\nMode 3 Precompute Time: {t_pre_fno:.2f} s")
    print(f"Mode 3 Mean Time per Inversion: {m3_mean_per_inversion_ms:.3f} ms ({m3_mean_per_inversion_ms/1000.0:.6f} s)")

    # Save summary data
    np.savez('data/spline_pipeline_results.npz',
             m2_precompute_s=t_pre_m2,
             m2_per_inv_ms=m2_mean_per_inversion_ms,
             m3_precompute_s=t_pre_fno,
             m3_per_inv_ms=m3_mean_per_inversion_ms)

if __name__ == '__main__':
    run_spline_pipeline()
