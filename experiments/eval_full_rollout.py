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
from models.fno2d import FNO2d
from models.pinn import PINN
from train_pinn import NormalizedPINN
from train_pinn_expB import ReparametrizedPINN
from train_expC import ReparametrizedFNO2d
from train_expD_pinn import BoundedReparametrizedPINN
from train_expD_fno import BoundedReparametrizedFNO2d

def absolute_l2_per_timestep(pred, target):
    diff_norms = torch.norm(pred - target, 2, dim=2)
    return diff_norms

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    data_dir = str(DATASETS)
    fno_chkpt = torch.load(str(MODELS / 'fno2d_heat.pt'), map_location=device)
    log_mean = fno_chkpt['log_alpha_mean']
    log_std = fno_chkpt['log_alpha_std']
    
    test_ood_dataset = HeatEquationDataset(os.path.join(data_dir, 'test_ood.npz'), 
                                           log_alpha_mean=log_mean, log_alpha_std=log_std)
    
    test_ood_loader = DataLoader(test_ood_dataset, batch_size=20, shuffle=False)
    
    data = np.load(os.path.join(data_dir, 'test_ood.npz'))
    x_np = data['x']
    t_np = data['t']
    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
    t_flat = torch.tensor(t_mesh, dtype=torch.float32, device=device).view(-1, 1)
    x_flat = torch.tensor(x_mesh, dtype=torch.float32, device=device).view(-1, 1)

    # PINN Models
    pinn_base = NormalizedPINN(log_mean, log_std).to(device)
    pinn_base.load_state_dict(torch.load(str(EXP_MODELS / 'pinn_heat.pt'), map_location=device)['model_state_dict'])
    pinn_base.eval()

    pinn_expB = ReparametrizedPINN(log_mean, log_std).to(device)
    pinn_expB.load_state_dict(torch.load(str(EXP_MODELS / 'pinn_expB.pt'), map_location=device)['model_state_dict'])
    pinn_expB.eval()
    
    pinn_expD = BoundedReparametrizedPINN(log_mean, log_std).to(device)
    pinn_expD.load_state_dict(torch.load(str(MODELS / 'pinn_expD.pt'), map_location=device)['model_state_dict'])
    pinn_expD.eval()

    # FNO Models
    fno_base = FNO2d(modes1=16, modes2=12, width=32).to(device)
    fno_base.load_state_dict(torch.load(str(MODELS / 'fno2d_heat.pt'), map_location=device)['model_state_dict'])
    fno_base.eval()

    fno_expC = ReparametrizedFNO2d(modes1=16, modes2=12, width=32).to(device)
    fno_expC.load_state_dict(torch.load(str(EXP_MODELS / 'fno2d_expC.pt'), map_location=device)['model_state_dict'])
    fno_expC.eval()
    
    fno_expD = BoundedReparametrizedFNO2d(modes1=16, modes2=12, width=32).to(device)
    fno_expD.load_state_dict(torch.load(str(MODELS / 'fno2d_expD.pt'), map_location=device)['model_state_dict'])
    fno_expD.eval()

    def get_fno_errors(model):
        abs_errors = []
        with torch.no_grad():
            for x, y in test_ood_loader:
                x, y = x.to(device), y.to(device)
                out = model(x)
                if out.dim() == 4: out = out.squeeze(1)
                if y.dim() == 4: y = y.squeeze(1)
                abs_err_t = absolute_l2_per_timestep(out, y)
                abs_errors.append(abs_err_t.cpu().numpy())
        return np.concatenate(abs_errors, axis=0)

    def get_pinn_errors(model_type, model):
        abs_errors = []
        with torch.no_grad():
            for idx in range(len(test_ood_dataset)):
                y = test_ood_dataset.u[idx].unsqueeze(0).to(device)
                alpha_raw = test_ood_dataset.alphas[idx].item()
                a_flat = torch.full_like(t_flat, alpha_raw)
                
                pred_flat = model(x_flat, t_flat, a_flat)
                pred = pred_flat.view(1, 100, 50)
                abs_err_t = absolute_l2_per_timestep(pred, y)
                abs_errors.append(abs_err_t.cpu().numpy())
        return np.concatenate(abs_errors, axis=0)

    print("Evaluating FNOs...")
    fno_base_errs = get_fno_errors(fno_base)
    fno_expC_errs = get_fno_errors(fno_expC)
    fno_expD_errs = get_fno_errors(fno_expD)
    
    print("Evaluating PINNs...")
    pinn_base_errs = get_pinn_errors('base', pinn_base)
    pinn_expB_errs = get_pinn_errors('expB', pinn_expB)
    pinn_expD_errs = get_pinn_errors('expD', pinn_expD)

    high_alpha_mask = test_ood_dataset.alphas.numpy() > 1.0

    fno_base_mean = np.mean(fno_base_errs[high_alpha_mask], axis=0)
    fno_expC_mean = np.mean(fno_expC_errs[high_alpha_mask], axis=0)
    fno_expD_mean = np.mean(fno_expD_errs[high_alpha_mask], axis=0)
    
    pinn_base_mean = np.mean(pinn_base_errs[high_alpha_mask], axis=0)
    pinn_expB_mean = np.mean(pinn_expB_errs[high_alpha_mask], axis=0)
    pinn_expD_mean = np.mean(pinn_expD_errs[high_alpha_mask], axis=0)

    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    plt.plot(pinn_base_mean, label='Baseline PINN')
    plt.plot(pinn_expB_mean, label='Exp B (Unbounded Reparam)')
    plt.plot(pinn_expD_mean, label='Exp D (Bounded Reparam)')
    plt.yscale('log')
    plt.xlabel('Timestep')
    plt.ylabel('Absolute L2 Error')
    plt.title('High-Alpha OOD: PINN')
    plt.legend()
    plt.grid(True)

    plt.subplot(1, 2, 2)
    plt.plot(fno_base_mean, label='Baseline FNO')
    plt.plot(fno_expC_mean, label='Exp C (Unbounded Reparam)')
    plt.plot(fno_expD_mean, label='Exp D (Bounded Reparam)')
    plt.yscale('log')
    plt.xlabel('Timestep')
    plt.ylabel('Absolute L2 Error')
    plt.title('High-Alpha OOD: FNO')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plot_dir = os.path.join(base_dir, 'plots')
    os.makedirs(plot_dir, exist_ok=True)
    plt.savefig(os.path.join(plot_dir, 'full_rollout_abs_error_comparison.png'), dpi=300)
    print("Saved plot to plots/full_rollout_abs_error_comparison.png")
    
    print("--- Mean Absolute Error Across Full Rollout (High-Alpha OOD) ---")
    print(f"FNO Baseline: {np.mean(fno_base_mean):.6e}")
    print(f"FNO Exp C:    {np.mean(fno_expC_mean):.6e}")
    print(f"FNO Exp D:    {np.mean(fno_expD_mean):.6e}")
    print("-" * 30)
    print(f"PINN Baseline: {np.mean(pinn_base_mean):.6e}")
    print(f"PINN Exp B:    {np.mean(pinn_expB_mean):.6e}")
    print(f"PINN Exp D:    {np.mean(pinn_expD_mean):.6e}")


if __name__ == '__main__':
    main()
