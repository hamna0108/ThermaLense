"""
Heat FNO Multi-Seed Training & Stability Study (Colab & Local Multi-Seed Runner)
Architecture: FNO2d(modes1=16, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=False)
Recipe: Identical to src/train.py
  - 1,000-sample train.npz, 200-sample val.npz
  - 100 epochs, batch size 20 (50 steps/epoch)
  - Adam optimizer (lr=1e-3, weight_decay=1e-4)
  - StepLR(step_size=50, gamma=0.5)
  - Loss: relative_l2_loss
  - Seeds: 42, 43, 44, 45, 46 (varying initialization and DataLoader shuffle)

Pre-Registered Rule:
  models/fno2d_heat.pt stays FROZEN and UNCHANGED.
  This multi-seed study is strictly a stability and variance report:
  - Reports cohort mean +- std, spread (max/min), and ranks where the frozen baseline sits.
  - Does NOT alter any frozen pipeline result or checkpoint.
"""

import os
import sys
import time
import json
import csv
import hashlib
import argparse
import platform
from datetime import datetime, timezone

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np
from scipy.interpolate import CubicSpline
import scipy.optimize as opt

# Ensure repo root is on sys.path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.models.fno2d import FNO2d, rel_l2_loss
from src.data.dataset import HeatEquationDataset
from src.solvers.heat_1d import solve_heat_1d_exact

def compute_sha256(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_env_manifest(device, data_dir):
    dataset_files = ["train.npz", "val.npz", "test_interpolation.npz", "test_ood.npz"]
    checksums = {}
    for fn in dataset_files:
        fp = os.path.join(data_dir, fn)
        if os.path.exists(fp):
            checksums[fn] = {
                "sha256": compute_sha256(fp),
                "bytes": os.path.getsize(fp)
            }
            
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "device_used": str(device),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() and device.type == "cuda" else "CPU",
        "numpy_version": np.__version__,
        "dataset_checksums": checksums,
        "stability_rule": "models/fno2d_heat.pt remains frozen; 5-seed study provides stability distribution only"
    }
    return manifest

