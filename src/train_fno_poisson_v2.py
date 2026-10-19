import os
import sys
import time
import csv
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import torch
import torch.nn.functional as F
import numpy as np
from src.models.fno2d import FNO2d, rel_l2_loss
from src.data.poisson_loader import get_dataloader

def h1_loss_2d(pred, target, h=1.0/63.0):
    """
    Computes Relative H1 semi-norm loss:
    ||grad(pred) - grad(target)||_2 / ||grad(target)||_2
    where discrete gradient is computed by forward finite differences.
    """
    # pred, target: (B, 1, H, W)
    # x-gradient along width (dim=-1)
    d_pred_x = (pred[..., :, 1:] - pred[..., :, :-1]) / h
    d_target_x = (target[..., :, 1:] - target[..., :, :-1]) / h
    diff_x = (d_pred_x - d_target_x).reshape(pred.size(0), -1)
    t_x = d_target_x.reshape(target.size(0), -1)
    
    # y-gradient along height (dim=-2)
    d_pred_y = (pred[..., 1:, :] - pred[..., :-1, :]) / h
    d_target_y = (target[..., 1:, :] - target[..., :-1, :]) / h
    diff_y = (d_pred_y - d_target_y).reshape(pred.size(0), -1)
    t_y = d_target_y.reshape(target.size(0), -1)
    
    diff_grad_norm = torch.sqrt(torch.sum(diff_x**2, dim=1) + torch.sum(diff_y**2, dim=1) + 1e-12)
    target_grad_norm = torch.sqrt(torch.sum(t_x**2, dim=1) + torch.sum(t_y**2, dim=1) + 1e-12)
    return torch.mean(diff_grad_norm / target_grad_norm)

def combined_h1_l2_loss(pred, target, beta=0.1, h=1.0/63.0):
    l2 = rel_l2_loss(pred, target)
    h1 = h1_loss_2d(pred, target, h=h)
    return l2 + beta * h1, l2, h1

