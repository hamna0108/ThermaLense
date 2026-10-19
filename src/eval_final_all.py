import os
import torch
import torch.nn as nn
import numpy as np

from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d
from models.pinn import PINN
try:
    from train_expC import ReparametrizedFNO2d
except ImportError:
    from experiments.train_expC import ReparametrizedFNO2d
from train_expD_fno import BoundedReparametrizedFNO2d

class NormalizedPINN(nn.Module):
    def __init__(self, log_alpha_mean, log_alpha_std):
        super().__init__()
        self.pinn = PINN(layers=[3, 64, 64, 64, 64, 1])
        self.log_alpha_mean = log_alpha_mean
        self.log_alpha_std = log_alpha_std
        
    def forward(self, x, t, alpha_raw):
        x_scaled = 2 * x - 1
        t_scaled = 2 * t - 1
        log_alpha = torch.log10(alpha_raw)
        alpha_scaled = (log_alpha - self.log_alpha_mean) / self.log_alpha_std
        return self.pinn(x_scaled, t_scaled, alpha_scaled)

class BoundedReparametrizedPINN(nn.Module):
    def __init__(self, log_alpha_mean, log_alpha_std):
        super().__init__()
        self.pinn = PINN(layers=[3, 64, 64, 64, 64, 1])
        self.log_alpha_mean = log_alpha_mean
        self.log_alpha_std = log_alpha_std
        
    def forward(self, x, t, alpha_raw):
        x_scaled = 2 * x - 1
        t_scaled = 2 * t - 1
        log_alpha = torch.log10(alpha_raw)
        alpha_scaled = (log_alpha - self.log_alpha_mean) / self.log_alpha_std
        
        N = self.pinn(x_scaled, t_scaled, alpha_scaled)
        
        bounded_t = 1.0 - torch.exp(-t * 5.0)
        out = torch.sin(np.pi * x) + x * (1.0 - x) * bounded_t * N
        return out

def evaluate_fno(model_class, model_path, npz_path, checkpoint, mask_fn, device, apply_override=False):
    model = model_class(modes1=16, modes2=12, width=32).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device)['model_state_dict'])
    model.eval()
    
    dataset = HeatEquationDataset(npz_path, 
                                  log_alpha_mean=checkpoint['log_alpha_mean'], 
                                  log_alpha_std=checkpoint['log_alpha_std'])
    
    data = np.load(npz_path)
    x_np = data['x']
    exact_ic = torch.tensor(np.sin(np.pi * x_np), dtype=torch.float32).to(device)
    
    mae_t0 = []
    mae_t1_99 = []
    field_rel_l2 = []
    
    with torch.no_grad():
        for i in range(len(dataset)):
            if not mask_fn(dataset.alphas[i].item()):
                continue
                
            x_input, y = dataset[i]
            x_input = x_input.unsqueeze(0).to(device)
            y = y.unsqueeze(0).to(device) # (1, 1, Nt, Nx)
            
            out = model(x_input)
            out = out.squeeze(1)
            y = y.squeeze(1)
            
            if apply_override:
                out[:, 0, :] = exact_ic
                
            diff = torch.abs(out - y)
            mae = torch.mean(diff, dim=2).squeeze(0) # (Nt)
            
            mae_t0.append(mae[0].item())
            mae_t1_99.append(torch.mean(mae[1:]).item())
            
            # Field-level relative L2 for the whole sample
            sample_diff_norm = torch.norm(out - y, 2)
            sample_y_norm = torch.norm(y, 2)
            field_rel_l2.append((sample_diff_norm / (sample_y_norm + 1e-8)).item())
            
    return np.mean(mae_t0), np.mean(mae_t1_99), np.mean(field_rel_l2)