def evaluate_model_comprehensive(model, log_alpha_mean, log_alpha_std, data_dir, device):
    """
    Evaluates a trained Heat FNO model across:
    1. test_interpolation.npz
    2. test_ood.npz partitioned into low-alpha (<0.01) and high-alpha (>1.0)
    3. Sensor layout interior MAE (x in [0.2, 0.8], t in [0.01, 1.0])
    4. Deterministic Mode 3 sigma=0 bias floor at alpha in {0.005, 0.100, 2.500}
    """
    model.eval()
    
    # Grid specification
    Nx, Nt = 50, 100
    x_grid = np.linspace(0, 1, Nx)
    t_grid = np.linspace(0, 1, Nt)
    t_mesh, x_mesh = np.meshgrid(t_grid, x_grid, indexing='ij')
    t_tensor = torch.tensor(2 * t_mesh - 1, dtype=torch.float32).to(device)
    x_tensor = torch.tensor(2 * x_mesh - 1, dtype=torch.float32).to(device)
    
    # 1. Evaluate test splits
    def eval_npz(filepath):
        data = np.load(filepath)
        u_arr = data['u']
        alphas = data['alpha']
        
        rel_l2_list = []
        t0_mae_list = []
        t1_mae_list = []
        sensor_mae_list = []
        
        # Sensor interior mask: x in [0.2, 0.8], t in [0.01, 1.0]
        x_mask = (x_grid >= 0.2) & (x_grid <= 0.8)
        t_mask = (t_grid >= 0.01) & (t_grid <= 1.0)
        sensor_box = np.outer(t_mask, x_mask)
        
        with torch.no_grad():
            for i in range(len(alphas)):
                a = float(alphas[i])
                y_true = u_arr[i]
                
                a_sc = (np.log10(a) - log_alpha_mean) / log_alpha_std
                a_tensor = torch.full_like(t_tensor, a_sc)
                inp = torch.stack([t_tensor, x_tensor, a_tensor], dim=0).unsqueeze(0)
                
                pred = model(inp).squeeze(0).squeeze(0).cpu().numpy()
                diff = pred - y_true
                
                rel_l2 = np.linalg.norm(diff) / np.linalg.norm(y_true)
                t0_mae = np.mean(np.abs(diff[0, :]))
                t1_mae = np.mean(np.abs(diff[-1, :]))
                s_mae = np.mean(np.abs(diff[sensor_box]))
                
                rel_l2_list.append(rel_l2)
                t0_mae_list.append(t0_mae)
                t1_mae_list.append(t1_mae)
                sensor_mae_list.append(s_mae)
                
        return {
            "alphas": alphas,
            "rel_l2": np.array(rel_l2_list),
            "t0_mae": np.array(t0_mae_list),
            "t1_mae": np.array(t1_mae_list),
            "sensor_mae": np.array(sensor_mae_list)
        }
        
    interp_res = eval_npz(os.path.join(data_dir, "test_interpolation.npz"))
    ood_res = eval_npz(os.path.join(data_dir, "test_ood.npz"))
    
    # Partition OOD into low-alpha and high-alpha
    low_mask = ood_res["alphas"] < 0.01
    high_mask = ood_res["alphas"] > 1.0
    
    def summarize_metrics(res, mask=None):
        if mask is not None:
            l2 = res["rel_l2"][mask]
            t0 = res["t0_mae"][mask]
            t1 = res["t1_mae"][mask]
            sm = res["sensor_mae"][mask]
        else:
            l2 = res["rel_l2"]
            t0 = res["t0_mae"]
            t1 = res["t1_mae"]
            sm = res["sensor_mae"]
            
        return {
            "rel_l2_median": float(np.median(l2)),
            "rel_l2_p90": float(np.percentile(l2, 90)),
            "rel_l2_max": float(np.max(l2)),
            "t0_mae_median": float(np.median(t0)),
            "t1_mae_median": float(np.median(t1)),
            "sensor_mae_median": float(np.median(sm))
        }
        
    metrics = {
        "test_interpolation": summarize_metrics(interp_res),
        "test_ood_low_alpha": summarize_metrics(ood_res, low_mask),
        "test_ood_high_alpha": summarize_metrics(ood_res, high_mask)
    }
    
    # 2. Mode 3 Deterministic Sigma=0 Bias Floor
    # Evaluate precomputed grid: 350 points in [-3.0, 1.0]
    grid_la = np.linspace(-3.0, 1.0, 350)
    a_sc_grid = (grid_la - log_alpha_mean) / log_alpha_std
    
    fno_slices = []
    with torch.no_grad():
        for b in range(0, 350, 50):
            b_sc = a_sc_grid[b:b+50]
            inp_batch = []
            for sc in b_sc:
                inp_batch.append(torch.stack([t_tensor, x_tensor, torch.full_like(t_tensor, sc)], dim=0))
            inp_batch = torch.stack(inp_batch, dim=0)
            out_b = model(inp_batch).squeeze(1).cpu().numpy()
            fno_slices.append(out_b)
    fno_grid = np.concatenate(fno_slices, axis=0) # (350, 100, 50)
    
    # Standard 10-sensor layout matching definitive benchmark
    np.random.seed(42) # fixed layout coordinates
    t_sensors = np.logspace(np.log10(0.01), np.log10(1.0), 10)
    x_sensors = np.random.uniform(0.1, 0.9, size=10)
    t_idx = [np.argmin(np.abs(t_grid - t)) for t in t_sensors]
    x_idx = [np.argmin(np.abs(x_grid - x)) for x in x_sensors]
    
    cs = CubicSpline(grid_la, fno_grid[:, t_idx, x_idx], axis=0)
    
    mode3_bias_floor = {}
    for a_val in [0.005, 0.100, 2.500]:
        y_exact = solve_heat_1d_exact(x_sensors, t_sensors, a_val)
        res = opt.minimize_scalar(lambda la: np.mean((cs(la) - y_exact)**2), bounds=(-3.0, 1.0), method='bounded')
        hat_a = float(10**res.x)
        rel_err = float(abs(hat_a - a_val) / a_val)
        mode3_bias_floor[str(a_val)] = {
            "alpha_hat": hat_a,
            "rel_error": rel_err
        }
        
    metrics["mode3_sigma0_bias_floor"] = mode3_bias_floor
    return metrics

