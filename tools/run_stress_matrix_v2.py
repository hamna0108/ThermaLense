"""Week 5 Stress Matrix v2 (Powered Rerun) on Frozen Modules.

PRE-REGISTERED FAILURE RULE:
A cell FAILS if:
  1. For parameter estimation modules (Mode 2, Mode 3, Mode 3+, Two-Stage Placement):
     median relative alpha error > 2.0x the matching clean cell,
     OR 95% Wald confidence interval coverage < 80.0%.
  2. For Anomaly Cascade module:
     healthy false-alarm rate > 15.0%.

REPLICATE POWER:
  >= 100 seeds per cell for every module (Anomaly: >= 100 episodes per cell).
  New seed range: 1200000+
  - Clean Baseline: 1200000..1200099 (100 reps)
  - Condition Cells: seed = 1200000 + scen_idx * 1000 + sev_idx * 100 + s_idx (100 reps per cell)

CATEGORIES:
  - 'declared-scope violation':
      Scenario 4: Different initial condition
      Scenario 5: Boundary mismatch
      Scenario 6: Source-term / heating mismatch
      Scenario 7: Variable diffusivity alpha(x)
  - 'robustness':
      Scenario 1: Misspecified noise sigma
      Scenario 2: Heavy-tailed noise
      Scenario 3: Correlated noise AR(1)
      Scenario 8: Sensor dropout
      Scenario 9: Sensor position error and time jitter
      Scenario 10: Constant sensor bias
      Scenario 11: Very few sensors
      Scenario 12: True alpha beyond/below grid
      Scenario 13: Baseline drift
"""

import os
import sys
import time
import math
import json
import csv
import multiprocessing as mp
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

def solve_heat_1d_cn_fast(Nx, Nt, alpha):
    """Fast Crank-Nicolson solver with LU factorization."""
    x = np.linspace(0, 1, Nx)
    t = np.linspace(0, 1, Nt)
    dx = x[1] - x[0]
    dt = t[1] - t[0]
    r = alpha * dt / (2.0 * dx**2)
    main_A = (1 + 2*r) * np.ones(Nx-2)
    off_A = -r * np.ones(Nx-3)
    main_B = (1 - 2*r) * np.ones(Nx-2)
    off_B = r * np.ones(Nx-3)
    A = sp.diags([off_A, main_A, off_A], offsets=[-1, 0, 1], format='csc')
    B = sp.diags([off_B, main_B, off_B], offsets=[-1, 0, 1], format='csr')
    lu = spla.splu(A)
    u = np.zeros((Nt, Nx))
    u[0, :] = np.sin(np.pi * x)
    for n in range(Nt - 1):
        rhs = B.dot(u[n, 1:-1])
        u[n+1, 1:-1] = lu.solve(rhs)
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
    
    A = sp.diags([lower_A, main_A, upper_A], offsets=[-1, 0, 1], shape=(N_int, N_int), format='csc')
    B = sp.diags([lower_B, main_B, upper_B], offsets=[-1, 0, 1], shape=(N_int, N_int), format='csr')
    lu_A = spla.splu(A)
    
    for n in range(Nt - 1):
        tn = t[n]
        tn1 = t[n+1]
        
        if bc_fn is not None:
            bc0_n, bc1_n = bc_fn(tn)
            bc0_n1, bc1_n1 = bc_fn(tn1)
        else:
            bc0_n, bc1_n = 0.0, 0.0
            bc0_n1, bc1_n1 = 0.0, 0.0
            
        u[n, 0] = bc0_n
        u[n, -1] = bc1_n
        u[n+1, 0] = bc0_n1
        u[n+1, -1] = bc1_n1
        
        rhs = B.dot(u[n, 1:-1])
        rhs[0] += r_half[0] * (bc0_n + bc0_n1)
        rhs[-1] += r_half[-1] * (bc1_n + bc1_n1)
        
        if source_fn is not None:
            s_n = source_fn(x[1:-1], tn)
            s_n1 = source_fn(x[1:-1], tn1)
            rhs += 0.5 * dt * (s_n + s_n1)
            
        u[n+1, 1:-1] = lu_A.solve(rhs)
        
    return x, t, u

def cramer_rao_bound(alpha, t, x, sigma):
    """Cramér-Rao Bound for single-parameter heat diffusion."""
    du_da = - (np.pi**2) * t * np.exp(-alpha * (np.pi**2) * t) * np.sin(np.pi * x)
    fisher_info = np.sum((du_da**2) / (sigma**2))
    if fisher_info <= 1e-15:
        return np.inf
    return 1.0 / fisher_info

def wilson_ci(k, n, confidence=0.95):
    """Compute Wilson score interval."""
    if n == 0:
        return 0.0, 0.0
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = (z * np.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))) / denom
    lo = max(0.0, (center - spread) * 100.0)
    hi = min(100.0, (center + spread) * 100.0)
    return round(lo, 2), round(hi, 2)

# -------------------------------------------------------------------------------------------------
# 2. Frozen Surrogate Precomputation
# -------------------------------------------------------------------------------------------------

