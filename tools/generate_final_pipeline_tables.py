try:
    from paths import RESULTS, MODELS
except ImportError:
    from src.paths import RESULTS, MODELS
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.interpolate import CubicSpline
import scipy.optimize as opt
import torch
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
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

def main():
    print("=" * 110)
    print("RUNNING FINAL CONSOLIDATED INVERSE PIPELINE EVALUATION")
    print("=" * 110)

    # 5 alphas per split as requested
    alphas_dict = {
        'Interpolation': [0.02, 0.05, 0.1, 0.2, 0.5],
        'Low-alpha OOD': [0.002, 0.003, 0.004, 0.005, 0.008],
        'High-alpha OOD': [1.5, 2.0, 2.5, 3.0, 4.0]
    }

    sensor_counts_m2 = [2, 5, 10, 20]
    sensor_counts_m3 = [5, 10, 20]
    noise_levels = [0.0, 0.01, 0.05]
    num_replications = 200

    Nx, Nt = 50, 100
    x_grid = np.linspace(0, 1, Nx)
    t_grid = np.linspace(0, 1, Nt)

    # Operational bounds: log10(0.001) to log10(4.0)
    bound_log_low = -3.0
    bound_log_high = np.log10(4.0)
    grid_la = np.linspace(bound_log_low, bound_log_high, 300)

    # -------------------------------------------------------------
    # PRECOMPUTE MODE 2 (Crank-Nicolson)
    # -------------------------------------------------------------
    print("\nPrecomputing Mode 2 (Crank-Nicolson) 300 grid points...")
    t0 = time.time()
    U_m2 = np.array([solve_heat_1d_cn(Nx, Nt, 10**la)[2] for la in grid_la])
    t_pre_m2 = time.time() - t0
    print(f"Mode 2 Precompute Time: {t_pre_m2:.2f} s")

    # -------------------------------------------------------------
    # PRECOMPUTE MODE 3 (FNO)
    # -------------------------------------------------------------
    print("Precomputing Mode 3 (FNO) 300 grid points...")
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

    # Bounds for Mode 3 Train comparison
    bounds_train = (np.log10(0.01), np.log10(1.0))
    bounds_narrow = (bound_log_low, bound_log_high)

    # -------------------------------------------------------------
    # BENCHMARK MODE 2
    # -------------------------------------------------------------
    print("\n" + "=" * 130)
    print("MODE 2 BENCHMARK RESULTS (Crank-Nicolson Spline)")
    print("=" * 130)
    print(f"{'Split':15s} | {'Alpha':5s} | {'Sensors':7s} | {'Sigma':5s} | {'MedRelErr':10s} | {'Spread(log)':11s} | {'WaldCov95':10s} | {'FracBound':9s} | {'Time/Fit':9s} | {'Status'}")
    print("-" * 130)

    m2_total_time = 0.0
    m2_total_fits = 0
    m2_table_records = []

    for split, alphas in alphas_dict.items():
        for alpha_true in alphas:
            for num_sensors in sensor_counts_m2:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid, seed=int(alpha_true*1000) + num_sensors)
                for sigma in noise_levels:
                    alpha_hats = []
                    crbs_log = []
                    cov_count = 0
                    bound_hits = 0

                    t_start = time.time()
                    for t_s, x_s, t_idx, x_idx in layouts:
                        u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                        y_s = u_exact + np.random.normal(0, sigma, size=num_sensors) if sigma > 0 else u_exact

                        crb_val = cramer_rao_bound(alpha_true, t_s, x_s, sigma)
                        crb_std_log = np.sqrt(crb_val) / (alpha_true * np.log(10)) if (crb_val != np.inf and crb_val != 0) else 0.0
                        crbs_log.append(crb_std_log)

                        cs = CubicSpline(grid_la, U_m2[:, t_idx, x_idx], axis=0)
                        res = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                                                 bounds=bounds_narrow, method='bounded')
                        hat = 10**res.x
                        alpha_hats.append(hat)

                        # Check bound hit (within 1e-3 of boundary)
                        if abs(res.x - bound_log_low) < 1e-3 or abs(res.x - bound_log_high) < 1e-3:
                            bound_hits += 1

                        if sigma > 0:
                            crb_hat = cramer_rao_bound(hat, t_s, x_s, sigma)
                            if crb_hat != np.inf and crb_hat != 0:
                                se_hat = np.sqrt(crb_hat) / (hat * np.log(10))
                                lower = np.log10(hat) - 1.96 * se_hat
                                upper = np.log10(hat) + 1.96 * se_hat
                                if lower <= np.log10(alpha_true) <= upper:
                                    cov_count += 1

                    dur = time.time() - t_start
                    m2_total_time += dur
                    m2_total_fits += num_replications

                    alpha_hats = np.array(alpha_hats)
                    med_rel_err = np.median(np.abs(alpha_hats - alpha_true) / alpha_true)
                    spread_log = np.std(np.log10(alpha_hats))
                    frac_bound = bound_hits / num_replications

                    if sigma == 0:
                        cov_str = "N/A"
                        status = "sigma=0 floor"
                    else:
                        cov_pct = 100.0 * cov_count / num_replications
                        cov_str = f"{cov_pct:4.1f}%"
                        # Identifiability rule: Wald cov < 90% or frac_bound >= 0.10
                        if cov_pct < 90.0 or frac_bound >= 0.10 or abs(med_rel_err - 0.8000) < 0.05:
                            status = "**Not Identifiable**"
                        else:
                            status = "Identifiable"

                    time_per_fit_ms = (dur / num_replications) * 1000.0
                    rec = {
                        'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                        'med_rel_err': med_rel_err, 'spread_log': spread_log, 'cov_str': cov_str,
                        'frac_bound': frac_bound, 'time_ms': time_per_fit_ms, 'status': status
                    }
                    m2_table_records.append(rec)
                    print(f"{split:15s} | {alpha_true:5.3f} | {num_sensors:7d} | {sigma:5.2f} | "
                          f"{med_rel_err:10.4f} | {spread_log:11.4f} | {cov_str:10s} | {frac_bound:9.2f} | {time_per_fit_ms:7.3f} ms | {status}")

    m2_mean_time_per_fit = (m2_total_time / m2_total_fits) * 1000.0
    print(f"\nMode 2 Overall Mean Time per Single Fit: {m2_mean_time_per_fit:.3f} ms ({m2_mean_time_per_fit/1000.0:.6f} s)")

    # -------------------------------------------------------------
    # BENCHMARK MODE 3
    # -------------------------------------------------------------
    print("\n" + "=" * 140)
    print("MODE 3 BENCHMARK RESULTS (FNO Spline - Single Fit Timing)")
    print("=" * 140)
    print(f"{'Split':15s} | {'Alpha':5s} | {'Sensors':7s} | {'Sigma':5s} | {'MedRelErr(Train)':17s} | {'MedRelErr(Narrow)':18s} | {'Sprd/CRB':8s} | {'WaldCov95':10s} | {'FracBound':9s} | {'Time/Fit':9s} | {'Status'}")
    print("-" * 140)

    m3_total_time_single_fit = 0.0
    m3_total_fits = 0
    m3_table_records = []

    for split, alphas in alphas_dict.items():
        for alpha_true in alphas:
            for num_sensors in sensor_counts_m3:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid, seed=int(alpha_true*2000) + num_sensors)
                for sigma in noise_levels:
                    alpha_hats_train = []
                    alpha_hats_narrow = []
                    crbs_log = []
                    cov_count = 0
                    bound_hits = 0

                    t_start = time.time()
                    for t_s, x_s, t_idx, x_idx in layouts:
                        u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                        y_s = u_exact + np.random.normal(0, sigma, size=num_sensors) if sigma > 0 else u_exact

                        crb_val = cramer_rao_bound(alpha_true, t_s, x_s, sigma)
                        crb_std_log = np.sqrt(crb_val) / (alpha_true * np.log(10)) if (crb_val != np.inf and crb_val != 0) else 0.0
                        crbs_log.append(crb_std_log)

                        cs = CubicSpline(grid_la, fno_grid[:, t_idx, x_idx], axis=0)
                        
                        # Train fit (for comparison)
                        res_tr = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                                                    bounds=bounds_train, method='bounded')
                        alpha_hats_train.append(10**res_tr.x)

                        # Primary operational fit (Narrow)
                        res_nr = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                                                    bounds=bounds_narrow, method='bounded')
                        hat = 10**res_nr.x
                        alpha_hats_narrow.append(hat)

                        if abs(res_nr.x - bound_log_low) < 1e-3 or abs(res_nr.x - bound_log_high) < 1e-3:
                            bound_hits += 1

                        if sigma > 0:
                            crb_hat = cramer_rao_bound(hat, t_s, x_s, sigma)
                            if crb_hat != np.inf and crb_hat != 0:
                                se_hat = np.sqrt(crb_hat) / (hat * np.log(10))
                                lower = np.log10(hat) - 1.96 * se_hat
                                upper = np.log10(hat) + 1.96 * se_hat
                                if lower <= np.log10(alpha_true) <= upper:
                                    cov_count += 1

                    dur = time.time() - t_start
                    # dur measures both train and narrow fits; single fit time is dur / 2
                    single_fit_dur = dur / 2.0
                    m3_total_time_single_fit += single_fit_dur
                    m3_total_fits += num_replications

                    alpha_hats_train = np.array(alpha_hats_train)
                    alpha_hats_narrow = np.array(alpha_hats_narrow)

                    med_train = np.median(np.abs(alpha_hats_train - alpha_true) / alpha_true)
                    med_narrow = np.median(np.abs(alpha_hats_narrow - alpha_true) / alpha_true)
                    spread_log = np.std(np.log10(alpha_hats_narrow))
                    mean_crb = np.mean(crbs_log)
                    frac_bound = bound_hits / num_replications

                    if sigma == 0:
                        sprd_crb_str = "N/A"
                        cov_str = "N/A"
                        status = "sigma=0 bias"
                    else:
                        sprd_crb = spread_log / mean_crb if mean_crb > 0 else 0.0
                        sprd_crb_str = f"{sprd_crb:8.2f}"
                        cov_pct = 100.0 * cov_count / num_replications
                        cov_str = f"{cov_pct:4.1f}%"
                        if cov_pct < 90.0 or frac_bound >= 0.10 or abs(med_narrow - 0.8000) < 0.05:
                            status = "**Not Identifiable**"
                        else:
                            status = "Identifiable"

                    time_per_fit_ms = (single_fit_dur / num_replications) * 1000.0
                    rec = {
                        'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                        'med_train': med_train, 'med_narrow': med_narrow, 'sprd_crb_str': sprd_crb_str,
                        'cov_str': cov_str, 'frac_bound': frac_bound, 'time_ms': time_per_fit_ms, 'status': status
                    }
                    m3_table_records.append(rec)
                    print(f"{split:15s} | {alpha_true:5.3f} | {num_sensors:7d} | {sigma:5.2f} | "
                          f"{med_train:17.4f} | {med_narrow:18.4f} | {sprd_crb_str:8s} | {cov_str:10s} | {frac_bound:9.2f} | {time_per_fit_ms:7.3f} ms | {status}")

    m3_mean_time_per_fit = (m3_total_time_single_fit / m3_total_fits) * 1000.0
    print(f"\nMode 3 Overall Mean Time per Single Fit: {m3_mean_time_per_fit:.3f} ms ({m3_mean_time_per_fit/1000.0:.6f} s)")

    # Save to disk
    import pickle
    with open(str(RESULTS / 'final_pipeline_tables.pkl'), 'wb') as f:
        pickle.dump({
            'm2_records': m2_table_records,
            'm3_records': m3_table_records,
            'm2_pre_s': t_pre_m2,
            'm3_pre_s': t_pre_m3,
            'm2_fit_ms': m2_mean_time_per_fit,
            'm3_fit_ms': m3_mean_time_per_fit
        }, f)
    print(f"\nSaved final records to {RESULTS / 'final_pipeline_tables.pkl'}.")

if __name__ == '__main__':
    main()
