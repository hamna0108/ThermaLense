import os
import sys
import time
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import torch
from src.solvers.poisson_2d import Poisson2DSolver, manufactured_source_2d
from src.models.fno2d import FNO2d
from src.models.linear_baseline import LinearPoissonBaseline

try:
    from paths import DATASETS, RESULTS, MODELS
except ImportError:
    from src.paths import DATASETS, RESULTS, MODELS

def benchmark_fresh_factorization_single(N=64, n_trials=30):
    """
    Measures the cost of solving -nabla^2 u = f with fresh matrix construction and fresh sparse LU factorization per query.
    """
    solver_ref = Poisson2DSolver(N=N)
    f_single = manufactured_source_2d(solver_ref.X, solver_ref.Y)
    b = f_single[1:-1, 1:-1].flatten()
    
    dx = 1.0 / (N - 1)
    dy = dx
    nx_int = N - 2
    ny_int = N - 2
    n_int = nx_int * ny_int
    cx = -1.0 / dx**2
    cy = -1.0 / dy**2
    cc = 2.0 / dx**2 + 2.0 / dy**2
    
    t0 = time.perf_counter()
    for _ in range(n_trials):
        # 1. Build matrix A from scratch
        main_diag = np.full(n_int, cc)
        off_diag_y = np.full(n_int - 1, cy)
        off_diag_y[ny_int - 1::ny_int] = 0.0
        off_diag_x = np.full(n_int - ny_int, cx)
        A = sp.diags(
            [main_diag, off_diag_y, off_diag_y, off_diag_x, off_diag_x],
            [0, 1, -1, ny_int, -ny_int],
            format='csc'
        )
        # 2. Factorize from scratch
        lu = spla.splu(A)
        # 3. Solve
        u_int = lu.solve(b)
        u = np.zeros((N, N))
        u[1:-1, 1:-1] = u_int.reshape(nx_int, ny_int)
        
    avg_ms = (time.perf_counter() - t0) / n_trials * 1000.0
    return avg_ms

def benchmark_solver_batched(solver, batch_size=32, n_trials=30):
    """
    Measures solving multiple RHS vectors simultaneously using SuperLU BLAS-3 multivector solve.
    """
    N = solver.N
    f_single = manufactured_source_2d(solver.X, solver.Y)
    b = f_single[1:-1, 1:-1].flatten()
    B_mat = np.tile(b[:, None], (1, batch_size)) # shape (3844, 32)
    
    # Warmup
    _ = solver.lu_solve(B_mat)
    
    t0 = time.perf_counter()
    for _ in range(n_trials):
        U_int_batch = solver.lu_solve(B_mat)
    total_batch_ms = (time.perf_counter() - t0) / n_trials * 1000.0
    per_query_ms = total_batch_ms / batch_size
    return total_batch_ms, per_query_ms

