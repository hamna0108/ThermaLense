import os
import sys
import csv
import torch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.models.fno2d import FNO2d
from src.data.poisson_loader import load_all_splits
from src.eval_poisson_v2 import compute_field_metrics

try:
    from paths import DATASETS, RESULTS
except ImportError:
    from src.paths import DATASETS, RESULTS

def evaluate_v1_on_v2():
    v1_ckpt_path = "archive/superseded/fno2d_poisson.pt"
    if not os.path.exists(v1_ckpt_path):
        raise FileNotFoundError(f"Cannot find archived checkpoint: {v1_ckpt_path}")
        
    print(f"Loading Poisson v1 model from {v1_ckpt_path}...")
    model = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    state_dict = torch.load(v1_ckpt_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    
    print("Loading Poisson v2 splits...")
    splits = load_all_splits(str(DATASETS), version="v2")
    N = splits["train"]["grid_x"].shape[0]
    h = 1.0 / (N - 1)
    
    grid_x = splits["train"]["grid_x"]
    grid_y = splits["train"]["grid_y"]
    X, Y = np.meshgrid(grid_x, grid_y, indexing='ij')
    coords = torch.from_numpy(np.stack([X, Y], axis=0)).float()
    
    rows = []
    print("\n--- Evaluation of Poisson v1 FNO on v2 Splits ---")
    for split_name, data in splits.items():
        F = data["F"]
        U = data["U"]
        M = len(F)
        
        F_tensor = torch.from_numpy(F).unsqueeze(1).float()
        coords_batch = coords.unsqueeze(0).repeat(M, 1, 1, 1)
        fno_in = torch.cat([F_tensor, coords_batch], dim=1)
        
        preds = []
        batch_sz = 32
        with torch.no_grad():
            for b in range(0, M, batch_sz):
                pred = model(fno_in[b:b+batch_sz])
                preds.append(pred.squeeze(1).cpu().numpy())
                
        U_pred = np.concatenate(preds, axis=0)
        metrics = compute_field_metrics(U_pred, U, F, h)
        
        row = {
            "split": split_name,
            "samples": M,
            "fno_v1_l2_med": metrics["rel_l2_median"],
            "fno_v1_l2_p90": metrics["rel_l2_p90"],
            "fno_v1_l2_max": metrics["rel_l2_max"],
            "fno_v1_res_med": metrics["res_median"]
        }
        rows.append(row)
        print(f"  {split_name:<20}: L2 Med={metrics['rel_l2_median']:.4e} | P90={metrics['rel_l2_p90']:.4e} | Max={metrics['rel_l2_max']:.4e} | Res={metrics['res_median']:.4e}")
        
    out_csv = str(RESULTS / "poisson_v1_on_v2_splits.csv")
    with open(out_csv, "w", newline="") as f:
        fieldnames = ["split", "samples", "fno_v1_l2_med", "fno_v1_l2_p90", "fno_v1_l2_max", "fno_v1_res_med"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"\nSaved v1 evaluation on v2 splits to: {out_csv}")

if __name__ == "__main__":
    evaluate_v1_on_v2()
