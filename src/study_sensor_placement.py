"""Task A: Sensor Time Placement Study for Hidden Parameter Inversion (Mode 2)

Evaluates sensor time placement strategies at domain center x = 0.5:
  1. uniform: linearly spaced points in [0.01, 1.0]
  2. log-spaced: logarithmically spaced points (canonical pipeline baseline)
  3. early-heavy: quadratic clustering towards t = 0.01
  4. late-heavy: quadratic clustering towards t = 1.0
  5. information-weighted (oracle alpha): quantiles of Fisher info density w(t) ~ t^2 * exp(-2*alpha*pi^2*t)
  6. all-at-t-star (oracle alpha): theoretical upper bound with all sensors at t* = min(1.0, max(0.01, 1/(alpha*pi^2)))
  7. two-stage deployable: place N1 = N//2 sensors log-spaced to obtain a first alpha_hat, then place N2 = N - N1
     sensors via information-weighting at alpha_hat, followed by joint Mode 2 fit across all N sensors.

Grid:
  N in {5, 10}
  alpha in {0.005, 0.1, 2.5}
  sigma in {0.01, 0.05}
  Replications: 200 per cell

Saves:
  - data/raw/sensor_placement_raw.csv: per-replication outputs (alpha_hat, layout_seed, noise_seed)
  - data/sensor_placement_summary.csv: aggregated cell summary
"""

import os
import sys
import time
import csv
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.interpolate import CubicSpline, interp1d
import scipy.optimize as opt

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def solve_heat_1d_cn_center(Nx, Nt, alpha):
    """Crank-Nicolson solution extracted at center x = 0.5."""
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
    
    center_idx = (Nx - 1) // 2
    for n in range(0, Nt - 1):
        rhs = B.dot(u[n, 1:-1])
        u[n+1, 1:-1] = spla.spsolve(A, rhs)
        u[n+1, 0] = 0.0
        u[n+1, -1] = 0.0
    return t, u[:, center_idx]

def get_time_placements(strategy, alpha, N, t_min=0.01, t_max=1.0):
    """Generate static sensor observation times according to the chosen strategy."""
    u = np.linspace(0.0, 1.0, N)
    if strategy == 'uniform':
        return np.linspace(t_min, t_max, N)
    elif strategy == 'log-spaced':
        return np.logspace(np.log10(t_min), np.log10(t_max), N)
    elif strategy == 'early-heavy':
        return t_min + (t_max - t_min) * (u ** 2)
    elif strategy == 'late-heavy':
        return t_min + (t_max - t_min) * (1.0 - (1.0 - u) ** 2)
    elif strategy == 'information-weighted (oracle alpha)':
        t_fine = np.linspace(t_min, t_max, 5000)
        w = (t_fine ** 2) * np.exp(-2 * alpha * (np.pi ** 2) * t_fine)
        cdf = np.cumsum(w)
        cdf = (cdf - cdf[0]) / (cdf[-1] - cdf[0] + 1e-15)
        u_q = (np.arange(N) + 0.5) / N
        inv_cdf = interp1d(cdf, t_fine, bounds_error=False, fill_value=(t_min, t_max))
        return inv_cdf(u_q)
    elif strategy == 'all-at-t-star (oracle alpha)':
        t_star = min(t_max, max(t_min, 1.0 / (alpha * (np.pi ** 2))))
        return np.full(N, t_star)
    else:
        raise ValueError(f"Unknown static strategy: {strategy}")

def get_info_weighted_times(alpha_hat, N, t_min=0.01, t_max=1.0):
    """Generate information-weighted sensor times evaluated at an estimated alpha_hat."""
    alpha_clamped = np.clip(alpha_hat, 1e-4, 10.0)
    t_fine = np.linspace(t_min, t_max, 2000)
    w = (t_fine ** 2) * np.exp(-2 * alpha_clamped * (np.pi ** 2) * t_fine)
    cdf = np.cumsum(w)
    cdf = (cdf - cdf[0]) / (cdf[-1] - cdf[0] + 1e-15)
    u_q = (np.arange(N) + 0.5) / N
    inv_cdf = interp1d(cdf, t_fine, bounds_error=False, fill_value=(t_min, t_max))
    return inv_cdf(u_q)

def compute_cramer_rao_stats(alpha, t_sensors, sigma):
    """Computes exact Fisher Information and CRB metrics for alpha at center x=0.5."""
    grads = -np.pi**2 * t_sensors * np.exp(-alpha * np.pi**2 * t_sensors)
    fisher_info = np.sum(grads**2) / (sigma**2 + 1e-15)
    if fisher_info <= 0:
        return np.inf, np.inf, np.inf, np.inf
    crb_var = 1.0 / fisher_info
    crb_std = np.sqrt(crb_var)
    crb_rel = crb_std / alpha
    crb_log = crb_std / (alpha * np.log(10))
    return crb_var, crb_std, crb_rel, crb_log

