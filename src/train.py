import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d
import json
import matplotlib.pyplot as plt
import numpy as np

def relative_l2_loss(pred, target):
    # 4. Confirming per-sample computation:
    # L2 norm over spatial+temporal dimensions for each sample individually
    diff_norms = torch.norm(pred.view(pred.size(0), -1) - target.view(target.size(0), -1), 2, dim=1)
    target_norms = torch.norm(target.view(target.size(0), -1), 2, dim=1)
    # Average across the batch
    return torch.mean(diff_norms / target_norms)

def relative_l2_per_sample(pred, target):
    diff_norms = torch.norm(pred.view(pred.size(0), -1) - target.view(target.size(0), -1), 2, dim=1)
    target_norms = torch.norm(target.view(target.size(0), -1), 2, dim=1)
    return diff_norms / target_norms, diff_norms

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    base_dir = os.path.dirname(os.path.dirname(__file__))
    try:
        from paths import DATASETS, MODELS, PLOTS
    except ImportError:
        from src.paths import DATASETS, MODELS, PLOTS
    data_dir = str(DATASETS)
    
    print("Loading datasets...")
    train_dataset = HeatEquationDataset(os.path.join(data_dir, 'train.npz'))
    val_dataset = HeatEquationDataset(os.path.join(data_dir, 'val.npz'), 
                                      log_alpha_mean=train_dataset.log_alpha_mean, 
                                      log_alpha_std=train_dataset.log_alpha_std)
                                      
    train_loader = DataLoader(train_dataset, batch_size=20, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=20, shuffle=False)
    
    # Grid is 100x50. Max modes are 50 and 25.
    model = FNO2d(modes1=16, modes2=12, width=32).to(device)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.5)
    
    epochs = 100
    
    print(f"Starting training for {epochs} epochs on {device}...")
    for epoch in range(epochs):
        model.train()
        train_l2 = 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            out = model(x)
            loss = relative_l2_loss(out, y)
            loss.backward()
            optimizer.step()
            train_l2 += loss.item() * x.size(0)
            
        train_l2 /= len(train_dataset)
        
        model.eval()
        val_l2 = 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                out = model(x)
                loss = relative_l2_loss(out, y)
                val_l2 += loss.item() * x.size(0)
        val_l2 /= len(val_dataset)
        
        scheduler.step()
        
        if (epoch+1) % 10 == 0 or epoch == 0:
            print(f"Epoch {epoch+1}/{epochs} | Train Rel-L2: {train_l2:.4f} | Val Rel-L2: {val_l2:.4f}")
            
    # Save the model
    model_dir = os.path.join(base_dir, 'models')
    os.makedirs(model_dir, exist_ok=True)
    torch.save({
        'model_state_dict': model.state_dict(),
        'log_alpha_mean': train_dataset.log_alpha_mean,
        'log_alpha_std': train_dataset.log_alpha_std
    }, os.path.join(model_dir, 'fno2d_heat.pt'))
    print("Training finished and model saved.")
    
    # ---------------- Evaluation ----------------
    print("\nStarting Evaluation on Held-out Sets...")
    test_in_dataset = HeatEquationDataset(os.path.join(data_dir, 'test_interpolation.npz'), 
                                          log_alpha_mean=train_dataset.log_alpha_mean, 
                                          log_alpha_std=train_dataset.log_alpha_std)
    test_ood_dataset = HeatEquationDataset(os.path.join(data_dir, 'test_ood.npz'), 
                                           log_alpha_mean=train_dataset.log_alpha_mean, 
                                           log_alpha_std=train_dataset.log_alpha_std)
                                           
    test_in_loader = DataLoader(test_in_dataset, batch_size=20, shuffle=False)
    test_ood_loader = DataLoader(test_ood_dataset, batch_size=20, shuffle=False)
    
    model.eval()
    
    def evaluate_set(loader, dataset):
        rel_errors = []
        abs_errors = []
        alphas = dataset.alphas.numpy()
        with torch.no_grad():
            for x, y in loader:
                x, y = x.to(device), y.to(device)
                out = model(x)
                rel_err, abs_err = relative_l2_per_sample(out, y)
                rel_errors.extend(rel_err.cpu().numpy().tolist())
                abs_errors.extend(abs_err.cpu().numpy().tolist())
        return alphas, np.array(rel_errors), np.array(abs_errors)
        
    alphas_in, errors_in, abs_in = evaluate_set(test_in_loader, test_in_dataset)
    alphas_ood, errors_ood, abs_ood = evaluate_set(test_ood_loader, test_ood_dataset)
    
    print(f"Interpolation Test Rel-L2 Error: {np.mean(errors_in):.4f} | Abs Error: {np.mean(abs_in):.4f}")
    print(f"OOD Extrapolation Test Rel-L2 Error: {np.mean(errors_ood):.4f} | Abs Error: {np.mean(abs_ood):.4f}")
    
    # Generate Plot
    plt.figure(figsize=(10, 6))
    plt.scatter(alphas_in, errors_in, c='blue', label='Interpolation', alpha=0.6)
    plt.scatter(alphas_ood, errors_ood, c='red', label='OOD Extrapolation', alpha=0.6)
    plt.axvline(x=0.01, color='k', linestyle='--', label='Training Bounds')
    plt.axvline(x=1.0, color='k', linestyle='--')
    plt.xscale('log')
    plt.yscale('log')
    plt.xlabel('Alpha')
    plt.ylabel('Relative L2 Error')
    plt.title('FNO Generalization: Relative L2 Error vs Alpha')
    plt.legend()
    plt.grid(True, which='both', ls='-', alpha=0.2)
    
    plot_dir = os.path.join(base_dir, 'plots')
    os.makedirs(plot_dir, exist_ok=True)
    plt.savefig(os.path.join(plot_dir, 'fno_generalization.png'), dpi=300)
    print(f"Evaluation plot saved to {os.path.join(plot_dir, 'fno_generalization.png')}")

if __name__ == '__main__':
    main()
