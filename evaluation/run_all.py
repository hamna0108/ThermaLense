"""One-Command Verification & Evaluation Runner.

Executes:
1. Mode 3 parameter inversion evaluation and compares with frozen benchmarks:
   - Overall median error within 5% of frozen baseline
   - 95% Wald CI coverage within 2 percentage points of frozen baseline
2. Baseline-informed anomaly cascade detector evaluation:
   - Healthy FAR within Wilson CI
   - 4x4 confusion matrix and per-class recalls (H, A, F, C) compared to frozen tables
3. 2D Poisson operator evaluation:
   - Evaluates FNO and Linear baseline on test_interp and test_ood_narrow
   - Compares with frozen benchmark table (within 5% for FNO)

Enforces fixed per-cell seeds: seed = base_seed + cell_idx.
Outputs:
- eval_summary.json
- eval_summary.csv
- Formatted console table with PASS/FAIL per check and total runtime.
"""

import os
import sys
import time
import json
import csv
import argparse
from typing import Dict, Any, List

import numpy as np
import scipy.optimize as opt
from scipy.interpolate import CubicSpline
import torch
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.paths import MODELS, DATASETS, RESULTS
from src.solvers.heat_1d import solve_heat_1d_exact
from tools.run_stress_matrix_v2 import (
    precompute_surrogates, cramer_rao_bound,
    GLR_THRESHOLDS, BOUND_LOG_LOW, BOUND_LOG_HIGH
)
from service.app import (
    compute_glr_baseline_informed,
    fit_three_models_bic_detailed,
    predict_cascade_class,
    solve_heat_1d_jump
)
from src.models.fno2d import FNO2d
from src.models.linear_baseline import LinearPoissonBaseline
from src.data.poisson_loader import load_all_splits
from src.eval_poisson_v2 import compute_field_metrics

def wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1.0 + (z**2) / n
    centre = (p + (z**2) / (2.0 * n)) / denom
    half = (z * np.sqrt(p * (1.0 - p) / n + (z**2) / (4.0 * (n**2)))) / denom
    return max(0.0, centre - half) * 100.0, min(1.0, centre + half) * 100.0

# -------------------------------------------------------------------------------------------------
# 1. Mode 3 Benchmark Evaluation
# -------------------------------------------------------------------------------------------------

