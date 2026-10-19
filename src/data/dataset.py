import torch
import numpy as np
from torch.utils.data import Dataset

class HeatEquationDataset(Dataset):
    def __init__(self, npz_path, log_alpha_mean=None, log_alpha_std=None):
        data = np.load(npz_path)
        self.u = torch.tensor(data['u'], dtype=torch.float32) # (N, Nt, Nx)
        self.alphas = torch.tensor(data['alpha'], dtype=torch.float32) # (N,)
        
        x_np = data['x']
        t_np = data['t']
        
        t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
        
        # 1. Coordinate normalization
        t_scaled = 2 * t_mesh - 1
        x_scaled = 2 * x_mesh - 1
        
        self.t_mesh = torch.tensor(t_scaled, dtype=torch.float32)
        self.x_mesh = torch.tensor(x_scaled, dtype=torch.float32)
        
        # 2. Alpha log-transformation and standardization
        log_alpha = torch.log10(self.alphas)
        
        if log_alpha_mean is None:
            self.log_alpha_mean = log_alpha.mean()
            self.log_alpha_std = log_alpha.std()
        else:
            self.log_alpha_mean = log_alpha_mean
            self.log_alpha_std = log_alpha_std
            
        self.log_alpha_scaled = (log_alpha - self.log_alpha_mean) / self.log_alpha_std
        
    def __len__(self):
        return len(self.u)
        
    def __getitem__(self, idx):
        alpha_channel = torch.full_like(self.t_mesh, self.log_alpha_scaled[idx].item())
        x_input = torch.stack([self.t_mesh, self.x_mesh, alpha_channel], dim=0)
        
        # Target is strictly in [0, 1] naturally, so no scaling is strictly required.
        y_target = self.u[idx].unsqueeze(0)
        
        return x_input, y_target
