import os
import sys
import time
import json
import csv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import torch
from src.solvers.poisson_2d import Poisson2DSolver, manufactured_source_2d, solve_poisson_2d_exact
from src.models.fno2d import FNO2d
from src.models.linear_baseline import LinearPoissonBaseline
from src.data.poisson_loader import load_all_splits

def compute_field_metrics(u_pred, u_true, f_true, h):
    M, N, _ = u_pred.shape
    diff = u_pred - u_true
    u_true_norm = np.linalg.norm(u_true.reshape(M, -1), axis=1) + 1e-12
    l2_errors = np.linalg.norm(diff.reshape(M, -1), axis=1) / u_true_norm
    
    # Discrete Laplacian residual
    u_int = u_pred[:, 1:-1, 1:-1]
    lap_u = (
        -4.0 * u_int
        + u_pred[:, 2:, 1:-1]
        + u_pred[:, :-2, 1:-1]
        + u_pred[:, 1:-1, 2:]
        + u_pred[:, 1:-1, :-2]
    ) / (h**2)
    neg_lap = -lap_u
    
    f_int = f_true[:, 1:-1, 1:-1]
    res = neg_lap - f_int
    f_int_norm = np.linalg.norm(f_int.reshape(M, -1), axis=1) + 1e-12
    res_errors = np.linalg.norm(res.reshape(M, -1), axis=1) / f_int_norm
    
    return {
        "rel_l2_median": float(np.median(l2_errors)),
        "rel_l2_p90": float(np.percentile(l2_errors, 90)),
        "rel_l2_max": float(np.max(l2_errors)),
        "res_median": float(np.median(res_errors)),
        "res_p90": float(np.percentile(res_errors, 90)),
        "res_max": float(np.max(res_errors)),
        "all_l2": l2_errors.tolist()
    }

def build_stress_matrix_cases(solver):
    """
    Construct at least 10 diverse, quantifiable stress / adversarial / out-of-distribution failure cases.
    """
    X, Y = solver.X, solver.Y
    cases = []
    
    # FC1: Ultra-narrow source (w = 0.03)
    f1 = 1.5 * np.exp(-((X - 0.5)**2 + (Y - 0.5)**2) / (2.0 * 0.03**2))
    cases.append(("FC01_ultra_narrow_w0.03", f1, "Spatial width w=0.03 (spectral cutoff limit)"))
    
    # FC2: Very high mode sine (m=8, n=8)
    f2 = 1.0 * (8**2 + 8**2) * (np.pi**2) * np.sin(8 * np.pi * X) * np.sin(8 * np.pi * Y)
    cases.append(("FC02_high_mode_8x8", f2, "Sine mode (8,8) exceeding modes 12 cutoff"))
    
    # FC3: Extreme boundary edge source (cx=0.03)
    f3 = 1.5 * np.exp(-((X - 0.03)**2 + (Y - 0.5)**2) / (2.0 * 0.10**2))
    cases.append(("FC03_edge_source_x0.03", f3, "Center at x=0.03 (boundary layer truncation)"))
    
    # FC4: Corner source (cx=0.04, cy=0.04)
    f4 = 1.5 * np.exp(-((X - 0.04)**2 + (Y - 0.04)**2) / (2.0 * 0.09**2))
    cases.append(("FC04_corner_source", f4, "Center at (0.04, 0.04) against two zero boundaries"))
    
    # FC5: High source density (8 Gaussians)
    rng5 = np.random.default_rng(99001)
    f5 = np.zeros_like(X)
    for _ in range(8):
        f5 += rng5.uniform(0.5, 1.5) * np.exp(-((X - rng5.uniform(0.2, 0.8))**2 + (Y - rng5.uniform(0.2, 0.8))**2) / (2.0 * 0.09**2))
    cases.append(("FC05_high_density_8_sources", f5, "8 overlapping Gaussians (energy saturation)"))
    
    # FC6: Dipole cancellation (+/- peaks near each other)
    f6 = 2.0 * np.exp(-((X - 0.46)**2 + (Y - 0.5)**2) / (2.0 * 0.08**2)) - 2.0 * np.exp(-((X - 0.54)**2 + (Y - 0.5)**2) / (2.0 * 0.08**2))
    cases.append(("FC06_dipole_cancellation", f6, "Opposite sign dipole (+2/-2) near cancellation"))
    
    # FC7: Amplitude out-of-distribution (A = 25.0)
    f7 = 25.0 * np.exp(-((X - 0.5)**2 + (Y - 0.5)**2) / (2.0 * 0.12**2))
    cases.append(("FC07_extreme_amplitude_25x", f7, "Amplitude A=25.0 (12.5x above training range)"))
    
    # FC8: Discontinuous cylinder / step source
    r_disc = np.sqrt((X - 0.5)**2 + (Y - 0.5)**2)
    f8 = np.where(r_disc <= 0.15, 2.0, 0.0)
    cases.append(("FC08_discontinuous_step_disk", f8, "Discontinuous step disk (Gibbs ringing)"))
    
    # FC9: Gaussian source + 20% high-frequency noise
    rng9 = np.random.default_rng(99002)
    clean_f = 1.5 * np.exp(-((X - 0.5)**2 + (Y - 0.5)**2) / (2.0 * 0.12**2))
    f9 = clean_f + rng9.normal(0.0, 0.2 * np.max(clean_f), size=clean_f.shape)
    cases.append(("FC09_source_with_20pct_noise", f9, "Source with 20% additive Gaussian noise"))
    
    # FC10: Point-like impulse (w = 0.018)
    f10 = 10.0 * np.exp(-((X - 0.5)**2 + (Y - 0.5)**2) / (2.0 * 0.018**2))
    cases.append(("FC10_point_impulse_w0.018", f10, "Narrow impulse w=0.018 (Dirac delta proxy)"))
    
    # FC11: Anisotropic elliptic source (aspect ratio 4:1)
    f11 = 1.5 * np.exp(-((X - 0.5)**2 / (2.0 * 0.04**2) + (Y - 0.5)**2 / (2.0 * 0.16**2)))
    cases.append(("FC11_anisotropic_ellipse_4to1", f11, "Anisotropic ellipse sigma_x=0.04, sigma_y=0.16"))
    
    # FC12: Ultra-high mode sine (m=10, n=10)
    f12 = 0.5 * (10**2 + 10**2) * (np.pi**2) * np.sin(10 * np.pi * X) * np.sin(10 * np.pi * Y)
    cases.append(("FC12_ultra_mode_10x10", f12, "Sine mode (10,10) far above all training modes"))
    
    return cases

