"""Accuracy evaluation across new boundary condition families.

Runs 40 seeds per condition at noise sigma = 0.01 with 10 sensors.
Outputs summary table and writes challenge/accuracy_new_bcs.csv.
"""

import os
import sys
import time
import csv
from typing import Dict, Any, List

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.v2.declared_physics import solve_heat_1d_general, invert_with_declared_physics

BC_CONFIGS = {
    "unequal_ends": {
        "description": "Dirichlet 0.2 (left), Dirichlet 0.8 (right), u0=0.5",
        "u0_fn": lambda x: np.full_like(x, 0.5),
        "bc_left": ("dirichlet", 0.2),
        "bc_right": ("dirichlet", 0.8),
        "alpha_true": 0.15
    },
    "one_insulated": {
        "description": "Neumann 0 (left), Dirichlet 0 (right), u0=cos(0.5*pi*x)",
        "u0_fn": lambda x: np.cos(0.5 * np.pi * x),
        "bc_left": ("neumann", 0.0),
        "bc_right": ("dirichlet", 0.0),
        "alpha_true": 0.10
    },
    "mixed": {
        "description": "Dirichlet 1.0 (left), Neumann 0 (right), u0=0.0",
        "u0_fn": lambda x: np.zeros_like(x),
        "bc_left": ("dirichlet", 1.0),
        "bc_right": ("neumann", 0.0),
        "alpha_true": 0.08
    },
    "both_insulated": {
        "description": "Neumann 0 (left), Neumann 0 (right), u0=cos(pi*x)",
        "u0_fn": lambda x: np.cos(np.pi * x),
        "bc_left": ("neumann", 0.0),
        "bc_right": ("neumann", 0.0),
        "alpha_true": 0.12
    }
}

def run_accuracy_study(
    num_seeds: int = 40,
    noise_sigma: float = 0.01,
    num_sensors: int = 10,
    base_seed: int = 20260101,
    out_csv: str = "challenge/accuracy_new_bcs.csv"
) -> List[Dict[str, Any]]:
    print(f"\n[Accuracy Study] Running {num_seeds} seeds x {len(BC_CONFIGS)} boundary condition families...")
    print(f"[Accuracy Study] Configuration: noise={noise_sigma}, sensors={num_sensors}, base_seed={base_seed}")

    Nx, Nt = 101, 101
    x_coords = np.linspace(0.15, 0.85, 5).tolist() * 2
    t_coords = np.linspace(0.10, 0.90, num_sensors).tolist()

    summary_rows = []
    t_start = time.perf_counter()

    for cond_name, cfg in BC_CONFIGS.items():
        alpha_true = cfg["alpha_true"]
        u0_fn = cfg["u0_fn"]
        bc_left = cfg["bc_left"]
        bc_right = cfg["bc_right"]

        # Forward solve for ground truth temperatures
        xg, tg, ug = solve_heat_1d_general(
            Nx=Nx, Nt=Nt, alpha=alpha_true,
            u0_fn=u0_fn, bc_left=bc_left, bc_right=bc_right
        )
        y_true = np.array([
            ug[int(round(t * (Nt - 1))), int(round(x * (Nx - 1)))]
            for x, t in zip(x_coords, t_coords)
        ])

        rel_errors = []
        coverage_flags = []
        estimates = []

        t0_cond = time.perf_counter()
        for seed_idx in range(num_seeds):
            rng = np.random.RandomState(base_seed + seed_idx * 17)
            noise = rng.normal(0, noise_sigma, size=len(y_true))
            y_obs = y_true + noise

            inv_res = invert_with_declared_physics(
                x_s=x_coords,
                t_s=t_coords,
                y_s=y_obs,
                sigma=noise_sigma,
                alpha_true=alpha_true,
                u0_fn=u0_fn,
                bc_left=bc_left,
                bc_right=bc_right,
                Nx=Nx,
                Nt=Nt
            )
            a_hat = inv_res["alpha_hat"]
            rel_err = abs(a_hat - alpha_true) / alpha_true
            rel_errors.append(rel_err)
            coverage_flags.append(inv_res["in_ci_95"])
            estimates.append(a_hat)

        elapsed_cond = time.perf_counter() - t0_cond
        med_err = float(np.median(rel_errors))
        mean_err = float(np.mean(rel_errors))
        cov_rate = float(np.mean(coverage_flags))

        row = {
            "boundary_family": cond_name,
            "description": cfg["description"],
            "alpha_true": alpha_true,
            "num_episodes": num_seeds,
            "noise_sigma": noise_sigma,
            "num_sensors": num_sensors,
            "median_rel_error": round(med_err, 4),
            "mean_rel_error": round(mean_err, 4),
            "coverage_95": round(cov_rate, 4),
            "elapsed_s": round(elapsed_cond, 2)
        }
        summary_rows.append(row)
        print(f"  {cond_name:<16}: median_error={med_err*100:.2f}%, coverage={cov_rate*100:.1f}% ({elapsed_cond:.2f}s)")

    total_s = time.perf_counter() - t_start
    print(f"[Accuracy Study] Completed {num_seeds * len(BC_CONFIGS)} inversions in {total_s:.2f}s.\n")

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "boundary_family", "description", "alpha_true", "num_episodes",
            "noise_sigma", "num_sensors", "median_rel_error", "mean_rel_error",
            "coverage_95", "elapsed_s"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in summary_rows:
            writer.writerow(r)

    print(f"[Accuracy Study] Saved results to: {out_csv}")
    return summary_rows

if __name__ == "__main__":
    run_accuracy_study()