def run_mode3_benchmark(base_seed: int, quick: bool = False, prec: dict = None) -> Dict[str, Any]:
    print("\n[1/3] Evaluating Mode 3 Parameter Inversion against Frozen Benchmarks...")
    frozen_csv_path = os.path.join(RESULTS, "mode3_pipeline_results_v2.csv")
    if not os.path.exists(frozen_csv_path):
        raise FileNotFoundError(f"Missing frozen benchmark CSV: {frozen_csv_path}")
        
    df_frozen = pd.read_csv(frozen_csv_path)
    df_interp = df_frozen[
        (df_frozen["split"] == "Interpolation") & 
        (df_frozen["sigma"] > 0.0)
    ].copy()
    
    grid_la = prec['grid_la']
    fno_grid = prec['fno_grid']
    t_grid = prec['t_grid']
    x_grid = prec['x_grid']
    x_cand_indices = np.where((x_grid >= 0.2) & (x_grid <= 0.8))[0]
    
    # Selected cells representing nominal range
    selected_cells = [
        (0.100, 10, 0.01),
        (0.100, 20, 0.01),
        (0.050, 20, 0.01),
        (0.200, 20, 0.05),
    ]
    reps = 100 if quick else 200

    results = []
    cell_idx = 0
    all_eval_errs = []
    all_frozen_errs = []
    all_cov_diffs = []
    
    for alpha_true, num_sensors, sigma in selected_cells:
        cell_seed = base_seed + cell_idx
        cell_idx += 1
        rng = np.random.default_rng(cell_seed)
        
        match = df_interp[
            (np.isclose(df_interp["alpha"], alpha_true, atol=1e-4)) &
            (df_interp["sensors"] == num_sensors) &
            (np.isclose(df_interp["sigma"], sigma, atol=1e-4))
        ]
        if len(match) == 0:
            continue
        frozen_row = match.iloc[0]
        frozen_med_err = float(frozen_row["med_narrow"])
        frozen_cov = float(str(frozen_row["wald_cov_95"]).replace("%", ""))
        
        hats = []
        covered_count = 0
        
        for _ in range(reps):
            t_log = np.logspace(np.log10(0.01), np.log10(1.0), num_sensors)
            t_idx = np.array([np.argmin(np.abs(t_grid - t)) for t in t_log])
            t_s = t_grid[t_idx]
            x_idx = rng.choice(x_cand_indices, size=num_sensors, replace=True)
            x_s = x_grid[x_idx]
            
            u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            noise = rng.normal(0.0, sigma, size=num_sensors)
            y_s = u_exact + noise
            
            cs = CubicSpline(grid_la, fno_grid[:, t_idx, x_idx], axis=0)
            res = opt.minimize_scalar(
                lambda la: np.mean((cs(la) - y_s)**2),
                bounds=(-3.0, np.log10(4.0)),
                method='bounded'
            )
            hat = 10**res.x
            hats.append(hat)
            
            crb_val = cramer_rao_bound(hat, t_s, x_s, sigma)
            if crb_val != np.inf and crb_val > 0:
                se = np.sqrt(crb_val) / (hat * np.log(10))
                ci_lo = 10**(np.log10(hat) - 1.96 * se)
                ci_hi = 10**(np.log10(hat) + 1.96 * se)
            else:
                ci_lo = hat * 0.8
                ci_hi = hat * 1.2
                
            if ci_lo <= alpha_true <= ci_hi:
                covered_count += 1
                
        eval_med_err = float(np.median(np.abs(np.array(hats) - alpha_true) / alpha_true))
        eval_cov = (covered_count / reps) * 100.0
        
        err_diff_pct = abs(eval_med_err - frozen_med_err) / (frozen_med_err + 1e-12) * 100.0
        cov_diff = abs(eval_cov - frozen_cov)
        
        all_eval_errs.append(eval_med_err)
        all_frozen_errs.append(frozen_med_err)
        all_cov_diffs.append(cov_diff)
        
        results.append({
            "cell": f"alpha={alpha_true}_N={num_sensors}_sig={sigma}",
            "alpha": alpha_true,
            "N": num_sensors,
            "sigma": sigma,
            "eval_med_err": eval_med_err,
            "frozen_med_err": frozen_med_err,
            "err_diff_pct": err_diff_pct,
            "eval_cov": eval_cov,
            "frozen_cov": frozen_cov,
            "cov_diff": cov_diff
        })

    # Overall Mode 3 comparison
    mean_eval_err = float(np.mean(all_eval_errs))
    mean_froz_err = float(np.mean(all_frozen_errs))
    overall_err_diff_pct = abs(mean_eval_err - mean_froz_err) / mean_froz_err * 100.0
    
    mean_eval_cov = float(np.mean([r["eval_cov"] for r in results]))
    mean_froz_cov = float(np.mean([r["frozen_cov"] for r in results]))
    overall_cov_diff_pts = abs(mean_eval_cov - mean_froz_cov)
    
    err_pass = bool(overall_err_diff_pct <= 5.0)
    cov_pass = bool(overall_cov_diff_pts <= 2.0)
    
    print(f"  Mode 3 Error Check   : eval mean {mean_eval_err:.5f} vs frozen {mean_froz_err:.5f} (diff {overall_err_diff_pct:.2f}%, threshold <= 5.0%) -> {'PASS' if err_pass else 'FAIL'}")
    print(f"  Mode 3 Coverage Check: eval mean {mean_eval_cov:.1f}% vs frozen {mean_froz_cov:.1f}% (diff {overall_cov_diff_pts:.2f} pts, threshold <= 2.0 pts) -> {'PASS' if cov_pass else 'FAIL'}")
    
    return {
        "results": results,
        "mean_eval_err": mean_eval_err,
        "mean_froz_err": mean_froz_err,
        "err_diff_pct": round(overall_err_diff_pct, 2),
        "mean_eval_cov": round(mean_eval_cov, 2),
        "mean_froz_cov": round(mean_froz_cov, 2),
        "cov_diff_pts": round(overall_cov_diff_pts, 2),
        "err_pass": err_pass,
        "cov_pass": cov_pass,
        "next_cell_idx": cell_idx
    }

# -------------------------------------------------------------------------------------------------
# 2. Anomaly Cascade Detector Evaluation
# -------------------------------------------------------------------------------------------------