def run_evaluation_v2(
    data_dir="data",
    fno_path="models/fno2d_poisson_v2.pt",
    save_results_path="data/poisson_v2_eval_results.json"
):
    print("--- Evaluating Stage 2 Round 2 Models on Dataset v2 ---")
    splits = load_all_splits(data_dir, version="v2")
    N = splits["train"]["grid_x"].shape[0]
    h = 1.0 / (N - 1)
    solver = Poisson2DSolver(N=N)
    
    # 1. Fit Linear Baseline on v2 train
    print("Fitting Linear Ridge Baseline on v2 train (u = G f)...")
    lin_model = LinearPoissonBaseline(alpha_reg=1e-8)
    lin_model.fit(
        splits["train"]["F"],
        splits["train"]["U"],
        val_data=(splits["val"]["F"], splits["val"]["U"])
    )
    lin_model.save("models/linear_baseline_poisson_v2.npz")
    print(f"Linear baseline fit in {lin_model.train_time:.3f}s (alpha_reg={lin_model.alpha_reg})")
    
    # 2. Load FNO2d v2
    fno_model = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    if os.path.exists(fno_path):
        fno_model.load_state_dict(torch.load(fno_path, map_location="cpu"))
        print(f"Loaded trained FNO2d from {fno_path}")
    else:
        print(f"Warning: {fno_path} not found, checking fallback...")
        if os.path.exists("models/fno2d_poisson.pt"):
            fno_model.load_state_dict(torch.load("models/fno2d_poisson.pt", map_location="cpu"))
    fno_model.eval()
    
    grid_x = splits["train"]["grid_x"]
    grid_y = splits["train"]["grid_y"]
    X, Y = np.meshgrid(grid_x, grid_y, indexing='ij')
    coords = torch.from_numpy(np.stack([X, Y], axis=0)).float()
    
    split_eval = {}
    table_rows = []
    
    for split_name, data in splits.items():
        F = data["F"]
        U = data["U"]
        M = len(F)
        
        # Predict Linear Baseline
        U_lin_pred = lin_model.predict(F)
        lin_metrics = compute_field_metrics(U_lin_pred, U, F, h)
        
        # Predict FNO2d
        F_tensor = torch.from_numpy(F).unsqueeze(1).float()
        coords_batch = coords.unsqueeze(0).repeat(M, 1, 1, 1)
        fno_in = torch.cat([F_tensor, coords_batch], dim=1)
        
        with torch.no_grad():
            U_fno_pred = []
            batch_sz = 32
            for b in range(0, M, batch_sz):
                out = fno_model(fno_in[b:b+batch_sz])
                U_fno_pred.append(out.squeeze(1).cpu().numpy())
            U_fno_pred = np.concatenate(U_fno_pred, axis=0)
            
        fno_metrics = compute_field_metrics(U_fno_pred, U, F, h)
        
        split_eval[split_name] = {
            "num_samples": M,
            "seed_range": [int(data["seeds"][0]), int(data["seeds"][-1])],
            "fno": fno_metrics,
            "linear": lin_metrics
        }
        
        table_rows.append({
            "split": split_name,
            "samples": M,
            "fno_l2_med": fno_metrics["rel_l2_median"],
            "fno_l2_p90": fno_metrics["rel_l2_p90"],
            "fno_l2_max": fno_metrics["rel_l2_max"],
            "fno_res_med": fno_metrics["res_median"],
            "lin_l2_med": lin_metrics["rel_l2_median"],
            "lin_l2_p90": lin_metrics["rel_l2_p90"],
            "lin_l2_max": lin_metrics["rel_l2_max"],
            "lin_res_med": lin_metrics["res_median"]
        })
        
    # Manufactured Sanity Case
    manuf_data = np.load(os.path.join(data_dir, "poisson_v2_manufactured_sanity.npz"))
    F_m = manuf_data["F"]
    U_exact = manuf_data["U_exact"]
    U_solv = manuf_data["U_solver"]
    
    solv_l2 = float(np.linalg.norm(U_solv - U_exact) / np.linalg.norm(U_exact))
    U_lin_m = lin_model.predict(F_m)
    lin_m_l2 = float(np.linalg.norm(U_lin_m - U_exact) / np.linalg.norm(U_exact))
    
    coords_m = coords.unsqueeze(0)
    fno_in_m = torch.cat([torch.from_numpy(F_m).unsqueeze(1), coords_m], dim=1)
    with torch.no_grad():
        U_fno_m = fno_model(fno_in_m).squeeze(1).cpu().numpy()
    fno_m_l2 = float(np.linalg.norm(U_fno_m - U_exact) / np.linalg.norm(U_exact))
    
    sanity_metrics = {
        "solver_vs_exact_rel_l2": solv_l2,
        "linear_vs_exact_rel_l2": lin_m_l2,
        "fno_vs_exact_rel_l2": fno_m_l2
    }
    
    # 3. Evaluate Stress Matrix Failure Cases (12 distinct failure cases)
    print("Evaluating Stress Matrix (12 structured failure cases)...")
    stress_cases = build_stress_matrix_cases(solver)
    stress_results = []
    
    for case_id, f_case, description in stress_cases:
        # Ground truth from solver
        u_gt = solver.solve(f_case)
        
        # Linear prediction
        u_lin = lin_model.predict(f_case)
        diff_lin = u_lin - u_gt
        lin_l2 = float(np.linalg.norm(diff_lin) / (np.linalg.norm(u_gt) + 1e-12))
        
        # FNO prediction
        f_tens = torch.from_numpy(f_case).unsqueeze(0).unsqueeze(0).float()
        fno_in = torch.cat([f_tens, coords.unsqueeze(0)], dim=1)
        with torch.no_grad():
            u_fno = fno_model(fno_in).squeeze().cpu().numpy()
        diff_fno = u_fno - u_gt
        fno_l2 = float(np.linalg.norm(diff_fno) / (np.linalg.norm(u_gt) + 1e-12))
        
        # PDE residual of FNO prediction
        r_rel, r_max = solver.compute_residual(u_fno, f_case)
        
        stress_results.append({
            "case_id": case_id,
            "description": description,
            "fno_rel_l2": fno_l2,
            "lin_rel_l2": lin_l2,
            "pde_residual_rel": r_rel,
            "fno_failure_flag": bool(fno_l2 > 0.05 or r_rel > 1.0)
        })
        
    full_output = {
        "splits": split_eval,
        "table_rows": table_rows,
        "sanity_manufactured": sanity_metrics,
        "stress_matrix": stress_results,
        "linear_fit_time_s": lin_model.train_time
    }
    
    with open(save_results_path, "w") as f:
        json.dump(full_output, f, indent=2)
        
    # Save CSV table
    with open("data/poisson_v2_benchmark_table.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "split", "samples",
            "fno_l2_med", "fno_l2_p90", "fno_l2_max", "fno_res_med",
            "lin_l2_med", "lin_l2_p90", "lin_l2_max", "lin_res_med"
        ])
        writer.writeheader()
        writer.writerows(table_rows)
        
    print(f"Saved evaluation results to {save_results_path}")
    return full_output

if __name__ == "__main__":
    run_evaluation_v2()
