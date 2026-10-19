import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d
import math
import matplotlib.pyplot as plt
import numpy as np

def relative_l2_loss(pred, target):
    diff_norms = torch.norm(pred.view(pred.size(0), -1) - target.view(target.size(0), -1), 2, dim=1)
    target_norms = torch.norm(target.view(target.size(0), -1), 2, dim=1)
    return torch.mean(diff_norms / target_norms)

class BoundedReparametrizedFNO2d(nn.Module):
    def __init__(self, modes1=16, modes2=12, width=32):
        super().__init__()
        self.fno = FNO2d(modes1, modes2, width)
        
    def forward(self, x):
        N = self.fno(x)
        
        t_scaled = x[:, 0:1, :, :]
        x_scaled = x[:, 1:2, :, :]
        
        t_raw = (t_scaled + 1.0) / 2.0
        x_raw = (x_scaled + 1.0) / 2.0
        
        # Bounded multiplier: 1 - exp(-t)
        bounded_t = 1.0 - torch.exp(-t_raw * 5.0) # tau = 0.2
        
        out = torch.sin(math.pi * x_raw) + x_raw * (1.0 - x_raw) * bounded_t * N
        return out

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, 'data', 'interim')
    
    train_dataset = HeatEquationDataset(os.path.join(data_dir, 'train.npz'))
    val_dataset = HeatEquationDataset(os.path.join(data_dir, 'val.npz'), 
                                      log_alpha_mean=train_dataset.log_alpha_mean, 
                                      log_alpha_std=train_dataset.log_alpha_std)
                                      
    train_loader = DataLoader(train_dataset, batch_size=20, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=20, shuffle=False)
    
    model = BoundedReparametrizedFNO2d(modes1=16, modes2=12, width=32).to(device)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.5)
    
    epochs = 100
    
    print(f"Starting FNO ExpD training for {epochs} epochs on {device}...")
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
            
    model_dir = os.path.join(base_dir, 'models')
    os.makedirs(model_dir, exist_ok=True)
    torch.save({
        'model_state_dict': model.state_dict(),
        'log_alpha_mean': train_dataset.log_alpha_mean,
        'log_alpha_std': train_dataset.log_alpha_std
    }, os.path.join(model_dir, 'fno2d_expD.pt'))
    print("Training finished and FNO ExpD model saved.")

if __name__ == '__main__':
    main()
