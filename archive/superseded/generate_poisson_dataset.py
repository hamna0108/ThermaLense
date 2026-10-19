import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import numpy as np
from src.solvers.poisson_2d import Poisson2DSolver, manufactured_source_2d, solve_poisson_2d_exact


def sample_gaussian_source(rng, X, Y, split_type="standard"):
    """
    Generate a 2D Gaussian mixture source f(x, y) on domain [0, 1]^2 according to split rules:
    - standard: 1-3 sources, centres in [0.15, 0.85]^2, widths in [0.08, 0.20], amps in [0.5, 2.0]
    - ood_narrow: 1-3 sources, widths in [0.04, 0.07], centres in [0.15, 0.85]^2, amps in [0.5, 2.0]
    - ood_count: 4-5 sources, centres in [0.15, 0.85]^2, widths in [0.08, 0.20], amps in [0.5, 2.0]
    - ood_boundary: 1-3 sources, centres within 0.12 of an edge (in [0.02, 0.98]^2), widths in [0.08, 0.20], amps in [0.5, 2.0]
    """
    if split_type == "ood_count":
        k_sources = rng.integers(4, 6) # 4 or 5
    else:
        k_sources = rng.integers(1, 4) # 1, 2, or 3

    f_total = np.zeros_like(X)
    centers = []
    widths = []
    amps = []

    for _ in range(k_sources):
        # Amplitudes in [0.5, 2.0]
        amp = rng.uniform(0.5, 2.0)
        
        # Widths
        if split_type == "ood_narrow":
            width = rng.uniform(0.04, 0.07)
        else:
            width = rng.uniform(0.08, 0.20)
            
        # Centres
        if split_type == "ood_boundary":
            # Edge band: within 0.12 of an edge (keep away from extreme 0.02 margin)
            edge = rng.choice(["left", "right", "bottom", "top"])
            if edge == "left":
                cx = rng.uniform(0.02, 0.12)
                cy = rng.uniform(0.02, 0.98)
            elif edge == "right":
                cx = rng.uniform(0.88, 0.98)
                cy = rng.uniform(0.02, 0.98)
            elif edge == "bottom":
                cx = rng.uniform(0.02, 0.98)
                cy = rng.uniform(0.02, 0.12)
            else: # top
                cx = rng.uniform(0.02, 0.98)
                cy = rng.uniform(0.88, 0.98)
        else:
            cx = rng.uniform(0.15, 0.85)
            cy = rng.uniform(0.15, 0.85)
            
        # Gaussian source term
        r2 = (X - cx)**2 + (Y - cy)**2
        comp = amp * np.exp(-r2 / (2.0 * width**2))
        f_total += comp
        
        centers.append([cx, cy])
        widths.append(width)
        amps.append(amp)
        
    return f_total, {
        "k_sources": k_sources,
        "centers": centers,
        "widths": widths,
        "amps": amps
    }

def generate_split(solver, n_samples, base_seed, split_type):
    """
    Generate a full split of (f, u) pairs with fixed, sequential disjoint seeds.
    """
    F_list = np.zeros((n_samples, solver.N, solver.N), dtype=np.float32)
    U_list = np.zeros((n_samples, solver.N, solver.N), dtype=np.float32)
    seeds = np.zeros(n_samples, dtype=np.int64)
    
    for i in range(n_samples):
        seed = base_seed + i
        seeds[i] = seed
        rng = np.random.default_rng(seed)
        f_arr, _ = sample_gaussian_source(rng, solver.X, solver.Y, split_type=split_type)
        u_arr = solver.solve(f_arr)
        
        F_list[i] = f_arr.astype(np.float32)
        U_list[i] = u_arr.astype(np.float32)
        
    return F_list, U_list, seeds

def build_poisson_dataset(out_dir="data", N=64):
    os.makedirs(out_dir, exist_ok=True)
    solver = Poisson2DSolver(N=N)
    
    # Specification configuration
    split_configs = [
        ("train", 1000, 100000, "standard"),
        ("val", 100, 200000, "standard"),
        ("test_interp", 200, 300000, "standard"),
        ("test_ood_narrow", 200, 400000, "ood_narrow"),
        ("test_ood_count", 200, 500000, "ood_count"),
        ("test_ood_boundary", 200, 600000, "ood_boundary"),
    ]
    
    t0 = time.time()
    all_seeds = []
    manifest = {}
    
    for name, n_samples, base_seed, split_type in split_configs:
        print(f"Generating split '{name}': {n_samples} samples, base_seed={base_seed}, type={split_type}...")
        F, U, seeds = generate_split(solver, n_samples, base_seed, split_type)
        
        out_path = os.path.join(out_dir, f"poisson_{name}.npz")
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
        
    # Also generate manufactured sanity case
    f_manuf = manufactured_source_2d(solver.X, solver.Y).astype(np.float32)
    u_exact = solve_poisson_2d_exact(solver.X, solver.Y).astype(np.float32)
    u_solver = solver.solve(f_manuf).astype(np.float32)
    manuf_path = os.path.join(out_dir, "poisson_manufactured_sanity.npz")
    np.savez_compressed(
        manuf_path,
        F=f_manuf[None, ...],
        U_exact=u_exact[None, ...],
        U_solver=u_solver[None, ...],
        grid_x=solver.x.astype(np.float32),
        grid_y=solver.y.astype(np.float32)
    )
    
    elapsed = time.time() - t0
    # Seed disjointness assertion
    assert len(all_seeds) == len(set(all_seeds)), "FATAL: Seed collision detected across splits!"
    print(f"Done! Generated {len(all_seeds)} total samples across 6 splits in {elapsed:.2f}s. All seeds strictly disjoint.")
    return manifest

if __name__ == "__main__":
    build_poisson_dataset()
