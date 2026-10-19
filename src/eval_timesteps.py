import os
import torch
import numpy as np
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader

from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d

def relative_l2_per_timestep(pred, target):
    # pred and target are shape: (batch, time, x)
    # We want relative l2 error per timestep t.
    # L2 norm over spatial dimensions for each sample and timestep
    
    diff_norms = torch.norm(pred - target, 2, dim=2) # (batch, time)
    target_norms = torch.norm(target, 2, dim=2) # (batch, time)
    
    # Avoid division by zero
    rel_err = diff_norms / (target_norms + 1e-8)
    return rel_err, diff_norms # (batch, time)

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, 'data', 'interim')
    model_dir = os.path.join(base_dir, 'models')
    
    model_path = os.path.join(model_dir, 'fno2d_heat.pt')
    checkpoint = torch.load(model_path, map_location=device)
    
    test_ood_dataset = HeatEquationDataset(os.path.join(data_dir, 'test_ood.npz'), 
                                           log_alpha_mean=checkpoint['log_alpha_mean'], 
                                           log_alpha_std=checkpoint['log_alpha_std'])
    
    test_ood_loader = DataLoader(test_ood_dataset, batch_size=20, shuffle=False)
    
    model = FNO2d(modes1=16, modes2=12, width=32).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    high_alpha_rel_errors = []
    high_alpha_abs_errors = []
    
    alphas = test_ood_dataset.alphas.numpy()
    
    with torch.no_grad():
        for x, y in test_ood_loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            
            # y is (batch, 1, Nt, Nx)
            # out is (batch, 1, Nt, Nx)
            if out.dim() == 4:
                out = out.squeeze(1) # (batch, Nt, Nx)
            if y.dim() == 4:
                y = y.squeeze(1)
                
            rel_err_t, abs_err_t = relative_l2_per_timestep(out, y)
            high_alpha_rel_errors.append(rel_err_t.cpu().numpy())
            high_alpha_abs_errors.append(abs_err_t.cpu().numpy())
            
    high_alpha_rel_errors = np.concatenate(high_alpha_rel_errors, axis=0)
    high_alpha_abs_errors = np.concatenate(high_alpha_abs_errors, axis=0)
    
    # Filter for high alpha > 1.0
    high_alpha_mask = alphas > 1.0
    high_alpha_rel_errors = high_alpha_rel_errors[high_alpha_mask]
    high_alpha_abs_errors = high_alpha_abs_errors[high_alpha_mask]
    
    mean_rel_err_per_t = np.mean(high_alpha_rel_errors, axis=0)
    mean_abs_err_per_t = np.mean(high_alpha_abs_errors, axis=0)
    
    print("Mean Error per timestep (High-alpha OOD):")
    for t, (rel_err, abs_err) in enumerate(zip(mean_rel_err_per_t, mean_abs_err_per_t)):
        print(f"t={t:02d}: Rel={rel_err:.4f}, Abs={abs_err:.4f}")
        
    plt.figure(figsize=(10, 5))
    plt.plot(mean_rel_err_per_t, marker='o', label='Relative L2')
    plt.plot(mean_abs_err_per_t, marker='s', label='Absolute L2', alpha=0.7)
    plt.yscale('log')
    plt.xlabel('Timestep')
    plt.ylabel('Mean Error')
    plt.title('High-Alpha OOD: Error across Timesteps')
    plt.legend()
    plt.grid(True)
    
    plot_dir = os.path.join(base_dir, 'plots')
    os.makedirs(plot_dir, exist_ok=True)
    plt.savefig(os.path.join(plot_dir, 'per_timestep_error.png'), dpi=300)
    print("Plot saved to plots/per_timestep_error.png")

if __name__ == '__main__':
    main()
