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
    """
    Computes distribution of Relative L2 error and discrete Relative PDE residual norm.
    u_pred: (M, N, N)
    u_true: (M, N, N)
    f_true: (M, N, N)
    """
    M, N, _ = u_pred.shape
    diff = u_pred - u_true
    u_true_norm = np.linalg.norm(u_true.reshape(M, -1), axis=1) + 1e-12
    l2_errors = np.linalg.norm(diff.reshape(M, -1), axis=1) / u_true_norm
    
    # Compute discrete Laplacian residual on interior points
    # -nabla_h^2 u = (4u - u_E - u_W - u_N - u_S) / h^2
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

def benchmark_timing(fno_model, linear_model, solver, N=64, n_trials=50):
    """
    Measure per-query CPU inference time (single & batch) for solver, FNO, and Linear baseline.
    """
    x = np.linspace(0, 1, N, dtype=np.float32)
    y = np.linspace(0, 1, N, dtype=np.float32)
    X, Y = np.meshgrid(x, y, indexing='ij')
    
    # Single sample source
    f_single = manufactured_source_2d(X, Y).astype(np.float32)
    f_batch = np.repeat(f_single[None, ...], 32, axis=0) # batch of 32
    
    # 1. Numerical Solver timing
    # Warmup
    _ = solver.solve(f_single)
    t0 = time.perf_counter()
    for _ in range(n_trials):
        _ = solver.solve(f_single)
    solver_single_ms = (time.perf_counter() - t0) / n_trials * 1000.0
    
    # 2. Linear baseline timing
    _ = linear_model.predict(f_single)
    t0 = time.perf_counter()
    for _ in range(n_trials):
        _ = linear_model.predict(f_single)
    lin_single_ms = (time.perf_counter() - t0) / n_trials * 1000.0
    
    _ = linear_model.predict(f_batch)
    t0 = time.perf_counter()
    for _ in range(n_trials):
        _ = linear_model.predict(f_batch)
    lin_batch_ms = (time.perf_counter() - t0) / (n_trials * 32) * 1000.0
    
    # 3. FNO timing (CPU)
    coords = torch.from_numpy(np.stack([X, Y], axis=0)).float()
    fno_in_single = torch.cat([torch.from_numpy(f_single).unsqueeze(0).unsqueeze(0), coords.unsqueeze(0)], dim=1)
    fno_in_batch = torch.cat([torch.from_numpy(f_batch).unsqueeze(1), coords.unsqueeze(0).repeat(32, 1, 1, 1)], dim=1)
    
    fno_model.eval()
    with torch.no_grad():
        _ = fno_model(fno_in_single)
        t0 = time.perf_counter()
        for _ in range(n_trials):
            _ = fno_model(fno_in_single)
        fno_single_ms = (time.perf_counter() - t0) / n_trials * 1000.0
        
        _ = fno_model(fno_in_batch)
        t0 = time.perf_counter()
        for _ in range(n_trials):
            _ = fno_model(fno_in_batch)
        fno_batch_ms = (time.perf_counter() - t0) / (n_trials * 32) * 1000.0
        
    return {
        "solver_single_ms": solver_single_ms,
        "fno_single_ms": fno_single_ms,
        "fno_batch_per_query_ms": fno_batch_ms,
        "linear_single_ms": lin_single_ms,
        "linear_batch_per_query_ms": lin_batch_ms
    }

def run_evaluation(
    data_dir="data",
    model_dir="models",
    fno_path="models/fno2d_poisson.pt",
    save_results_path="data/poisson_eval_results.json"
):
    print("--- Evaluating All Models & Splits ---")
    splits = load_all_splits(data_dir)
    N = splits["train"]["grid_x"].shape[0]
    h = 1.0 / (N - 1)
    solver = Poisson2DSolver(N=N)
    
    # 1. Fit Linear Baseline
    print("Fitting Linear Ridge Baseline (u = G f)...")
    lin_model = LinearPoissonBaseline()
    lin_model.fit(
        splits["train"]["F"],
        splits["train"]["U"],
        val_data=(splits["val"]["F"], splits["val"]["U"])
    )
    lin_model.save("models/linear_baseline_poisson.npz")
    print(f"Linear baseline fit in {lin_model.train_time:.3f}s (alpha_reg={lin_model.alpha_reg})")
    
    # 2. Load FNO2d
    print(f"Loading FNO2d from {fno_path}...")
    fno_model = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    if os.path.exists(fno_path):
        fno_model.load_state_dict(torch.load(fno_path, map_location="cpu"))
    else:
        print(f"Warning: FNO weights not found at {fno_path}, using initialized weights.")
    fno_model.eval()
    
    # Build coordinate grid for FNO input
    grid_x = splits["train"]["grid_x"]
    grid_y = splits["train"]["grid_y"]
    X, Y = np.meshgrid(grid_x, grid_y, indexing='ij')
    coords = torch.from_numpy(np.stack([X, Y], axis=0)).float() # (2, N, N)
    
    split_eval = {}
    table_rows = []
    
    for split_name, data in splits.items():
        F = data["F"] # (M, N, N)
        U = data["U"] # (M, N, N)
        M = len(F)
        
        # Predict Linear Baseline
        U_lin_pred = lin_model.predict(F)
        lin_metrics = compute_field_metrics(U_lin_pred, U, F, h)
        
        # Predict FNO2d
        F_tensor = torch.from_numpy(F).unsqueeze(1).float()
        coords_batch = coords.unsqueeze(0).repeat(M, 1, 1, 1)
        fno_in = torch.cat([F_tensor, coords_batch], dim=1)
        
        with torch.no_grad():
            # Batch forward pass
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
        
    # Sanity case: Manufactured solution
    manuf_data = np.load(os.path.join(data_dir, "poisson_manufactured_sanity.npz"))
    F_m = manuf_data["F"]
    U_exact = manuf_data["U_exact"]
    U_solv = manuf_data["U_solver"]
    
    # Solver sanity
    solv_diff = U_solv - U_exact
    solv_l2 = float(np.linalg.norm(solv_diff) / np.linalg.norm(U_exact))
    
    # Linear baseline on manufactured sanity
    U_lin_m = lin_model.predict(F_m)
    lin_m_l2 = float(np.linalg.norm(U_lin_m - U_exact) / np.linalg.norm(U_exact))
    
    # FNO on manufactured sanity
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
    
    # PINN baseline results
    pinn_summary_path = os.path.join(data_dir, "pinn_poisson_summary.json")
    if os.path.exists(pinn_summary_path):
        with open(pinn_summary_path) as f:
            pinn_metrics = json.load(f)
    else:
        pinn_metrics = {}
        
    # Timing benchmarks
    timing_metrics = benchmark_timing(fno_model, lin_model, solver, N=N)
    
    full_results = {
        "splits": split_eval,
        "table_rows": table_rows,
        "sanity_manufactured": sanity_metrics,
        "pinn_baseline": pinn_metrics,
        "timing": timing_metrics,
        "linear_fit_time_s": lin_model.train_time
    }
    
    with open(save_results_path, "w") as f:
        json.dump(full_results, f, indent=2)
        
    # Also save CSV table
    table_csv_path = "data/poisson_benchmark_table.csv"
    with open(table_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "split", "samples",
            "fno_l2_med", "fno_l2_p90", "fno_l2_max", "fno_res_med",
            "lin_l2_med", "lin_l2_p90", "lin_l2_max", "lin_res_med"
        ])
        writer.writeheader()
        writer.writerows(table_rows)
        
    print(f"Results saved to {save_results_path} and {table_csv_path}")
    return full_results

if __name__ == "__main__":
    run_evaluation()
