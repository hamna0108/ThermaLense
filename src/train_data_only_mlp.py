import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
import numpy as np

from paths import DATASETS, MODELS

class DataOnlyMLP(nn.Module):
    """
    Standard MLP baseline without physics loss (pure supervised regression).
    Same capacity as base PINN: [3, 64, 64, 64, 64, 1] with Tanh activations.
    Input: (x, t, alpha_raw).
    Loss: Mean Squared Error on observed field values u(x, t).
    """
    def __init__(self, log_alpha_mean, log_alpha_std, layers=[3, 64, 64, 64, 64, 1]):
        super().__init__()
        self.log_alpha_mean = float(log_alpha_mean)
        self.log_alpha_std = float(log_alpha_std)
        self.layers = nn.ModuleList()
        for i in range(len(layers) - 1):
            self.layers.append(nn.Linear(layers[i], layers[i+1]))
        self.activation = nn.Tanh()

    def forward(self, x, t, alpha_raw):
        # x, t, alpha_raw: (N, 1) or broadcastable
        x_scaled = 2.0 * x - 1.0
        t_scaled = 2.0 * t - 1.0
        log_alpha = torch.log10(alpha_raw)
        alpha_scaled = (log_alpha - self.log_alpha_mean) / self.log_alpha_std
        
        inp = torch.cat([x_scaled, t_scaled, alpha_scaled], dim=-1)
        out = inp
        for i in range(len(self.layers) - 1):
            out = self.activation(self.layers[i](out))
        out = self.layers[-1](out)
        return out

def train_data_only_mlp(seed=42, epochs=25, batch_size=2048, lr=1e-3, num_pts=100000):
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Training Data-Only MLP on {device} (seed={seed})...", flush=True)
    
    train_path = DATASETS / 'train.npz'
    d = np.load(train_path)
    alphas = d['alpha'] # (1000,)
    x_grid = d['x']     # (50,)
    t_grid = d['t']     # (100,)
    u = d['u']         # (1000, 100, 50)
    
    log_mean = float(np.mean(np.log10(alphas)))
    log_std = float(np.std(np.log10(alphas)))
    
    t_mesh, x_mesh = np.meshgrid(t_grid, x_grid, indexing='ij')
    t_all = np.broadcast_to(t_mesh, u.shape).flatten()
    x_all = np.broadcast_to(x_mesh, u.shape).flatten()
    a_all = np.repeat(alphas, len(t_grid) * len(x_grid))
    u_all = u.flatten()
    
    rng = np.random.RandomState(seed)
    sub_idx = rng.choice(len(u_all), size=num_pts, replace=False)
    
    dataset = TensorDataset(
        torch.tensor(x_all[sub_idx, None], dtype=torch.float32),
        torch.tensor(t_all[sub_idx, None], dtype=torch.float32),
        torch.tensor(a_all[sub_idx, None], dtype=torch.float32),
        torch.tensor(u_all[sub_idx, None], dtype=torch.float32)
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    model = DataOnlyMLP(log_mean, log_std).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    criterion = nn.MSELoss()
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for bx, bt, ba, bu in loader:
            bx, bt, ba, bu = bx.to(device), bt.to(device), ba.to(device), bu.to(device)
            optimizer.zero_grad()
            pred = model(bx, bt, ba)
            loss = criterion(pred, bu)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(bx)
        total_loss /= len(dataset)
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch {epoch+1:2d}/{epochs} - Loss (MSE): {total_loss:.6f}", flush=True)
            
    out_path = MODELS / 'mlp_data_only.pt'
    os.makedirs(MODELS, exist_ok=True)
    torch.save({
        'model_state_dict': model.state_dict(),
        'log_alpha_mean': log_mean,
        'log_alpha_std': log_std,
        'seed': seed,
        'layers': [3, 64, 64, 64, 64, 1]
    }, out_path)
    print(f"Saved Data-Only MLP checkpoint to {out_path}", flush=True)

if __name__ == '__main__':
    train_data_only_mlp()
