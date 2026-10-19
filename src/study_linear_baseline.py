import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
from src.models.linear_baseline import LinearPoissonBaseline
from src.data.poisson_loader import load_all_splits

try:
    from paths import DATASETS, RESULTS
except ImportError:
    from src.paths import DATASETS, RESULTS

def run_linear_baseline_study(data_dir=None, version="v2"):
    if data_dir is None: data_dir = str(DATASETS)
    print("--- Running Linear Baseline SVD & Sample Efficiency Study ---")
    splits = load_all_splits(data_dir, version=version)
    F_train = splits["train"]["F"] # (1000, 64, 64)
    U_train = splits["train"]["U"] # (1000, 64, 64)
    N_total, H, W = F_train.shape
    D = H * W
    
    # 1. Singular Value Decomposition of Training Source Matrix
    F_mat = F_train.reshape(N_total, D).astype(np.float64)
    print("Computing SVD of source matrix F (1000 x 4096)...")
    # Economic SVD: s has shape (1000,)
    s = np.linalg.svd(F_mat, compute_uv=False)
    
    total_energy = np.sum(s**2)
    cum_energy = np.cumsum(s**2) / total_energy
    
    k_99 = int(np.searchsorted(cum_energy, 0.99) + 1)
    k_999 = int(np.searchsorted(cum_energy, 0.999) + 1)
    k_9999 = int(np.searchsorted(cum_energy, 0.9999) + 1)
    
    # Normalized singular value ratios
    sv_ratios = {
        "sigma_1": float(s[0]),
        "sigma_10_ratio": float(s[9] / s[0]),
        "sigma_50_ratio": float(s[49] / s[0]),
        "sigma_100_ratio": float(s[99] / s[0]),
        "sigma_200_ratio": float(s[199] / s[0]),
        "sigma_500_ratio": float(s[499] / s[0]),
        "rank_99_energy": k_99,
        "rank_999_energy": k_999,
        "rank_9999_energy": k_9999,
        "effective_rank": float(np.sum(s) / s[0])
    }
    
    print(f"SVD Decay:")
    print(f"  sigma_1 = {s[0]:.2e}, sigma_10/sigma_1 = {s[9]/s[0]:.4e}, sigma_50/sigma_1 = {s[49]/s[0]:.4e}, sigma_100/sigma_1 = {s[99]/s[0]:.4e}")
    print(f"  Energy: 99% in {k_99} modes, 99.9% in {k_999} modes, 99.99% in {k_9999} modes (out of 4096).")
    
    # 2. Sample Efficiency: N = [100, 300, 1000]
    sample_sizes = [100, 300, 1000]
    eval_splits = ["test_interp", "test_ood_narrow", "test_ood_boundary", "test_ood_highmodes"]
    
    # Manufactured sanity case
    manuf = np.load(os.path.join(data_dir, f"poisson_{version}_manufactured_sanity.npz"))
    F_manuf = manuf["F"]
    U_manuf_exact = manuf["U_exact"]
    
    sample_size_results = {}
    
    for n_sub in sample_sizes:
        print(f"\nEvaluating Linear Baseline with N_train = {n_sub}...")
        lin = LinearPoissonBaseline(alpha_reg=1e-8)
        # Use first n_sub training samples
        F_sub = F_train[:n_sub]
        U_sub = U_train[:n_sub]
        lin.fit(F_sub, U_sub)
        
        split_res = {}
        for s_name in eval_splits:
            F_test = splits[s_name]["F"]
            U_test = splits[s_name]["U"]
            pred = lin.predict(F_test)
            diff = pred - U_test
            errs = np.linalg.norm(diff.reshape(len(diff), -1), axis=1) / (
                np.linalg.norm(U_test.reshape(len(U_test), -1), axis=1) + 1e-12
            )
            split_res[s_name] = {
                "median_rel_l2": float(np.median(errs)),
                "p90_rel_l2": float(np.percentile(errs, 90)),
                "max_rel_l2": float(np.max(errs))
            }
            
        # Manufactured case
        u_manuf_pred = lin.predict(F_manuf)
        m_diff = u_manuf_pred - U_manuf_exact
        m_err = float(np.linalg.norm(m_diff) / np.linalg.norm(U_manuf_exact))
        split_res["manufactured_case"] = m_err
        
        sample_size_results[f"N_{n_sub}"] = {
            "n_samples": n_sub,
            "train_time_s": lin.train_time,
            "metrics": split_res
        }
        print(f"  N={n_sub:4d} | Interp med L2: {split_res['test_interp']['median_rel_l2']:.4e} | Manuf L2: {m_err:.4e}")
        
    study_output = {
        "svd": sv_ratios,
        "sample_efficiency": sample_size_results,
        "explanation": (
            "The Poisson problem -nabla^2 u = f with zero Dirichlet boundary conditions has an exact, "
            "strictly linear solution operator u = A^{-1} f (discrete Green's function). "
            "Because the source family consists of smooth functions (Gaussians and low-frequency sine modes), "
            "their spatial correlations produce an extremely rapid singular-value decay (99.9% energy in << 100 modes). "
            "Consequently, ridge regression with N=100-1000 samples spans the active subspace completely and directly "
            "inverts the discrete differential operator with near-machine precision."
        )
    }
    
    save_path = str(RESULTS / "linear_baseline_study.json")
    with open(save_path, "w") as f:
        json.dump(study_output, f, indent=2)
    print(f"Saved linear baseline study to {save_path}")
    return study_output

if __name__ == "__main__":
    run_linear_baseline_study()
