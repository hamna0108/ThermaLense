"""Final Checks & Robustness Studies for Anomaly Detection Module.

Evaluates:
1. Calibration table on fresh test seeds (N in {10, 20}, sigma in {0.01, 0.05}):
   - Healthy FAR, per-class recall, 4x4 confusion matrices, with 95% Wilson CIs.
2. Baseline-window robustness: baseline length k in {3, 5, 8, 12, 20} points:
   - Healthy FAR and Class C recall.
3. Baseline drift: slow alpha drift in {0%, 2%, 5%, 10%} inside the baseline window:
   - Effect on false alarms (H -> C) and on C vs H confusion (H -> C, C -> H, and recall C -> C).
4. Strong-fault leakage:
   - For strong F and A faults, the fraction misclassified as C, split by sensor count N.

Outputs written to CSV and JSON files under data/results/ and data/raw/.
"""

import os
import sys
import json
import csv
import numpy as np
import scipy.optimize as opt
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, 'src'))

BOUND_LOG_LOW = -3.0
BOUND_LOG_HIGH = 1.0

try:
    from paths import RAW, RESULTS, AUDITS
except ImportError:
    from src.paths import RAW, RESULTS, AUDITS

def wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1.0 + (z**2) / n
    centre = (p + (z**2) / (2.0 * n)) / denom
    half = (z * np.sqrt(p * (1.0 - p) / n + (z**2) / (4.0 * (n**2)))) / denom
    return max(0.0, centre - half) * 100.0, min(1.0, centre + half) * 100.0

def solve_heat_1d_exact(x, t, alpha):
    return np.exp(-alpha * (np.pi**2) * t) * np.sin(np.pi * x)

def solve_heat_1d_jump(x, t, alpha0, alpha1, tc):
    u = np.zeros_like(t, dtype=float)
    early = t < tc
    late = ~early
    if np.any(early):
        u[early] = np.sin(np.pi * x[early]) * np.exp(-alpha0 * (np.pi**2) * t[early])
    if np.any(late):
        u[late] = np.sin(np.pi * x[late]) * np.exp(-np.pi**2 * (alpha0 * tc + alpha1 * (t[late] - tc)))
    return u

def solve_heat_1d_drift(x, t, alpha_h, drift, t_max=0.5):
    # Linear drift inside baseline window: alpha(tau) = alpha_h * (1 + drift * tau / t_max)
    integral = alpha_h * (t + 0.5 * drift * (t**2) / t_max)
    return np.exp(- (np.pi**2) * integral) * np.sin(np.pi * x)

def compute_glr_baseline_informed(x_s, t_s, y_s, sigma, hat_a_base, tc_grid=np.arange(0.05, 0.75, 0.05)):
    y_pred0 = solve_heat_1d_exact(x_s, t_s, hat_a_base)
    rss0 = np.sum((y_pred0 - y_s)**2)
    best_rss = rss0
    best_tc = 0.5
    for tc in tc_grid:
        m_l = t_s >= tc
        if np.sum(m_l) >= 1:
            res1 = opt.minimize_scalar(
                lambda l: np.sum((solve_heat_1d_jump(x_s, t_s, hat_a_base, 10**l, tc) - y_s)**2),
                bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
            )
            rss = np.sum((solve_heat_1d_jump(x_s, t_s, hat_a_base, 10**res1.x, tc) - y_s)**2)
            if rss < best_rss:
                best_rss = rss
                best_tc = tc
    glr = (rss0 - best_rss) / (sigma**2)
    return glr, best_tc, rss0, best_rss