def evaluate_pinn(model_class, model_path, npz_path, checkpoint, mask_fn, device):
    model = model_class(checkpoint['log_alpha_mean'], checkpoint['log_alpha_std']).to(device)
    state_dict = torch.load(model_path, map_location=device)['model_state_dict']
    model.load_state_dict(state_dict)
    model.eval()
    
    dataset = HeatEquationDataset(npz_path, 
                                  log_alpha_mean=checkpoint['log_alpha_mean'], 
                                  log_alpha_std=checkpoint['log_alpha_std'])
                                  
    data = np.load(npz_path)
    x_np = data['x']
    t_np = data['t']
    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
    
    t_flat = torch.tensor(t_mesh, dtype=torch.float32, device=device).view(-1, 1)
    x_flat = torch.tensor(x_mesh, dtype=torch.float32, device=device).view(-1, 1)
    
    mae_t0 = []
    mae_t1_99 = []
    field_rel_l2 = []
    
    with torch.no_grad():
        for i in range(len(dataset)):
            if not mask_fn(dataset.alphas[i].item()):
                continue
                
            y = dataset.u[i].unsqueeze(0).to(device) # (1, Nt, Nx)
            alpha_raw = dataset.alphas[i].item()
            
            a_flat = torch.full_like(t_flat, alpha_raw)
            pred_flat = model(x_flat, t_flat, a_flat)
            pred = pred_flat.view(1, len(t_np), len(x_np))
            
            diff = torch.abs(pred - y)
            mae = torch.mean(diff, dim=2).squeeze(0) # (Nt)
            
            mae_t0.append(mae[0].item())
            mae_t1_99.append(torch.mean(mae[1:]).item())
            
            sample_diff_norm = torch.norm(pred - y, 2)
            sample_y_norm = torch.norm(y, 2)
            field_rel_l2.append((sample_diff_norm / (sample_y_norm + 1e-8)).item())
            
    return np.mean(mae_t0), np.mean(mae_t1_99), np.mean(field_rel_l2)

def print_row(name, res):
    print(f"{name:22s} | {res[0]:.6f} | {res[1]:.6f} | {res[2]:.6f}")

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    checkpoint = torch.load('models/fno2d_heat.pt', map_location=device)
    
    splits = [
        ("Interpolation", 'data/interim/test_interpolation.npz', lambda a: True),
        ("Low-alpha OOD", 'data/interim/test_ood.npz', lambda a: a < 0.01),
        ("High-alpha OOD", 'data/interim/test_ood.npz', lambda a: a > 1.0)
    ]
    
    print("====== FNO Decision Verification ======")
    print("Format: MAE (t=0) | MAE (t=1-99) | Field-level Rel L2")
    for split_name, npz_path, mask_fn in splits:
        print(f"\n--- {split_name} ---")
        res_fno = evaluate_fno(FNO2d, 'models/fno2d_heat.pt', npz_path, checkpoint, mask_fn, device, apply_override=True)
        res_expC = evaluate_fno(ReparametrizedFNO2d, 'models/fno2d_expC.pt', npz_path, checkpoint, mask_fn, device)
        res_expD = evaluate_fno(BoundedReparametrizedFNO2d, 'models/fno2d_expD.pt', npz_path, checkpoint, mask_fn, device)
        
        print_row("FNO Baseline (+t=0)", res_fno)
        print_row("FNO Exp C", res_expC)
        print_row("FNO Exp D", res_expD)
        
    print("\n====== Final Locked Configurations ======")
    print("Format: MAE (t=0) | MAE (t=1-99) | Field-level Rel L2")
    for split_name, npz_path, mask_fn in splits:
        print(f"\n--- {split_name} ---")
        res_fno = evaluate_fno(FNO2d, 'models/fno2d_heat.pt', npz_path, checkpoint, mask_fn, device, apply_override=True)
        res_pinn = evaluate_pinn(BoundedReparametrizedPINN, 'models/pinn_expD.pt', npz_path, checkpoint, mask_fn, device)
        print_row("FNO Baseline (+t=0)", res_fno)
        print_row("PINN Exp D", res_pinn)

if __name__ == '__main__':
    main()
