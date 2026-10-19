import os
import sys
import time
import csv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import torch
import numpy as np
from src.models.fno2d import FNO2d, rel_l2_loss
from src.data.poisson_loader import get_dataloader

def train_fno(
    train_path="data/poisson_train.npz",
    val_path="data/poisson_val.npz",
    epochs=15,
    batch_size=32,
    lr=2e-3,
    save_model_path="models/fno2d_poisson.pt",
    log_csv_path="data/fno2d_training_log.csv",
    seed=42
):
    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(min(8, os.cpu_count() or 4))
    
    os.makedirs(os.path.dirname(save_model_path), exist_ok=True)
    os.makedirs(os.path.dirname(log_csv_path), exist_ok=True)
    
    train_loader = get_dataloader(train_path, batch_size=batch_size, shuffle=True)
    val_loader = get_dataloader(val_path, batch_size=batch_size, shuffle=False)
    
    model = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-4)
    
    print(f"--- Starting FNO2d Training ---")
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Epochs: {epochs}, Batch size: {batch_size}, LR: {lr}")
    
    log_rows = []
    best_val_loss = float("inf")
    t_start = time.time()
    
    for epoch in range(1, epochs + 1):
        t_epoch_start = time.time()
        model.train()
        train_loss_sum = 0.0
        train_count = 0
        
        for x, y in train_loader:
            optimizer.zero_grad()
            pred = model(x)
            loss = rel_l2_loss(pred, y)
            loss.backward()
            optimizer.step()
            
            train_loss_sum += loss.item() * len(x)
            train_count += len(x)
            
        train_loss = train_loss_sum / train_count
        scheduler.step()
        
        # Validation
        model.eval()
        val_loss_sum = 0.0
        val_count = 0
        with torch.no_grad():
            for x, y in val_loader:
                pred = model(x)
                loss = rel_l2_loss(pred, y)
                val_loss_sum += loss.item() * len(x)
                val_count += len(x)
        val_loss = val_loss_sum / val_count
        epoch_time = time.time() - t_epoch_start
        
        log_rows.append({
            "epoch": epoch,
            "train_rel_l2": train_loss,
            "val_rel_l2": val_loss,
            "epoch_time_s": epoch_time
        })
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), save_model_path)
            
        print(f"Epoch {epoch:2d}/{epochs:2d} | Train Rel L2: {train_loss:.4e} | Val Rel L2: {val_loss:.4e} | Time: {epoch_time:.2f}s")
        
    total_time = time.time() - t_start
    print(f"Training completed in {total_time:.2f}s! Best Val Rel L2: {best_val_loss:.4e}")
    
    # Save training log
    with open(log_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["epoch", "train_rel_l2", "val_rel_l2", "epoch_time_s"])
        writer.writeheader()
        writer.writerows(log_rows)
        
    return model, log_rows

if __name__ == "__main__":
    train_fno()
