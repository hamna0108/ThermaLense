import sys, os
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_dir = os.path.join(base_dir, "src")
exp_dir = os.path.abspath(os.path.dirname(__file__))
for p in [base_dir, src_dir, exp_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from paths import DATASETS, MODELS, EXP_MODELS, PLOTS
import torch
import numpy as np
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader

from data.dataset import HeatEquationDataset
from train_pinn import NormalizedPINN

def relative_l2_per_timestep(pred, target):
    diff_norms = torch.norm(pred - target, 2, dim=2) # (batch, time)
    target_norms = torch.norm(target, 2, dim=2) # (batch, time)
    rel_err = diff_norms / (target_norms + 1e-8)
    return rel_err, diff_norms # (batch, time)

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    data_dir = str(DATASETS)
    pinn_path = str(EXP_MODELS / 'pinn_heat.pt')
    checkpoint = torch.load(pinn_path, map_location=device)
    
    test_ood_dataset = HeatEquationDataset(os.path.join(data_dir, 'test_ood.npz'), 
                                           log_alpha_mean=checkpoint['log_alpha_mean'], 
                                           log_alpha_std=checkpoint['log_alpha_std'])
    
    test_ood_loader = DataLoader(test_ood_dataset, batch_size=20, shuffle=False)
    
    model = NormalizedPINN(checkpoint['log_alpha_mean'], checkpoint['log_alpha_std']).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    high_alpha_rel_errors = []
    high_alpha_abs_errors = []
    low_alpha_rel_errors = []
    low_alpha_abs_errors = []
    
    alphas = test_ood_dataset.alphas.numpy()
    
    # We need to construct the grid for PINN
    # x in [0, 1], t in [0, 1]
    data = np.load(os.path.join(data_dir, 'test_ood.npz'))
    x_np = data['x']
    t_np = data['t']
    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij') # (100, 50)
    
    t_flat = torch.tensor(t_mesh, dtype=torch.float32, device=device).view(-1, 1)
    x_flat = torch.tensor(x_mesh, dtype=torch.float32, device=device).view(-1, 1)
    
    with torch.no_grad():
        for x_input, y in test_ood_loader:
            y = y.to(device)
            if y.dim() == 4:
                y = y.squeeze(1) # (batch, Nt, Nx)
                
            batch_size = y.size(0)
            
            # x_input has shape (batch, 3, Nt, Nx) -> the third channel is log_alpha_scaled.
            # But the PINN expects raw alpha!
            # Wait, the dataset alphas are in test_ood_dataset.alphas. We can just use the batch idx.
            # Or get alpha from x_input? Actually, it's easier to just pass alpha_raw.
            
            batch_alphas_raw = test_ood_dataset.alphas[test_ood_loader.sampler.indices if hasattr(test_ood_loader.sampler, 'indices') else range(len(high_alpha_rel_errors), len(high_alpha_rel_errors)+batch_size)]
            # wait, that's brittle. Better to just pass alpha_raw directly from the dataset.
            pass # we will manually iterate without dataloader for simplicity
            
    # Iterate manually
    high_rel = []
    high_abs = []
    low_rel = []
    low_abs = []
    
    with torch.no_grad():
        for idx in range(len(test_ood_dataset)):
            y = test_ood_dataset.u[idx].unsqueeze(0).to(device) # (1, Nt, Nx)
            alpha_raw = test_ood_dataset.alphas[idx].item()
            
            # Prepare inputs for PINN
            a_flat = torch.full_like(t_flat, alpha_raw)
            pred_flat = model(x_flat, t_flat, a_flat) # (Nt*Nx, 1)
            pred = pred_flat.view(1, 100, 50) # (1, Nt, Nx)
            
            rel_err_t, abs_err_t = relative_l2_per_timestep(pred, y)
            
            if alpha_raw > 1.0:
                high_rel.append(rel_err_t.cpu().numpy())
                high_abs.append(abs_err_t.cpu().numpy())
            elif alpha_raw < 0.01:
                low_rel.append(rel_err_t.cpu().numpy())
                low_abs.append(abs_err_t.cpu().numpy())
            
    high_rel = np.concatenate(high_rel, axis=0)
    high_abs = np.concatenate(high_abs, axis=0)
    low_rel = np.concatenate(low_rel, axis=0)
    low_abs = np.concatenate(low_abs, axis=0)
    
    mean_high_rel = np.mean(high_rel, axis=0)
    mean_high_abs = np.mean(high_abs, axis=0)
    mean_low_rel = np.mean(low_rel, axis=0)
    mean_low_abs = np.mean(low_abs, axis=0)
    
    print("PINN Evaluation:")
    print(f"High-Alpha OOD t=0: Rel={mean_high_rel[0]:.4f}, Abs={mean_high_abs[0]:.4f}")
    print(f"Low-Alpha OOD t=0: Rel={mean_low_rel[0]:.4f}, Abs={mean_low_abs[0]:.4f}")
    print(f"High-Alpha OOD t=99: Rel={mean_high_rel[-1]:.4f}, Abs={mean_high_abs[-1]:.4f}")
    print(f"Low-Alpha OOD t=99: Rel={mean_low_rel[-1]:.4f}, Abs={mean_low_abs[-1]:.4f}")

if __name__ == '__main__':
    main()