def run_timing_honesty_benchmark(N=64, batch_size=32, fno_path=None):
    if fno_path is None:
        fno_path = str(MODELS / "fno2d_poisson_v2.pt")
    print("--- Running Timing Honesty Benchmark ---")
    solver = Poisson2DSolver(N=N)
    
    # 1. Solver: prefactorized single query
    f_single = manufactured_source_2d(solver.X, solver.Y).astype(np.float32)
    _ = solver.solve(f_single)
    t0 = time.perf_counter()
    n_trials = 50
    for _ in range(n_trials):
        _ = solver.solve(f_single)
    solver_prefact_single_ms = (time.perf_counter() - t0) / n_trials * 1000.0
    
    # 2. Solver: prefactorized batch solve (B=32)
    solver_batch_total_ms, solver_batch_per_query_ms = benchmark_solver_batched(solver, batch_size=batch_size)
    
    # 3. Solver: fresh factorization from scratch per query
    solver_fresh_fact_single_ms = benchmark_fresh_factorization_single(N=N)
    
    # 4. Linear Ridge baseline
    lin = LinearPoissonBaseline()
    lin_path_v2 = str(MODELS / "linear_baseline_poisson_v2.npz")
    if os.path.exists(lin_path_v2):
        lin.load(lin_path_v2)
    elif os.path.exists("archive/superseded/linear_baseline_poisson.npz"):
        lin.load("archive/superseded/linear_baseline_poisson.npz")
    else:
        d = np.load(str(DATASETS / "poisson_v2_train.npz"))
        lin.fit(d["F"][:1000], d["U"][:1000])
        
    f_batch = np.repeat(f_single[None, ...], batch_size, axis=0)
    _ = lin.predict(f_single)
    t0 = time.perf_counter()
    for _ in range(n_trials):
        _ = lin.predict(f_single)
    lin_single_ms = (time.perf_counter() - t0) / n_trials * 1000.0
    
    _ = lin.predict(f_batch)
    t0 = time.perf_counter()
    for _ in range(n_trials):
        _ = lin.predict(f_batch)
    lin_batch_per_query_ms = (time.perf_counter() - t0) / (n_trials * batch_size) * 1000.0
    
    # 5. FNO2d on CPU
    fno = FNO2d(modes1=12, modes2=12, width=32, use_hard_mask=True)
    if os.path.exists(fno_path):
        fno.load_state_dict(torch.load(fno_path, map_location="cpu"))
    fno.eval()
    
    coords = torch.from_numpy(np.stack([solver.X, solver.Y], axis=0)).float()
    fno_in_single = torch.cat([torch.from_numpy(f_single).unsqueeze(0).unsqueeze(0), coords.unsqueeze(0)], dim=1)
    fno_in_batch = torch.cat([torch.from_numpy(f_batch).unsqueeze(1), coords.unsqueeze(0).repeat(batch_size, 1, 1, 1)], dim=1)
    
    with torch.no_grad():
        _ = fno(fno_in_single)
        t0 = time.perf_counter()
        for _ in range(n_trials):
            _ = fno(fno_in_single)
        fno_single_ms = (time.perf_counter() - t0) / n_trials * 1000.0
        
        _ = fno(fno_in_batch)
        t0 = time.perf_counter()
        for _ in range(n_trials):
            _ = fno(fno_in_batch)
        fno_batch_per_query_ms = (time.perf_counter() - t0) / (n_trials * batch_size) * 1000.0
        
    results = {
        "solver_prefact_single_ms": solver_prefact_single_ms,
        "solver_prefact_batch_per_query_ms": solver_batch_per_query_ms,
        "solver_fresh_fact_single_ms": solver_fresh_fact_single_ms,
        "fno_single_ms": fno_single_ms,
        "fno_batch_per_query_ms": fno_batch_per_query_ms,
        "linear_single_ms": lin_single_ms,
        "linear_batch_per_query_ms": lin_batch_per_query_ms,
        "speedup_solver_vs_fno_single": fno_single_ms / solver_prefact_single_ms,
        "speedup_solver_vs_fno_batch": fno_batch_per_query_ms / solver_batch_per_query_ms,
        "honest_statement": (
            f"At 64x64 resolution, the classical sparse direct solver is vastly faster than FNO on CPU: "
            f"{solver_prefact_single_ms:.3f} ms vs {fno_single_ms:.3f} ms single-query ({fno_single_ms/solver_prefact_single_ms:.1f}x faster), "
            f"and {solver_batch_per_query_ms:.3f} ms vs {fno_batch_per_query_ms:.3f} ms batched ({fno_batch_per_query_ms/solver_batch_per_query_ms:.1f}x faster). "
            f"Even rebuilding and re-factorizing the sparse matrix from scratch on every query ({solver_fresh_fact_single_ms:.3f} ms) "
            f"is ~{fno_single_ms/solver_fresh_fact_single_ms:.1f}x faster than FNO ({fno_single_ms:.3f} ms) on CPU, 64x64. "
            f"The classical solver is faster, exact, and zero-parameter at this scale."
        )
    }
    
    with open(str(RESULTS / "timing_honesty.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    print("\n--- Timing Summary ---")
    print(f"Solver (Prefactorized LU, single) : {solver_prefact_single_ms:.3f} ms")
    print(f"Solver (Prefactorized LU, batch32): {solver_batch_per_query_ms:.3f} ms/query ({solver_batch_total_ms:.2f} ms total)")
    print(f"Solver (Fresh LU Factorization)   : {solver_fresh_fact_single_ms:.3f} ms")
    print(f"Linear Baseline (single / batch) : {lin_single_ms:.3f} ms / {lin_batch_per_query_ms:.3f} ms")
    print(f"FNO2d Operator  (single / batch) : {fno_single_ms:.3f} ms / {fno_batch_per_query_ms:.3f} ms")
    print(f"\n{results['honest_statement']}")
    return results

if __name__ == "__main__":
    run_timing_honesty_benchmark()