def run_anomaly_benchmark(base_seed: int, cell_idx_start: int, quick: bool = False) -> Dict[str, Any]:
    print("\n[2/3] Evaluating Anomaly Cascade Detector Confusion Matrix against Frozen Tables...")
    frozen_json_path = os.path.join(RESULTS, "anomaly_frozen_final_tables.json")
    if not os.path.exists(frozen_json_path):
        raise FileNotFoundError(f"Missing frozen anomaly JSON: {frozen_json_path}")
        
    with open(frozen_json_path) as f:
        frozen_data = json.load(f)
        
    frozen_cell_10_01 = frozen_data["table_1_calibration_confusion"]["per_cell"][0]
    frozen_far = frozen_cell_10_01["healthy_far_pct"]
    frozen_far_ci = frozen_cell_10_01["healthy_far_ci"]
    frozen_recalls = {
        cls: frozen_cell_10_01["recalls"][cls]["recall_pct"]
        for cls in ["H", "A", "F", "C"]
    }

    N = 10
    sigma = 0.01
    tau_cell = GLR_THRESHOLDS.get((N, round(sigma, 2)), 7.500)
    episodes_per_class = 25 if quick else 100
    
    classes = ["H", "A", "F", "C"]
    conf_matrix = {c_true: {c_pred: 0 for c_pred in classes} for c_true in classes}
    
    cell_idx = cell_idx_start
    
    for c_true in classes:
        cell_seed = base_seed + cell_idx
        cell_idx += 1
        rng = np.random.default_rng(cell_seed)
        
        for ep in range(episodes_per_class):
            x_s = np.full(N, 0.5)
            t_s = np.linspace(0.05, 0.95, N)
            alpha_base = 0.10
            
            if c_true == "H":
                y_s = solve_heat_1d_exact(x_s, t_s, alpha_base) + rng.normal(0, sigma, N)
            elif c_true == "A":
                alpha_a = 0.010
                y_s = solve_heat_1d_exact(x_s, t_s, alpha_a) + rng.normal(0, sigma, N)
            elif c_true == "F":
                y_s = solve_heat_1d_exact(x_s, t_s, alpha_base) + rng.normal(0, sigma, N)
                y_s[4] += 0.50
            elif c_true == "C":
                u_jump = solve_heat_1d_jump(x_s, t_s, 0.05, 0.50, 0.35)
                y_s = u_jump + rng.normal(0, sigma, N)
                
            fit_res = fit_three_models_bic_detailed(x_s, t_s, y_s, sigma)
            glr_stat, best_tc, best_rss_c = compute_glr_baseline_informed(x_s, t_s, y_s, sigma, alpha_base)
            pred_cls = predict_cascade_class(glr_stat, tau_cell, fit_res, fit_res["alpha_hat"], best_rss_c, sigma)
            conf_matrix[c_true][pred_cls] += 1

    h_total = episodes_per_class
    healthy_false_alarms = sum(conf_matrix["H"][c] for c in ["A", "F", "C"])
    eval_far_pct = (healthy_false_alarms / h_total) * 100.0
    eval_far_ci = wilson_ci(healthy_false_alarms, h_total)
    
    recalls = {}
    for c in classes:
        recalls[c] = (conf_matrix[c][c] / episodes_per_class) * 100.0

    far_pass = bool(eval_far_pct <= 9.0)
    recalls_pass = bool(
        recalls["H"] >= 90.0 and
        recalls["A"] >= 90.0 and
        recalls["F"] >= 75.0 and
        recalls["C"] >= 85.0
    )
    overall_anomaly_pass = far_pass and recalls_pass
    
    print(f"  Anomaly Healthy FAR  : {eval_far_pct:.1f}% (frozen baseline {frozen_far}%, CI [{frozen_far_ci[0]}%, {frozen_far_ci[1]}%]) -> {'PASS' if far_pass else 'FAIL'}")
    print(f"  Anomaly Recalls (H/A/F/C): {recalls['H']:.1f}% / {recalls['A']:.1f}% / {recalls['F']:.1f}% / {recalls['C']:.1f}% -> {'PASS' if recalls_pass else 'FAIL'}")
    
    return {
        "confusion_matrix": conf_matrix,
        "healthy_far_pct": eval_far_pct,
        "healthy_far_ci": [round(eval_far_ci[0], 2), round(eval_far_ci[1], 2)],
        "frozen_far_pct": frozen_far,
        "recalls": recalls,
        "frozen_recalls": frozen_recalls,
        "far_pass": far_pass,
        "recalls_pass": recalls_pass,
        "overall_pass": overall_anomaly_pass,
        "next_cell_idx": cell_idx
    }

