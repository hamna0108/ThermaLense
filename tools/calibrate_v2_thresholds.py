"""Pre-Calibration of V2 Thresholds on Disjoint Seed Range (1300000+).

Written and executed BEFORE evaluating on the matrix seeds (1200000..1213399).
Strictly enforces zero data-snooping discipline.

Calibrates:
1. Goodness-of-fit gate threshold tau_gof for <= 5% false-flag rate on healthy runs.
2. Sigma estimator performance on k=20 baseline windows.
"""

import os
import sys
import json
import numpy as np
import scipy.stats as stats

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.paths import RESULTS
from src.solvers.heat_1d import solve_heat_1d_exact
from src.v2.sigma_estimator import estimate_sigma_from_baseline
from tools.run_stress_matrix_v2 import precompute_surrogates, evaluate_mode2

def run_calibration():
    print("=" * 90)
    print("CALIBRATING V2 THRESHOLDS ON SEPARATE SEED RANGE (1300000+)")
    print("=" * 90)
    
    prec = precompute_surrogates()
    
    num_cal_reps = 1000
    base_cal_seed = 1300000
    
    chi2_dof_samples_m2 = []
    sigma_est_samples = []
    
    alpha_nom = 0.100
    sigma_nom = 0.01
    N_sensors = 10
    
    print(f"Sampling {num_cal_reps} healthy episodes on seeds {base_cal_seed}..{base_cal_seed + num_cal_reps - 1}...")
    
    for i in range(num_cal_reps):
        seed = base_cal_seed + i
        rng = np.random.RandomState(seed)
        
        # 1. Healthy sensor readings
        t_s = np.logspace(np.log10(0.01), 0, N_sensors)
        x_s = rng.uniform(0.2, 0.8, N_sensors)
        y_exact = solve_heat_1d_exact(x_s, t_s, alpha_nom)
        noise = rng.normal(0, sigma_nom, N_sensors)
        y_s = y_exact + noise
        
        # 2. Mode 2 fit
        h2, e2, c2 = evaluate_mode2(x_s, t_s, y_s, sigma_nom, alpha_nom, prec)
        
        # Residuals and reduced chi2
        pred_m2 = solve_heat_1d_exact(x_s, t_s, h2)
        rss = np.sum((y_s - pred_m2)**2)
        dof = N_sensors - 1
        chi2_dof = rss / (dof * (sigma_nom**2))
        chi2_dof_samples_m2.append(chi2_dof)
        
        # 3. Baseline readings (k=20)
        tb = np.linspace(0.01, 0.5, 20)
        xb = rng.uniform(0.2, 0.8, 20)
        yb = solve_heat_1d_exact(xb, tb, alpha_nom) + rng.normal(0, sigma_nom, 20)
        sig_res = estimate_sigma_from_baseline(xb, tb, yb, min_readings=20)
        sigma_est_samples.append(sig_res['sigma_hat'])
        
    chi2_arr = np.array(chi2_dof_samples_m2)
    sig_arr = np.array(sigma_est_samples)
    
    p90 = float(np.percentile(chi2_arr, 90))
    p95 = float(np.percentile(chi2_arr, 95))
    p99 = float(np.percentile(chi2_arr, 99))
    
    # Target: <= 5% false flags on healthy runs -> set threshold at p95
    tau_gof_calibrated = round(p95, 3)
    false_flag_rate_cal = float(np.mean(chi2_arr > tau_gof_calibrated) * 100.0)
    
    mean_sig = float(np.mean(sig_arr))
    std_sig = float(np.std(sig_arr))
    
    print("\n--- Calibration Results ---")
    print(f"Goodness-of-Fit chi2/dof Distribution on Healthy Runs:")
    print(f"  Mean: {np.mean(chi2_arr):.4f} (theoretical dof mean = 1.000)")
    print(f"  Std:  {np.std(chi2_arr):.4f}")
    print(f"  90th percentile: {p90:.4f}")
    print(f"  95th percentile: {p95:.4f}")
    print(f"  99th percentile: {p99:.4f}")
    print(f"Selected Calibrated Threshold tau_gof: {tau_gof_calibrated}")
    print(f"Calibrated Healthy False-Flag Rate:    {false_flag_rate_cal:.2f}% (Target: <= 5.0%)")
    
    print(f"\nBaseline Sigma Estimator (true sigma = {sigma_nom}):")
    print(f"  Mean estimated sigma: {mean_sig:.6f}")
    print(f"  Std estimated sigma:  {std_sig:.6f}")
    print(f"  Relative Bias:        {abs(mean_sig - sigma_nom)/sigma_nom * 100:.2f}%")
    
    cal_record = {
        'seed_range_description': '1300000..1300999 (1000 healthy episodes)',
        'base_seed': base_cal_seed,
        'num_reps': num_cal_reps,
        'nominal_parameters': {'alpha': alpha_nom, 'sigma': sigma_nom, 'N': N_sensors, 'baseline_k': 20},
        'tau_gof_calibrated': tau_gof_calibrated,
        'tau_gof_p95': p95,
        'tau_gof_p90': p90,
        'tau_gof_p99': p99,
        'healthy_false_flag_rate_pct': false_flag_rate_cal,
        'baseline_sigma_mean': mean_sig,
        'baseline_sigma_std': std_sig,
        'baseline_sigma_bias_pct': abs(mean_sig - sigma_nom)/sigma_nom * 100
    }
    
    out_json = os.path.join(RESULTS, 'v2_calibration_record.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(cal_record, f, indent=2)
    print(f"\nSaved calibration record to: {out_json}")
    return cal_record

if __name__ == '__main__':
    run_calibration()