def run_task_a():
    print("=" * 115)
    print("TASK A: SENSOR TIME PLACEMENT STUDY (MODE 2)")
    print("=" * 115)
    
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    Nx, Nt = 51, 501
    t_min, t_max = 0.01, 1.0
    bound_log_low = -3.0
    bound_log_high = 1.0
    
    print("Precomputing Crank-Nicolson solutions at domain centre (x = 0.5)...")
    grid_la = np.linspace(bound_log_low, bound_log_high, 300)
    t0_pre = time.time()
    t_grid = np.linspace(0, 1, Nt)
    U_cn_center = np.array([solve_heat_1d_cn_center(Nx, Nt, 10**la)[1] for la in grid_la])
    t_pre = time.time() - t0_pre
    print(f"Precomputation complete: {len(grid_la)} points in {t_pre:.2f} s\n")
    
    cs_time = CubicSpline(t_grid, U_cn_center, axis=1)
    
    strategies = [
        'uniform',
        'log-spaced',
        'early-heavy',
        'late-heavy',
        'information-weighted (oracle alpha)',
        'all-at-t-star (oracle alpha)',
        'two-stage deployable'
    ]
    sensor_counts = [5, 10]
    alphas = [0.005, 0.1, 2.5]
    sigmas = [0.01, 0.05]
    num_reps = 200
    
    raw_csv_path = "data/raw/sensor_placement_raw.csv"
    summary_csv_path = "data/sensor_placement_summary.csv"
    
    raw_rows = []
    summary_rows = []
    
    total_fits = 0
    t0_all = time.time()
    
    header = f"{'Strategy':35s} | {'N':2s} | {'Alpha':5s} | {'Sigma':5s} | {'MedRelErr':10s} | {'CRB(Rel)':9s} | {'SpreadLog':10s} | {'Sprd/CRB':9s} | {'Time(ms)':8s}"
    print(header)
    print("-" * len(header))
    
    for N in sensor_counts:
        for alpha_true in alphas:
            for sigma in sigmas:
                layout_seed = int(alpha_true * 1000) + N
                base_noise_seed = int(alpha_true * 5000) + N * 10 + int(sigma * 100)
                
                # Pre-draw paired noise realizations across all strategies
                rng_noise = np.random.RandomState(base_noise_seed)
                paired_noise = [rng_noise.normal(0, sigma, size=N) for _ in range(num_reps)]
                
                for strat in strategies:
                    hats = []
                    fit_times = []
                    crbs_rel = []
                    crbs_log = []
                    
                    if strat != 'two-stage deployable':
                        # Static sensor placement
                        t_s = get_time_placements(strat, alpha_true, N, t_min, t_max)
                        u_exact = np.exp(-alpha_true * np.pi**2 * t_s)
                        crb_var, crb_std, crb_rel, crb_log = compute_cramer_rao_stats(alpha_true, t_s, sigma)
                        
                        U_s = cs_time(t_s)
                        cs_la = CubicSpline(grid_la, U_s, axis=0)
                        
                        for rep in range(num_reps):
                            noise = paired_noise[rep]
                            y = u_exact + noise
                            
                            t0_fit = time.perf_counter()
                            res = opt.minimize_scalar(
                                lambda la: np.mean((cs_la(la) - y)**2),
                                bounds=(bound_log_low, bound_log_high),
                                method='bounded'
                            )
                            dur_fit = (time.perf_counter() - t0_fit) * 1000.0
                            hat = 10**res.x
                            hats.append(hat)
                            fit_times.append(dur_fit)
                            
                            rel_err = abs(hat - alpha_true) / alpha_true
                            rep_noise_seed = base_noise_seed + rep
                            
                            raw_rows.append({
                                'strategy': strat,
                                'alpha_true': alpha_true,
                                'sensors': N,
                                'sigma': sigma,
                                'rep': rep,
                                'alpha_hat': hat,
                                'rel_err': rel_err,
                                'layout_seed': layout_seed,
                                'noise_seed': rep_noise_seed
                            })
                            
                        crbs_rel = [crb_rel] * num_reps
                        crbs_log = [crb_log] * num_reps
                    else:
                        # Two-stage deployable design: N1 log-spaced, then N2 info-weighted at alpha_hat1
                        N1 = N // 2
                        N2 = N - N1
                        t1 = np.logspace(np.log10(t_min), np.log10(t_max), N1)
                        u_exact1 = np.exp(-alpha_true * np.pi**2 * t1)
                        
                        U_s1 = cs_time(t1)
                        cs_la1 = CubicSpline(grid_la, U_s1, axis=0)
                        
                        for rep in range(num_reps):
                            noise_full = paired_noise[rep]
                            noise1 = noise_full[:N1]
                            noise2 = noise_full[N1:]
                            
                            t0_fit = time.perf_counter()
                            # Stage 1: fit alpha1 from log-spaced sensors
                            y1 = u_exact1 + noise1
                            res1 = opt.minimize_scalar(
                                lambda la: np.mean((cs_la1(la) - y1)**2),
                                bounds=(bound_log_low, bound_log_high),
                                method='bounded'
                            )
                            hat1 = 10**res1.x
                            
                            # Stage 2: information-weighting at hat1
                            t2 = get_info_weighted_times(hat1, N2, t_min, t_max)
                            u_exact2 = np.exp(-alpha_true * np.pi**2 * t2)
                            y2 = u_exact2 + noise2
                            
                            # Joint fit using all N measurements
                            t_all = np.concatenate([t1, t2])
                            y_all = np.concatenate([y1, y2])
                            U_all = cs_time(t_all)
                            cs_la_all = CubicSpline(grid_la, U_all, axis=0)
                            
                            res_final = opt.minimize_scalar(
                                lambda la: np.mean((cs_la_all(la) - y_all)**2),
                                bounds=(bound_log_low, bound_log_high),
                                method='bounded'
                            )
                            dur_fit = (time.perf_counter() - t0_fit) * 1000.0
                            hat_final = 10**res_final.x
                            
                            hats.append(hat_final)
                            fit_times.append(dur_fit)
                            
                            # Per-rep CRB given realized sensor times
                            _, _, crb_r, crb_l = compute_cramer_rao_stats(alpha_true, t_all, sigma)
                            crbs_rel.append(crb_r)
                            crbs_log.append(crb_l)
                            
                            rel_err = abs(hat_final - alpha_true) / alpha_true
                            rep_noise_seed = base_noise_seed + rep
                            
                            raw_rows.append({
                                'strategy': strat,
                                'alpha_true': alpha_true,
                                'sensors': N,
                                'sigma': sigma,
                                'rep': rep,
                                'alpha_hat': hat_final,
                                'rel_err': rel_err,
                                'layout_seed': layout_seed,
                                'noise_seed': rep_noise_seed
                            })
                            
                    total_fits += num_reps
                    hats = np.array(hats)
                    med_rel_err = np.median(np.abs(hats - alpha_true) / alpha_true)
                    mean_rel_err = np.mean(np.abs(hats - alpha_true) / alpha_true)
                    spread_log = np.std(np.log10(hats))
                    mean_crb_rel = np.mean(crbs_rel)
                    mean_crb_log = np.mean(crbs_log)
                    sprd_crb = spread_log / mean_crb_log if mean_crb_log > 0 and mean_crb_log != np.inf else 0.0
                    mean_fit_ms = np.mean(fit_times)
                    
                    summary_rows.append({
                        'strategy': strat,
                        'alpha_true': alpha_true,
                        'sensors': N,
                        'sigma': sigma,
                        'med_rel_err': med_rel_err,
                        'mean_rel_err': mean_rel_err,
                        'spread_log': spread_log,
                        'crb_rel': mean_crb_rel,
                        'crb_log': mean_crb_log,
                        'sprd_crb': sprd_crb,
                        'single_fit_time_ms': mean_fit_ms
                    })
                    
                    print(f"{strat:35s} | {N:2d} | {alpha_true:5.3f} | {sigma:5.2f} | {med_rel_err:10.4f} | {mean_crb_rel:9.4f} | {spread_log:10.4f} | {sprd_crb:9.2f} | {mean_fit_ms:8.3f}")

    # Write raw per-replication CSV
    print(f"\nWriting {len(raw_rows)} per-replication rows to {raw_csv_path}...")
    with open(raw_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'strategy', 'alpha_true', 'sensors', 'sigma', 'rep',
            'alpha_hat', 'rel_err', 'layout_seed', 'noise_seed'
        ])
        writer.writeheader()
        writer.writerows(raw_rows)
        
    # Write summary CSV
    print(f"Writing {len(summary_rows)} cell summaries to {summary_csv_path}...")
    with open(summary_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'strategy', 'alpha_true', 'sensors', 'sigma',
            'med_rel_err', 'mean_rel_err', 'spread_log',
            'crb_rel', 'crb_log', 'sprd_crb',
            'single_fit_time_ms'
        ])
        writer.writeheader()
        writer.writerows(summary_rows)
        
    total_time = time.time() - t0_all
    print(f"\nTask A complete: {total_fits} total fits across 84 cells in {total_time:.2f} s.")

if __name__ == '__main__':
    run_task_a()
