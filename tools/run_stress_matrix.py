"""Week 5 Stress Matrix Evaluation on Frozen Modules.

PRE-REGISTERED FAILURE RULE:
A cell FAILS if:
  1. For parameter estimation modules (Mode 2, Mode 3, Mode 3+, Two-Stage Placement):
     median relative alpha error > 2x the matching clean cell,
     OR 95% confidence interval coverage < 80.0%.
  2. For Anomaly Cascade module:
     healthy false-alarm rate > 15.0%.

Modules Tested (FROZEN - zero modifications):
  - Mode 2: Crank-Nicolson Spline Inversion
  - Mode 3: FNO-2D Spline Inversion
  - Mode 3+: Hybrid FNO + Crank-Nicolson Polish
  - Two-Stage Placement: Adaptive Sensor Time Placement
  - Anomaly Cascade: 4-Class Model-Selection Detector (H, A, F, C)

Scenarios (13 scenarios x 3 severity levels x 5 seeds):
  1. Misspecified noise sigma (assumed 0.01, true 0.05; and the reverse)
  2. Heavy-tailed noise (Student-t, df=3)
  3. Correlated noise (AR(1), rho 0.5/0.8/0.95)
  4. Different initial condition (sin(2 pi x), two-mode sum, Gaussian bump)
  5. Boundary mismatch (small non-zero boundary value or drifting boundary)
  6. Source-term / heating mismatch (u_t = a u_xx + s)
  7. Variable diffusivity alpha(x)
  8. Sensor dropout (10/30/50% readings missing)
  9. Sensor position error and time jitter
 10. Constant sensor bias (does it look like class F or C?)
 11. Very few sensors (N=3, 5)
 12. True alpha beyond the grid (alpha = 5, 10, 20) and below it (alpha = 5e-4)
 13. Baseline drift (carried from anomaly checks)
"""

import os
import sys
import time
import csv
import json
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.interpolate import CubicSpline, interp1d
import scipy.optimize as opt
import scipy.stats as stats
import torch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, 'src'))

from paths import RESULTS, MODELS, RAW
from models.fno2d import FNO2d

BOUND_LOG_LOW = -3.0
BOUND_LOG_HIGH = 1.0

# -------------------------------------------------------------------------------------------------
# 1. Forward Numerical Solvers & Ground-Truth Generators
# -------------------------------------------------------------------------------------------------

def solve_heat_1d_exact(x, t, alpha):
    """Analytic Fourier series fundamental mode."""
    return np.exp(-alpha * (np.pi**2) * t) * np.sin(np.pi * x)

def solve_heat_1d_cn_standard(Nx, Nt, alpha):
    """Standard CN solver on fundamental mode."""
    x = np.linspace(0, 1, Nx)
    t = np.linspace(0, 1, Nt)
    dx = x[1] - x[0]
    dt = t[1] - t[0]
    r = alpha * dt / (2.0 * dx**2)
    main_A = (1 + 2*r) * np.ones(Nx-2)
    off_A = -r * np.ones(Nx-3)
    main_B = (1 - 2*r) * np.ones(Nx-2)
    off_B = r * np.ones(Nx-3)
    A = sp.diags([off_A, main_A, off_A], offsets=[-1, 0, 1], format='csr')
    B = sp.diags([off_B, main_B, off_B], offsets=[-1, 0, 1], format='csr')
    u = np.zeros((Nt, Nx))
    u[0, :] = np.sin(np.pi * x)
    for n in range(Nt - 1):
        rhs = B.dot(u[n, 1:-1])
        u[n+1, 1:-1] = spla.spsolve(A, rhs)
    return x, t, u

def solve_heat_1d_general(Nx=101, Nt=501, alpha=0.1, u0_fn=None, bc_fn=None, source_fn=None, alpha_fn=None):
    """Generalized Crank-Nicolson solver for arbitrary ICs, BCs, source terms, and variable diffusivity."""
    x = np.linspace(0, 1, Nx)
    t = np.linspace(0, 1, Nt)
    dx = x[1] - x[0]
    dt = t[1] - t[0]
    
    if alpha_fn is not None:
        a_nodes = alpha_fn(x)
    elif np.isscalar(alpha):
        a_nodes = np.full(Nx, alpha)
    else:
        a_nodes = alpha
        
    u = np.zeros((Nt, Nx))
    if u0_fn is not None:
        u[0, :] = u0_fn(x)
    else:
        u[0, :] = np.sin(np.pi * x)
        
    N_int = Nx - 2
    a_half = 0.5 * (a_nodes[:-1] + a_nodes[1:])
    r_half = a_half * dt / (2.0 * dx**2)
    
    main_A = 1.0 + r_half[:N_int] + r_half[1:N_int+1]
    lower_A = -r_half[1:N_int]
    upper_A = -r_half[1:N_int]
    
    main_B = 1.0 - (r_half[:N_int] + r_half[1:N_int+1])
    lower_B = r_half[1:N_int]
    upper_B = r_half[1:N_int]
    
    A = sp.diags([lower_A, main_A, upper_A], offsets=[-1, 0, 1], shape=(N_int, N_int), format='csr')
    B = sp.diags([lower_B, main_B, upper_B], offsets=[-1, 0, 1], shape=(N_int, N_int), format='csr')
    
    for n in range(Nt - 1):
        tn = t[n]
        tn1 = t[n+1]
        rhs = B.dot(u[n, 1:-1])
        if source_fn is not None:
            s_n = source_fn(x[1:-1], tn)
            s_n1 = source_fn(x[1:-1], tn1)
            rhs += 0.5 * dt * (s_n + s_n1)
        bc0 = bc_fn(0.0, tn1) if bc_fn else 0.0
        bc1 = bc_fn(1.0, tn1) if bc_fn else 0.0
        rhs[0] += r_half[0] * bc0
        rhs[-1] += r_half[-1] * bc1
        
        u[n+1, 1:-1] = spla.spsolve(A, rhs)
        u[n+1, 0] = bc0
        u[n+1, -1] = bc1
        
    return x, t, u

def cramer_rao_bound(alpha, t_sensors, x_sensors, sigma):
    """Scalar CRB on log10(alpha)."""
    alpha_c = max(1e-5, alpha)
    grads = -np.pi**2 * t_sensors * np.exp(-alpha_c * np.pi**2 * t_sensors) * np.sin(np.pi * x_sensors)
    fisher_info = np.sum(grads**2) / (sigma**2 + 1e-12)
    if fisher_info <= 0:
        return np.inf
    return 1.0 / fisher_info

# -------------------------------------------------------------------------------------------------
# 2. Frozen Precomputed Grids (Mode 2, Mode 3, Bias Lookup Curves)
# -------------------------------------------------------------------------------------------------

