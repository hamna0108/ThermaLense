import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.data.generate_poisson_dataset_v2 import sample_sine_mode_source
from archive.superseded.generate_poisson_dataset import sample_gaussian_source
from src.models.fno2d import FNO2d

try:
    from paths import DATASETS, RESULTS, MODELS
except ImportError:
    from src.paths import DATASETS, RESULTS, MODELS

def run_failure_case_analysis():
    eval_json_path = str(RESULTS / "poisson_v2_eval_results.json")
    with open(eval_json_path, "r") as f:
        eval_data = json.load(f)["splits"]
        
    ood_splits = ["test_ood_narrow", "test_ood_count", "test_ood_boundary", "test_ood_highmodes"]
    
    failure_reports = {}
    
    grid_x = np.linspace(0, 1, 64)
    grid_y = np.linspace(0, 1, 64)
    X, Y = np.meshgrid(grid_x, grid_y, indexing="ij")
    
    print("=" * 90)
    print("TOP 10 WORST FNO SAMPLES PER OOD SPLIT (STRESS MATRIX FAILURE MODES)")
    print("=" * 90)
    
    for split_name in ood_splits:
        npz_path = str(DATASETS / f"poisson_v2_{split_name}.npz")
        d = np.load(npz_path)
        seeds = d["seeds"]
        errors = np.array(eval_data[split_name]["fno"]["all_l2"])
        
        # Sort descending
        worst_indices = np.argsort(errors)[::-1][:10]
        
        split_cases = []
        print(f"\n--- Split: {split_name} (Median Rel L2: {eval_data[split_name]['fno']['rel_l2_median']:.4e}, Max: {eval_data[split_name]['fno']['rel_l2_max']:.4e}) ---")
        print(f"{'Rank':<5} | {'Idx':<5} | {'Seed':<8} | {'Rel L2':<12} | {'Source Parameters'}")
        print("-" * 90)
        
        for rank, idx in enumerate(worst_indices, 1):
            seed = int(seeds[idx])
            err = float(errors[idx])
            rng = np.random.default_rng(seed)
            
            if split_name == "test_ood_highmodes":
                _, _, modes = sample_sine_mode_source(rng, X, Y, is_highmodes=True)
                modes_serializable = [(int(m), int(n), float(a)) for m, n, a in modes]
                param_desc = f"modes: {[(m, n, round(a, 3)) for m, n, a in modes_serializable]}"
                param_dict = {"modes": modes_serializable}
            elif split_name == "test_ood_narrow":
                _, info = sample_gaussian_source(rng, X, Y, split_type="ood_narrow")
                param_desc = f"k={info['k_sources']}, widths={[round(w, 4) for w in info['widths']]}, amps={[round(a, 2) for a in info['amps']]}"
                param_dict = {
                    "k_sources": int(info["k_sources"]),
                    "centers": [[float(c[0]), float(c[1])] for c in info["centers"]],
                    "widths": [float(w) for w in info["widths"]],
                    "amps": [float(a) for a in info["amps"]]
                }
            elif split_name == "test_ood_count":
                _, info = sample_gaussian_source(rng, X, Y, split_type="ood_count")
                param_desc = f"k={info['k_sources']}, widths={[round(w, 4) for w in info['widths']]}, amps={[round(a, 2) for a in info['amps']]}"
                param_dict = {
                    "k_sources": int(info["k_sources"]),
                    "centers": [[float(c[0]), float(c[1])] for c in info["centers"]],
                    "widths": [float(w) for w in info["widths"]],
                    "amps": [float(a) for a in info["amps"]]
                }
            elif split_name == "test_ood_boundary":
                _, info = sample_gaussian_source(rng, X, Y, split_type="ood_boundary")
                centers_str = [f"({round(c[0], 2)}, {round(c[1], 2)})" for c in info['centers']]
                param_desc = f"k={info['k_sources']}, centers={centers_str}, widths={[round(w, 3) for w in info['widths']]}"
                param_dict = {
                    "k_sources": int(info["k_sources"]),
                    "centers": [[float(c[0]), float(c[1])] for c in info["centers"]],
                    "widths": [float(w) for w in info["widths"]],
                    "amps": [float(a) for a in info["amps"]]
                }
                
            print(f"{rank:<5} | {idx:<5} | {seed:<8} | {err:<12.6f} | {param_desc}")
            split_cases.append({
                "rank": rank,
                "split_index": int(idx),
                "seed": seed,
                "rel_l2_error": err,
                "source_parameters": param_dict,
                "description": param_desc
            })
            
        failure_reports[split_name] = split_cases
        
    # Save JSON summary of failure cases
    out_json = str(RESULTS / "poisson_v2_failure_cases.json")
    with open(out_json, "w") as f:
        json.dump(failure_reports, f, indent=2, default=str)
    print(f"\nSaved structured failure cases to: {out_json}")
    
    # Save Example Field Plots for Highmodes Worst Sample
    print("\nGenerating field failure visualization for test_ood_highmodes...")
    highmodes_npz = np.load(str(DATASETS / "poisson_v2_test_ood_highmodes.npz"))
    hm_F = highmodes_npz["F"]
    hm_U = highmodes_npz["U"]
    worst_hm_idx = failure_reports["test_ood_highmodes"][0]["split_index"]
    worst_hm_err = failure_reports["test_ood_highmodes"][0]["rel_l2_error"]
    worst_hm_desc = failure_reports["test_ood_highmodes"][0]["description"]
    
    # Compute prediction with FNO v2
    fno = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    fno.load_state_dict(torch.load(str(MODELS / "fno2d_poisson_v2.pt"), map_location="cpu"))
    fno.eval()
    
    f_sample = hm_F[worst_hm_idx]
    u_true = hm_U[worst_hm_idx]
    coords = torch.from_numpy(np.stack([X, Y], axis=0)).float()
    f_tensor = torch.from_numpy(f_sample).unsqueeze(0).unsqueeze(0).float()
    fno_in = torch.cat([f_tensor, coords.unsqueeze(0)], dim=1)
    
    with torch.no_grad():
        u_pred = fno(fno_in).squeeze().numpy()
        
    abs_err = np.abs(u_pred - u_true)
    
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.2))
    
    im0 = axes[0].contourf(X, Y, f_sample, levels=40, cmap="viridis")
    axes[0].set_title(f"Source f(x, y)\n({worst_hm_desc})", fontsize=10)
    axes[0].set_aspect('equal')
    plt.colorbar(im0, ax=axes[0])
    
    im1 = axes[1].contourf(X, Y, u_true, levels=40, cmap="viridis")
    axes[1].set_title(f"Ground Truth Solution u(x, y)", fontsize=10)
    axes[1].set_aspect('equal')
    plt.colorbar(im1, ax=axes[1])
    
    im2 = axes[2].contourf(X, Y, u_pred, levels=40, cmap="viridis")
    axes[2].set_title(f"FNO v2 Prediction u_hat(x, y)\n(rel L2 = {worst_hm_err:.2%})", fontsize=10)
    axes[2].set_aspect('equal')
    plt.colorbar(im2, ax=axes[2])
    
    im3 = axes[3].contourf(X, Y, abs_err, levels=40, cmap="magma")
    axes[3].set_title(f"Pointwise Absolute Error\nMax |u - u_hat| = {np.max(abs_err):.4f}", fontsize=10)
    axes[3].set_aspect('equal')
    plt.colorbar(im3, ax=axes[3])
    
    plt.tight_layout()
    os.makedirs("plots", exist_ok=True)
    plot_path = "plots/fno_v2_highmodes_failure.png"
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"Saved failure field plot to: {plot_path}")

if __name__ == "__main__":
    run_failure_case_analysis()
