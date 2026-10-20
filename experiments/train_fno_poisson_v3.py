"""
FNO v3 Training and Verification Script (Colab & Local Multi-Seed Runner)
Architecture: FNO2d (width=64, modes=16, use_hard_mask=True)
Dataset: Poisson v2 (1000 train, 100 val, 5 test splits)
Scheduler: CosineAnnealingLR up to 300 epochs with Early Stopping on validation loss.

Acceptance Rule:
  Accept v3 ONLY IF:
    1. Val median relative L2 improves by >= 2x vs v2 (<= 0.016728 vs v2's 0.033455)
    2. AND all OOD medians are no worse than v2:
         narrow <= 0.090019
         count <= 0.027709
         boundary <= 0.141791
         highmodes <= 0.804159
  Otherwise: Freeze v2.
"""

import os
import sys
import time
import json
import csv
import argparse
import platform
from datetime import datetime, timezone

import torch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.models.fno2d import FNO2d, rel_l2_loss
from src.solvers.poisson_2d import Poisson2DSolver
from src.data.poisson_loader import get_dataloader, load_all_splits
from src.eval_poisson_v2 import compute_field_metrics
from src.train_fno_poisson_v2 import h1_loss_2d, combined_h1_l2_loss

# v2 reference baselines for acceptance check
V2_BASELINES = {
    "val_l2_med": 0.03345513343811035,
    "narrow_l2_med": 0.09001921862363815,
    "count_l2_med": 0.02770945057272911,
    "boundary_l2_med": 0.14179149270057678,
    "highmodes_l2_med": 0.8041586875915527
}

def get_env_manifest(device):
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
        "numpy_version": np.__version__
    }
    return manifest

