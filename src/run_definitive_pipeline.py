try:
    from paths import RESULTS
except ImportError:
    from src.paths import RESULTS
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.interpolate import CubicSpline
import scipy.optimize as opt
import torch
import time
import os
import sys
import csv

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

def run_pipeline():
    print("=" * 110)
    print("DEFINITIVE INVERSE PIPELINE EXECUTION (UPPER BOUND = 10, DEPLOYABLE BIAS CORRECTION)")
    print("=" * 110)

    # 15 alpha values categorized cleanly
    splits_dict = {
        'Extended Low-alpha OOD': [0.002],
        'Low-alpha OOD': [0.003, 0.004, 0.005, 0.008],
        'Interpolation': [0.02, 0.05, 0.1, 0.2, 0.5],
        'High-alpha OOD': [1.5, 2.0, 2.5, 3.0],
        'Extended High-alpha OOD': [4.0]
    }

    sensor_counts_m2 = [2, 5, 10, 20]
    sensor_counts_m3 = [5, 10, 20]
    noise_levels = [0.0, 0.01, 0.05]
    num_replications = 200

    Nx, Nt = 50, 100
    x_grid = np.linspace(0, 1, Nx)
    t_grid = np.linspace(0, 1, Nt)

    # Search bounds: log10(0.001) to log10(10.0) -> bounds=[-3.0, 1.0]
    bound_log_low = -3.0
    bound_log_high = 1.0 # 10^1.0 = 10.0!
    bound_narrow_high = np.log10(4.0) # narrow bound for Mode 3 comparison
    
    # Precomputation grid: 350 points from log10(0.001) to log10(10.0)
    grid_la = np.linspace(bound_log_low, bound_log_high, 350)

    # -------------------------------------------------------------
    # 1. PRECOMPUTE CRANK-NICOLSON (MODE 2)
    # -------------------------------------------------------------
    print("\nPrecomputing Mode 2 (Crank-Nicolson) on 350 grid points up to alpha=10...")
    t0 = time.time()
    U_m2 = np.array([solve_heat_1d_cn(Nx, Nt, 10**la)[2] for la in grid_la])
    t_pre_m2 = time.time() - t0
    print(f"Mode 2 Precompute Time: {t_pre_m2:.2f} s")

    # -------------------------------------------------------------
    # 2. PRECOMPUTE FNO (MODE 3)
    # -------------------------------------------------------------
    print("Precomputing Mode 3 (FNO) on 350 grid points up to alpha=10...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    checkpoint = torch.load('models/fno2d_heat.pt', map_location=device)
    model = FNO2d(modes1=16, modes2=12, width=32).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    log_alpha_mean = checkpoint['log_alpha_mean'].item()
    log_alpha_std = checkpoint['log_alpha_std'].item()

    t_mesh, x_mesh = np.meshgrid(t_grid, x_grid, indexing='ij')
    t_tensor = torch.tensor(2 * t_mesh - 1, dtype=torch.float32).to(device)
    x_tensor = torch.tensor(2 * x_mesh - 1, dtype=torch.float32).to(device)

    t0 = time.time()
    out_list = []
    batch_size = 50
    for i in range(0, len(grid_la), batch_size):
        batch_la = grid_la[i:i+batch_size]
        x_inputs = []
        for la in batch_la:
            a_scaled = (la - log_alpha_mean) / log_alpha_std
            a_tensor = torch.full_like(t_tensor, a_scaled)
            x_inputs.append(torch.stack([t_tensor, x_tensor, a_tensor], dim=0))
        x_batch = torch.stack(x_inputs, dim=0)
        with torch.no_grad():
            out_batch = model(x_batch).squeeze(1).cpu().numpy()
        out_list.append(out_batch)
    fno_grid = np.concatenate(out_list, axis=0)
    t_pre_m3 = time.time() - t0
    print(f"Mode 3 Precompute Time: {t_pre_m3:.2f} s")

    # -------------------------------------------------------------
    # 3. PRECOMPUTE DEPLOYABLE SIGMA=0 BIAS LOOKUP FOR BOTH MODES
    # -------------------------------------------------------------
    # For a deployable interval, b is estimated from the sigma=0 run for that forward model.
    # We precompute b(alpha_grid, layout) at grid_la or per-alpha to interpolate b(hat_alpha).
    # Since b(hat_alpha) is an intrinsic property of the model surrogate:
    # Mode 2 bias curve b_m2(alpha):
    # Mode 3 bias curve b_m3(alpha):
    print("Computing surrogate bias lookup curves b_model(alpha) for deployable bias correction...")
    # Evaluate sigma=0 bias on a 100-point reference curve
    alpha_ref_curve = np.logspace(-3.0, 1.0, 100)
    la_ref_curve = np.log10(alpha_ref_curve)
    
    # We test on 20-sensor layout for reference bias
    t_log_ref = np.logspace(np.log10(0.01), np.log10(1.0), 20)
    t_idx_ref = [np.argmin(np.abs(t_grid - t)) for t in t_log_ref]
    x_idx_ref = [25] * 20
    
    cs_m2_ref = CubicSpline(grid_la, U_m2[:, t_idx_ref, x_idx_ref], axis=0)
    cs_m3_ref = CubicSpline(grid_la, fno_grid[:, t_idx_ref, x_idx_ref], axis=0)
    
    b_m2_curve = []
    b_m3_curve = []
    for a_val in alpha_ref_curve:
        y_ref = solve_heat_1d_exact(x_grid[x_idx_ref], t_grid[t_idx_ref], a_val)
        res_m2 = opt.minimize_scalar(lambda la: np.mean((cs_m2_ref(la) - y_ref)**2), bounds=(bound_log_low, bound_log_high), method='bounded')
        res_m3 = opt.minimize_scalar(lambda la: np.mean((cs_m3_ref(la) - y_ref)**2), bounds=(bound_log_low, bound_log_high), method='bounded')
        b_m2_curve.append(res_m2.x - np.log10(a_val))
        b_m3_curve.append(res_m3.x - np.log10(a_val))
        
    cs_b_m2 = CubicSpline(la_ref_curve, b_m2_curve)
    cs_b_m3 = CubicSpline(la_ref_curve, b_m3_curve)

    # -------------------------------------------------------------
    # 4. BENCHMARK MODE 2
    # -------------------------------------------------------------
    print("\nExecuting Mode 2 Benchmark across all cells...")
    m2_records = []
    m2_total_time = 0.0
    m2_total_fits = 0

    for split, alphas in splits_dict.items():
        for alpha_true in alphas:
            for num_sensors in sensor_counts_m2:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid, seed=int(alpha_true*1000) + num_sensors)
                for sigma in noise_levels:
                    alpha_hats = []
                    bound_hits = 0
                    wald_cov_count = 0
                    deployable_cov_count = 0

                    t_start = time.time()
                    for t_s, x_s, t_idx, x_idx in layouts:
                        u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                        y_s = u_exact + np.random.normal(0, sigma, size=num_sensors) if sigma > 0 else u_exact

                        cs = CubicSpline(grid_la, U_m2[:, t_idx, x_idx], axis=0)
                        res = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                                                 bounds=(bound_log_low, bound_log_high), method='bounded')
                        hat = 10**res.x
                        alpha_hats.append(hat)

                        # Bound hit: within 1e-3 of [-3.0, 1.0]
                        if abs(res.x - bound_log_low) < 1e-3 or abs(res.x - bound_log_high) < 1e-3:
                            bound_hits += 1

                        if sigma > 0:
                            crb_hat = cramer_rao_bound(hat, t_s, x_s, sigma)
                            if crb_hat != np.inf and crb_hat != 0:
                                se_hat = np.sqrt(crb_hat) / (hat * np.log(10))
                                # 1. Standard Wald CI
                                if np.log10(hat) - 1.96 * se_hat <= np.log10(alpha_true) <= np.log10(hat) + 1.96 * se_hat:
                                    wald_cov_count += 1
                                # 2. Deployable bias-corrected CI: sqrt(se^2 + b^2) where b is from sigma=0 lookup at hat
                                b_est = cs_b_m2(np.clip(res.x, -3.0, 1.0))
                                total_uncertainty = np.sqrt(se_hat**2 + b_est**2)
                                if (res.x - b_est) - 1.96 * total_uncertainty <= np.log10(alpha_true) <= (res.x - b_est) + 1.96 * total_uncertainty:
                                    deployable_cov_count += 1

                    dur = time.time() - t_start
                    m2_total_time += dur
                    m2_total_fits += num_replications

                    alpha_hats = np.array(alpha_hats)
                    med_rel_err = np.median(np.abs(alpha_hats - alpha_true) / alpha_true)
                    spread_log = np.std(np.log10(alpha_hats))
                    frac_bound = bound_hits / num_replications
                    time_per_fit_ms = (dur / num_replications) * 1000.0

                    if sigma == 0:
                        wald_cov_str = "N/A"
                        deploy_cov_str = "N/A"
                        status = "sigma=0 floor"
                    else:
                        w_cov = 100.0 * wald_cov_count / num_replications
                        d_cov = 100.0 * deployable_cov_count / num_replications
                        wald_cov_str = f"{w_cov:4.1f}%"
                        deploy_cov_str = f"{d_cov:4.1f}%"
                        
                        # Unified Status Rule:
                        if frac_bound >= 0.10 or w_cov < 80.0:
                            status = "Not Identifiable"
                        elif w_cov < 90.0:
                            # Check if bias-dominated: deployable coverage restores it to >= 90%
                            if d_cov >= 90.0:
                                status = "bias-dominated"
                            else:
                                status = "Not Identifiable"
                        else:
                            status = "Identifiable"

                    m2_records.append({
                        'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                        'med_rel_err': med_rel_err, 'spread_log': spread_log, 'wald_cov_95': wald_cov_str,
                        'deploy_cov_95': deploy_cov_str, 'frac_bound': frac_bound, 'time_ms': time_per_fit_ms,
                        'status': status
                    })

    m2_mean_fit_ms = (m2_total_time / m2_total_fits) * 1000.0
    print(f"Mode 2 completed. Mean single-fit time: {m2_mean_fit_ms:.3f} ms")

    # -------------------------------------------------------------
    # 5. BENCHMARK MODE 3 (NARROW AND WIDE BOUNDS REPORTED)
    # -------------------------------------------------------------
    print("\nExecuting Mode 3 Benchmark across all cells...")
    m3_records = []
    m3_total_time = 0.0
    m3_total_fits = 0

    for split, alphas in splits_dict.items():
        for alpha_true in alphas:
            for num_sensors in sensor_counts_m3:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid, seed=int(alpha_true*2000) + num_sensors)
                for sigma in noise_levels:
                    alpha_hats_narrow = []
                    alpha_hats_wide = []
                    crbs_log = []
                    bound_hits = 0
                    wald_cov_count = 0
                    deployable_cov_count = 0

                    t_start = time.time()
                    for t_s, x_s, t_idx, x_idx in layouts:
                        u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                        y_s = u_exact + np.random.normal(0, sigma, size=num_sensors) if sigma > 0 else u_exact

                        crb_val = cramer_rao_bound(alpha_true, t_s, x_s, sigma)
                        crb_std_log = np.sqrt(crb_val) / (alpha_true * np.log(10)) if (crb_val != np.inf and crb_val != 0) else 0.0
                        crbs_log.append(crb_std_log)

                        cs = CubicSpline(grid_la, fno_grid[:, t_idx, x_idx], axis=0)

                        # 1. Narrow fit: bounds [-3.0, log10(4.0)]
                        res_nr = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                                                    bounds=(bound_log_low, bound_narrow_high), method='bounded')
                        alpha_hats_narrow.append(10**res_nr.x)

                        # 2. Wide fit: bounds [-3.0, 1.0] (up to alpha=10)
                        res_wd = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                                                    bounds=(bound_log_low, bound_log_high), method='bounded')
                        hat_wide = 10**res_wd.x
                        alpha_hats_wide.append(hat_wide)

                        if abs(res_wd.x - bound_log_low) < 1e-3 or abs(res_wd.x - bound_log_high) < 1e-3:
                            bound_hits += 1

                        if sigma > 0:
                            crb_hat = cramer_rao_bound(hat_wide, t_s, x_s, sigma)
                            if crb_hat != np.inf and crb_hat != 0:
                                se_hat = np.sqrt(crb_hat) / (hat_wide * np.log(10))
                                # Standard Wald CI
                                if np.log10(hat_wide) - 1.96 * se_hat <= np.log10(alpha_true) <= np.log10(hat_wide) + 1.96 * se_hat:
                                    wald_cov_count += 1
                                # Deployable bias-corrected CI: sqrt(se^2 + b^2)
                                b_est = cs_b_m3(np.clip(res_wd.x, -3.0, 1.0))
                                total_uncertainty = np.sqrt(se_hat**2 + b_est**2)
                                if (res_wd.x - b_est) - 1.96 * total_uncertainty <= np.log10(alpha_true) <= (res_wd.x - b_est) + 1.96 * total_uncertainty:
                                    deployable_cov_count += 1

                    dur = time.time() - t_start
                    # Two fits executed; per single fit time is dur / 2
                    single_fit_time = dur / 2.0
                    m3_total_time += single_fit_time
                    m3_total_fits += num_replications

                    alpha_hats_narrow = np.array(alpha_hats_narrow)
                    alpha_hats_wide = np.array(alpha_hats_wide)

                    med_narrow = np.median(np.abs(alpha_hats_narrow - alpha_true) / alpha_true)
                    med_wide = np.median(np.abs(alpha_hats_wide - alpha_true) / alpha_true)
                    spread_wide = np.std(np.log10(alpha_hats_wide))
                    mean_crb = np.mean(crbs_log)
                    frac_bound = bound_hits / num_replications
                    time_per_fit_ms = (single_fit_time / num_replications) * 1000.0

                    if sigma == 0:
                        sprd_crb_str = "N/A"
                        wald_cov_str = "N/A"
                        deploy_cov_str = "N/A"
                        status = "sigma=0 bias"
                    else:
                        sprd_crb = spread_wide / mean_crb if mean_crb > 0 else 0.0
                        sprd_crb_str = f"{sprd_crb:6.2f}"
                        w_cov = 100.0 * wald_cov_count / num_replications
                        d_cov = 100.0 * deployable_cov_count / num_replications
                        wald_cov_str = f"{w_cov:4.1f}%"
                        deploy_cov_str = f"{d_cov:4.1f}%"

                        # Unified Status Rule:
                        if frac_bound >= 0.10 or w_cov < 80.0:
                            # If w_cov was pulled down purely by surrogate bias and deployable coverage is >= 90%
                            if d_cov >= 90.0 and frac_bound < 0.10:
                                status = "bias-dominated (FNO)"
                            else:
                                status = "Not Identifiable"
                        elif w_cov < 90.0:
                            if d_cov >= 90.0:
                                status = "bias-dominated (FNO)"
                            else:
                                status = "Not Identifiable"
                        else:
                            status = "Identifiable"

                    m3_records.append({
                        'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                        'med_narrow': med_narrow, 'med_wide': med_wide, 'sprd_crb': sprd_crb_str,
                        'wald_cov_95': wald_cov_str, 'deploy_cov_95': deploy_cov_str,
                        'frac_bound': frac_bound, 'time_ms': time_per_fit_ms, 'status': status
                    })

    m3_mean_fit_ms = (m3_total_time / m3_total_fits) * 1000.0
    print(f"Mode 3 completed. Mean single-fit time: {m3_mean_fit_ms:.3f} ms")

    # -------------------------------------------------------------
    # 6. EXPORT UPDATED CSV FILES
    # -------------------------------------------------------------
    os.makedirs(str(RESULTS), exist_ok=True)
    csv_m2_path = str(RESULTS / 'mode2_pipeline_results_v2.csv')
    with open(csv_m2_path, 'w', newline='') as f:
        fields = ['split', 'alpha', 'sensors', 'sigma', 'med_rel_err', 'spread_log', 'wald_cov_95', 'deploy_cov_95', 'frac_bound', 'single_fit_time_ms', 'status']
        w = csv.writer(f)
        w.writerow(fields)
        for r in m2_records:
            w.writerow([r['split'], f"{r['alpha']:.3f}", r['sensors'], f"{r['sigma']:.2f}",
                        f"{r['med_rel_err']:.6f}", f"{r['spread_log']:.6f}", r['wald_cov_95'],
                        r['deploy_cov_95'], f"{r['frac_bound']:.3f}", f"{r['time_ms']:.3f}", r['status']])

    csv_m3_path = str(RESULTS / 'mode3_pipeline_results_v2.csv')
    with open(csv_m3_path, 'w', newline='') as f:
        fields = ['split', 'alpha', 'sensors', 'sigma', 'med_narrow', 'med_wide', 'sprd_crb', 'wald_cov_95', 'deploy_cov_95', 'frac_bound', 'single_fit_time_ms', 'status']
        w = csv.writer(f)
        w.writerow(fields)
        for r in m3_records:
            w.writerow([r['split'], f"{r['alpha']:.3f}", r['sensors'], f"{r['sigma']:.2f}",
                        f"{r['med_narrow']:.6f}", f"{r['med_wide']:.6f}", r['sprd_crb'],
                        r['wald_cov_95'], r['deploy_cov_95'], f"{r['frac_bound']:.3f}", f"{r['time_ms']:.3f}", r['status']])

    print(f"\nUpdated CSVs successfully written to {csv_m2_path} and {csv_m3_path}.")

if __name__ == '__main__':
    run_pipeline()
