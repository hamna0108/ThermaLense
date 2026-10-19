try:
    from paths import DATASETS
except ImportError:
    from src.paths import DATASETS
import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import numpy as np
from src.solvers.poisson_2d import Poisson2DSolver, manufactured_source_2d, solve_poisson_2d_exact
from src.data.generate_poisson_dataset import sample_gaussian_source

def sample_sine_mode_source(rng, X, Y, is_highmodes=False):
    """
    Generate 2D Sine mode source:
        f(x, y) = sum_k a_k * (m_k^2 + n_k^2) * pi^2 * sin(m_k * pi * x) * sin(n_k * pi * y)
    Corresponding exact analytic solution:
        u(x, y) = sum_k a_k * sin(m_k * pi * x) * sin(n_k * pi * y)
    - In-distribution: m, n in {1, 2, 3, 4}, a_k in [0.2, 1.5]
    - OOD Highmodes: at least one of m or n in {5, 6, 7, 8}
    Manufactured solution f = 2*pi^2*sin(pi*x)*sin(pi*y) corresponds to K=1, m=1, n=1, a=1.0.
    """
    k_modes = rng.integers(1, 4) # 1, 2, or 3 modes
    f_total = np.zeros_like(X)
    u_exact_total = np.zeros_like(X)
    modes = []
    
    for i in range(k_modes):
        a = rng.uniform(0.2, 1.5)
        if is_highmodes:
            # At least one mode in 5..8
            if i == 0 or rng.random() < 0.5:
                m = rng.integers(5, 9)
                n = rng.integers(1, 9)
            else:
                m = rng.integers(1, 9)
                n = rng.integers(5, 9)
        else:
            m = rng.integers(1, 5) # 1..4
            n = rng.integers(1, 5) # 1..4
            
        coeff = a * (m**2 + n**2) * (np.pi**2)
        comp_f = coeff * np.sin(m * np.pi * X) * np.sin(n * np.pi * Y)
        comp_u = a * np.sin(m * np.pi * X) * np.sin(n * np.pi * Y)
        
        f_total += comp_f
        u_exact_total += comp_u
        modes.append((m, n, a))
        
    return f_total, u_exact_total, modes

def sample_mixed_source(rng, X, Y, is_sine):
    """
    50/50 mixture of Gaussian mixture and sine modes (m,n in 1..4).
    """
    if is_sine:
        f_arr, _, _ = sample_sine_mode_source(rng, X, Y, is_highmodes=False)
    else:
        f_arr, _ = sample_gaussian_source(rng, X, Y, split_type="standard")
    return f_arr

def generate_split_v2(solver, n_samples, base_seed, split_type):
    F_list = np.zeros((n_samples, solver.N, solver.N), dtype=np.float32)
    U_list = np.zeros((n_samples, solver.N, solver.N), dtype=np.float32)
    seeds = np.zeros(n_samples, dtype=np.int64)
    
    for i in range(n_samples):
        seed = base_seed + i
        seeds[i] = seed
        rng = np.random.default_rng(seed)
        
        if split_type == "mixed_50_50":
            is_sine = (i % 2 == 1) # Alternating 50/50 deterministic mix
            f_arr = sample_mixed_source(rng, solver.X, solver.Y, is_sine)
            u_arr = solver.solve(f_arr)
        elif split_type == "ood_highmodes":
            f_arr, _, _ = sample_sine_mode_source(rng, solver.X, solver.Y, is_highmodes=True)
            u_arr = solver.solve(f_arr)
        else:
            # Gaussian OOD splits: ood_narrow, ood_count, ood_boundary
            f_arr, _ = sample_gaussian_source(rng, solver.X, solver.Y, split_type=split_type)
            u_arr = solver.solve(f_arr)
            
        F_list[i] = f_arr.astype(np.float32)
        U_list[i] = u_arr.astype(np.float32)
        
    return F_list, U_list, seeds

def build_poisson_dataset_v2(out_dir=None, N=64):
    if out_dir is None: out_dir = str(DATASETS)
    os.makedirs(out_dir, exist_ok=True)
    solver = Poisson2DSolver(N=N)
    
    # New disjoint seed layout starting at 1,100,000
    split_configs = [
        ("train", 1000, 1100000, "mixed_50_50"),
        ("val", 100, 1200000, "mixed_50_50"),
        ("test_interp", 200, 1300000, "mixed_50_50"),
        ("test_ood_narrow", 200, 1400000, "ood_narrow"),
        ("test_ood_count", 200, 1500000, "ood_count"),
        ("test_ood_boundary", 200, 1600000, "ood_boundary"),
        ("test_ood_highmodes", 200, 1700000, "ood_highmodes")
    ]
    
    t0 = time.time()
    all_seeds = []
    manifest = {}
    
    for name, n_samples, base_seed, split_type in split_configs:
        print(f"Generating v2 split '{name}': {n_samples} samples, base_seed={base_seed}, type={split_type}...")
        F, U, seeds = generate_split_v2(solver, n_samples, base_seed, split_type)
        
        out_path = os.path.join(out_dir, f"poisson_v2_{name}.npz")
        np.savez_compressed(
            out_path,
            F=F,
            U=U,
            seeds=seeds,
            grid_x=solver.x.astype(np.float32),
            grid_y=solver.y.astype(np.float32),
            split_name=name,
            split_type=split_type
        )
        all_seeds.extend(seeds.tolist())
        manifest[name] = {
            "samples": n_samples,
            "seed_range": [int(seeds[0]), int(seeds[-1])],
            "split_type": split_type,
            "file": out_path
        }
        
    # Manufactured sanity case
    f_manuf = manufactured_source_2d(solver.X, solver.Y).astype(np.float32)
    u_exact = solve_poisson_2d_exact(solver.X, solver.Y).astype(np.float32)
    u_solver = solver.solve(f_manuf).astype(np.float32)
    manuf_path = os.path.join(out_dir, "poisson_v2_manufactured_sanity.npz")
    np.savez_compressed(
        manuf_path,
        F=f_manuf[None, ...],
        U_exact=u_exact[None, ...],
        U_solver=u_solver[None, ...],
        grid_x=solver.x.astype(np.float32),
        grid_y=solver.y.astype(np.float32)
    )
    
    elapsed = time.time() - t0
    assert len(all_seeds) == len(set(all_seeds)), "FATAL: Seed collision in v2 dataset!"
    print(f"Done v2! Generated {len(all_seeds)} total samples across 7 splits in {elapsed:.2f}s. All seeds strictly disjoint.")
    return manifest

if __name__ == "__main__":
    build_poisson_dataset_v2()
