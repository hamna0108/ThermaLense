import os
import sys
import json
import torch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.models.fno2d import FNO2d
from src.data.poisson_loader import load_all_splits
from src.eval_poisson_v2 import compute_field_metrics

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(base_dir, "data", "datasets")
    ckpt_dir = r"C:\Users\HP\Downloads\fno_v3_results\models\fno_v3"
    report_path = os.path.join(base_dir, "data", "results", "poisson_fno_v3", "fno_v3_acceptance_report.json")
    
    with open(report_path, "r") as f:
        report = json.load(f)
        
    seeds = [42, 43, 44, 45, 46]
    splits = load_all_splits(data_dir, version="v2")
    
    grid_x = splits["train"]["grid_x"]
    grid_y = splits["train"]["grid_y"]
    N = grid_x.shape[0]
    h = 1.0 / (N - 1)
    
    X, Y = np.meshgrid(grid_x, grid_y, indexing='ij')
    coords = torch.from_numpy(np.stack([X, Y], axis=0)).float().unsqueeze(0)
    
    device = torch.device("cpu")
    max_diff_seen = 0.0
    all_comparisons = []
    
    print("Evaluating 5 v3 checkpoints on LOCAL data/datasets/poisson_v2_*.npz...")
    
    for s_idx, seed in enumerate(seeds):
        ckpt_path = os.path.join(ckpt_dir, f"fno2d_v3_seed{seed}_best.pt")
        if not os.path.exists(ckpt_path):
            print(f"ERROR: Checkpoint missing for seed {seed} at {ckpt_path}")
            continue
            
        ckpt = torch.load(ckpt_path, map_location=device)
        state_dict = ckpt["model_state_dict"] if "model_state_dict" in ckpt else ckpt
        modes = ckpt.get("modes", 16)
        width = ckpt.get("width", 64)
        use_mask = ckpt.get("use_hard_mask", True)
        
        model = FNO2d(modes1=modes, modes2=modes, width=width, in_channels=3, out_channels=1, use_hard_mask=use_mask).to(device)
        model.load_state_dict(state_dict)
        model.eval()
        
        # Report recorded metrics
        report_metrics = report["per_seed_results"][s_idx]["metrics"]
        
        for split_name, s_data in splits.items():
            F = s_data["F"]
            U = s_data["U"]
            M = len(F)
            
            preds = []
            batch_sz = 32
            with torch.no_grad():
                for b in range(0, M, batch_sz):
                    f_batch = torch.from_numpy(F[b:b+batch_sz]).unsqueeze(1).float().to(device)
                    c_batch = coords.repeat(len(f_batch), 1, 1, 1)
                    inp = torch.cat([f_batch, c_batch], dim=1)
                    pred = model(inp)
                    preds.append(pred.squeeze(1).cpu().numpy())
                    
            U_pred = np.concatenate(preds, axis=0)
            m = compute_field_metrics(U_pred, U, F, h)
            local_med = float(m["rel_l2_median"])
            colab_med = float(report_metrics[split_name]["rel_l2_median"])
            
            diff = abs(local_med - colab_med)
            if diff > max_diff_seen:
                max_diff_seen = diff
                
            all_comparisons.append({
                "seed": seed,
                "split": split_name,
                "local_median": local_med,
                "colab_median": colab_med,
                "diff": diff,
                "exceeds_1e4": diff > 1e-4
            })
            print(f"Seed {seed:2d} | Split {split_name:<18} | Local: {local_med:.6f} | Colab: {colab_med:.6f} | Diff: {diff:.2e}")
            
    print(f"\nEvaluation Complete! Maximum absolute difference between Local and Colab: {max_diff_seen:.2e}")
    if max_diff_seen > 1e-4:
        print("WARNING: Max difference exceeds 1e-4 threshold!")
    else:
        print("SUCCESS: All splits match Colab report within 1e-4 threshold (exact floating-point CPU/GPU tolerance).")

    out_file = os.path.join(base_dir, "data", "results", "poisson_fno_v3", "local_vs_colab_verification.json")
    with open(out_file, "w") as f:
        json.dump({
            "max_difference": max_diff_seen,
            "threshold": 1e-4,
            "passed": max_diff_seen <= 1e-4,
            "comparisons": all_comparisons
        }, f, indent=2)
    print(f"Saved verification log to {out_file}")

if __name__ == "__main__":
    main()