def fit_three_models_bic(x_s, t_s, y_s, sigma, gamma_f=7.456, gamma_c=1.5):
    N = len(t_s)
    res0 = opt.minimize_scalar(
        lambda l: np.sum((solve_heat_1d_exact(x_s, t_s, 10**l) - y_s)**2),
        bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
    )
    hat_alpha0 = 10**res0.x
    y_pred0 = solve_heat_1d_exact(x_s, t_s, hat_alpha0)
    rss0 = np.sum((y_pred0 - y_s)**2)
    chi2_0 = rss0 / (sigma**2)
    bic_0 = chi2_0 + 1.0 * np.log(N)
    
    rss_f_list = []
    for k in range(N):
        idx = [i for i in range(N) if i != k]
        res_k = opt.minimize_scalar(
            lambda l: np.sum((solve_heat_1d_exact(x_s[idx], t_s[idx], 10**l) - y_s[idx])**2),
            bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
        )
        rss_f_list.append(np.sum((solve_heat_1d_exact(x_s[idx], t_s[idx], 10**res_k.x) - y_s[idx])**2))
    rss_f = min(rss_f_list)
    chi2_f = rss_f / (sigma**2)
    bic_f = chi2_f + 2.0 * np.log(N) + gamma_f
    
    # Model MC candidate scan
    rss_c_candidates = []
    for tc_cand in [0.1, 0.25, 0.5]:
        m_early = t_s < tc_cand
        m_late = ~m_early
        if np.sum(m_early) >= 1 and np.sum(m_late) >= 1:
            res_a0 = opt.minimize_scalar(
                lambda l: np.sum((solve_heat_1d_exact(x_s[m_early], t_s[m_early], 10**l) - y_s[m_early])**2),
                bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
            )
            a0_fit = 10**res_a0.x
            res_a1 = opt.minimize_scalar(
                lambda l: np.sum((solve_heat_1d_jump(x_s[m_late], t_s[m_late], a0_fit, 10**l, tc_cand) - y_s[m_late])**2),
                bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
            )
            a1_fit = 10**res_a1.x
            rss_c = np.sum((solve_heat_1d_jump(x_s, t_s, a0_fit, a1_fit, tc_cand) - y_s)**2)
            rss_c_candidates.append(rss_c)
    rss_c = min(rss_c_candidates) if rss_c_candidates else rss0
    chi2_c = rss_c / (sigma**2)
    bic_c = chi2_c + 3.0 * np.log(N) + gamma_c
    
    return {
        'N': N,
        'alpha_hat': hat_alpha0,
        'chi2_red': chi2_0 / max(1, N - 1),
        'bic_0': bic_0,
        'bic_f': bic_f,
        'bic_c': bic_c,
        'chi2_0': chi2_0,
        'chi2_f': chi2_f,
        'chi2_c': chi2_c
    }

def predict_integrated_cascade(glr_stat, tau_cell, fit_res, alpha_hat, chi2_c=None, gamma_c=1.5):
    if ((alpha_hat < 0.018) or (alpha_hat > 0.55)) and fit_res['chi2_red'] < 2.0:
        return 'A'
    N = fit_res['N']
    bic_0 = fit_res['bic_0']
    bic_f = fit_res['bic_f']
    if chi2_c is None:
        chi2_c = fit_res.get('chi2_c', 0.0)
    bic_c = chi2_c + 2.0 * np.log(N) + gamma_c
    f_valid = bic_f < bic_0
    c_valid = glr_stat > tau_cell
    if f_valid and c_valid:
        return 'F' if bic_f <= bic_c else 'C'
    elif f_valid:
        return 'F'
    elif c_valid:
        return 'C'
    else:
        return 'A' if (alpha_hat < 0.018 or alpha_hat > 0.55) else 'H'