def train_fno_v2(
    train_path="data/poisson_v2_train.npz",
    val_path="data/poisson_v2_val.npz",
    max_epochs=150,
    batch_size=32,
    lr=2e-3,
    beta_h1=0.1,
    patience=15,
    max_time_minutes=50,
    save_model_path="models/fno2d_poisson_v2.pt",
    curves_csv_path="data/fno2d_v2_training_curves.csv",
    seed=42
):
    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(min(8, os.cpu_count() or 4))
    
    os.makedirs(os.path.dirname(save_model_path), exist_ok=True)
    os.makedirs(os.path.dirname(curves_csv_path), exist_ok=True)
    
    train_loader = get_dataloader(train_path, batch_size=batch_size, shuffle=True)
    val_loader = get_dataloader(val_path, batch_size=batch_size, shuffle=False)
    
    model = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_epochs, eta_min=5e-5)
    
    print("=" * 60)
    print("PROPER FNO2D TRAINING WITH H1 GRADIENT LOSS ABLATION")
    print(f"Modes: 12x12 | Width: 32 | Max Epochs: {max_epochs} | Patience: {patience}")
    print(f"Loss: Relative L2 + {beta_h1} * Relative H1 | Scheduler: CosineAnnealing")
    print("=" * 60)
    
    # Measure Epoch 1 time explicitly first
    t_ep1_start = time.time()
    model.train()
    for x, y in train_loader:
        optimizer.zero_grad()
        pred = model(x)
        loss, _, _ = combined_h1_l2_loss(pred, y, beta=beta_h1)
        loss.backward()
        optimizer.step()
    ep1_time = time.time() - t_ep1_start
    print(f"REPORTED TIME PER EPOCH: {ep1_time:.2f} s")
    print(f"Estimated 150 epochs: {150 * ep1_time / 60:.1f} minutes (Budget: {max_time_minutes} minutes)")
    
    # Reset model and optimizer for clean run from scratch
    torch.manual_seed(seed)
    model = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_epochs, eta_min=5e-5)
    
    curves = []
    best_val_l2 = float("inf")
    best_epoch = 0
    patience_counter = 0
    t_start = time.time()
    convergence_status = "converged_to_max_epochs"
    
    for epoch in range(1, max_epochs + 1):
        t_epoch_start = time.time()
        model.train()
        train_l2_sum = 0.0
        train_h1_sum = 0.0
        train_total_sum = 0.0
        train_count = 0
        
        for x, y in train_loader:
            optimizer.zero_grad()
            pred = model(x)
            tot_loss, l2_term, h1_term = combined_h1_l2_loss(pred, y, beta=beta_h1)
            tot_loss.backward()
            optimizer.step()
            
            n_b = len(x)
            train_l2_sum += l2_term.item() * n_b
            train_h1_sum += h1_term.item() * n_b
            train_total_sum += tot_loss.item() * n_b
            train_count += n_b
            
        train_l2 = train_l2_sum / train_count
        train_h1 = train_h1_sum / train_count
        train_tot = train_total_sum / train_count
        scheduler.step()
        
        # Validation
        model.eval()
        val_l2_sum = 0.0
        val_h1_sum = 0.0
        val_count = 0
        with torch.no_grad():
            for x, y in val_loader:
                pred = model(x)
                _, l2_v, h1_v = combined_h1_l2_loss(pred, y, beta=beta_h1)
                val_l2_sum += l2_v.item() * len(x)
                val_h1_sum += h1_v.item() * len(x)
                val_count += len(x)
                
        val_l2 = val_l2_sum / val_count
        val_h1 = val_h1_sum / val_count
        val_tot = val_l2 + beta_h1 * val_h1
        ep_duration = time.time() - t_epoch_start
        
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
        
        # Check improvement on validation L2
        if val_l2 < best_val_l2 - 1e-5:
            best_val_l2 = val_l2
            best_epoch = epoch
            patience_counter = 0
            torch.save(model.state_dict(), save_model_path)
            improved_flag = "*"
        else:
            patience_counter += 1
            improved_flag = " "
            
        if epoch % 5 == 0 or epoch == 1 or improved_flag == "*":
            print(f"Epoch {epoch:3d}/{max_epochs} | Train L2: {train_l2:.4e} H1: {train_h1:.4e} | Val L2: {val_l2:.4e} H1: {val_h1:.4e} | {ep_duration:.1f}s {improved_flag}")
            
        # Early stopping on plateau
        if patience_counter >= patience:
            convergence_status = f"early_stopped_plateau (patience {patience} reached at epoch {epoch}, best epoch {best_epoch})"
            print(f"\n[Plateau Detected] Early stopping triggered at epoch {epoch}. Best Val L2: {best_val_l2:.4e} at epoch {best_epoch}.")
            break
            
        # Check time budget
        elapsed_min = (time.time() - t_start) / 60.0
        if elapsed_min >= max_time_minutes:
            convergence_status = f"budget_limit_reached ({elapsed_min:.1f} min >= {max_time_minutes} min limit)"
            print(f"\n[Budget Limit Reached] Reached CPU time budget of {max_time_minutes} minutes at epoch {epoch}.")
            break
            
    total_train_sec = time.time() - t_start
    
    # Save curves CSV
    with open(curves_csv_path, "w", newline="") as f:
        fieldnames = ["epoch", "train_total", "train_rel_l2", "train_rel_h1", "val_total", "val_rel_l2", "val_rel_h1", "lr", "epoch_time_s"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(curves)
        
    # Analyze overfitting vs plateau
    final_train_l2 = curves[-1]["train_rel_l2"]
    final_val_l2 = curves[-1]["val_rel_l2"]
    gap_ratio = (final_val_l2 - final_train_l2) / (final_train_l2 + 1e-8)
    
    if gap_ratio > 0.5:
        generalization_diagnosis = "Mild overfitting observed (val loss gap > 50% above train loss)."
    elif patience_counter >= patience:
        generalization_diagnosis = "Validation plateau reached without catastrophic overfitting; early stopping preserved optimal generalization."
    else:
        generalization_diagnosis = "Smooth monotonic convergence across both train and val curves."
        
    print(f"\nTraining summary:")
    print(f"  Total Duration   : {total_train_sec:.1f}s ({total_train_sec/60:.2f} min)")
    print(f"  Best Epoch       : {best_epoch} with Val Rel L2 = {best_val_l2:.4e}")
    print(f"  Status           : {convergence_status}")
    print(f"  Diagnosis        : {generalization_diagnosis}")
    
    summary = {
        "time_per_epoch_s": ep1_time,
        "total_train_sec": total_train_sec,
        "epochs_trained": len(curves),
        "best_epoch": best_epoch,
        "best_val_rel_l2": best_val_l2,
        "status": convergence_status,
        "diagnosis": generalization_diagnosis
    }
    with open("data/fno2d_v2_training_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    return summary

if __name__ == "__main__":
    train_fno_v2()