def precompute_surrogates():
    print("Precomputing Mode 2 (Crank-Nicolson) & Mode 3 (FNO) forward solution grids...")
    Nx, Nt = 50, 100
    x_grid = np.linspace(0, 1, Nx)
    t_grid = np.linspace(0, 1, Nt)
    grid_la = np.linspace(BOUND_LOG_LOW, BOUND_LOG_HIGH, 350)
    
    U_m2 = np.array([solve_heat_1d_cn_standard(Nx, Nt, 10**la)[2] for la in grid_la])
    
    # Load frozen FNO
    fno_path = os.path.join(REPO_ROOT, 'models', 'fno2d_heat.pt')
    ckpt = torch.load(fno_path, map_location='cpu')
    model = FNO2d(modes1=16, modes2=12, width=32, use_hard_mask=ckpt.get('use_hard_mask', False))
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()
    
    lm = ckpt['log_alpha_mean'].item()
    ls = ckpt['log_alpha_std'].item()
    
    t_mesh, x_mesh = np.meshgrid(t_grid, x_grid, indexing='ij')
    t_tensor = torch.tensor(2 * t_mesh - 1, dtype=torch.float32)
    x_tensor = torch.tensor(2 * x_mesh - 1, dtype=torch.float32)
    
    x_inputs = []
    for la in grid_la:
        a_sc = (la - lm) / ls
        x_inputs.append(torch.stack([t_tensor, x_tensor, torch.full_like(t_tensor, a_sc)], dim=0))
    x_batch = torch.stack(x_inputs, dim=0)
    with torch.no_grad():
        fno_grid = model(x_batch).squeeze(1).numpy()
        
    # Bias lookup curves
    alpha_ref = np.logspace(-3.0, 1.0, 60)
    la_ref = np.log10(alpha_ref)
    t_ref = np.logspace(np.log10(0.01), np.log10(1.0), 20)
    t_idx_ref = [np.argmin(np.abs(t_grid - t)) for t in t_ref]
    x_idx_ref = [25] * 20
    
    cs_m2_ref = CubicSpline(grid_la, U_m2[:, t_idx_ref, x_idx_ref], axis=0)
    cs_m3_ref = CubicSpline(grid_la, fno_grid[:, t_idx_ref, x_idx_ref], axis=0)
    b_m2 = []
    b_m3 = []
    for a in alpha_ref:
        y_ref = solve_heat_1d_exact(x_grid[x_idx_ref], t_grid[t_idx_ref], a)
        res2 = opt.minimize_scalar(lambda la: np.mean((cs_m2_ref(la) - y_ref)**2), bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
        res3 = opt.minimize_scalar(lambda la: np.mean((cs_m3_ref(la) - y_ref)**2), bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
        b_m2.append(res2.x - np.log10(a))
        b_m3.append(res3.x - np.log10(a))
    cs_b_m2 = CubicSpline(la_ref, b_m2)
    cs_b_m3 = CubicSpline(la_ref, b_m3)
    
    # Crank-Nicolson center grid for Two-Stage Placement
    Nx_c, Nt_c = 51, 501
    grid_la_c = np.linspace(BOUND_LOG_LOW, BOUND_LOG_HIGH, 300)
    t_grid_c = np.linspace(0, 1, Nt_c)
    U_cn_center = np.array([solve_heat_1d_cn_standard(Nx_c, Nt_c, 10**la)[2][:, (Nx_c-1)//2] for la in grid_la_c])
    cs_time_c = CubicSpline(t_grid_c, U_cn_center, axis=1)
    
    return {
        'x_grid': x_grid, 't_grid': t_grid, 'grid_la': grid_la,
        'U_m2': U_m2, 'fno_grid': fno_grid,
        'cs_b_m2': cs_b_m2, 'cs_b_m3': cs_b_m3,
        'grid_la_c': grid_la_c, 'cs_time_c': cs_time_c
    }

# -------------------------------------------------------------------------------------------------
# 3. Frozen Anomaly Detection Cascade Functions
# -------------------------------------------------------------------------------------------------

GLR_THRESHOLDS = {
    (10, 0.01): 7.544,
    (10, 0.05): 7.079,
    (20, 0.01): 9.270,
    (20, 0.05): 9.921,
    (5,  0.01): 6.580,
    (5,  0.05): 6.783,
    (3,  0.01): 5.500,
    (3,  0.05): 5.500,
    (2,  0.01): 4.500,
    (2,  0.05): 4.500,
}

def solve_heat_1d_jump(x, t, alpha0, alpha1, tc):
    u = np.zeros_like(t, dtype=float)
    early = t < tc
    late = ~early
    if np.any(early):
        u[early] = np.sin(np.pi * x[early]) * np.exp(-alpha0 * (np.pi**2) * t[early])
    if np.any(late):
        u[late] = np.sin(np.pi * x[late]) * np.exp(-np.pi**2 * (alpha0 * tc + alpha1 * (t[late] - tc)))
    return u

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
    glr = (rss0 - best_rss) / (sigma**2 + 1e-12)
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
    chi2_0 = rss0 / (sigma**2 + 1e-12)
    bic_0 = chi2_0 + 1.0 * np.log(max(2, N))
    
    rss_f_list = []
    for k in range(N):
        idx = [i for i in range(N) if i != k]
        if len(idx) > 0:
            res_k = opt.minimize_scalar(
                lambda l: np.sum((solve_heat_1d_exact(x_s[idx], t_s[idx], 10**l) - y_s[idx])**2),
                bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
            )
            rss_f_list.append(np.sum((solve_heat_1d_exact(x_s[idx], t_s[idx], 10**res_k.x) - y_s[idx])**2))
        else:
            rss_f_list.append(rss0)
    rss_f = min(rss_f_list) if rss_f_list else rss0
    chi2_f = rss_f / (sigma**2 + 1e-12)
    bic_f = chi2_f + 2.0 * np.log(max(2, N)) + gamma_f
    
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
    chi2_c = rss_c / (sigma**2 + 1e-12)
    bic_c = chi2_c + 3.0 * np.log(max(2, N)) + gamma_c
    
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
    bic_c = chi2_c + 2.0 * np.log(max(2, N)) + gamma_c
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

# -------------------------------------------------------------------------------------------------
# 4. Evaluation Wrappers for the 5 Modules
# -------------------------------------------------------------------------------------------------

def evaluate_mode2(x_s, t_s, y_s, sigma_assumed, alpha_true, prec):
    grid_la = prec['grid_la']
    U_m2 = prec['U_m2']
    t_grid = prec['t_grid']
    x_grid = prec['x_grid']
    
    t_idx = [np.argmin(np.abs(t_grid - t)) for t in t_s]
    x_idx = [np.argmin(np.abs(x_grid - x)) for x in x_s]
    cs = CubicSpline(grid_la, U_m2[:, t_idx, x_idx], axis=0)
    
    res = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                              bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
    hat = 10**res.x
    rel_err = abs(hat - alpha_true) / max(1e-5, alpha_true)
    
    # 95% Wald CI coverage
    crb = cramer_rao_bound(hat, t_s, x_s, sigma_assumed)
    in_ci = 0
    if crb != np.inf and crb > 0:
        se = np.sqrt(crb) / (hat * np.log(10))
        if np.log10(hat) - 1.96 * se <= np.log10(alpha_true) <= np.log10(hat) + 1.96 * se:
            in_ci = 1
    return hat, rel_err, in_ci

def evaluate_mode3(x_s, t_s, y_s, sigma_assumed, alpha_true, prec):
    grid_la = prec['grid_la']
    fno_grid = prec['fno_grid']
    t_grid = prec['t_grid']
    x_grid = prec['x_grid']
    cs_b_m3 = prec['cs_b_m3']
    
    t_idx = [np.argmin(np.abs(t_grid - t)) for t in t_s]
    x_idx = [np.argmin(np.abs(x_grid - x)) for x in x_s]
    cs = CubicSpline(grid_la, fno_grid[:, t_idx, x_idx], axis=0)
    
    res = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_s)**2),
                              bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
    hat = 10**res.x
    rel_err = abs(hat - alpha_true) / max(1e-5, alpha_true)
    
    # 95% Deployable bias-corrected CI coverage
    crb = cramer_rao_bound(hat, t_s, x_s, sigma_assumed)
    in_ci = 0
    if crb != np.inf and crb > 0:
        se = np.sqrt(crb) / (hat * np.log(10))
        b_est = cs_b_m3(np.clip(res.x, -3.0, 1.0))
        tot_unc = np.sqrt(se**2 + b_est**2)
        if (res.x - b_est) - 1.96 * tot_unc <= np.log10(alpha_true) <= (res.x - b_est) + 1.96 * tot_unc:
            in_ci = 1
    return hat, rel_err, in_ci

def evaluate_mode3plus(x_s, t_s, y_s, sigma_assumed, alpha_true, hat_m3, prec):
    la_0 = np.log10(max(1e-4, hat_m3))
    bracket = (max(-3.0, la_0 - 0.3), min(1.0, la_0 + 0.3))
    
    def cn_obj(la):
        _, _, u_num = solve_heat_1d_cn_standard(50, 100, 10**la)
        t_grid = prec['t_grid']
        x_grid = prec['x_grid']
        t_idx = [np.argmin(np.abs(t_grid - t)) for t in t_s]
        x_idx = [np.argmin(np.abs(x_grid - x)) for x in x_s]
        return np.mean((u_num[t_idx, x_idx] - y_s)**2)
        
    res = opt.minimize_scalar(cn_obj, bounds=bracket, method='bounded', options={'xatol': 1e-4})
    hat = 10**res.x
    rel_err = abs(hat - alpha_true) / max(1e-5, alpha_true)
    
    crb = cramer_rao_bound(hat, t_s, x_s, sigma_assumed)
    in_ci = 0
    if crb != np.inf and crb > 0:
        se = np.sqrt(crb) / (hat * np.log(10))
        if np.log10(hat) - 1.96 * se <= np.log10(alpha_true) <= np.log10(hat) + 1.96 * se:
            in_ci = 1
    return hat, rel_err, in_ci

def evaluate_two_stage(N, sigma_assumed, alpha_true, prec, rng_noise, u_fn=None):
    """Adaptive Two-Stage Placement at domain center x = 0.5."""
    t_min, t_max = 0.01, 1.0
    N1 = max(1, N // 2)
    N2 = N - N1
    
    t1 = np.logspace(np.log10(t_min), np.log10(t_max), N1)
    if u_fn is not None:
        u1 = u_fn(np.full(N1, 0.5), t1)
    else:
        u1 = np.exp(-alpha_true * np.pi**2 * t1)
    y1 = u1 + rng_noise.normal(0, sigma_assumed, N1)
    
    grid_la_c = prec['grid_la_c']
    cs_time_c = prec['cs_time_c']
    
    U_s1 = cs_time_c(t1)
    cs_la1 = CubicSpline(grid_la_c, U_s1, axis=0)
    res1 = opt.minimize_scalar(lambda la: np.mean((cs_la1(la) - y1)**2),
                              bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
    hat1 = 10**res1.x
    
    # Stage 2: information-weighted at hat1
    alpha_clamped = np.clip(hat1, 1e-4, 10.0)
    t_fine = np.linspace(t_min, t_max, 2000)
    w = (t_fine ** 2) * np.exp(-2 * alpha_clamped * (np.pi ** 2) * t_fine)
    cdf = np.cumsum(w)
    cdf = (cdf - cdf[0]) / (cdf[-1] - cdf[0] + 1e-15)
    u_q = (np.arange(N2) + 0.5) / max(1, N2)
    inv_cdf = interp1d(cdf, t_fine, bounds_error=False, fill_value=(t_min, t_max))
    t2 = inv_cdf(u_q)
    
    if u_fn is not None:
        u2 = u_fn(np.full(N2, 0.5), t2)
    else:
        u2 = np.exp(-alpha_true * np.pi**2 * t2)
    y2 = u2 + rng_noise.normal(0, sigma_assumed, N2)
    
    t_all = np.concatenate([t1, t2])
    y_all = np.concatenate([y1, y2])
    U_all = cs_time_c(t_all)
    cs_la_all = CubicSpline(grid_la_c, U_all, axis=0)
    res_final = opt.minimize_scalar(lambda la: np.mean((cs_la_all(la) - y_all)**2),
                                   bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
    hat = 10**res_final.x
    rel_err = abs(hat - alpha_true) / max(1e-5, alpha_true)
    
    crb = cramer_rao_bound(hat, t_all, np.full(N, 0.5), sigma_assumed)
    in_ci = 0
    if crb != np.inf and crb > 0:
        se = np.sqrt(crb) / (hat * np.log(10))
        if np.log10(hat) - 1.96 * se <= np.log10(alpha_true) <= np.log10(hat) + 1.96 * se:
            in_ci = 1
    return hat, rel_err, in_ci

def evaluate_anomaly_cascade(x_s, t_s, y_s, sigma_assumed, alpha_nominal, hat_a_base):
    N = len(t_s)
    tau_cell = GLR_THRESHOLDS.get((N, sigma_assumed), 7.500)
    fit_res = fit_three_models_bic(x_s, t_s, y_s, sigma_assumed)
    glr, best_tc, _, _ = compute_glr_baseline_informed(x_s, t_s, y_s, sigma_assumed, hat_a_base)
    pred = predict_integrated_cascade(glr, tau_cell, fit_res, fit_res['alpha_hat'])
    is_fa = int(pred != 'H')
    return pred, is_fa

# -------------------------------------------------------------------------------------------------
# 5. Master Stress Matrix Execution Loop
# -------------------------------------------------------------------------------------------------

def run_stress_matrix():
    print("=" * 115)
    print("WEEK 5 STRESS MATRIX ON FROZEN MODULES")
    print("Pre-registered failure rule: Error > 2x clean, Coverage < 80%, or Anomaly Healthy FAR > 15%")
    print("=" * 115)
    
    prec = precompute_surrogates()
    base_seed = 850000
    num_seeds = 5
    
    # 1. Evaluate Clean Matching Cells (Alpha = 0.100, N = 10, Sigma = 0.01)
    print("\n[Step 1] Evaluating Clean Matching Baseline Cells (Alpha = 0.100, N = 10, Sigma = 0.01, 20 reps)...")
    clean_records = {m: [] for m in ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']}
    
    alpha_clean = 0.100
    N_clean = 10
    sig_clean = 0.01
    num_clean_reps = 20
    
    for s_idx in range(num_clean_reps):
        seed = base_seed + s_idx
        rng = np.random.RandomState(seed)
        
        t_s = np.logspace(np.log10(0.01), 0, N_clean)
        x_s = rng.uniform(0.2, 0.8, N_clean)
        y_exact = solve_heat_1d_exact(x_s, t_s, alpha_clean)
        y_clean = y_exact + rng.normal(0, sig_clean, N_clean)
        
        # Mode 2
        h2, e2, c2 = evaluate_mode2(x_s, t_s, y_clean, sig_clean, alpha_clean, prec)
        clean_records['Mode 2'].append((e2, c2))
        
        # Mode 3
        h3, e3, c3 = evaluate_mode3(x_s, t_s, y_clean, sig_clean, alpha_clean, prec)
        clean_records['Mode 3'].append((e3, c3))
        
        # Mode 3+
        h3p, e3p, c3p = evaluate_mode3plus(x_s, t_s, y_clean, sig_clean, alpha_clean, h3, prec)
        clean_records['Mode 3+'].append((e3p, c3p))
        
        # Two-stage
        rng_ts = np.random.RandomState(seed + 999)
        hts, ets, cts = evaluate_two_stage(N_clean, sig_clean, alpha_clean, prec, rng_ts)
        clean_records['Two-Stage Placement'].append((ets, cts))
        
        # Anomaly Cascade baseline: separate 20-point healthy window
        rng_b = np.random.RandomState(seed + 12345)
        xb = rng_b.uniform(0.2, 0.8, 20)
        tb = np.linspace(0.01, 0.5, 20)
        yb = solve_heat_1d_exact(xb, tb, alpha_clean) + rng_b.normal(0, sig_clean, 20)
        res_b = opt.minimize_scalar(lambda l: np.sum((solve_heat_1d_exact(xb, tb, 10**l) - yb)**2),
                                   bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
        hat_b = 10**res_b.x
        pred_a, fa_a = evaluate_anomaly_cascade(x_s, t_s, y_clean, sig_clean, alpha_clean, hat_b)
        clean_records['Anomaly Cascade'].append(fa_a)
        
    clean_baselines = {
        'Mode 2': {
            'med_err': float(np.median([r[0] for r in clean_records['Mode 2']])),
            'coverage': float(np.mean([r[1] for r in clean_records['Mode 2']])) * 100.0
        },
        'Mode 3': {
            'med_err': float(np.median([r[0] for r in clean_records['Mode 3']])),
            'coverage': float(np.mean([r[1] for r in clean_records['Mode 3']])) * 100.0
        },
        'Mode 3+': {
            'med_err': float(np.median([r[0] for r in clean_records['Mode 3+']])),
            'coverage': float(np.mean([r[1] for r in clean_records['Mode 3+']])) * 100.0
        },
        'Two-Stage Placement': {
            'med_err': float(np.median([r[0] for r in clean_records['Two-Stage Placement']])),
            'coverage': float(np.mean([r[1] for r in clean_records['Two-Stage Placement']])) * 100.0
        },
        'Anomaly Cascade': {
            'healthy_far': float(np.mean(clean_records['Anomaly Cascade'])) * 100.0
        }
    }
    print("Clean Baselines Established:")
    for mod, vals in clean_baselines.items():
        print(f"  {mod:20s}: {vals}")
        
    # 2. Define the 13 Stress Scenarios
    scenarios = [
        {
            'idx': 1,
            'name': 'Misspecified noise sigma',
            'severities': [
                {'sev_idx': 1, 'desc': 'Mild under-specified: true=0.02, assumed=0.01', 'true_sig': 0.02, 'assumed_sig': 0.01},
                {'sev_idx': 2, 'desc': 'Severe under-specified: true=0.05, assumed=0.01', 'true_sig': 0.05, 'assumed_sig': 0.01},
                {'sev_idx': 3, 'desc': 'Severe over-specified: true=0.01, assumed=0.05', 'true_sig': 0.01, 'assumed_sig': 0.05},
            ]
        },
        {
            'idx': 2,
            'name': 'Heavy-tailed noise (Student-t)',
            'severities': [
                {'sev_idx': 1, 'desc': 'Standardized Student-t (df=5)', 'df': 5, 'outlier_prob': 0.0},
                {'sev_idx': 2, 'desc': 'Standardized Student-t (df=3)', 'df': 3, 'outlier_prob': 0.0},
                {'sev_idx': 3, 'desc': 'Contaminated Student-t (df=3) with 10% 5-sigma outliers', 'df': 3, 'outlier_prob': 0.10},
            ]
        },
        {
            'idx': 3,
            'name': 'Correlated noise (AR(1))',
            'severities': [
                {'sev_idx': 1, 'desc': 'Temporal AR(1) rho = 0.50', 'rho': 0.50},
                {'sev_idx': 2, 'desc': 'Temporal AR(1) rho = 0.80', 'rho': 0.80},
                {'sev_idx': 3, 'desc': 'Temporal AR(1) rho = 0.95', 'rho': 0.95},
            ]
        },
        {
            'idx': 4,
            'name': 'Different initial condition',
            'severities': [
                {'sev_idx': 1, 'desc': 'Second harmonic: sin(2 pi x)', 'type': 'harmonic2'},
                {'sev_idx': 2, 'desc': 'Two-mode sum: sin(pi x) + 0.5 sin(3 pi x)', 'type': 'twomode'},
                {'sev_idx': 3, 'desc': 'Gaussian bump IC', 'type': 'gaussian'},
            ]
        },
        {
            'idx': 5,
            'name': 'Boundary mismatch',
            'severities': [
                {'sev_idx': 1, 'desc': 'Constant offset BC = 0.05', 'bc_val': 0.05, 'drifting': False},
                {'sev_idx': 2, 'desc': 'Moderate constant BC = 0.15', 'bc_val': 0.15, 'drifting': False},
                {'sev_idx': 3, 'desc': 'Time-drifting oscillating BC', 'bc_val': 0.10, 'drifting': True},
            ]
        },
        {
            'idx': 6,
            'name': 'Source-term / heating mismatch',
            'severities': [
                {'sev_idx': 1, 'desc': 'Weak constant source s = 0.10', 's_val': 0.10, 'localized': False},
                {'sev_idx': 2, 'desc': 'Moderate constant source s = 0.50', 's_val': 0.50, 'localized': False},
                {'sev_idx': 3, 'desc': 'Strong localized heating s = 2.0 at core', 's_val': 2.00, 'localized': True},
            ]
        },
        {
            'idx': 7,
            'name': 'Variable diffusivity alpha(x)',
            'severities': [
                {'sev_idx': 1, 'desc': 'Linear gradient +/- 20%', 'grad': 0.20, 'step': False},
                {'sev_idx': 2, 'desc': 'Linear gradient +/- 50%', 'grad': 0.50, 'step': False},
                {'sev_idx': 3, 'desc': 'Discontinuous step (alpha to 2.0 alpha)', 'grad': 0.0, 'step': True},
            ]
        },
        {
            'idx': 8,
            'name': 'Sensor dropout',
            'severities': [
                {'sev_idx': 1, 'desc': '10% readings missing (1 sensor dropped)', 'drop_frac': 0.10},
                {'sev_idx': 2, 'desc': '30% readings missing (3 sensors dropped)', 'drop_frac': 0.30},
                {'sev_idx': 3, 'desc': '50% readings missing (5 sensors dropped)', 'drop_frac': 0.50},
            ]
        },
        {
            'idx': 9,
            'name': 'Sensor position error and time jitter',
            'severities': [
                {'sev_idx': 1, 'desc': 'Small jitter sigma_jitter = 0.01', 'jitter': 0.01},
                {'sev_idx': 2, 'desc': 'Moderate jitter sigma_jitter = 0.03', 'jitter': 0.03},
                {'sev_idx': 3, 'desc': 'Large jitter sigma_jitter = 0.06', 'jitter': 0.06},
            ]
        },
        {
            'idx': 10,
            'name': 'Constant sensor bias',
            'severities': [
                {'sev_idx': 1, 'desc': 'Small sensor bias b = 3 sigma (0.03)', 'bias': 0.03},
                {'sev_idx': 2, 'desc': 'Medium sensor bias b = 6 sigma (0.06)', 'bias': 0.06},
                {'sev_idx': 3, 'desc': 'Strong sensor bias b = 15 sigma (0.15)', 'bias': 0.15},
            ]
        },
        {
            'idx': 11,
            'name': 'Very few sensors',
            'severities': [
                {'sev_idx': 1, 'desc': 'Sparse array N = 5 sensors', 'N': 5},
                {'sev_idx': 2, 'desc': 'Very sparse array N = 3 sensors', 'N': 3},
                {'sev_idx': 3, 'desc': 'Minimal array N = 2 sensors', 'N': 2},
            ]
        },
        {
            'idx': 12,
            'name': 'True alpha beyond the grid',
            'severities': [
                {'sev_idx': 1, 'desc': 'Sub-grid low diffusivity alpha = 5e-4', 'alpha': 0.0005},
                {'sev_idx': 2, 'desc': 'Super-grid high diffusivity alpha = 5.0', 'alpha': 5.0},
                {'sev_idx': 3, 'desc': 'Super-grid extreme diffusivity alpha = 20.0', 'alpha': 20.0},
            ]
        },
        {
            'idx': 13,
            'name': 'Baseline drift',
            'severities': [
                {'sev_idx': 1, 'desc': 'Slow drift delta = 2%', 'drift': 0.02},
                {'sev_idx': 2, 'desc': 'Moderate drift delta = 5%', 'drift': 0.05},
                {'sev_idx': 3, 'desc': 'Severe drift delta = 10%', 'drift': 0.10},
            ]
        },
    ]
    
    matrix_rows = []
    summary_rows = []
    
    print("\n[Step 2] Executing 13 Stress Scenarios across 5 Seeds...")
    
    for scen in scenarios:
        scen_id = scen['idx']
        scen_name = scen['name']
        print(f"\n--> Running Scenario {scen_id:2d}: {scen_name}...")
        
        for sev in scen['severities']:
            sev_idx = sev['sev_idx']
            sev_desc = sev['desc']
            
            # Module collectors across 5 seeds
            mod_results = {m: [] for m in ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']}
            
            for s_idx in range(num_seeds):
                cell_idx = scen_id * 100 + sev_idx * 10 + s_idx
                seed = base_seed + cell_idx
                rng = np.random.RandomState(seed)
                
                # Base nominal parameters for this cell
                alpha_true = 0.100
                N_sensors = 10
                sig_true = 0.01
                sig_assumed = 0.01
                
                # Setup specific scenario condition
                u_interp_fn = None
                hat_b = None
                
                # Default coordinates
                t_s = np.logspace(np.log10(0.01), 0, N_sensors)
                x_s = rng.uniform(0.2, 0.8, N_sensors)
                
                # Handle Scenarios:
                if scen_id == 1: # Misspecified noise sigma
                    sig_true = sev['true_sig']
                    sig_assumed = sev['assumed_sig']
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                    y_s = y_exact + noise
                    
                elif scen_id == 2: # Heavy-tailed noise
                    df_t = sev['df']
                    raw_t = rng.standard_t(df_t, size=N_sensors)
                    scale_t = sig_true * np.sqrt((df_t - 2.0) / df_t)
                    noise = raw_t * scale_t
                    if sev['outlier_prob'] > 0:
                        outliers = rng.uniform(0, 1, N_sensors) < sev['outlier_prob']
                        noise[outliers] += 5.0 * sig_true * rng.choice([-1.0, 1.0], size=np.sum(outliers))
                    y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                    y_s = y_exact + noise
                    
                elif scen_id == 3: # Correlated noise AR(1)
                    rho = sev['rho']
                    raw_w = rng.normal(0, sig_true, N_sensors)
                    noise = np.zeros(N_sensors)
                    noise[0] = raw_w[0]
                    for i in range(1, N_sensors):
                        noise[i] = rho * noise[i-1] + np.sqrt(1.0 - rho**2) * raw_w[i]
                    y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                    y_s = y_exact + noise
                    
                elif scen_id == 4: # Different initial condition
                    ic_type = sev['type']
                    if ic_type == 'harmonic2':
                        u0_f = lambda x: np.sin(2 * np.pi * x)
                    elif ic_type == 'twomode':
                        u0_f = lambda x: np.sin(np.pi * x) + 0.5 * np.sin(3 * np.pi * x)
                    else: # gaussian
                        u0_f = lambda x: np.exp(-(x - 0.5)**2 / (2 * 0.12**2)) - np.exp(-0.5**2 / (2 * 0.12**2))
                    xg, tg, ug = solve_heat_1d_general(Nx=101, Nt=501, alpha=alpha_true, u0_fn=u0_f)
                    cs_g = CubicSpline(tg, ug, axis=0)
                    y_exact = np.array([cs_g(t_s[i])[np.argmin(np.abs(xg - x_s[i]))] for i in range(N_sensors)])
                    u_interp_fn = lambda x_arr, t_arr: np.array([cs_g(t_arr[i])[np.argmin(np.abs(xg - x_arr[i]))] for i in range(len(t_arr))])
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    
                elif scen_id == 5: # Boundary mismatch
                    bc_val = sev['bc_val']
                    drifting = sev['drifting']
                    if drifting:
                        bc_f = lambda b_side, t: 0.10 * np.sin(2 * np.pi * t) if b_side == 0 else 0.05 * np.cos(2 * np.pi * t)
                    else:
                        bc_f = lambda b_side, t: bc_val
                    xg, tg, ug = solve_heat_1d_general(Nx=101, Nt=501, alpha=alpha_true, bc_fn=bc_f)
                    cs_g = CubicSpline(tg, ug, axis=0)
                    y_exact = np.array([cs_g(t_s[i])[np.argmin(np.abs(xg - x_s[i]))] for i in range(N_sensors)])
                    u_interp_fn = lambda x_arr, t_arr: np.array([cs_g(t_arr[i])[np.argmin(np.abs(xg - x_arr[i]))] for i in range(len(t_arr))])
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    
                elif scen_id == 6: # Source term mismatch
                    s_val = sev['s_val']
                    localized = sev['localized']
                    if localized:
                        src_f = lambda x, t: np.where(np.abs(x - 0.5) < 0.15, s_val, 0.0)
                    else:
                        src_f = lambda x, t: np.full_like(x, s_val)
                    xg, tg, ug = solve_heat_1d_general(Nx=101, Nt=501, alpha=alpha_true, source_fn=src_f)
                    cs_g = CubicSpline(tg, ug, axis=0)
                    y_exact = np.array([cs_g(t_s[i])[np.argmin(np.abs(xg - x_s[i]))] for i in range(N_sensors)])
                    u_interp_fn = lambda x_arr, t_arr: np.array([cs_g(t_arr[i])[np.argmin(np.abs(xg - x_arr[i]))] for i in range(len(t_arr))])
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    
                elif scen_id == 7: # Variable diffusivity
                    grad = sev['grad']
                    step = sev['step']
                    if step:
                        a_fn = lambda x: np.where(x <= 0.5, alpha_true, 2.0 * alpha_true)
                    else:
                        a_fn = lambda x: alpha_true * (1.0 + grad * (x - 0.5))
                    xg, tg, ug = solve_heat_1d_general(Nx=101, Nt=501, alpha=alpha_true, alpha_fn=a_fn)
                    cs_g = CubicSpline(tg, ug, axis=0)
                    y_exact = np.array([cs_g(t_s[i])[np.argmin(np.abs(xg - x_s[i]))] for i in range(N_sensors)])
                    u_interp_fn = lambda x_arr, t_arr: np.array([cs_g(t_arr[i])[np.argmin(np.abs(xg - x_arr[i]))] for i in range(len(t_arr))])
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    
                elif scen_id == 8: # Sensor dropout
                    drop_frac = sev['drop_frac']
                    keep_count = int(round(N_sensors * (1.0 - drop_frac)))
                    keep_idx = np.sort(rng.choice(N_sensors, size=keep_count, replace=False))
                    t_s = t_s[keep_idx]
                    x_s = x_s[keep_idx]
                    y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                    noise = rng.normal(0, sig_true, len(keep_idx))
                    y_s = y_exact + noise
                    
                elif scen_id == 9: # Sensor jitter
                    jit = sev['jitter']
                    x_s_true = np.clip(x_s + rng.normal(0, jit, N_sensors), 0.05, 0.95)
                    t_s_true = np.clip(t_s + rng.normal(0, jit, N_sensors), 0.01, 1.0)
                    y_exact = solve_heat_1d_exact(x_s_true, t_s_true, alpha_true)
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    # Model still assumes original (x_s, t_s)
                    
                elif scen_id == 10: # Constant sensor bias
                    b_val = sev['bias']
                    y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    y_s[0] += b_val # Add constant bias to first sensor
                    
                elif scen_id == 11: # Very few sensors
                    N_few = sev['N']
                    N_sensors = N_few
                    t_s = np.logspace(np.log10(0.01), 0, N_sensors)
                    x_s = rng.uniform(0.2, 0.8, N_sensors)
                    y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    
                elif scen_id == 12: # Beyond the grid
                    alpha_true = sev['alpha']
                    y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    
                elif scen_id == 13: # Baseline drift
                    drift_val = sev['drift']
                    # Baseline window had drift
                    tb_20 = np.linspace(0.01, 0.5, 20)
                    xb_20 = rng.uniform(0.2, 0.8, 20)
                    # exact integral: alpha_true * (t + 0.5*drift*t^2/0.5)
                    integral_b = alpha_true * (tb_20 + 0.5 * drift_val * (tb_20**2) / 0.5)
                    yb_drf = np.sin(np.pi * xb_20) * np.exp(-np.pi**2 * integral_b) + rng.normal(0, sig_true, 20)
                    res_bd = opt.minimize_scalar(lambda l: np.sum((solve_heat_1d_exact(xb_20, tb_20, 10**l) - yb_drf)**2),
                                                bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
                    hat_b = 10**res_bd.x
                    y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                    noise = rng.normal(0, sig_true, N_sensors)
                    y_s = y_exact + noise
                    
                # Run Module Inferences:
                # 1. Mode 2
                h2, e2, c2 = evaluate_mode2(x_s, t_s, y_s, sig_assumed, alpha_true, prec)
                mod_results['Mode 2'].append((e2, c2, h2))
                matrix_rows.append({
                    'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                    'severity_level': sev_desc, 'module': 'Mode 2', 'seed': seed,
                    'alpha_true': alpha_true, 'alpha_hat': h2, 'rel_error': round(e2, 5),
                    'in_ci_95': c2, 'anomaly_pred': 'N/A', 'anomaly_is_healthy_fa': 'N/A'
                })
                
                # 2. Mode 3
                h3, e3, c3 = evaluate_mode3(x_s, t_s, y_s, sig_assumed, alpha_true, prec)
                mod_results['Mode 3'].append((e3, c3, h3))
                matrix_rows.append({
                    'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                    'severity_level': sev_desc, 'module': 'Mode 3', 'seed': seed,
                    'alpha_true': alpha_true, 'alpha_hat': h3, 'rel_error': round(e3, 5),
                    'in_ci_95': c3, 'anomaly_pred': 'N/A', 'anomaly_is_healthy_fa': 'N/A'
                })
                
                # 3. Mode 3+
                h3p, e3p, c3p = evaluate_mode3plus(x_s, t_s, y_s, sig_assumed, alpha_true, h3, prec)
                mod_results['Mode 3+'].append((e3p, c3p, h3p))
                matrix_rows.append({
                    'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                    'severity_level': sev_desc, 'module': 'Mode 3+', 'seed': seed,
                    'alpha_true': alpha_true, 'alpha_hat': h3p, 'rel_error': round(e3p, 5),
                    'in_ci_95': c3p, 'anomaly_pred': 'N/A', 'anomaly_is_healthy_fa': 'N/A'
                })
                
                # 4. Two-Stage Placement
                rng_ts = np.random.RandomState(seed + 999)
                hts, ets, cts = evaluate_two_stage(N_sensors, sig_assumed, alpha_true, prec, rng_ts, u_fn=u_interp_fn)
                mod_results['Two-Stage Placement'].append((ets, cts, hts))
                matrix_rows.append({
                    'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                    'severity_level': sev_desc, 'module': 'Two-Stage Placement', 'seed': seed,
                    'alpha_true': alpha_true, 'alpha_hat': hts, 'rel_error': round(ets, 5),
                    'in_ci_95': cts, 'anomaly_pred': 'N/A', 'anomaly_is_healthy_fa': 'N/A'
                })
                
                # 5. Anomaly Cascade
                if hat_b is None:
                    # Clean separate healthy baseline window
                    rng_b = np.random.RandomState(seed + 12345)
                    xb = rng_b.uniform(0.2, 0.8, 20)
                    tb = np.linspace(0.01, 0.5, 20)
                    yb = solve_heat_1d_exact(xb, tb, alpha_clean) + rng_b.normal(0, sig_clean, 20)
                    res_b = opt.minimize_scalar(lambda l: np.sum((solve_heat_1d_exact(xb, tb, 10**l) - yb)**2),
                                               bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
                    hat_b = 10**res_b.x
                pred_a, fa_a = evaluate_anomaly_cascade(x_s, t_s, y_s, sig_assumed, alpha_true, hat_b)
                mod_results['Anomaly Cascade'].append((fa_a, pred_a))
                matrix_rows.append({
                    'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                    'severity_level': sev_desc, 'module': 'Anomaly Cascade', 'seed': seed,
                    'alpha_true': alpha_true, 'alpha_hat': 'N/A', 'rel_error': 'N/A',
                    'in_ci_95': 'N/A', 'anomaly_pred': pred_a, 'anomaly_is_healthy_fa': fa_a
                })
                
            # Aggregate Summary for this (Scenario, Severity, Module)
            for m_name in ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']:
                res_list = mod_results[m_name]
                
                if m_name != 'Anomaly Cascade':
                    med_err = float(np.median([r[0] for r in res_list]))
                    cov_pct = float(np.mean([r[1] for r in res_list])) * 100.0
                    clean_err = clean_baselines[m_name]['med_err']
                    clean_cov = clean_baselines[m_name]['coverage']
                    err_ratio = med_err / max(1e-5, clean_err)
                    
                    # Pre-registered failure rule: err_ratio > 2.0 OR cov < 80%
                    failed = (err_ratio > 2.0) or (cov_pct < 80.0)
                    status = 'FAIL' if failed else 'PASS'
                    
                    fail_reasons = []
                    if err_ratio > 2.0: fail_reasons.append(f"Error {err_ratio:.1f}x > 2x clean")
                    if cov_pct < 80.0: fail_reasons.append(f"Coverage {cov_pct:.1f}% < 80%")
                    fail_str = "; ".join(fail_reasons) if failed else "Within specification"
                    
                    # Hypotheses
                    if failed:
                        if scen_id == 1 and sev_idx == 2:
                            cause = "Under-specified noise underestimates residual variance, causing catastrophic Wald CI collapse."
                            v2_fix = "V2 candidate: Residual-adaptive noise variance estimation via restricted maximum likelihood (REML)."
                        elif scen_id == 1 and sev_idx == 1:
                            cause = "Mild noise under-specification reduces CI width below true empirical dispersion."
                            v2_fix = "V2 candidate: Robust sandwich Huber-White covariance estimator."
                        elif scen_id == 2:
                            cause = "Heavy-tailed noise violates L2 Gaussian likelihood, heavily skewing least-squares optimum."
                            v2_fix = "V2 candidate: Huber loss or Student-t robust M-estimator likelihood objective."
                        elif scen_id == 3:
                            cause = "AR(1) temporal correlation creates systematic pseudo-trend residuals, shrinking effective sample size."
                            v2_fix = "V2 candidate: Generalized least squares (GLS) whitening filter (I - rho L) on temporal sensor stream."
                        elif scen_id == 4:
                            cause = "Forward model assumes fundamental mode sin(pi*x); higher spatial harmonics decay at exp(-k^2 pi^2 alpha t), severely biasing single-parameter alpha fit."
                            v2_fix = "V2 candidate: Fourier spatial mode decomposition to isolate k=1 harmonic prior to parameter estimation."
                        elif scen_id == 5:
                            cause = "Dirichlet boundary mismatch creates non-zero asymptotic temperature floor, destroying exponential decay assumption."
                            v2_fix = "V2 candidate: Joint estimation of boundary offsets u_0, u_1 alongside diffusivity alpha."
                        elif scen_id == 6:
                            cause = "Internal heat generation counteracts thermal diffusion decay, shifting apparent alpha toward zero."
                            v2_fix = "V2 candidate: Dual-parameter source-diffusivity inversion or PDE residual penalty term."
                        elif scen_id == 7:
                            cause = "Spatially variable alpha(x) invalidates scalar constant diffusion hypothesis; fit settles on spatially averaged surrogate value."
                            v2_fix = "V2 candidate: Spatial spline parameterization alpha(x) = sum_k c_k B_k(x) with Tikhonov smoothness regularization."
                        elif scen_id == 8:
                            cause = "Sensor dropout reduces temporal Fisher information below threshold needed for narrow CI coverage."
                            v2_fix = "V2 candidate: Information-preserving adaptive re-sampling triggered upon sensor heartbeat loss."
                        elif scen_id == 9:
                            cause = "Sensor position and timing jitter introduce observation coordinate errors that propagate nonlinearly into gradient-based fits."
                            v2_fix = "V2 candidate: Total least squares (TLS) or measurement-error model incorporating coordinate uncertainty."
                        elif scen_id == 10:
                            cause = "Constant sensor offset acts as persistent non-zero residual, pulling fitted alpha away from true value."
                            v2_fix = "V2 candidate: Automated outlier sensor calibration gate and median-based spatial filtering."
                        elif scen_id == 11:
                            cause = "N <= 3 observations lack sufficient temporal support to constrain curvature of exponential decay."
                            v2_fix = "V2 candidate: Physics-informed Bayesian prior shrinkage to prevent unidentifiable divergence."
                        elif scen_id == 12:
                            cause = "Alpha lies outside surrogate precomputation grid [-3.0, 1.0], hitting artificial search boundary."
                            v2_fix = "V2 candidate: Dynamic multi-scale grid expansion with adaptive domain re-normalization."
                        else:
                            cause = "Unmodeled environmental disturbance violates forward PDE assumptions."
                            v2_fix = "V2 candidate: Adaptive surrogate residual inflation."
                    else:
                        cause = "Robust parameter estimation within tolerance."
                        v2_fix = "None needed."
                        
                    summary_rows.append({
                        'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                        'severity_level': sev_desc, 'module': m_name,
                        'clean_rel_err': round(clean_err, 4), 'median_rel_err': round(med_err, 4),
                        'err_ratio_vs_clean': round(err_ratio, 2),
                        'clean_cov_pct': round(clean_cov, 1), 'coverage_pct': round(cov_pct, 1),
                        'clean_far_pct': 'N/A', 'healthy_far_pct': 'N/A',
                        'status': status, 'failure_reason': fail_str,
                        'likely_cause_hypothesis': cause, 'v2_candidate_fix_hypothesis': v2_fix
                    })
                else:
                    # Anomaly Cascade
                    fa_count = sum(r[0] for r in res_list)
                    tot_ep = len(res_list)
                    far_pct = (fa_count / tot_ep) * 100.0
                    clean_far = clean_baselines['Anomaly Cascade']['healthy_far']
                    
                    # Pre-registered failure rule: Healthy FAR > 15%
                    failed = far_pct > 15.0
                    status = 'FAIL' if failed else 'PASS'
                    fail_str = f"Healthy FAR {far_pct:.1f}% > 15%" if failed else "Healthy FAR within specification"
                    
                    if failed:
                        if scen_id == 1:
                            cause = "Assumed noise mismatch causes GLR test statistic normalization (RSS / sigma^2) to trip gating threshold."
                            v2_fix = "V2 candidate: Pre-gate noise floor estimation using robust MAD (median absolute deviation) of baseline differences."
                        elif scen_id == 2:
                            cause = "Heavy-tailed noise outliers falsely trigger LOO sensor exclusion (BIC_F < BIC_0) or change-point GLR."
                            v2_fix = "V2 candidate: Trimmed likelihood or student-t BIC penalty term."
                        elif scen_id == 3:
                            cause = "Correlated noise creates systematic multi-step residual deviations mimicking physical change-points."
                            v2_fix = "V2 candidate: Whittle likelihood or AR(1) pre-whitening filter in GLR hypothesis score."
                        elif scen_id in [4, 5, 6, 7]:
                            cause = "Physical model mismatch (IC, BC, heating, variable alpha) produces large structured residuals that trip the physical jump gate C or sensor fault gate F."
                            v2_fix = "V2 candidate: Model discrepancy Gaussian process (Kennedy-O'Hagan framework) isolating structural bias from discrete jumps."
                        elif scen_id == 10:
                            cause = "Constant sensor bias trips BIC fault gate; strong bias mimics physical regime shift if single-sensor gate saturates."
                            v2_fix = "V2 candidate: Enhanced LOO sensor exclusion with explicit sensor bias hypothesis M_B."
                        elif scen_id == 13:
                            cause = "Slow baseline drift causes parameter mismatch between anchored alpha_0 and operational window, tripping change-point GLR."
                            v2_fix = "V2 candidate: Dynamic rolling baseline window with exponential forgetting factor."
                        else:
                            cause = "Severe input perturbation exceeds GLR threshold tolerance."
                            v2_fix = "V2 candidate: Nonparametric change-point CUSUM detector."
                    else:
                        cause = "Cascade correctly absorbs perturbation without false alarm."
                        v2_fix = "None needed."
                        
                    summary_rows.append({
                        'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                        'severity_level': sev_desc, 'module': m_name,
                        'clean_rel_err': 'N/A', 'median_rel_err': 'N/A', 'err_ratio_vs_clean': 'N/A',
                        'clean_cov_pct': 'N/A', 'coverage_pct': 'N/A',
                        'clean_far_pct': round(clean_far, 1), 'healthy_far_pct': round(far_pct, 1),
                        'status': status, 'failure_reason': fail_str,
                        'likely_cause_hypothesis': cause, 'v2_candidate_fix_hypothesis': v2_fix
                    })
                    
    # Save CSVs
    df_matrix = pd.DataFrame(matrix_rows)
    df_summary = pd.DataFrame(summary_rows)
    
    matrix_csv_path = str(RESULTS / "stress_matrix.csv")
    summary_csv_path = str(RESULTS / "stress_summary.csv")
    
    df_matrix.to_csv(matrix_csv_path, index=False)
    df_summary.to_csv(summary_csv_path, index=False)
    
    print(f"\n[Complete] Saved full replication data to {matrix_csv_path} ({len(df_matrix)} rows)")
    print(f"[Complete] Saved pass/fail summary to {summary_csv_path} ({len(df_summary)} rows)")
    
    # Generate Markdown Report FROM CSV ONLY
    generate_markdown_report(summary_csv_path)

def generate_markdown_report(summary_csv_path):
    df = pd.read_csv(summary_csv_path)
    report_path = os.path.join(REPO_ROOT, "reports", "stress_matrix.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    total_cells = len(df)
    total_pass = (df['status'] == 'PASS').sum()
    total_fail = (df['status'] == 'FAIL').sum()
    pass_rate = (total_pass / total_cells) * 100.0
    
    lines = []
    lines.append("# Week 5 Stress Matrix Report: Comprehensive Stress Testing of Frozen Digital Twin Modules\n")
    lines.append("This document records the empirical stress testing of all five frozen digital twin modules under severe, non-standard operating conditions. In accordance with strict experimental discipline, **zero changes were made to any module** during this study. Failures are the explicit deliverable of this stress test, revealing the precise mathematical and operational boundaries of the frozen architectures.\n")
    lines.append("## Pre-Registered Failure Criteria (Fixed Pre-Run)\n")
    lines.append("A cell is classified as **FAIL** if:\n")
    lines.append("1. **Parameter Estimation Modules** (`Mode 2`, `Mode 3`, `Mode 3+`, `Two-Stage Placement`):\n")
    lines.append("   - Median relative $\\alpha$ error $> 2.0\\times$ the matching clean cell error, **OR**\n")
    lines.append("   - Empirical 95% confidence interval coverage $< 80.0\\%$.\n")
    lines.append("2. **Anomaly Cascade Module** (`Anomaly Cascade`):\n")
    lines.append("   - Healthy false-alarm rate (FAR on Class H) $> 15.0\\%$.\n\n")
    lines.append("Otherwise, the cell is classified as **PASS**.\n\n")
    
    lines.append("## Executive Summary Statistics\n")
    lines.append(f"- **Total Scenarios Evaluated:** 13 scenarios across 3 severity levels (39 unique stress regimes).\n")
    lines.append(f"- **Total Module Cells Evaluated:** {total_cells} module-scenario conditions (evaluated across 5 random seeds each = {total_cells * 5} runs total).\n")
    lines.append(f"- **Overall Pass Count:** {total_pass} / {total_cells} ({pass_rate:.1f}% pass rate).\n")
    lines.append(f"- **Overall Failure Count:** {total_fail} / {total_cells} ({100.0 - pass_rate:.1f}% failure rate).\n\n")
    
    # Per-module pass rates
    lines.append("### Module Pass/Fail Breakdown\n")
    lines.append("| Module | Total Conditions | Passed | Failed | Pass Rate (%) | Primary Failure Drivers |\n")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :--- |\n")
    
    for mod in ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']:
        sub = df[df['module'] == mod]
        p_cnt = (sub['status'] == 'PASS').sum()
        f_cnt = (sub['status'] == 'FAIL').sum()
        tot = len(sub)
        p_rate = p_cnt / tot * 100.0
        
        # Primary drivers
        failed_scens = sub[sub['status'] == 'FAIL']['scenario_name'].unique()
        drivers = ", ".join(failed_scens[:3]) if len(failed_scens) > 0 else "None (100% Pass)"
        if len(failed_scens) > 3: drivers += f", +{len(failed_scens)-3} more"
        lines.append(f"| **{mod}** | {tot} | {p_cnt} | {f_cnt} | **{p_rate:.1f}%** | {drivers} |\n")
        
    lines.append("\n---\n\n")
    lines.append("## Complete Stress Matrix Results\n")
    lines.append("The table below reports the complete results across all 39 conditions and 5 modules, generated strictly from [`data/results/stress_summary.csv`](file:///c:/Users/HP/Desktop/Digital%20twin/data/results/stress_summary.csv).\n\n")
    
    # Table grouped by scenario
    lines.append("| Scen # | Scenario | Severity Level | Module | Metric (Median Error / FAR) | Clean Baseline | Error Ratio / FAR | Coverage (%) | Status |\n")
    lines.append("| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n")
    
    for _, r in df.iterrows():
        s_idx = r['scenario_idx']
        s_name = r['scenario_name']
        s_sev = r['severity_level']
        mod = r['module']
        st = r['status']
        st_badge = f"**{st}**" if st == 'FAIL' else "PASS"
        
        if mod != 'Anomaly Cascade':
            m_val = f"{r['median_rel_err']:.4f}"
            c_val = f"{r['clean_rel_err']:.4f}"
            ratio = f"{r['err_ratio_vs_clean']:.2f}x"
            cov = f"{r['coverage_pct']:.1f}%"
        else:
            m_val = f"FAR {r['healthy_far_pct']:.1f}%"
            c_val = f"FAR {r['clean_far_pct']:.1f}%"
            ratio = "N/A"
            cov = "N/A"
            
        lines.append(f"| {s_idx:2d} | {s_name} | {s_sev} | {mod} | {m_val} | {c_val} | {ratio} | {cov} | {st_badge} |\n")
        
    lines.append("\n---\n\n")
    lines.append("## Root Cause Analysis & V2 Candidate Fixes for Failed Cells\n")
    lines.append("Each failure below documents the observed empirical degradation, the likely physical/mathematical mechanism, and a candidate V2 architectural mitigation. *All causes and fixes are explicitly marked as hypotheses (unverified in V1).*\n\n")
    
    failed_df = df[df['status'] == 'FAIL']
    for scen_id, grp in failed_df.groupby('scenario_idx'):
        scen_name = grp['scenario_name'].iloc[0]
        lines.append(f"### Scenario {scen_id}: {scen_name}\n")
        for _, r in grp.iterrows():
            lines.append(f"- **Module:** `{r['module']}` | **Severity:** {r['severity_level']}\n")
            lines.append(f"  - *Failure Reason:* {r['failure_reason']}\n")
            lines.append(f"  - *Likely Cause (Hypothesis):* {r['likely_cause_hypothesis']}\n")
            lines.append(f"  - *V2 Candidate Fix (Hypothesis):* {r['v2_candidate_fix_hypothesis']}\n\n")
            
    with open(report_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"[Report Complete] Markdown report written to {report_path}")

if __name__ == '__main__':
    run_stress_matrix()