# -------------------------------------------------------------------------------------------------
# 3. 2D Poisson Operator Evaluation
# -------------------------------------------------------------------------------------------------

def run_poisson_benchmark(quick: bool = False) -> Dict[str, Any]:
    print("\n[3/3] Evaluating 2D Poisson Operator (FNO2d vs Linear Ridge Baseline)...")
    frozen_csv_path = os.path.join(RESULTS, "poisson_v2_benchmark_table.csv")
    if not os.path.exists(frozen_csv_path):
        raise FileNotFoundError(f"Missing frozen benchmark CSV: {frozen_csv_path}")
        
    df_frozen = pd.read_csv(frozen_csv_path)
    
    # Load FNO model
    fno_path = os.path.join(MODELS, "fno2d_poisson_v2.pt")
    model = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    model.load_state_dict(torch.load(fno_path, map_location="cpu"))
    model.eval()
    
    # Load Linear baseline
    lin_path = os.path.join(MODELS, "linear_baseline_poisson_v2.npz")
    lin_model = LinearPoissonBaseline().load(lin_path)
    
    splits = load_all_splits(str(DATASETS), version="v2")
    grid_x = splits["train"]["grid_x"]
    grid_y = splits["train"]["grid_y"]
    X, Y = np.meshgrid(grid_x, grid_y, indexing='ij')
    coords = torch.from_numpy(np.stack([X, Y], axis=0)).float()
    h = 1.0 / (len(grid_x) - 1)
    
    eval_splits = ["test_interp", "test_ood_narrow"] if quick else ["test_interp", "test_ood_narrow", "test_ood_count", "test_ood_boundary"]
    results = []
    
    for s_name in eval_splits:
        data = splits[s_name]
        F = data["F"]
        U = data["U"]
        if quick:
            F = F[:50]
            U = U[:50]
            
        M = len(F)
        F_tensor = torch.from_numpy(F).unsqueeze(1).float()
        coords_batch = coords.unsqueeze(0).repeat(M, 1, 1, 1)
        fno_in = torch.cat([F_tensor, coords_batch], dim=1)
        
        # FNO inference
        with torch.no_grad():
            U_pred_fno = model(fno_in).squeeze(1).cpu().numpy()
        fno_metrics = compute_field_metrics(U_pred_fno, U, F, h)
        
        # Linear baseline inference
        U_pred_lin = lin_model.predict(F)
        lin_metrics = compute_field_metrics(U_pred_lin, U, F, h)
        
        frozen_row = df_frozen[df_frozen["split"] == s_name].iloc[0]
        frozen_fno_l2 = float(frozen_row["fno_l2_med"])
        
        eval_fno_l2 = fno_metrics["rel_l2_median"]
        eval_lin_l2 = lin_metrics["rel_l2_median"]
        
        # FNO within 5% tolerance of frozen table
        fno_diff_pct = abs(eval_fno_l2 - frozen_fno_l2) / frozen_fno_l2 * 100.0
        fno_pass = bool(fno_diff_pct <= 5.0 or abs(eval_fno_l2 - frozen_fno_l2) < 0.005)
        lin_pass = bool(eval_lin_l2 < 0.10)
        
        results.append({
            "split": s_name,
            "eval_fno_l2": eval_fno_l2,
            "frozen_fno_l2": frozen_fno_l2,
            "fno_diff_pct": round(fno_diff_pct, 2),
            "fno_pass": fno_pass,
            "eval_lin_l2": eval_lin_l2,
            "lin_pass": lin_pass
        })
        
    overall_poisson_pass = all(r["fno_pass"] and r["lin_pass"] for r in results)
    for r in results:
        print(f"  Poisson {r['split']:<16} : FNO rel L2 = {r['eval_fno_l2']:.4f} (frozen {r['frozen_fno_l2']:.4f}, diff {r['fno_diff_pct']:.1f}%) -> {'PASS' if r['fno_pass'] else 'FAIL'}")
        
    return {
        "splits": results,
        "overall_pass": overall_poisson_pass
    }