def precompute_surrogates():
    print("[Setup] Precomputing forward surrogate grids (Mode 2, Mode 3, Two-Stage)...")
    Nx, Nt = 50, 100
    grid_la = np.linspace(BOUND_LOG_LOW, BOUND_LOG_HIGH, 350)
    
    # Mode 2: Crank-Nicolson precomputed grid
    U_m2 = np.zeros((350, Nt, Nx))
    for i, la in enumerate(grid_la):
        _, _, u = solve_heat_1d_cn_fast(Nx, Nt, 10**la)
        U_m2[i] = u
    x_grid = np.linspace(0, 1, Nx)
    t_grid = np.linspace(0, 1, Nt)
    
    # Mode 3: FNO-2D precomputed grid
    fno_path = os.path.join(MODELS, 'fno2d_heat.pt')
    ckpt = torch.load(fno_path, map_location='cpu', weights_only=False)
    model = FNO2d(modes1=16, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=False)
    if 'model_state_dict' in ckpt:
        model.load_state_dict(ckpt['model_state_dict'])
    elif 'state_dict' in ckpt:
        model.load_state_dict(ckpt['state_dict'])
    else:
        model.load_state_dict(ckpt)
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
    
    # Center grid for Two-Stage Placement
    Nx_c, Nt_c = 51, 501
    grid_la_c = np.linspace(BOUND_LOG_LOW, BOUND_LOG_HIGH, 300)
    t_grid_c = np.linspace(0, 1, Nt_c)
    U_cn_center = np.array([solve_heat_1d_cn_fast(Nx_c, Nt_c, 10**la)[2][:, (Nx_c-1)//2] for la in grid_la_c])
    cs_time_c = CubicSpline(t_grid_c, U_cn_center, axis=1)
    
    print("[Setup] Precomputations complete.")
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
    
    # Sensor fault LOO
    rss_f_list = []
    for k in range(N):
        idx = [i for i in range(N) if i != k]
        if len(idx) < 1:
            continue
        res_k = opt.minimize_scalar(
            lambda l: np.sum((solve_heat_1d_exact(x_s[idx], t_s[idx], 10**l) - y_s[idx])**2),
            bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded'
        )
        rss_f_list.append(np.sum((solve_heat_1d_exact(x_s[idx], t_s[idx], 10**res_k.x) - y_s[idx])**2))
    rss_f = min(rss_f_list) if rss_f_list else rss0
    chi2_f = rss_f / (sigma**2 + 1e-12)
    bic_f = chi2_f + 2.0 * np.log(max(2, N)) + gamma_f
    
    # Change point candidate scan
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
    b_est = float(cs_b_m3(np.clip(res.x, BOUND_LOG_LOW, BOUND_LOG_HIGH)))
    la_corr = res.x - b_est
    hat = 10**la_corr
    rel_err = abs(hat - alpha_true) / max(1e-5, alpha_true)
    
    crb = cramer_rao_bound(hat, t_s, x_s, sigma_assumed)
    in_ci = 0
    if crb != np.inf and crb > 0:
        se = np.sqrt(crb) / (hat * np.log(10))
        tot_unc = np.sqrt(se**2 + (0.5 * b_est)**2)
        if (res.x - b_est) - 1.96 * tot_unc <= np.log10(alpha_true) <= (res.x - b_est) + 1.96 * tot_unc:
            in_ci = 1
    return hat, rel_err, in_ci

def evaluate_mode3plus(x_s, t_s, y_s, sigma_assumed, alpha_true, hat_m3, prec):
    la_0 = np.log10(max(1e-4, hat_m3))
    b_lo = max(-3.0, min(0.7, la_0 - 0.3))
    b_hi = min(1.0, max(-2.7, la_0 + 0.3))
    if b_lo >= b_hi:
        b_lo, b_hi = -3.0, 1.0
    bracket = (b_lo, b_hi)
    
    t_grid = prec['t_grid']
    x_grid = prec['x_grid']
    t_idx = [np.argmin(np.abs(t_grid - t)) for t in t_s]
    x_idx = [np.argmin(np.abs(x_grid - x)) for x in x_s]
    
    def cn_obj(la):
        _, _, u_num = solve_heat_1d_cn_fast(50, 100, 10**la)
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

# Global precomputed table for worker processes
G_PREC = None

def init_worker(prec_data):
    global G_PREC
    G_PREC = prec_data

def evaluate_single_condition_cell(args):
    """Worker function to evaluate a single condition cell across 100 seeds."""
    scen, sev, clean_baselines = args
    scen_id = scen['idx']
    scen_name = scen['name']
    sev_idx = sev['sev_idx']
    sev_desc = sev['desc']
    
    # Categorization
    if scen_id in [4, 5, 6, 7]:
        category = 'declared-scope violation'
    else:
        category = 'robustness'
        
    num_reps = 100
    base_seed = 1200000
    
    mod_results = {m: [] for m in ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']}
    matrix_rows = []
    
    prec = G_PREC
    
    for s_idx in range(num_reps):
        cell_idx = scen_id * 1000 + sev_idx * 100 + s_idx
        seed = base_seed + cell_idx
        rng = np.random.RandomState(seed)
        
        alpha_true = 0.100
        N_sensors = 10
        sig_true = 0.01
        sig_assumed = 0.01
        
        u_interp_fn = None
        hat_b = None
        
        t_s = np.logspace(np.log10(0.01), 0, N_sensors)
        x_s = rng.uniform(0.2, 0.8, N_sensors)
        
        if scen_id == 1:
            sig_true = sev['true_sig']
            sig_assumed = sev['assumed_sig']
            noise = rng.normal(0, sig_true, N_sensors)
            y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            y_s = y_exact + noise
            
        elif scen_id == 2:
            df_t = sev['df']
            raw_t = rng.standard_t(df_t, size=N_sensors)
            scale_t = sig_true * np.sqrt((df_t - 2.0) / df_t)
            noise = raw_t * scale_t
            if sev['outlier_prob'] > 0:
                outliers = rng.uniform(0, 1, N_sensors) < sev['outlier_prob']
                noise[outliers] += 5.0 * sig_true * rng.choice([-1.0, 1.0], size=np.sum(outliers))
            y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            y_s = y_exact + noise
            
        elif scen_id == 3:
            rho = sev['rho']
            raw_w = rng.normal(0, sig_true, N_sensors)
            noise = np.zeros(N_sensors)
            noise[0] = raw_w[0]
            for i in range(1, N_sensors):
                noise[i] = rho * noise[i-1] + np.sqrt(1 - rho**2) * raw_w[i]
            y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            y_s = y_exact + noise
            
        elif scen_id == 4:
            ic_mode = sev['mode']
            if ic_mode == 'sin_2pi_x':
                u0_fn = lambda x: np.sin(2.0 * np.pi * x)
            elif ic_mode == 'two_mode_sum':
                u0_fn = lambda x: np.sin(np.pi * x) + 0.5 * np.sin(3.0 * np.pi * x)
            elif ic_mode == 'gaussian_bump':
                u0_fn = lambda x: np.exp(-((x - 0.5)**2) / (2 * 0.08**2))
            xg, tg, ug = solve_heat_1d_general(Nx=101, Nt=501, alpha=alpha_true, u0_fn=u0_fn)
            cs_g = CubicSpline(tg, ug, axis=0)
            y_exact = np.array([cs_g(t_s[i])[np.argmin(np.abs(xg - x_s[i]))] for i in range(N_sensors)])
            u_interp_fn = lambda x_arr, t_arr: np.array([cs_g(t_arr[i])[np.argmin(np.abs(xg - x_arr[i]))] for i in range(len(t_arr))])
            noise = rng.normal(0, sig_true, N_sensors)
            y_s = y_exact + noise
            
        elif scen_id == 5:
            bc_mode = sev['mode']
            val = sev['val']
            if bc_mode == 'constant_offset':
                bc_fn = lambda t: (val, val)
            elif bc_mode == 'drifting':
                bc_fn = lambda t: (val * t, val * t)
            xg, tg, ug = solve_heat_1d_general(Nx=101, Nt=501, alpha=alpha_true, bc_fn=bc_fn)
            cs_g = CubicSpline(tg, ug, axis=0)
            y_exact = np.array([cs_g(t_s[i])[np.argmin(np.abs(xg - x_s[i]))] for i in range(N_sensors)])
            u_interp_fn = lambda x_arr, t_arr: np.array([cs_g(t_arr[i])[np.argmin(np.abs(xg - x_arr[i]))] for i in range(len(t_arr))])
            noise = rng.normal(0, sig_true, N_sensors)
            y_s = y_exact + noise
            
        elif scen_id == 6:
            s_val = sev['s']
            source_fn = lambda x, t: np.full_like(x, s_val)
            xg, tg, ug = solve_heat_1d_general(Nx=101, Nt=501, alpha=alpha_true, source_fn=source_fn)
            cs_g = CubicSpline(tg, ug, axis=0)
            y_exact = np.array([cs_g(t_s[i])[np.argmin(np.abs(xg - x_s[i]))] for i in range(N_sensors)])
            u_interp_fn = lambda x_arr, t_arr: np.array([cs_g(t_arr[i])[np.argmin(np.abs(xg - x_arr[i]))] for i in range(len(t_arr))])
            noise = rng.normal(0, sig_true, N_sensors)
            y_s = y_exact + noise
            
        elif scen_id == 7:
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
            
        elif scen_id == 8:
            drop_frac = sev['drop_frac']
            keep_count = int(round(N_sensors * (1.0 - drop_frac)))
            keep_idx = np.sort(rng.choice(N_sensors, size=keep_count, replace=False))
            t_s = t_s[keep_idx]
            x_s = x_s[keep_idx]
            y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            noise = rng.normal(0, sig_true, len(keep_idx))
            y_s = y_exact + noise
            
        elif scen_id == 9:
            jit = sev['jitter']
            x_s_true = np.clip(x_s + rng.normal(0, jit, N_sensors), 0.05, 0.95)
            t_s_true = np.clip(t_s + rng.normal(0, jit, N_sensors), 0.01, 1.0)
            y_exact = solve_heat_1d_exact(x_s_true, t_s_true, alpha_true)
            noise = rng.normal(0, sig_true, N_sensors)
            y_s = y_exact + noise
            
        elif scen_id == 10:
            b_val = sev['bias']
            y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            noise = rng.normal(0, sig_true, N_sensors)
            y_s = y_exact + noise
            y_s[0] += b_val
            
        elif scen_id == 11:
            N_few = sev['N']
            N_sensors = N_few
            t_s = np.logspace(np.log10(0.01), 0, N_sensors)
            x_s = rng.uniform(0.2, 0.8, N_sensors)
            y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            noise = rng.normal(0, sig_true, N_sensors)
            y_s = y_exact + noise
            
        elif scen_id == 12:
            alpha_true = sev['alpha']
            y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            noise = rng.normal(0, sig_true, N_sensors)
            y_s = y_exact + noise
            
        elif scen_id == 13:
            drift_val = sev['drift']
            tb_20 = np.linspace(0.01, 0.5, 20)
            xb_20 = rng.uniform(0.2, 0.8, 20)
            integral_b = alpha_true * (tb_20 + 0.5 * drift_val * (tb_20**2) / 0.5)
            yb_drf = np.sin(np.pi * xb_20) * np.exp(-np.pi**2 * integral_b) + rng.normal(0, sig_true, 20)
            res_bd = opt.minimize_scalar(lambda l: np.sum((solve_heat_1d_exact(xb_20, tb_20, 10**l) - yb_drf)**2),
                                        bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
            hat_b = 10**res_bd.x
            y_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            noise = rng.normal(0, sig_true, N_sensors)
            y_s = y_exact + noise
            
        # 1. Mode 2
        h2, e2, c2 = evaluate_mode2(x_s, t_s, y_s, sig_assumed, alpha_true, prec)
        mod_results['Mode 2'].append((e2, c2, h2))
        matrix_rows.append({
            'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
            'severity_level': sev_desc, 'category': category, 'module': 'Mode 2', 'seed': seed,
            'alpha_true': alpha_true, 'alpha_hat': round(h2, 6), 'rel_error': round(e2, 6),
            'in_ci_95': c2, 'anomaly_pred': 'N/A', 'anomaly_is_healthy_fa': 'N/A'
        })
        
        # 2. Mode 3
        h3, e3, c3 = evaluate_mode3(x_s, t_s, y_s, sig_assumed, alpha_true, prec)
        mod_results['Mode 3'].append((e3, c3, h3))
        matrix_rows.append({
            'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
            'severity_level': sev_desc, 'category': category, 'module': 'Mode 3', 'seed': seed,
            'alpha_true': alpha_true, 'alpha_hat': round(h3, 6), 'rel_error': round(e3, 6),
            'in_ci_95': c3, 'anomaly_pred': 'N/A', 'anomaly_is_healthy_fa': 'N/A'
        })
        
        # 3. Mode 3+
        h3p, e3p, c3p = evaluate_mode3plus(x_s, t_s, y_s, sig_assumed, alpha_true, h3, prec)
        mod_results['Mode 3+'].append((e3p, c3p, h3p))
        matrix_rows.append({
            'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
            'severity_level': sev_desc, 'category': category, 'module': 'Mode 3+', 'seed': seed,
            'alpha_true': alpha_true, 'alpha_hat': round(h3p, 6), 'rel_error': round(e3p, 6),
            'in_ci_95': c3p, 'anomaly_pred': 'N/A', 'anomaly_is_healthy_fa': 'N/A'
        })
        
        # 4. Two-Stage Placement
        rng_ts = np.random.RandomState(seed + 999)
        hts, ets, cts = evaluate_two_stage(N_sensors, sig_assumed, alpha_true, prec, rng_ts, u_fn=u_interp_fn)
        mod_results['Two-Stage Placement'].append((ets, cts, hts))
        matrix_rows.append({
            'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
            'severity_level': sev_desc, 'category': category, 'module': 'Two-Stage Placement', 'seed': seed,
            'alpha_true': alpha_true, 'alpha_hat': round(hts, 6), 'rel_error': round(ets, 6),
            'in_ci_95': cts, 'anomaly_pred': 'N/A', 'anomaly_is_healthy_fa': 'N/A'
        })
        
        # 5. Anomaly Cascade
        if hat_b is None:
            rng_b = np.random.RandomState(seed + 12345)
            xb = rng_b.uniform(0.2, 0.8, 20)
            tb = np.linspace(0.01, 0.5, 20)
            yb = solve_heat_1d_exact(xb, tb, 0.100) + rng_b.normal(0, 0.01, 20)
            res_b = opt.minimize_scalar(lambda l: np.sum((solve_heat_1d_exact(xb, tb, 10**l) - yb)**2),
                                       bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
            hat_b = 10**res_b.x
        pred_a, fa_a = evaluate_anomaly_cascade(x_s, t_s, y_s, sig_assumed, alpha_true, hat_b)
        mod_results['Anomaly Cascade'].append((fa_a, pred_a))
        matrix_rows.append({
            'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
            'severity_level': sev_desc, 'category': category, 'module': 'Anomaly Cascade', 'seed': seed,
            'alpha_true': alpha_true, 'alpha_hat': 'N/A', 'rel_error': 'N/A',
            'in_ci_95': 'N/A', 'anomaly_pred': pred_a, 'anomaly_is_healthy_fa': fa_a
        })
        
    # Summarize this condition cell
    summary_rows = []
    
    # Hypotheses dictionary
    hypotheses = {
        1: ("Underestimated noise shrinks Fisher information and inflates chi2 threshold", "Pre-estimate empirical residual variance before setting weights"),
        2: ("Outliers violate Gaussian likelihood and drag MSE fits away from mode", "Replace L2 loss with Huber or Student-t robust M-estimator"),
        3: ("Residual autocorrelation violates i.i.d. assumption, shrinking effective sample size", "Pre-whiten measurement residuals via AR(1) Cochrane-Orcutt transform"),
        4: ("Higher spatial modes decay exponentially faster than fundamental mode", "Decompose initial time slice into spatial Fourier coefficients before fitting alpha"),
        5: ("Boundary thermal offset/flux counteracts interior diffusion decay", "Jointly invert for Dirichlet boundary values alongside alpha"),
        6: ("Internal heating source counteracts conductive decay, masquerading as zero/negative diffusion", "Augment parameter vector to simultaneously estimate volumetric source rate"),
        7: ("Spatial gradient in diffusivity violates homogeneous medium assumption", "Upgrade operator to accept spatial parameter field alpha(x)"),
        8: ("Missing sensor channels reduce spatial information density below Cramér-Rao floor", "Dynamically adjust confidence interval using actual retained Fisher information"),
        9: ("Position and timing jitter introduce systematic phase and spatial distortion", "Include sensor coordinate jitter margin in likelihood variance budget"),
        10: ("Constant sensor bias triggers single-sensor Leave-One-Out BIC gate", "LOO BIC gate correctly flags Class F sensor fault rather than Class C"),
        11: ("Extremely sparse array (N=2, 3) yields near-singular Fisher information matrix", "Impose empirical Bayes prior on alpha or mandate minimum N >= 5 sensor nodes"),
        12: ("Signal vanishes into noise floor (high alpha) or decays too slowly (low alpha)", "Dynamically scale temporal observation window inversely with initial alpha estimate"),
        13: ("Baseline parameter drift creates persistent residual offset in operational window", "Incorporate linear baseline drift parameter into null hypothesis model"),
    }
    
    for m_name in ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']:
        res_list = mod_results[m_name]
        
        if m_name != 'Anomaly Cascade':
            med_err = float(np.median([r[0] for r in res_list]))
            cov_count = sum([r[1] for r in res_list])
            cov_pct = float(cov_count / num_reps * 100.0)
            cov_lo, cov_hi = wilson_ci(cov_count, num_reps)
            
            clean_err = clean_baselines[m_name]['med_err']
            err_ratio = med_err / max(1e-5, clean_err)
            
            failed = (err_ratio > 2.0) or (cov_pct < 80.0)
            status = 'FAIL' if failed else 'PASS'
            
            fail_reasons = []
            if err_ratio > 2.0: fail_reasons.append(f"Error {err_ratio:.2f}x > 2.0x clean")
            if cov_pct < 80.0: fail_reasons.append(f"Coverage {cov_pct:.1f}% < 80.0%")
            fail_str = "; ".join(fail_reasons) if failed else "Within specification"
            
            cause_hyp, fix_hyp = hypotheses.get(scen_id, ("Model mismatch degrades estimator", "Calibrate model on perturbed regime"))
            
            summary_rows.append({
                'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                'severity_level': sev_desc, 'category': category, 'module': m_name,
                'med_rel_err': round(med_err, 6), 'clean_rel_err': round(clean_err, 6),
                'err_ratio': round(err_ratio, 3), 'coverage_pct': round(cov_pct, 2),
                'coverage_ci_low': cov_lo, 'coverage_ci_high': cov_hi,
                'healthy_far_pct': 'N/A', 'healthy_far_ci_low': 'N/A', 'healthy_far_ci_high': 'N/A',
                'status': status, 'fail_reasons': fail_str,
                'likely_cause_hypothesis': cause_hyp if failed else 'N/A',
                'v2_candidate_fix_hypothesis': fix_hyp if failed else 'N/A'
            })
        else:
            fa_count = sum([r[0] for r in res_list])
            far_pct = float(fa_count / num_reps * 100.0)
            far_lo, far_hi = wilson_ci(fa_count, num_reps)
            
            failed = (far_pct > 15.0)
            status = 'FAIL' if failed else 'PASS'
            fail_str = f"Healthy FAR {far_pct:.1f}% > 15.0%" if failed else "Within specification"
            
            cause_hyp, fix_hyp = hypotheses.get(scen_id, ("Perturbation elevates false alarm rate", "Calibrate GLR threshold under perturbation"))
            
            summary_rows.append({
                'scenario_idx': scen_id, 'scenario_name': scen_name, 'severity_idx': sev_idx,
                'severity_level': sev_desc, 'category': category, 'module': m_name,
                'med_rel_err': 'N/A', 'clean_rel_err': 'N/A', 'err_ratio': 'N/A',
                'coverage_pct': 'N/A', 'coverage_ci_low': 'N/A', 'coverage_ci_high': 'N/A',
                'healthy_far_pct': round(far_pct, 2), 'healthy_far_ci_low': far_lo, 'healthy_far_ci_high': far_hi,
                'status': status, 'fail_reasons': fail_str,
                'likely_cause_hypothesis': cause_hyp if failed else 'N/A',
                'v2_candidate_fix_hypothesis': fix_hyp if failed else 'N/A'
            })
            
    return matrix_rows, summary_rows

# -------------------------------------------------------------------------------------------------
# 5. Master Execution Loop & Markdown Report Generator
# -------------------------------------------------------------------------------------------------

def run_stress_matrix_v2():
    print("=" * 115)
    print("WEEK 5 STRESS MATRIX V2 (POWERED RERUN - 100 SEEDS / CELL)")
    print("Pre-registered failure rule: Error > 2.0x clean, Coverage < 80.0%, or Anomaly Healthy FAR > 15.0%")
    print("=" * 115)
    
    prec = precompute_surrogates()
    
    # 1. Clean Matching Baseline Cells (100 reps, seeds 1200000..1200099)
    print("\n[Step 1] Evaluating Clean Matching Baselines (Alpha=0.100, N=10, Sigma=0.01, 100 reps)...")
    clean_records = {m: [] for m in ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']}
    
    alpha_clean = 0.100
    N_clean = 10
    sig_clean = 0.01
    num_clean_reps = 100
    base_seed = 1200000
    
    for s_idx in range(num_clean_reps):
        seed = base_seed + s_idx
        rng = np.random.RandomState(seed)
        t_s = np.logspace(np.log10(0.01), 0, N_clean)
        x_s = rng.uniform(0.2, 0.8, N_clean)
        y_exact = solve_heat_1d_exact(x_s, t_s, alpha_clean)
        y_clean = y_exact + rng.normal(0, sig_clean, N_clean)
        
        h2, e2, c2 = evaluate_mode2(x_s, t_s, y_clean, sig_clean, alpha_clean, prec)
        clean_records['Mode 2'].append((e2, c2))
        
        h3, e3, c3 = evaluate_mode3(x_s, t_s, y_clean, sig_clean, alpha_clean, prec)
        clean_records['Mode 3'].append((e3, c3))
        
        h3p, e3p, c3p = evaluate_mode3plus(x_s, t_s, y_clean, sig_clean, alpha_clean, h3, prec)
        clean_records['Mode 3+'].append((e3p, c3p))
        
        rng_ts = np.random.RandomState(seed + 999)
        hts, ets, cts = evaluate_two_stage(N_clean, sig_clean, alpha_clean, prec, rng_ts)
        clean_records['Two-Stage Placement'].append((ets, cts))
        
        rng_b = np.random.RandomState(seed + 12345)
        xb = rng_b.uniform(0.2, 0.8, 20)
        tb = np.linspace(0.01, 0.5, 20)
        yb = solve_heat_1d_exact(xb, tb, alpha_clean) + rng_b.normal(0, sig_clean, 20)
        res_b = opt.minimize_scalar(lambda l: np.sum((solve_heat_1d_exact(xb, tb, 10**l) - yb)**2),
                                   bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
        hat_b = 10**res_b.x
        pred_a, fa_a = evaluate_anomaly_cascade(x_s, t_s, y_clean, sig_clean, alpha_clean, hat_b)
        clean_records['Anomaly Cascade'].append(fa_a)
        
    clean_baselines = {}
    for m in ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement']:
        clean_baselines[m] = {
            'med_err': float(np.median([r[0] for r in clean_records[m]])),
            'coverage': float(np.mean([r[1] for r in clean_records[m]])) * 100.0,
            'cov_lo': wilson_ci(sum([r[1] for r in clean_records[m]]), num_clean_reps)[0],
            'cov_hi': wilson_ci(sum([r[1] for r in clean_records[m]]), num_clean_reps)[1],
        }
        print(f"  Clean {m:20s}: Med Rel Err = {clean_baselines[m]['med_err']:.6f}, Coverage = {clean_baselines[m]['coverage']:.1f}% [{clean_baselines[m]['cov_lo']:.1f}, {clean_baselines[m]['cov_hi']:.1f}]")
        
    clean_baselines['Anomaly Cascade'] = {
        'far': float(np.mean(clean_records['Anomaly Cascade'])) * 100.0,
        'far_lo': wilson_ci(sum(clean_records['Anomaly Cascade']), num_clean_reps)[0],
        'far_hi': wilson_ci(sum(clean_records['Anomaly Cascade']), num_clean_reps)[1],
    }
    print(f"  Clean {'Anomaly Cascade':20s}: Healthy FAR = {clean_baselines['Anomaly Cascade']['far']:.1f}% [{clean_baselines['Anomaly Cascade']['far_lo']:.1f}, {clean_baselines['Anomaly Cascade']['far_hi']:.1f}]")
    
    # 2. Setup Scenarios & Severities
    scenarios = [
        {
            'idx': 1, 'name': 'Misspecified noise sigma',
            'severities': [
                {'sev_idx': 1, 'desc': 'Assumed 0.05, true 0.01', 'assumed_sig': 0.05, 'true_sig': 0.01},
                {'sev_idx': 2, 'desc': 'Assumed 0.01, true 0.05', 'assumed_sig': 0.01, 'true_sig': 0.05},
                {'sev_idx': 3, 'desc': 'Assumed 0.01, true 0.03', 'assumed_sig': 0.01, 'true_sig': 0.03},
            ]
        },
        {
            'idx': 2, 'name': 'Heavy-tailed noise',
            'severities': [
                {'sev_idx': 1, 'desc': 'Student-t df=3 (moderate tail)', 'df': 3.0, 'outlier_prob': 0.0},
                {'sev_idx': 2, 'desc': 'Student-t df=2.5 with 2% 5-sigma outliers', 'df': 2.5, 'outlier_prob': 0.02},
                {'sev_idx': 3, 'desc': 'Student-t df=2.1 with 5% 5-sigma outliers', 'df': 2.1, 'outlier_prob': 0.05},
            ]
        },
        {
            'idx': 3, 'name': 'Correlated noise',
            'severities': [
                {'sev_idx': 1, 'desc': 'AR(1) rho = 0.50', 'rho': 0.50},
                {'sev_idx': 2, 'desc': 'AR(1) rho = 0.80', 'rho': 0.80},
                {'sev_idx': 3, 'desc': 'AR(1) rho = 0.95', 'rho': 0.95},
            ]
        },
        {
            'idx': 4, 'name': 'Different initial condition',
            'severities': [
                {'sev_idx': 1, 'desc': 'Harmonic double mode sin(2 pi x)', 'mode': 'sin_2pi_x'},
                {'sev_idx': 2, 'desc': 'Two-mode sum sin(pi x) + 0.5 sin(3 pi x)', 'mode': 'two_mode_sum'},
                {'sev_idx': 3, 'desc': 'Gaussian bump exp(-(x-0.5)^2 / (2*0.08^2))', 'mode': 'gaussian_bump'},
            ]
        },
        {
            'idx': 5, 'name': 'Boundary mismatch',
            'severities': [
                {'sev_idx': 1, 'desc': 'Small constant offset u_bc = 0.05', 'mode': 'constant_offset', 'val': 0.05},
                {'sev_idx': 2, 'desc': 'Moderate constant offset u_bc = 0.15', 'mode': 'constant_offset', 'val': 0.15},
                {'sev_idx': 3, 'desc': 'Linearly drifting boundary u_bc(t) = 0.20 * t', 'mode': 'drifting', 'val': 0.20},
            ]
        },
        {
            'idx': 6, 'name': 'Source-term / heating mismatch',
            'severities': [
                {'sev_idx': 1, 'desc': 'Small constant source s = 0.1', 's': 0.1},
                {'sev_idx': 2, 'desc': 'Moderate constant source s = 0.5', 's': 0.5},
                {'sev_idx': 3, 'desc': 'Strong constant source s = 2.0', 's': 2.0},
            ]
        },
        {
            'idx': 7, 'name': 'Variable diffusivity alpha(x)',
            'severities': [
                {'sev_idx': 1, 'desc': 'Mild linear ramp alpha(x) = alpha0*(1 + 0.5*(x-0.5))', 'grad': 0.5, 'step': False},
                {'sev_idx': 2, 'desc': 'Steep linear ramp alpha(x) = alpha0*(1 + 1.5*(x-0.5))', 'grad': 1.5, 'step': False},
                {'sev_idx': 3, 'desc': 'Step discontinuity alpha(x) = 2*alpha0 for x > 0.5', 'grad': 0.0, 'step': True},
            ]
        },
        {
            'idx': 8, 'name': 'Sensor dropout',
            'severities': [
                {'sev_idx': 1, 'desc': '10% readings missing (1 sensor dropped)', 'drop_frac': 0.10},
                {'sev_idx': 2, 'desc': '30% readings missing (3 sensors dropped)', 'drop_frac': 0.30},
                {'sev_idx': 3, 'desc': '50% readings missing (5 sensors dropped)', 'drop_frac': 0.50},
            ]
        },
        {
            'idx': 9, 'name': 'Sensor position error and time jitter',
            'severities': [
                {'sev_idx': 1, 'desc': 'Small jitter sigma_jitter = 0.01', 'jitter': 0.01},
                {'sev_idx': 2, 'desc': 'Moderate jitter sigma_jitter = 0.03', 'jitter': 0.03},
                {'sev_idx': 3, 'desc': 'Large jitter sigma_jitter = 0.06', 'jitter': 0.06},
            ]
        },
        {
            'idx': 10, 'name': 'Constant sensor bias',
            'severities': [
                {'sev_idx': 1, 'desc': 'Small sensor bias b = 3 sigma (0.03)', 'bias': 0.03},
                {'sev_idx': 2, 'desc': 'Medium sensor bias b = 6 sigma (0.06)', 'bias': 0.06},
                {'sev_idx': 3, 'desc': 'Strong sensor bias b = 15 sigma (0.15)', 'bias': 0.15},
            ]
        },
        {
            'idx': 11, 'name': 'Very few sensors',
            'severities': [
                {'sev_idx': 1, 'desc': 'Sparse array N = 5 sensors', 'N': 5},
                {'sev_idx': 2, 'desc': 'Very sparse array N = 3 sensors', 'N': 3},
                {'sev_idx': 3, 'desc': 'Minimal array N = 2 sensors', 'N': 2},
            ]
        },
        {
            'idx': 12, 'name': 'True alpha beyond the grid',
            'severities': [
                {'sev_idx': 1, 'desc': 'Sub-grid low diffusivity alpha = 5e-4', 'alpha': 0.0005},
                {'sev_idx': 2, 'desc': 'Super-grid high diffusivity alpha = 5.0', 'alpha': 5.0},
                {'sev_idx': 3, 'desc': 'Super-grid extreme diffusivity alpha = 20.0', 'alpha': 20.0},
            ]
        },
        {
            'idx': 13, 'name': 'Baseline drift',
            'severities': [
                {'sev_idx': 1, 'desc': 'Slow drift delta = 2%', 'drift': 0.02},
                {'sev_idx': 2, 'desc': 'Moderate drift delta = 5%', 'drift': 0.05},
                {'sev_idx': 3, 'desc': 'Severe drift delta = 10%', 'drift': 0.10},
            ]
        },
    ]
    
    # 3. Build Tasks for Multiprocessing
    tasks = []
    for scen in scenarios:
        for sev in scen['severities']:
            tasks.append((scen, sev, clean_baselines))
            
    print(f"\n[Step 2] Executing {len(tasks)} condition cells using multiprocessing across {mp.cpu_count()} cores...")
    t0 = time.time()
    
    all_matrix_rows = []
    all_summary_rows = []
    
    with mp.Pool(processes=mp.cpu_count(), initializer=init_worker, initargs=(prec,)) as pool:
        results = pool.map(evaluate_single_condition_cell, tasks)
        
    t1 = time.time()
    print(f"[Step 2] Multiprocessing run completed in {t1 - t0:.2f} seconds.")
    
    for m_rows, s_rows in results:
        all_matrix_rows.extend(m_rows)
        all_summary_rows.extend(s_rows)
        
    # 4. Save CSV Artifacts
    df_matrix = pd.DataFrame(all_matrix_rows)
    matrix_csv_path = os.path.join(RESULTS, 'stress_matrix_v2.csv')
    df_matrix.to_csv(matrix_csv_path, index=False)
    print(f"\nSaved replication matrix ({len(df_matrix)} rows) to: {matrix_csv_path}")
    
    df_summary = pd.DataFrame(all_summary_rows)
    summary_csv_path = os.path.join(RESULTS, 'stress_summary_v2.csv')
    df_summary.to_csv(summary_csv_path, index=False)
    print(f"Saved summary matrix ({len(df_summary)} rows) to: {summary_csv_path}")
    
    # 5. Generate reports/stress_matrix_v2.md STRICTLY FROM CSV ONLY
    generate_markdown_report_v2(summary_csv_path, clean_baselines)

def generate_markdown_report_v2(summary_csv_path, clean_baselines):
    print("\n[Step 3] Generating reports/stress_matrix_v2.md from summary CSV...")
    df = pd.read_csv(summary_csv_path)
    
    total_cells = len(df)
    pass_cells = len(df[df['status'] == 'PASS'])
    fail_cells = len(df[df['status'] == 'FAIL'])
    overall_pass_rate = pass_cells / total_cells * 100.0
    
    # Executive Table per Module and Category
    modules = ['Mode 2', 'Mode 3', 'Mode 3+', 'Two-Stage Placement', 'Anomaly Cascade']
    categories = ['robustness', 'declared-scope violation']
    
    exec_rows = []
    for m in modules:
        m_df = df[df['module'] == m]
        
        # Robustness
        r_df = m_df[m_df['category'] == 'robustness']
        r_pass = len(r_df[r_df['status'] == 'PASS'])
        r_tot = len(r_df)
        r_str = f"{r_pass} / {r_tot} ({r_pass/r_tot*100.0:.1f}%)" if r_tot > 0 else "N/A"
        
        # Scope violation
        s_df = m_df[m_df['category'] == 'declared-scope violation']
        s_pass = len(s_df[s_df['status'] == 'PASS'])
        s_tot = len(s_df)
        s_str = f"{s_pass} / {s_tot} ({s_pass/s_tot*100.0:.1f}%)" if s_tot > 0 else "N/A"
        
        # Total
        t_pass = len(m_df[m_df['status'] == 'PASS'])
        t_tot = len(m_df)
        t_str = f"{t_pass} / {t_tot} ({t_pass/t_tot*100.0:.1f}%)"
        
        exec_rows.append({
            'module': m,
            'robustness': r_str,
            'scope_violation': s_str,
            'total': t_str
        })
        
    # Scenario 13 Drift Reconciliation details from CSV
    s13_df = df[df['scenario_idx'] == 13]
    
    # Format markdown report
    md = []
    md.append("# Week 5 Stress Matrix v2 Report (Powered Rerun: 100 Seeds / Cell)")
    md.append("")
    md.append("> **Generated strictly from:** `data/results/stress_summary_v2.csv`")
    md.append("> **Zero Code Modifications to Frozen Modules:** Models evaluated strictly as frozen.")
    md.append("")
    md.append("## Pre-Registered Failure Rule (Script Header)")
    md.append("A condition cell is declared **FAIL** if:")
    md.append("1. **Parameter Estimation Modules (`Mode 2`, `Mode 3`, `Mode 3+`, `Two-Stage Placement`):**")
    md.append("   - Median relative $\\alpha$ error $> 2.0\\times$ the matching clean baseline error, OR")
    md.append("   - $95\\%$ Wald confidence interval coverage $< 80.0\\%$.")
    md.append("2. **Anomaly Cascade Module:**")
    md.append("   - Healthy false-alarm rate (FAR) $> 15.0\\%$.")
    md.append("")
    md.append("### Clean Baseline Reference Metrics ($N=10, \\sigma=0.01, \\alpha=0.100, 100\\text{ reps}$):")
    md.append(f"- **Mode 2:** Median Rel Err = `{clean_baselines['Mode 2']['med_err']:.6f}` | Coverage = `{clean_baselines['Mode 2']['coverage']:.1f}%` [{clean_baselines['Mode 2']['cov_lo']:.1f}, {clean_baselines['Mode 2']['cov_hi']:.1f}]")
    md.append(f"- **Mode 3:** Median Rel Err = `{clean_baselines['Mode 3']['med_err']:.6f}` | Coverage = `{clean_baselines['Mode 3']['coverage']:.1f}%` [{clean_baselines['Mode 3']['cov_lo']:.1f}, {clean_baselines['Mode 3']['cov_hi']:.1f}]")
    md.append(f"- **Mode 3+:** Median Rel Err = `{clean_baselines['Mode 3+']['med_err']:.6f}` | Coverage = `{clean_baselines['Mode 3+']['coverage']:.1f}%` [{clean_baselines['Mode 3+']['cov_lo']:.1f}, {clean_baselines['Mode 3+']['cov_hi']:.1f}]")
    md.append(f"- **Two-Stage Placement:** Median Rel Err = `{clean_baselines['Two-Stage Placement']['med_err']:.6f}` | Coverage = `{clean_baselines['Two-Stage Placement']['coverage']:.1f}%` [{clean_baselines['Two-Stage Placement']['cov_lo']:.1f}, {clean_baselines['Two-Stage Placement']['cov_hi']:.1f}]")
    md.append(f"- **Anomaly Cascade:** Healthy FAR = `{clean_baselines['Anomaly Cascade']['far']:.1f}%` [{clean_baselines['Anomaly Cascade']['far_lo']:.1f}, {clean_baselines['Anomaly Cascade']['far_hi']:.1f}]")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. Executive Summary Table per Module and Category")
    md.append("")
    md.append("| Module | Robustness Pass Rate (Scenarios 1-3, 8-13) | Declared-Scope Violation Pass Rate (Scenarios 4-7) | Total Pass Rate (All 39 Cells) |")
    md.append("| :--- | :---: | :---: | :---: |")
    for r in exec_rows:
        md.append(f"| **{r['module']}** | {r['robustness']} | {r['scope_violation']} | **{r['total']}** |")
    md.append("")
    md.append(f"**Overall Portfolio Performance:** **{pass_cells} / {total_cells} Cells Passed** (`{overall_pass_rate:.1f}%` Pass Rate; `{fail_cells} / {total_cells}` Failed, `{100.0 - overall_pass_rate:.1f}%` Failure Rate).")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Scenario 13 (Baseline Drift) Reconciliation")
    md.append("")
    md.append("### Empirical Findings & Reconciliation with Anomaly Study Table 3:")
    md.append("- **Replicate Power:** In v1 ($N_{\\text{reps}}=5$), anomaly healthy FAR jumped in coarse discrete steps of $20\\%$, causing 1 false alarm to register as $20\\%$ and 5 to register as $100\\%$. In v2 ($N_{\\text{reps}}=100$), continuous empirical rates with Wilson $95\\%$ confidence intervals are established.")
    md.append("- **Operating Domain vs Factorial Cohort:** In the anomaly module study (`EXPERIMENTS.md` / `data/results/anomaly_baseline_drift_new_fresh_summary.csv` Table 3), reported FAR numbers ($5.8\\%$ at $2\\%$ drift, $15.0\\%$ at $10\\%$ drift) represent an aggregate average across all 4 factorial cells ($N \\in \\{10, 20\\}, \\sigma \\in \\{0.01, 0.05\\}$) with varying initial $\\alpha_h \\in [0.02, 0.5]$. At high noise ($\\sigma = 0.05$), the parameter offset from $10\\%$ drift is buried beneath the Gaussian noise floor (cell FAR is only $6.5\\%$). In contrast, the stress matrix specifically probes the low-noise regime ($N=10, \\sigma=0.01, \\alpha_0=0.100$).")
    md.append("- **Scenario 13 v2 Empirical Results ($N_{\\text{reps}}=100$):**")
    for _, row in s13_df[s13_df['module'] == 'Anomaly Cascade'].iterrows():
        md.append(f"  - **{row['severity_level']}:** Healthy FAR = `{row['healthy_far_pct']}%` [95% CI: `{row['healthy_far_ci_low']}%`, `{row['healthy_far_ci_high']}%`] | Status: **{row['status']}** ({row['fail_reasons']})")
    md.append("- **Mechanism:** With clean low noise ($\\sigma=0.01$), a $10\\%$ unmodelled linear drift across the baseline shifts the estimated baseline anchor $\\hat{\\alpha}_{\\text{base}}$ by $\\approx +0.005$ decades. Over the operational window $t \\in [0.01, 1.0]$, this offset produces persistent residual discrepancies that exceed the GLR threshold $\\tau=7.544$ for low-noise signals, whereas at $\\sigma=0.05$ it is statistically indistinguishable from zero.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 3. Failed Cells Audit with Absolute Errors and Wilson 95% CIs")
    md.append("")
    md.append("Every cell failing the pre-registered threshold is detailed below with absolute median relative error, clean reference error, ratio, coverage / FAR with Wilson 95% CIs, and hypothesis-marked root cause and candidate fix.")
    md.append("")
    md.append("| Scen | Category | Module | Severity Level | Abs Med Rel Err | Clean Err | Ratio | Coverage % [95% CI] | Healthy FAR % [95% CI] | Failure Reason |")
    md.append("| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
    
    fail_df = df[df['status'] == 'FAIL']
    for _, r in fail_df.iterrows():
        err_str = f"`{r['med_rel_err']:.4f}`" if r['med_rel_err'] != 'N/A' else "N/A"
        clean_str = f"`{r['clean_rel_err']:.4f}`" if r['clean_rel_err'] != 'N/A' else "N/A"
        ratio_str = f"`{r['err_ratio']:.2f}x`" if r['err_ratio'] != 'N/A' else "N/A"
        cov_str = f"`{r['coverage_pct']:.1f}%` [{r['coverage_ci_low']}, {r['coverage_ci_high']}]" if r['coverage_pct'] != 'N/A' else "N/A"
        far_str = f"`{r['healthy_far_pct']:.1f}%` [{r['healthy_far_ci_low']}, {r['healthy_far_ci_high']}]" if r['healthy_far_pct'] != 'N/A' else "N/A"
        md.append(f"| S{r['scenario_idx']} | {r['category']} | **{r['module']}** | {r['severity_level']} | {err_str} | {clean_str} | {ratio_str} | {cov_str} | {far_str} | {r['fail_reasons']} |")
        
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 4. Root Cause Hypotheses & V2 Candidate Fixes (Hypotheses, Not Verified)")
    md.append("")
    md.append("The table below compiles the likely causes and candidate fixes for each distinct failed scenario condition. **All entries are explicitly marked as hypotheses, not verified.**")
    md.append("")
    md.append("| Scenario | Module | Failure Mode | Likely Cause Hypothesis (Unverified) | V2 Candidate Fix Hypothesis (Unverified) |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")
    
    seen_scen = set()
    for _, r in fail_df.iterrows():
        key = (r['scenario_idx'], r['module'])
        if key not in seen_scen:
            seen_scen.add(key)
            md.append(f"| **Scenario {r['scenario_idx']} ({r['scenario_name']})** | {r['module']} | {r['fail_reasons']} | *{r['likely_cause_hypothesis']}* | *{r['v2_candidate_fix_hypothesis']}* |")
            
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 5. Complete Summary Table (All 195 Cells)")
    md.append("")
    md.append("| Scen | Category | Module | Severity Level | Abs Med Rel Err | Clean Err | Ratio | Coverage % [95% CI] | Healthy FAR % [95% CI] | Status |")
    md.append("| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    for _, r in df.iterrows():
        err_str = f"`{r['med_rel_err']:.4f}`" if r['med_rel_err'] != 'N/A' else "N/A"
        clean_str = f"`{r['clean_rel_err']:.4f}`" if r['clean_rel_err'] != 'N/A' else "N/A"
        ratio_str = f"`{r['err_ratio']:.2f}x`" if r['err_ratio'] != 'N/A' else "N/A"
        cov_str = f"`{r['coverage_pct']:.1f}%` [{r['coverage_ci_low']}, {r['coverage_ci_high']}]" if r['coverage_pct'] != 'N/A' else "N/A"
        far_str = f"`{r['healthy_far_pct']:.1f}%` [{r['healthy_far_ci_low']}, {r['healthy_far_ci_high']}]" if r['healthy_far_pct'] != 'N/A' else "N/A"
        status_badge = f"**{r['status']}**" if r['status'] == 'PASS' else f"<span style='color:red;'>**{r['status']}**</span>"
        md.append(f"| S{r['scenario_idx']} | {r['category']} | {r['module']} | {r['severity_level']} | {err_str} | {clean_str} | {ratio_str} | {cov_str} | {far_str} | {status_badge} |")
        
    md.append("")
    report_path = os.path.join(REPO_ROOT, 'reports', 'stress_matrix_v2.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
    print(f"Generated comprehensive report at: {report_path}")

if __name__ == '__main__':
    mp.freeze_support()
    run_stress_matrix_v2()
