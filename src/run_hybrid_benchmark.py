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
import argparse

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

def classify_cell(med_rel_err, frac_bound, wald_cov_pct, bias_corr_cov_pct, sigma, mode="mode2"):
    """Unified status rule applied identically across all modes inside the pipeline script."""
    if sigma == 0:
        return "sigma=0 floor"
    if med_rel_err <= 0.20 and frac_bound < 0.10:
        if wald_cov_pct >= 90.0:
            return "Identifiable"
        elif bias_corr_cov_pct >= 90.0:
            return "bias-dominated (FNO)" if mode == "mode3" else "bias-dominated"
        else:
            return "bias-uncorrected"
    return "Not Identifiable"

def run_comprehensive_benchmark(target_mode='all'):
    print("=" * 115)
    print(f"DEFINITIVE BENCHMARK: TARGET MODE = {target_mode.upper()}")
    print("=" * 115)

    splits_dict = {
        'Extended Low-alpha OOD': [0.002],
        'Low-alpha OOD': [0.003, 0.004, 0.005, 0.008],
        'Interpolation': [0.02, 0.05, 0.1, 0.2, 0.5],
        'High-alpha OOD': [1.5, 2.0, 2.5, 3.0],
        'Extended High-alpha OOD': [4.0]
    }

    sensor_counts = [5, 10, 20]
    noise_levels = [0.0, 0.01, 0.05]
    num_replications = 200

    Nx, Nt = 50, 100
    x_grid = np.linspace(0, 1, Nx)
    t_grid = np.linspace(0, 1, Nt)

    bound_log_low = -3.0
    bound_log_high = 1.0 # alpha = 10.0
    bound_narrow_high = np.log10(4.0)

    # Precomputation grid for splines
    grid_la = np.linspace(bound_log_low, bound_log_high, 350)
    alpha_ref_curve = np.logspace(-3.0, 1.0, 100)
    la_ref_curve = np.log10(alpha_ref_curve)
    t_log_ref = np.logspace(np.log10(0.01), np.log10(1.0), 20)
    t_idx_ref = [np.argmin(np.abs(t_grid - t)) for t in t_log_ref]
    x_idx_ref = [25] * 20

    U_m2 = None
    cs_b_m2 = None
    if target_mode in ['all', 'mode2', 'ablation']:
        print("\nPrecomputing Mode 2 (Crank-Nicolson) on 350 grid points up to alpha=10...")
        t0 = time.time()
        U_m2 = np.array([solve_heat_1d_cn(Nx, Nt, 10**la)[2] for la in grid_la])
        t_pre_m2 = time.time() - t0
        print(f"Mode 2 Precompute Time: {t_pre_m2:.2f} s")

        cs_m2_ref = CubicSpline(grid_la, U_m2[:, t_idx_ref, x_idx_ref], axis=0)
        b_m2_curve = []
        for a_val in alpha_ref_curve:
            y_ref = solve_heat_1d_exact(x_grid[x_idx_ref], t_grid[t_idx_ref], a_val)
            res_m2 = opt.minimize_scalar(lambda la: np.mean((cs_m2_ref(la) - y_ref)**2), bounds=(bound_log_low, bound_log_high), method='bounded')
            b_m2_curve.append(res_m2.x - np.log10(a_val))
        cs_b_m2 = CubicSpline(la_ref_curve, b_m2_curve)

    fno_grid = None
    cs_b_m3 = None
    if target_mode in ['all', 'mode3', 'ablation']:
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

        cs_m3_ref = CubicSpline(grid_la, fno_grid[:, t_idx_ref, x_idx_ref], axis=0)
        b_m3_curve = []
        for a_val in alpha_ref_curve:
            y_ref = solve_heat_1d_exact(x_grid[x_idx_ref], t_grid[t_idx_ref], a_val)
            res_m3 = opt.minimize_scalar(lambda la: np.mean((cs_m3_ref(la) - y_ref)**2), bounds=(bound_log_low, bound_log_high), method='bounded')
            b_m3_curve.append(res_m3.x - np.log10(a_val))
        cs_b_m3 = CubicSpline(la_ref_curve, b_m3_curve)

    m2_records = []
    m3_records = []
    m3plus_records = []

    m2_total_time = 0.0
    m3_total_time = 0.0
    m3p_total_time = 0.0
    total_fits = 0

    print("\nRunning paired evaluation over identical noise draws across all modes...")

    # We also evaluate 2 sensors for Mode 2
    for split, alphas in splits_dict.items():
        for alpha_true in alphas:
            sensors_to_eval = [5, 10, 20] if target_mode == 'mode3' else [2, 5, 10, 20]
            for num_sensors in sensors_to_eval:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid, seed=int(alpha_true*1000) + num_sensors)
                for sigma in noise_levels:
                    # Pre-generate paired noise realizations
                    rng_noise = np.random.RandomState(int(alpha_true*5000) + num_sensors*10 + int(sigma*100))
                    noise_realizations = [rng_noise.normal(0, sigma, size=num_sensors) if sigma > 0 else np.zeros(num_sensors) for _ in range(num_replications)]

                    # ----------------- MODE 2 -----------------
                    if target_mode in ['all', 'mode2']:
                        m2_hats = []
                        m2_bound_hits = 0
                        m2_wald_cov = 0
                        m2_bcorr_cov = 0
                        t0 = time.time()
                        for rep in range(num_replications):
                            t_s, x_s, t_idx, x_idx = layouts[rep]
                            y = solve_heat_1d_exact(x_s, t_s, alpha_true) + noise_realizations[rep]
                            cs2 = CubicSpline(grid_la, U_m2[:, t_idx, x_idx], axis=0)
                            res2 = opt.minimize_scalar(lambda la: np.mean((cs2(la) - y)**2), bounds=(bound_log_low, bound_log_high), method='bounded')
                            hat2 = 10**res2.x
                            m2_hats.append(hat2)
                            if abs(res2.x - bound_log_low) < 1e-3 or abs(res2.x - bound_log_high) < 1e-3:
                                m2_bound_hits += 1
                            if sigma > 0:
                                crb = cramer_rao_bound(hat2, t_s, x_s, sigma)
                                se = np.sqrt(crb) / (hat2 * np.log(10)) if crb != np.inf and crb != 0 else 0.0
                                if np.log10(hat2) - 1.96*se <= np.log10(alpha_true) <= np.log10(hat2) + 1.96*se:
                                    m2_wald_cov += 1
                                b_est = cs_b_m2(np.clip(res2.x, -3.0, 1.0))
                                sig_tot = np.sqrt(se**2 + b_est**2)
                                if (res2.x - b_est) - 1.96*sig_tot <= np.log10(alpha_true) <= (res2.x - b_est) + 1.96*sig_tot:
                                    m2_bcorr_cov += 1
                        t_m2_dur = time.time() - t0
                        m2_total_time += t_m2_dur
                        
                        m2_hats = np.array(m2_hats)
                        m2_med_err = np.median(np.abs(m2_hats - alpha_true) / alpha_true)
                        m2_spread = np.std(np.log10(m2_hats))
                        m2_fb = m2_bound_hits / num_replications
                        m2_w_pct = m2_wald_cov / num_replications * 100.0 if sigma > 0 else 0.0
                        m2_bc_pct = m2_bcorr_cov / num_replications * 100.0 if sigma > 0 else 0.0
                        m2_status = classify_cell(m2_med_err, m2_fb, m2_w_pct, m2_bc_pct, sigma, mode="mode2")

                        m2_records.append({
                            'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                            'med_rel_err': m2_med_err, 'spread_log': m2_spread,
                            'wald_cov_95': f"{m2_w_pct:4.1f}%" if sigma > 0 else "N/A",
                            'deploy_cov_95': f"{m2_bc_pct:4.1f}%" if sigma > 0 else "N/A",
                            'frac_bound': m2_fb, 'single_fit_time_ms': t_m2_dur / num_replications * 1000.0,
                            'status': m2_status
                        })

                    # If num_sensors in [5, 10, 20], run Mode 3 and Mode 3+ on the EXACT same layout & noise
                    if num_sensors in [5, 10, 20]:
                        total_fits += num_replications

                        # ----------------- MODE 3 -----------------
                        if target_mode in ['all', 'mode3']:
                            m3_hats_n = []
                            m3_hats_w = []
                            m3_bound_hits = 0
                            m3_wald_cov = 0
                            m3_bcorr_cov = 0
                            crbs_log = []
                            t0 = time.time()
                            for rep in range(num_replications):
                                t_s, x_s, t_idx, x_idx = layouts[rep]
                                y = solve_heat_1d_exact(x_s, t_s, alpha_true) + noise_realizations[rep]
                                crb = cramer_rao_bound(alpha_true, t_s, x_s, sigma)
                                crbs_log.append(np.sqrt(crb) / (alpha_true * np.log(10)) if crb != np.inf and crb != 0 else 0.0)

                                cs3 = CubicSpline(grid_la, fno_grid[:, t_idx, x_idx], axis=0)
                                res3_n = opt.minimize_scalar(lambda la: np.mean((cs3(la) - y)**2), bounds=(bound_log_low, bound_narrow_high), method='bounded')
                                res3_w = opt.minimize_scalar(lambda la: np.mean((cs3(la) - y)**2), bounds=(bound_log_low, bound_log_high), method='bounded')
                                
                                hat3_n = 10**res3_n.x
                                hat3_w = 10**res3_w.x
                                m3_hats_n.append(hat3_n)
                                m3_hats_w.append(hat3_w)
                                if abs(res3_w.x - bound_log_low) < 1e-3 or abs(res3_w.x - bound_log_high) < 1e-3:
                                    m3_bound_hits += 1
                                if sigma > 0:
                                    crb_hat = cramer_rao_bound(hat3_w, t_s, x_s, sigma)
                                    se = np.sqrt(crb_hat) / (hat3_w * np.log(10)) if crb_hat != np.inf and crb_hat != 0 else 0.0
                                    if np.log10(hat3_w) - 1.96*se <= np.log10(alpha_true) <= np.log10(hat3_w) + 1.96*se:
                                        m3_wald_cov += 1
                                    b_est = cs_b_m3(np.clip(res3_w.x, -3.0, 1.0))
                                    sig_tot = np.sqrt(se**2 + b_est**2)
                                    if (res3_w.x - b_est) - 1.96*sig_tot <= np.log10(alpha_true) <= (res3_w.x - b_est) + 1.96*sig_tot:
                                        m3_bcorr_cov += 1
                            t_m3_dur = (time.time() - t0) / 2.0 # single fit time
                            m3_total_time += t_m3_dur

                            m3_hats_n = np.array(m3_hats_n)
                            m3_hats_w = np.array(m3_hats_w)
                            m3_med_n = np.median(np.abs(m3_hats_n - alpha_true) / alpha_true)
                            m3_med_w = np.median(np.abs(m3_hats_w - alpha_true) / alpha_true)
                            m3_spread = np.std(np.log10(m3_hats_w))
                            m3_fb = m3_bound_hits / num_replications
                            m3_w_pct = m3_wald_cov / num_replications * 100.0 if sigma > 0 else 0.0
                            m3_bc_pct = m3_bcorr_cov / num_replications * 100.0 if sigma > 0 else 0.0
                            m3_mean_crb = np.mean(crbs_log)
                            m3_sprd_crb = m3_spread / m3_mean_crb if m3_mean_crb > 0 and sigma > 0 else 0.0
                            m3_status = classify_cell(m3_med_w, m3_fb, m3_w_pct, m3_bc_pct, sigma, mode="mode3")
                            med_narrow_repr = "N/A (bound=true)" if abs(alpha_true - 4.0) < 1e-4 else m3_med_n

                            m3_records.append({
                                'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                                'med_narrow': med_narrow_repr, 'med_wide': m3_med_w,
                                'sprd_crb': f"{m3_sprd_crb:6.2f}" if sigma > 0 else "N/A",
                                'wald_cov_95': f"{m3_w_pct:4.1f}%" if sigma > 0 else "N/A",
                                'deploy_cov_95': f"{m3_bc_pct:4.1f}%" if sigma > 0 else "N/A",
                                'frac_bound': m3_fb, 'single_fit_time_ms': t_m3_dur / num_replications * 1000.0,
                                'status': m3_status
                            })

                        # ----------------- MODE 3+ (HYBRID) -----------------
                        # Take Mode 3 estimate hat0, refine by bounded 1-D Brent search using CN solver in ±0.3 decades
                        if target_mode in ['all', 'ablation']:
                            m3p_hats = []
                            m3p_bound_hits = 0
                            m3p_wald_cov = 0
                            m3p_bcorr_cov = 0
                            t0 = time.time()
                            for rep in range(num_replications):
                                t_s, x_s, t_idx, x_idx = layouts[rep]
                                y = solve_heat_1d_exact(x_s, t_s, alpha_true) + noise_realizations[rep]
                                # Initial FNO estimate
                                la_0 = np.log10(m3_hats_w[rep])
                                bracket = (max(-3.0, la_0 - 0.3), min(1.0, la_0 + 0.3))

                                def cn_objective(la):
                                    _, _, u_num = solve_heat_1d_cn(Nx, Nt, 10**la)
                                    return np.mean((u_num[t_idx, x_idx] - y)**2)

                                res_hybrid = opt.minimize_scalar(cn_objective, bounds=bracket, method='bounded', options={'xatol': 1e-4})
                                hat_p = 10**res_hybrid.x
                                m3p_hats.append(hat_p)
                                if abs(res_hybrid.x - bound_log_low) < 1e-3 or abs(res_hybrid.x - bound_log_high) < 1e-3:
                                    m3p_bound_hits += 1
                                if sigma > 0:
                                    crb = cramer_rao_bound(hat_p, t_s, x_s, sigma)
                                    se = np.sqrt(crb) / (hat_p * np.log(10)) if crb != np.inf and crb != 0 else 0.0
                                    if np.log10(hat_p) - 1.96*se <= np.log10(alpha_true) <= np.log10(hat_p) + 1.96*se:
                                        m3p_wald_cov += 1
                                    b_est = cs_b_m2(np.clip(res_hybrid.x, -3.0, 1.0)) # Mode 3+ uses CN solver!
                                    sig_tot = np.sqrt(se**2 + b_est**2)
                                    if (res_hybrid.x - b_est) - 1.96*sig_tot <= np.log10(alpha_true) <= (res_hybrid.x - b_est) + 1.96*sig_tot:
                                        m3p_bcorr_cov += 1
                            t_m3p_dur = time.time() - t0
                            m3p_total_time += t_m3p_dur

                            m3p_hats = np.array(m3p_hats)
                            m3p_med_err = np.median(np.abs(m3p_hats - alpha_true) / alpha_true)
                            m3p_spread = np.std(np.log10(m3p_hats))
                            m3p_fb = m3p_bound_hits / num_replications
                            m3p_w_pct = m3p_wald_cov / num_replications * 100.0 if sigma > 0 else 0.0
                            m3p_bc_pct = m3p_bcorr_cov / num_replications * 100.0 if sigma > 0 else 0.0
                            m3p_sprd_crb = m3p_spread / m3_mean_crb if m3_mean_crb > 0 and sigma > 0 else 0.0
                            m3p_status = classify_cell(m3p_med_err, m3p_fb, m3p_w_pct, m3p_bc_pct, sigma, mode="mode3plus")

                            m3plus_records.append({
                                'split': split, 'alpha': alpha_true, 'sensors': num_sensors, 'sigma': sigma,
                                'med_rel_err': m3p_med_err, 'spread_log': m3p_spread,
                                'sprd_crb': f"{m3p_sprd_crb:6.2f}" if sigma > 0 else "N/A",
                                'wald_cov_95': f"{m3p_w_pct:4.1f}%" if sigma > 0 else "N/A",
                                'deploy_cov_95': f"{m3p_bc_pct:4.1f}%" if sigma > 0 else "N/A",
                                'frac_bound': m3p_fb, 'single_fit_time_ms': t_m3p_dur / num_replications * 1000.0,
                                'status': m3p_status
                            })

    print(f"Paired evaluation complete.")
    if len(m2_records) > 0:
        print(f"Mode 2 mean fit time: {m2_total_time / len(m2_records) / num_replications * 1000.0:.3f} ms")
    if len(m3_records) > 0:
        print(f"Mode 3 mean fit time: {m3_total_time / len(m3_records) / num_replications * 1000.0:.3f} ms")
    if len(m3plus_records) > 0:
        print(f"Mode 3+ mean fit time: {m3p_total_time / len(m3plus_records) / num_replications * 1000.0:.3f} ms")

    # ----------------- EXPORT FINAL CSV FILES -----------------
    os.makedirs('data', exist_ok=True)
    if target_mode in ['all', 'mode2'] and len(m2_records) > 0:
        with open('data/mode2_pipeline_results_v2.csv', 'w', newline='') as f:
            fields = ['split', 'alpha', 'sensors', 'sigma', 'med_rel_err', 'spread_log', 'wald_cov_95', 'deploy_cov_95', 'frac_bound', 'single_fit_time_ms', 'status']
            w = csv.writer(f)
            w.writerow(fields)
            for r in m2_records:
                w.writerow([r['split'], f"{r['alpha']:.3f}", r['sensors'], f"{r['sigma']:.2f}",
                            f"{r['med_rel_err']:.6f}", f"{r['spread_log']:.6f}", r['wald_cov_95'],
                            r['deploy_cov_95'], f"{r['frac_bound']:.3f}", f"{r['single_fit_time_ms']:.3f}", r['status']])
        print("Exported data/mode2_pipeline_results_v2.csv")

    if target_mode in ['all', 'mode3'] and len(m3_records) > 0:
        with open('data/mode3_pipeline_results_v2.csv', 'w', newline='') as f:
            fields = ['split', 'alpha', 'sensors', 'sigma', 'med_narrow', 'med_wide', 'sprd_crb', 'wald_cov_95', 'deploy_cov_95', 'frac_bound', 'single_fit_time_ms', 'status']
            w = csv.writer(f)
            w.writerow(fields)
            for r in m3_records:
                med_n_str = f"{r['med_narrow']:.6f}" if isinstance(r['med_narrow'], (int, float)) else str(r['med_narrow'])
                w.writerow([r['split'], f"{r['alpha']:.3f}", r['sensors'], f"{r['sigma']:.2f}",
                            med_n_str, f"{r['med_wide']:.6f}", r['sprd_crb'],
                            r['wald_cov_95'], r['deploy_cov_95'], f"{r['frac_bound']:.3f}", f"{r['single_fit_time_ms']:.3f}", r['status']])
        print("Exported data/mode3_pipeline_results_v2.csv")

    if target_mode in ['all', 'ablation'] and len(m3plus_records) > 0:
        with open('data/mode3plus_hybrid_results.csv', 'w', newline='') as f:
            fields = ['split', 'alpha', 'sensors', 'sigma', 'med_rel_err', 'spread_log', 'sprd_crb', 'wald_cov_95', 'deploy_cov_95', 'frac_bound', 'single_fit_time_ms', 'status']
            w = csv.writer(f)
            w.writerow(fields)
            for r in m3plus_records:
                w.writerow([r['split'], f"{r['alpha']:.3f}", r['sensors'], f"{r['sigma']:.2f}",
                            f"{r['med_rel_err']:.6f}", f"{r['spread_log']:.6f}", r['sprd_crb'],
                            r['wald_cov_95'], r['deploy_cov_95'], f"{r['frac_bound']:.3f}", f"{r['single_fit_time_ms']:.3f}", r['status']])
        print("Exported data/mode3plus_hybrid_results.csv")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Definitive Benchmark Runner")
    parser.add_argument('--mode', choices=['all', 'mode2', 'mode3', 'ablation'], default='all',
                        help="Select which mode to evaluate (all, mode2, mode3, ablation)")
    args = parser.parse_args()
    run_comprehensive_benchmark(target_mode=args.mode)