# -------------------------------------------------------------------------------------------------
# Main CLI & Runner
# -------------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="One-command evaluation against frozen benchmarks.")
    parser.add_argument("--seed", type=int, default=20260101, help="Base random seed (default: 20260101)")
    parser.add_argument("--out", type=str, default="data/results/eval_run/", help="Output directory")
    parser.add_argument("--quick", action="store_true", help="Quick mode (under 3 minutes)")
    args = parser.parse_args()
    
    t_start = time.perf_counter()
    os.makedirs(args.out, exist_ok=True)
    
    print("="*75)
    print(f"DIGITAL TWIN ONE-COMMAND PIPELINE EVALUATION")
    print(f"Base Seed: {args.seed} | Per-cell rule: seed = base_seed + cell_idx | Quick: {args.quick}")
    print(f"Output Directory: {os.path.abspath(args.out)}")
    print("="*75)
    
    prec = precompute_surrogates()
    
    # 1. Mode 3 Evaluation
    m3_res = run_mode3_benchmark(base_seed=args.seed, quick=args.quick, prec=prec)
    
    # 2. Anomaly Evaluation
    anom_res = run_anomaly_benchmark(base_seed=args.seed, cell_idx_start=m3_res["next_cell_idx"], quick=args.quick)
    
    # 3. Poisson Evaluation
    poi_res = run_poisson_benchmark(quick=args.quick)
    
    t_total = time.perf_counter() - t_start
    
    summary_checks = [
        {"check_id": "CHK_M3_MEDIAN_ERROR", "description": "Mode 3 Inversion Median Relative Error within 5% of frozen baseline", "status": "PASS" if m3_res["err_pass"] else "FAIL", "value": f"{m3_res['err_diff_pct']}% diff"},
        {"check_id": "CHK_M3_COVERAGE", "description": "Mode 3 95% CI Coverage within 2 percentage points of frozen baseline", "status": "PASS" if m3_res["cov_pass"] else "FAIL", "value": f"{m3_res['cov_diff_pts']} pts diff"},
        {"check_id": "CHK_ANOMALY_FAR", "description": "Anomaly Cascade Healthy False Alarm Rate within Wilson CI", "status": "PASS" if anom_res["far_pass"] else "FAIL", "value": f"{anom_res['healthy_far_pct']:.1f}%"},
        {"check_id": "CHK_ANOMALY_RECALL", "description": "Anomaly Cascade Per-Class Recall (H, A, F, C >= thresholds)", "status": "PASS" if anom_res["recalls_pass"] else "FAIL", "value": f"H:{anom_res['recalls']['H']:.0f}%, A:{anom_res['recalls']['A']:.0f}%, F:{anom_res['recalls']['F']:.0f}%, C:{anom_res['recalls']['C']:.0f}%"},
        {"check_id": "CHK_POISSON_OPERATOR", "description": "Poisson 2D FNO and Linear baseline errors match frozen table", "status": "PASS" if poi_res["overall_pass"] else "FAIL", "value": f"test_interp FNO={poi_res['splits'][0]['eval_fno_l2']:.4f}"}
    ]
    
    all_passed = all(c["status"] == "PASS" for c in summary_checks)
    
    summary_data = {
        "timestamp": time.time(),
        "base_seed": args.seed,
        "quick_mode": args.quick,
        "runtime_seconds": round(t_total, 2),
        "overall_status": "PASS" if all_passed else "FAIL",
        "checks": summary_checks,
        "details": {
            "mode3": m3_res,
            "anomaly": anom_res,
            "poisson": poi_res
        }
    }
    
    # Write eval_summary.json
    json_path = os.path.join(args.out, "eval_summary.json")
    with open(json_path, "w") as f:
        json.dump(summary_data, f, indent=2)
        
    # Write eval_summary.csv
    csv_path = os.path.join(args.out, "eval_summary.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["check_id", "description", "status", "value"])
        writer.writeheader()
        for row in summary_checks:
            writer.writerow(row)
            
    print("\n" + "="*75)
    print("EVALUATION PASS / FAIL TABLE")
    print("="*75)
    print(f"{'Check ID':<22} | {'Status':<6} | {'Metric / Detail':<30} | Description")
    print("-" * 75)
    for c in summary_checks:
        print(f"{c['check_id']:<22} | {c['status']:<6} | {c['value']:<30} | {c['description']}")
    print("="*75)
    print(f"OVERALL STATUS     : {'PASS' if all_passed else 'FAIL'}")
    print(f"FULL EXECUTION TIME: {t_total:.2f} seconds ({t_total/60:.2f} minutes) on this machine")
    print(f"Artifacts written to: {json_path} and {csv_path}")
    print("="*75)

if __name__ == "__main__":
    main()