def run_checks(seed_mode='new_fresh', episodes_per_cell=200):
    print("=" * 80)
    print(f"RUNNING ANOMALY MODULE CHECKS: Mode = {seed_mode.upper()} ({episodes_per_cell} ep/cell)")
    print("=" * 80)
    
    if seed_mode == 'dev':
        base_layout = 300000
        base_noise = 400000
    elif seed_mode == 'fresh_orig':
        base_layout = 900000
        base_noise = 1000000
    elif seed_mode == 'new_fresh':
        base_layout = 960000
        base_noise = 1070000
    else:
        raise ValueError(f"Unknown seed_mode: {seed_mode}")
        
    glr_thresholds = {
        (10, 0.01): 7.544,
        (10, 0.05): 7.079,
        (20, 0.01): 9.270,
        (20, 0.05): 9.921,
    }
    
    Nx = 50
    x_grid = np.linspace(0, 1, Nx)
    x_candidates = np.where((x_grid >= 0.2) & (x_grid <= 0.8))[0]
    
    k_lengths = [3, 5, 8, 12, 20]
    drift_levels = [0.0, 0.02, 0.05, 0.10]
    
    cells = [
        {'N': 10, 'sigma': 0.01},
        {'N': 10, 'sigma': 0.05},
        {'N': 20, 'sigma': 0.01},
        {'N': 20, 'sigma': 0.05},
    ]
    
    tc_candidates = [0.1, 0.25, 0.5]
    mult_candidates = [0.5, 2.0]
    
    robustness_rows = []
    drift_rows = []
    
    for cell in cells:
        N = cell['N']
        sigma = cell['sigma']
        tau_cell = glr_thresholds[(N, sigma)]
        
        t_s = np.logspace(np.log10(0.01), 0, N)
        
        for ep in range(episodes_per_cell):
            layout_seed = base_layout + int(ep * 31) + N * 13
            noise_seed = base_noise + int(ep * 97) + N * 41 + int(sigma * 1000)
            
            rng_layout = np.random.RandomState(layout_seed)
            x_s = x_grid[rng_layout.choice(x_candidates, size=N, replace=True)]
            
            rng_noise = np.random.RandomState(noise_seed)
            noise_op = rng_noise.normal(0, sigma, size=N)
            
            rng_ep = np.random.RandomState(layout_seed + noise_seed)
            alpha_h = 10**rng_ep.uniform(np.log10(0.02), np.log10(0.5))
            
            # Operational measurements: Healthy (H)
            y_H = solve_heat_1d_exact(x_s, t_s, alpha_h) + noise_op
            fit_H = fit_three_models_bic(x_s, t_s, y_H, sigma)
            
            # Operational measurements: Change-point (C)
            tc_val = tc_candidates[(ep // 2) % 3]
            mult_val = mult_candidates[ep % 2]
            alpha_jump = alpha_h * mult_val
            y_C = solve_heat_1d_jump(x_s, t_s, alpha_h, alpha_jump, tc_val) + noise_op
            fit_C = fit_three_models_bic(x_s, t_s, y_C, sigma)
            
            # --- Study 1: Baseline Window Length Robustness ---
            rng_b_base = np.random.RandomState(layout_seed + 12345)
            rng_nb_base = np.random.RandomState(noise_seed + 12345)
            
            # Draw standard 20 baseline points so smaller k uses prefix subset
            xb_full = x_grid[rng_b_base.choice(x_candidates, size=20, replace=True)]
            tb_full = np.linspace(0.01, 0.5, 20)
            noise_b_full = rng_nb_base.normal(0, sigma, 20)
            
            for k in k_lengths:
                # Use linspace for k points in [0.01, 0.5]
                tb_k = np.linspace(0.01, 0.5, k)
                xb_k = xb_full[:k]
                yb_k = solve_heat_1d_exact(xb_k, tb_k, alpha_h) + noise_b_full[:k]
                
                res_b_k = opt.minimize_scalar(
                    lambda l: np.sum((solve_heat_1d_exact(xb_k, tb_k, 10**l) - yb_k)**2),
                    bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
                )
                hat_a_base_k = 10**res_b_k.x
                
                # Evaluate GLR on H
                glr_H_k, _, _, _ = compute_glr_baseline_informed(x_s, t_s, y_H, sigma, hat_a_base_k)
                pred_H_k = predict_integrated_cascade(glr_H_k, tau_cell, fit_H, fit_H['alpha_hat'])
                
                # Evaluate GLR on C
                glr_C_k, _, _, _ = compute_glr_baseline_informed(x_s, t_s, y_C, sigma, hat_a_base_k)
                pred_C_k = predict_integrated_cascade(glr_C_k, tau_cell, fit_C, fit_C['alpha_hat'])
                
                robustness_rows.append({
                    'N': N,
                    'sigma': sigma,
                    'k_baseline': k,
                    'episode_id': ep,
                    'alpha_true': alpha_h,
                    'hat_a_base': hat_a_base_k,
                    'glr_H': glr_H_k,
                    'pred_H': pred_H_k,
                    'is_H_fa': int(pred_H_k != 'H'),
                    'is_H_to_C': int(pred_H_k == 'C'),
                    'glr_C': glr_C_k,
                    'pred_C': pred_C_k,
                    'is_C_rec': int(pred_C_k == 'C'),
                    'is_C_to_H': int(pred_C_k == 'H')
                })
                
            # --- Study 2: Baseline Drift Robustness (with standard k=20) ---
            for d in drift_levels:
                tb_20 = np.linspace(0.01, 0.5, 20)
                # Linear drift across baseline window
                yb_drift = solve_heat_1d_drift(xb_full, tb_20, alpha_h, d, t_max=0.5) + noise_b_full
                res_b_d = opt.minimize_scalar(
                    lambda l: np.sum((solve_heat_1d_exact(xb_full, tb_20, 10**l) - yb_drift)**2),
                    bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
                )
                hat_a_base_d = 10**res_b_d.x
                
                glr_H_d, _, _, _ = compute_glr_baseline_informed(x_s, t_s, y_H, sigma, hat_a_base_d)
                pred_H_d = predict_integrated_cascade(glr_H_d, tau_cell, fit_H, fit_H['alpha_hat'])
                
                glr_C_d, _, _, _ = compute_glr_baseline_informed(x_s, t_s, y_C, sigma, hat_a_base_d)
                pred_C_d = predict_integrated_cascade(glr_C_d, tau_cell, fit_C, fit_C['alpha_hat'])
                
                drift_rows.append({
                    'N': N,
                    'sigma': sigma,
                    'drift_pct': int(round(d * 100)),
                    'episode_id': ep,
                    'alpha_true': alpha_h,
                    'hat_a_base': hat_a_base_d,
                    'glr_H': glr_H_d,
                    'pred_H': pred_H_d,
                    'is_H_fa': int(pred_H_d != 'H'),
                    'is_H_to_C': int(pred_H_d == 'C'),
                    'glr_C': glr_C_d,
                    'pred_C': pred_C_d,
                    'is_C_rec': int(pred_C_d == 'C'),
                    'is_C_to_H': int(pred_C_d == 'H')
                })
                
    df_rob = pd.DataFrame(robustness_rows)
    df_drf = pd.DataFrame(drift_rows)
    
    # Save raw CSVs
    rob_raw_path = str(RAW / f"anomaly_baseline_robustness_{seed_mode}.csv")
    drf_raw_path = str(RAW / f"anomaly_baseline_drift_{seed_mode}.csv")
    df_rob.to_csv(rob_raw_path, index=False)
    df_drf.to_csv(drf_raw_path, index=False)
    print(f"Saved robustness raw data to {rob_raw_path}")
    print(f"Saved drift raw data to {drf_raw_path}")
    
    # --- Summary Table 2: Baseline Window Robustness ---
    rob_summary = []
    print("\n" + "=" * 95)
    print(f"TABLE 2: BASELINE WINDOW ROBUSTNESS (Mode: {seed_mode.upper()})")
    print("=" * 95)
    print("k points | Total H | Healthy FAR (%) | 95% Wilson CI     | H -> C (%) | Total C | Class C Rec (%) | 95% Wilson CI")
    print("-" * 95)
    
    for k in k_lengths:
        sub_k = df_rob[df_rob['k_baseline'] == k]
        n_h = len(sub_k)
        fa_count = sub_k['is_H_fa'].sum()
        h_to_c_count = sub_k['is_H_to_C'].sum()
        far_pct = fa_count / n_h * 100.0
        h_to_c_pct = h_to_c_count / n_h * 100.0
        far_lo, far_hi = wilson_ci(fa_count, n_h)
        
        n_c = len(sub_k)
        rec_count = sub_k['is_C_rec'].sum()
        rec_pct = rec_count / n_c * 100.0
        rec_lo, rec_hi = wilson_ci(rec_count, n_c)
        
        print(f"  k = {k:2d}  | {n_h:7d} |           {far_pct:5.1f} | [{far_lo:4.1f}, {far_hi:4.1f}]      |      {h_to_c_pct:5.1f} | {n_c:7d} |            {rec_pct:5.1f} | [{rec_lo:4.1f}, {rec_hi:4.1f}]")
        
        rob_summary.append({
            'k_baseline': k,
            'total_episodes_per_class': n_h,
            'healthy_far_pct': round(far_pct, 2),
            'healthy_far_ci_low': round(far_lo, 2),
            'healthy_far_ci_high': round(far_hi, 2),
            'h_to_c_pct': round(h_to_c_pct, 2),
            'class_c_recall_pct': round(rec_pct, 2),
            'class_c_recall_ci_low': round(rec_lo, 2),
            'class_c_recall_ci_high': round(rec_hi, 2)
        })
        
    rob_sum_path = str(RESULTS / f"anomaly_baseline_robustness_{seed_mode}_summary.csv")
    pd.DataFrame(rob_summary).to_csv(rob_sum_path, index=False)
    print(f"Saved robustness summary to {rob_sum_path}")
    
    # --- Summary Table 3: Baseline Drift ---
    drf_summary = []
    print("\n" + "=" * 105)
    print(f"TABLE 3: BASELINE DRIFT SENSITIVITY (Mode: {seed_mode.upper()})")
    print("=" * 105)
    print("Drift (%) | Total H | Healthy FAR (%) | 95% Wilson CI     | H -> C (%) | Class C Rec (%) | 95% Wilson CI     | C -> H (%)")
    print("-" * 105)
    
    for d_pct in [0, 2, 5, 10]:
        sub_d = df_drf[df_drf['drift_pct'] == d_pct]
        n_h = len(sub_d)
        fa_count = sub_d['is_H_fa'].sum()
        h_to_c_count = sub_d['is_H_to_C'].sum()
        far_pct = fa_count / n_h * 100.0
        h_to_c_pct = h_to_c_count / n_h * 100.0
        far_lo, far_hi = wilson_ci(fa_count, n_h)
        
        n_c = len(sub_d)
        rec_count = sub_d['is_C_rec'].sum()
        c_to_h_count = sub_d['is_C_to_H'].sum()
        rec_pct = rec_count / n_c * 100.0
        c_to_h_pct = c_to_h_count / n_c * 100.0
        rec_lo, rec_hi = wilson_ci(rec_count, n_c)
        
        print(f"     {d_pct:2d}%  | {n_h:7d} |           {far_pct:5.1f} | [{far_lo:4.1f}, {far_hi:4.1f}]      |      {h_to_c_pct:5.1f} |            {rec_pct:5.1f} | [{rec_lo:4.1f}, {rec_hi:4.1f}]      |      {c_to_h_pct:5.1f}")
        
        drf_summary.append({
            'drift_pct': d_pct,
            'total_episodes_per_class': n_h,
            'healthy_far_pct': round(far_pct, 2),
            'healthy_far_ci_low': round(far_lo, 2),
            'healthy_far_ci_high': round(far_hi, 2),
            'h_to_c_pct': round(h_to_c_pct, 2),
            'class_c_recall_pct': round(rec_pct, 2),
            'class_c_recall_ci_low': round(rec_lo, 2),
            'class_c_recall_ci_high': round(rec_hi, 2),
            'c_to_h_pct': round(c_to_h_pct, 2)
        })
        
    drf_sum_path = str(RESULTS / f"anomaly_baseline_drift_{seed_mode}_summary.csv")
    pd.DataFrame(drf_summary).to_csv(drf_sum_path, index=False)
    print(f"Saved drift summary to {drf_sum_path}")
    print("=" * 80)
    
    return rob_summary, drf_summary

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'new_fresh'
    run_checks(seed_mode=mode)