def train_single_seed(seed, epochs, batch_size, lr, weight_decay, device, data_dir, out_dir, resume=False):
    os.makedirs(out_dir, exist_ok=True)
    best_model_path = os.path.join(out_dir, f"fno2d_heat_seed{seed}_best.pt")
    curves_path = os.path.join(out_dir, f"curves_heat_seed{seed}.csv")
    metrics_path = os.path.join(out_dir, f"metrics_heat_seed{seed}.json")
    
    if resume and os.path.exists(metrics_path) and os.path.exists(best_model_path):
        print(f"Seed {seed} already completed. Resuming (skipping training).")
        with open(metrics_path, "r") as f:
            return json.load(f)
            
    # Set seeds
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        
    train_dataset = HeatEquationDataset(os.path.join(data_dir, 'train.npz'))
    val_dataset = HeatEquationDataset(os.path.join(data_dir, 'val.npz'), 
                                      log_alpha_mean=train_dataset.log_alpha_mean, 
                                      log_alpha_std=train_dataset.log_alpha_std)
                                      
    g = torch.Generator()
    g.manual_seed(seed)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, generator=g)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # Explicit use_hard_mask=False
    model = FNO2d(modes1=16, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=False).to(device)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.5)
    
    curves = []
    best_val_rel_l2 = float('inf')
    best_epoch = 0
    t_start = time.time()
    
    print(f"\n--- Training Seed {seed} for {epochs} epochs on {device} ---")
    for epoch in range(epochs):
        t_ep = time.time()
        model.train()
        train_l2_sum = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            out = model(x)
            loss = rel_l2_loss(out, y)
            loss.backward()
            optimizer.step()
            train_l2_sum += loss.item() * len(x)
            
        train_l2 = train_l2_sum / len(train_dataset)
        
        model.eval()
        val_l2_sum = 0.0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                out = model(x)
                loss = rel_l2_loss(out, y)
                val_l2_sum += loss.item() * len(x)
        val_l2 = val_l2_sum / len(val_dataset)
        
        scheduler.step()
        ep_sec = time.time() - t_ep
        
        curves.append({
            "epoch": epoch,
            "train_rel_l2": train_l2,
            "val_rel_l2": val_l2,
            "lr": scheduler.get_last_lr()[0],
            "epoch_sec": ep_sec
        })
        
        if val_l2 < best_val_rel_l2:
            best_val_rel_l2 = val_l2
            best_epoch = epoch
            torch.save({
                "model_state_dict": model.state_dict(),
                "log_alpha_mean": train_dataset.log_alpha_mean,
                "log_alpha_std": train_dataset.log_alpha_std,
                "use_hard_mask": False,
                "epoch": epoch,
                "val_rel_l2": val_l2,
                "seed": seed
            }, best_model_path)
            
        if (epoch + 1) % 25 == 0 or epoch == 0:
            print(f"Epoch {epoch+1:3d}/{epochs} | Train L2: {train_l2:.4f} | Val L2: {val_l2:.4f} | Best Val: {best_val_rel_l2:.4f} (ep {best_epoch})")
            
    total_sec = time.time() - t_start
    
    # Save curves CSV
    with open(curves_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["epoch", "train_rel_l2", "val_rel_l2", "lr", "epoch_sec"])
        writer.writeheader()
        writer.writerows(curves)
        
    print(f"Seed {seed} finished in {total_sec:.1f}s. Evaluating best checkpoint...")
    
    # Comprehensive evaluation of best checkpoint
    best_ckpt = torch.load(best_model_path, map_location=device)
    model.load_state_dict(best_ckpt["model_state_dict"])
    
    metrics = evaluate_model_comprehensive(model, train_dataset.log_alpha_mean, train_dataset.log_alpha_std, data_dir, device)
    metrics["seed"] = seed
    metrics["best_epoch"] = best_epoch
    metrics["best_val_rel_l2"] = best_val_rel_l2
    metrics["total_train_sec"] = total_sec
    
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics to {metrics_path}")
    
    return metrics