def train_single_seed(
    seed,
    data_dir,
    out_dir,
    device,
    epochs=300,
    patience=25,
    lr=2e-3,
    modes=16,
    width=64,
    batch_size=32,
    resume=False
):
    print(f"\n=======================================================")
    print(f"=== Starting FNO v3 Training: Seed {seed} ===")
    print(f"=======================================================")
    
    torch.manual_seed(seed)
    np.random.seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
        
    os.makedirs(out_dir, exist_ok=True)
    best_model_path = os.path.join(out_dir, f"fno2d_v3_seed{seed}_best.pt")
    curves_csv_path = os.path.join(out_dir, f"curves_v3_seed{seed}.csv")
    
    train_path = os.path.join(data_dir, "poisson_v2_train.npz")
    val_path = os.path.join(data_dir, "poisson_v2_val.npz")
    
    train_loader = get_dataloader(train_path, batch_size=batch_size, shuffle=True)
    val_loader = get_dataloader(val_path, batch_size=batch_size, shuffle=False)
    
    model = FNO2d(modes1=modes, modes2=modes, width=width, in_channels=3, out_channels=1, use_hard_mask=True).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    
    start_epoch = 1
    best_val_l2 = float("inf")
    best_epoch = 1
    patience_counter = 0
    curves = []
    
    # Resume support
    if resume and os.path.exists(best_model_path) and os.path.exists(curves_csv_path):
        print(f"Resuming from existing run at {best_model_path}...")
        with open(curves_csv_path, "r") as f:
            curves = list(csv.DictReader(f))
        if curves:
            start_epoch = int(curves[-1]["epoch"]) + 1
            best_val_l2 = min(float(c["val_rel_l2"]) for c in curves)
            best_epoch = [int(c["epoch"]) for c in curves if float(c["val_rel_l2"]) == best_val_l2][0]
            print(f"Resuming at epoch {start_epoch}. Prior best Val Rel L2 = {best_val_l2:.4e} at epoch {best_epoch}.")
            
    t_start = time.time()
    
    for epoch in range(start_epoch, epochs + 1):
        t_ep_start = time.time()
        model.train()
        train_l2_sum, train_h1_sum, train_count = 0.0, 0.0, 0
        
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            pred = model(x)
            loss, l2, h1 = combined_h1_l2_loss(pred, y, beta=0.1)
            loss.backward()
            optimizer.step()
            
            train_l2_sum += l2.item() * len(x)
            train_h1_sum += h1.item() * len(x)
            train_count += len(x)
            
        train_l2 = train_l2_sum / train_count
        train_h1 = train_h1_sum / train_count
        train_tot = train_l2 + 0.1 * train_h1
        scheduler.step()
        
        # Validation evaluation (strictly val set, no test sets!)
        model.eval()
        val_l2_sum, val_h1_sum, val_count = 0.0, 0.0, 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                pred = model(x)
                _, l2_v, h1_v = combined_h1_l2_loss(pred, y, beta=0.1)
                val_l2_sum += l2_v.item() * len(x)
                val_h1_sum += h1_v.item() * len(x)
                val_count += len(x)
                
        val_l2 = val_l2_sum / val_count
        val_h1 = val_h1_sum / val_count
        val_tot = val_l2 + 0.1 * val_h1
        ep_duration = time.time() - t_ep_start
        
        curves.append({
            "epoch": epoch,
            "train_total": train_tot,
            "train_rel_l2": train_l2,
            "train_rel_h1": train_h1,
            "val_total": val_tot,
            "val_rel_l2": val_l2,
            "val_rel_h1": val_h1,
            "lr": scheduler.get_last_lr()[0],
            "epoch_time_s": ep_duration
        })
        
        if val_l2 < best_val_l2 - 1e-5:
            best_val_l2 = val_l2
            best_epoch = epoch
            patience_counter = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_rel_l2": val_l2,
                "modes": modes,
                "width": width,
                "seed": seed,
                "use_hard_mask": True
            }, best_model_path)
            flag = "*"
        else:
            patience_counter += 1
            flag = " "
            
        if epoch % 10 == 0 or epoch == 1 or flag == "*":
            print(f"Epoch {epoch:3d}/{epochs} | Train L2: {train_l2:.4e} | Val L2: {val_l2:.4e} | {ep_duration:.1f}s {flag}")
            
        if patience_counter >= patience:
            print(f"\n[Early Stopping] Triggered at epoch {epoch}. Best Val L2 = {best_val_l2:.4e} at epoch {best_epoch}.")
            break
            
    total_train_sec = time.time() - t_start
    
    # Save curves CSV
    with open(curves_csv_path, "w", newline="") as f:
        fieldnames = ["epoch", "train_total", "train_rel_l2", "train_rel_h1", "val_total", "val_rel_l2", "val_rel_h1", "lr", "epoch_time_s"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(curves)
        
    print(f"Seed {seed} finished in {total_train_sec:.1f}s. Evaluating best checkpoint on all splits...")
    
    # Load best checkpoint for post-hoc evaluation
    ckpt = torch.load(best_model_path, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    
    splits = load_all_splits(data_dir, version="v2")
    N = splits["train"]["grid_x"].shape[0]
    h = 1.0 / (N - 1)
    
    grid_x = splits["train"]["grid_x"]
    grid_y = splits["train"]["grid_y"]
    X, Y = np.meshgrid(grid_x, grid_y, indexing='ij')
    coords = torch.from_numpy(np.stack([X, Y], axis=0)).float().to(device)
    
    eval_metrics = {}
    for split_name, data in splits.items():
        F = data["F"]
        U = data["U"]
        M = len(F)
        
        preds = []
        batch_sz = 32
        with torch.no_grad():
            for b in range(0, M, batch_sz):
                f_batch = torch.from_numpy(F[b:b+batch_sz]).unsqueeze(1).float().to(device)
                c_batch = coords.unsqueeze(0).repeat(len(f_batch), 1, 1, 1)
                inp = torch.cat([f_batch, c_batch], dim=1)
                pred = model(inp)
                preds.append(pred.squeeze(1).cpu().numpy())
                
        U_pred = np.concatenate(preds, axis=0)
        m = compute_field_metrics(U_pred, U, F, h)
        eval_metrics[split_name] = {
            "rel_l2_median": m["rel_l2_median"],
            "rel_l2_p90": m["rel_l2_p90"],
            "rel_l2_max": m["rel_l2_max"],
            "res_median": m["res_median"]
        }
        
    return {
        "seed": seed,
        "best_epoch": best_epoch,
        "best_val_l2": best_val_l2,
        "total_train_sec": total_train_sec,
        "metrics": eval_metrics
    }

def main():
    parser = argparse.ArgumentParser(description="FNO v3 Multi-Seed Training & Acceptance Runner")
    parser.add_argument("--seed", type=int, default=None, help="Run single seed if specified")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46], help="List of 5 seeds")
    parser.add_argument("--device", type=str, default="auto", help="Device: cuda, cpu, or auto")
    parser.add_argument("--data-dir", type=str, default="data/datasets", help="Path to v2 npz datasets")
    parser.add_argument("--out-dir", type=str, default="models/fno_v3", help="Output directory")
    parser.add_argument("--epochs", type=int, default=300, help="Max epochs")
    parser.add_argument("--patience", type=int, default=25, help="Early stopping patience")
    parser.add_argument("--lr", type=float, default=2e-3, help="Initial learning rate")
    parser.add_argument("--modes", type=int, default=16, help="Fourier modes (default: 16)")
    parser.add_argument("--width", type=int, default=64, help="Channel width (default: 64)")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--resume", action="store_true", help="Resume from existing progress")
    args = parser.parse_args()
    
    if args.device == "auto":
        dev_str = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        dev_str = args.device
    device = torch.device(dev_str)
    
    os.makedirs(args.out_dir, exist_ok=True)
    
    # Save environment & hardware manifest
    manifest = get_env_manifest(device)
    manifest_path = os.path.join(args.out_dir, "fno_v3_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Environment manifest saved to: {manifest_path}")
    print(f"Running on Device: {manifest['device_name']} ({manifest['torch_version']}, CUDA: {manifest['cuda_version']})")
    
    seeds_to_run = [args.seed] if args.seed is not None else args.seeds
    seed_results = []
    
    for s in seeds_to_run:
        res = train_single_seed(
            seed=s,
            data_dir=args.data_dir,
            out_dir=args.out_dir,
            device=device,
            epochs=args.epochs,
            patience=args.patience,
            lr=args.lr,
            modes=args.modes,
            width=args.width,
            batch_size=args.batch_size,
            resume=args.resume
        )
        seed_results.append(res)
        
    # Aggregate multi-seed results
    print("\n" + "="*80)
    print("=== FNO v3 Multi-Seed Results Summary ===")
    print("="*80)
    
    splits_order = ["val", "test_interp", "test_ood_narrow", "test_ood_count", "test_ood_boundary", "test_ood_highmodes"]
    
    # Print per-seed table
    print(f"{'Seed':<6} | {'Split':<20} | {'Rel L2 Med':<12} | {'Rel L2 P90':<12} | {'Rel L2 Max':<12} | {'PDE Res Med':<12}")
    print("-" * 80)
    for sr in seed_results:
        s = sr["seed"]
        for sp in splits_order:
            m = sr["metrics"][sp]
            print(f"{s:<6} | {sp:<20} | {m['rel_l2_median']:.6f}     | {m['rel_l2_p90']:.6f}     | {m['rel_l2_max']:.6f}     | {m['res_median']:.6f}")
        print("-" * 80)
        
    # Compute seed spread across splits
    spread_summary = {}
    for sp in splits_order:
        meds = [sr["metrics"][sp]["rel_l2_median"] for sr in seed_results]
        p90s = [sr["metrics"][sp]["rel_l2_p90"] for sr in seed_results]
        maxs = [sr["metrics"][sp]["rel_l2_max"] for sr in seed_results]
        ress = [sr["metrics"][sp]["res_median"] for sr in seed_results]
        
        spread_summary[sp] = {
            "l2_med_mean": float(np.mean(meds)),
            "l2_med_std": float(np.std(meds)),
            "l2_med_min": float(np.min(meds)),
            "l2_med_max": float(np.max(meds)),
            "l2_p90_mean": float(np.mean(p90s)),
            "l2_max_mean": float(np.mean(maxs)),
            "res_med_mean": float(np.mean(ress))
        }
        
    print("\n=== Multi-Seed Aggregated Statistics (Mean +/- Std across seeds) ===")
    for sp, ss in spread_summary.items():
        print(f"  {sp:<20}: L2 Med = {ss['l2_med_mean']:.6f} +/- {ss['l2_med_std']:.6f} | P90 = {ss['l2_p90_mean']:.6f} | Res = {ss['res_med_mean']:.6f}")
        
    # Evaluate Hard Acceptance Criteria
    mean_val_med = spread_summary["val"]["l2_med_mean"]
    mean_narrow_med = spread_summary["test_ood_narrow"]["l2_med_mean"]
    mean_count_med = spread_summary["test_ood_count"]["l2_med_mean"]
    mean_boundary_med = spread_summary["test_ood_boundary"]["l2_med_mean"]
    mean_highmodes_med = spread_summary["test_ood_highmodes"]["l2_med_mean"]
    
    val_target = V2_BASELINES["val_l2_med"] / 2.0
    cond_val = mean_val_med <= val_target
    cond_narrow = mean_narrow_med <= V2_BASELINES["narrow_l2_med"]
    cond_count = mean_count_med <= V2_BASELINES["count_l2_med"]
    cond_boundary = mean_boundary_med <= V2_BASELINES["boundary_l2_med"]
    cond_highmodes = mean_highmodes_med <= V2_BASELINES["highmodes_l2_med"]
    
    accepted = cond_val and cond_narrow and cond_count and cond_boundary and cond_highmodes
    
    print("\n" + "="*80)
    print("=== ACCEPTANCE RULE EVALUATION ===")
    print("="*80)
    print(f"1. Val Median Improvement: {mean_val_med:.6f} vs Target <= {val_target:.6f} (2x vs v2 {V2_BASELINES['val_l2_med']:.6f}) -> {'PASS' if cond_val else 'FAIL'}")
    print(f"2. OOD Narrow Check      : {mean_narrow_med:.6f} vs v2 {V2_BASELINES['narrow_l2_med']:.6f} -> {'PASS' if cond_narrow else 'FAIL'}")
    print(f"3. OOD Count Check       : {mean_count_med:.6f} vs v2 {V2_BASELINES['count_l2_med']:.6f} -> {'PASS' if cond_count else 'FAIL'}")
    print(f"4. OOD Boundary Check    : {mean_boundary_med:.6f} vs v2 {V2_BASELINES['boundary_l2_med']:.6f} -> {'PASS' if cond_boundary else 'FAIL'}")
    print(f"5. OOD Highmodes Check   : {mean_highmodes_med:.6f} vs v2 {V2_BASELINES['highmodes_l2_med']:.6f} -> {'PASS' if cond_highmodes else 'FAIL'}")
    print("-" * 80)
    
    if accepted:
        decision_verdict = "ACCEPTED: FNO v3 surpasses all acceptance criteria (val improved by >=2x without OOD regression)."
    else:
        decision_verdict = "REJECTED: Acceptance rule not satisfied. Freezing Poisson FNO v2 as the final model."
    print(f"VERDICT: {decision_verdict}\n")
    
    # Save summary report JSON
    final_report = {
        "acceptance_verdict": decision_verdict,
        "accepted": bool(accepted),
        "v2_baselines": V2_BASELINES,
        "criteria_eval": {
            "val_2x_improvement": bool(cond_val),
            "ood_narrow_no_worse": bool(cond_narrow),
            "ood_count_no_worse": bool(cond_count),
            "ood_boundary_no_worse": bool(cond_boundary),
            "ood_highmodes_no_worse": bool(cond_highmodes)
        },
        "spread_summary": spread_summary,
        "per_seed_results": seed_results,
        "manifest": manifest
    }
    
    report_json_path = os.path.join(args.out_dir, "fno_v3_acceptance_report.json")
    with open(report_json_path, "w") as f:
        json.dump(final_report, f, indent=2)
    print(f"Full acceptance report saved to: {report_json_path}")

if __name__ == "__main__":
    main()