def evaluate_frozen_baseline(data_dir, out_dir, device):
    """
    Evaluates the committed models/fno2d_heat.pt through the identical evaluation protocol
    for direct apples-to-apples stability positioning.
    """
    frozen_ckpt_path = os.path.join(base_dir, "models", "fno2d_heat.pt")
    if not os.path.exists(frozen_ckpt_path):
        print(f"Warning: Frozen checkpoint {frozen_ckpt_path} not found.")
        return None
        
    print("\n--- Evaluating Frozen Baseline models/fno2d_heat.pt ---")
    ckpt = torch.load(frozen_ckpt_path, map_location=device)
    model = FNO2d(modes1=16, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=False).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    
    lm = ckpt["log_alpha_mean"].item() if torch.is_tensor(ckpt["log_alpha_mean"]) else ckpt["log_alpha_mean"]
    ls = ckpt["log_alpha_std"].item() if torch.is_tensor(ckpt["log_alpha_std"]) else ckpt["log_alpha_std"]
    
    frozen_metrics = evaluate_model_comprehensive(model, lm, ls, data_dir, device)
    frozen_metrics["model"] = "models/fno2d_heat.pt (frozen baseline)"
    
    out_path = os.path.join(out_dir, "metrics_heat_frozen.json")
    with open(out_path, "w") as f:
        json.dump(frozen_metrics, f, indent=2)
    print(f"Saved frozen reference metrics to {out_path}")
    return frozen_metrics

def main():
    parser = argparse.ArgumentParser(description="Heat FNO Multi-Seed Training Runner")
    parser.add_argument("--seed", type=int, default=None, help="Train single seed")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46], help="Seeds list")
    parser.add_argument("--device", type=str, default="auto", help="auto, cuda, cpu")
    parser.add_argument("--data-dir", type=str, default="data/datasets", help="Path to heat datasets")
    parser.add_argument("--out-dir", type=str, default="models/fno_heat_seeds", help="Output directory")
    parser.add_argument("--epochs", type=int, default=100, help="Epochs")
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--weight-decay", type=float, default=1e-4, help="Weight decay")
    parser.add_argument("--resume", action="store_true", help="Resume completed seeds")
    args = parser.parse_args()
    
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
        
    data_dir = os.path.abspath(args.data_dir)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Save manifest
    manifest = get_env_manifest(device, data_dir)
    manifest_path = os.path.join(out_dir, "fno_heat_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Environment manifest saved to {manifest_path}")
    
    # 2. Evaluate frozen baseline
    frozen_res = evaluate_frozen_baseline(data_dir, out_dir, device)
    
    # 3. Train seeds
    seeds = [args.seed] if args.seed is not None else args.seeds
    cohort_results = []
    
    for s in seeds:
        res = train_single_seed(s, args.epochs, args.batch_size, args.lr, args.weight_decay, device, data_dir, out_dir, args.resume)
        cohort_results.append(res)
        
    # 4. Cohort Stability Summary
    if len(cohort_results) > 1:
        interp_meds = [r["test_interpolation"]["rel_l2_median"] for r in cohort_results]
        low_meds = [r["test_ood_low_alpha"]["rel_l2_median"] for r in cohort_results]
        high_meds = [r["test_ood_high_alpha"]["rel_l2_median"] for r in cohort_results]
        
        summary = {
            "test_interpolation": {
                "mean": float(np.mean(interp_meds)),
                "std": float(np.std(interp_meds)),
                "min": float(np.min(interp_meds)),
                "max": float(np.max(interp_meds)),
                "spread_ratio": float(np.max(interp_meds) / np.min(interp_meds))
            },
            "test_ood_low_alpha": {
                "mean": float(np.mean(low_meds)),
                "std": float(np.std(low_meds)),
                "min": float(np.min(low_meds)),
                "max": float(np.max(low_meds)),
                "spread_ratio": float(np.max(low_meds) / np.min(low_meds))
            },
            "test_ood_high_alpha": {
                "mean": float(np.mean(high_meds)),
                "std": float(np.std(high_meds)),
                "min": float(np.min(high_meds)),
                "max": float(np.max(high_meds)),
                "spread_ratio": float(np.max(high_meds) / np.min(high_meds))
            }
        }
        if frozen_res:
            summary["frozen_baseline_comparison"] = {
                "frozen_interp_median": frozen_res["test_interpolation"]["rel_l2_median"],
                "frozen_low_alpha_median": frozen_res["test_ood_low_alpha"]["rel_l2_median"],
                "frozen_high_alpha_median": frozen_res["test_ood_high_alpha"]["rel_l2_median"]
            }
            
        summary_path = os.path.join(out_dir, "heat_fno_seeds_stability_summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nCohort Stability Summary saved to {summary_path}")

if __name__ == "__main__":
    main()
