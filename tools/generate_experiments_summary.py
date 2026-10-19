import sys
import os

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_dir = os.path.join(base_dir, "src")
exp_dir = os.path.join(base_dir, "experiments")
for p in [base_dir, src_dir, exp_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

import torch
import torch.nn as nn
import numpy as np
import pandas as pd

from paths import DATASETS, MODELS, EXP_MODELS, RESULTS
from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d
from models.pinn import PINN
from train_pinn import NormalizedPINN
from train_pinn_expB import ReparametrizedPINN
from train_expC import ReparametrizedFNO2d
from train_expD_fno import BoundedReparametrizedFNO2d
from train_expD_pinn import BoundedReparametrizedPINN
from train_data_only_mlp import DataOnlyMLP
from inverse_mode2 import solve_heat_1d_cn

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
checkpoint = torch.load(str(MODELS / 'fno2d_heat.pt'), map_location=device)
log_mean = checkpoint['log_alpha_mean'].item()
log_std = checkpoint['log_alpha_std'].item()

splits = [
    ("Interpolation", str(DATASETS / 'test_interpolation.npz'), lambda a: True, 44),
    ("Low-alpha OOD", str(DATASETS / 'test_ood.npz'), lambda a: a < 0.01, 45),
    ("High-alpha OOD", str(DATASETS / 'test_ood.npz'), lambda a: a > 1.0, 45)
]

# Load models
models = {}

# 1. FNO Base
fno_base = FNO2d(modes1=16, modes2=12, width=32).to(device)
fno_base.load_state_dict(checkpoint['model_state_dict'])
fno_base.eval()
models['fno_base'] = ('fno', fno_base, 'src/train.py', '42 (train)')

# 2. FNO Exp C
fno_expC = ReparametrizedFNO2d(modes1=16, modes2=12, width=32).to(device)
fno_expC.load_state_dict(torch.load(str(EXP_MODELS / 'fno2d_expC.pt'), map_location=device)['model_state_dict'])
fno_expC.eval()
models['fno_expC'] = ('fno', fno_expC, 'experiments/train_expC.py', '42 (train)')

# 3. FNO Exp D
fno_expD = BoundedReparametrizedFNO2d(modes1=16, modes2=12, width=32).to(device)
fno_expD.load_state_dict(torch.load(str(MODELS / 'fno2d_expD.pt'), map_location=device)['model_state_dict'])
fno_expD.eval()
models['fno_expD'] = ('fno', fno_expD, 'src/train_expD_fno.py', '42 (train)')

# 4. PINN Base
pinn_base = NormalizedPINN(log_mean, log_std).to(device)
pinn_base.load_state_dict(torch.load(str(EXP_MODELS / 'pinn_heat.pt'), map_location=device)['model_state_dict'])
pinn_base.eval()
models['pinn_base'] = ('pinn', pinn_base, 'experiments/train_pinn.py', '42 (train)')

# 5. PINN Exp A
pinn_expA = NormalizedPINN(log_mean, log_std).to(device)
pinn_expA.load_state_dict(torch.load(str(EXP_MODELS / 'pinn_expA.pt'), map_location=device)['model_state_dict'])
pinn_expA.eval()
models['pinn_expA'] = ('pinn', pinn_expA, 'experiments/train_pinn_expA.py', '42 (train)')

# 6. PINN Exp B
pinn_expB = ReparametrizedPINN(log_mean, log_std).to(device)
pinn_expB.load_state_dict(torch.load(str(EXP_MODELS / 'pinn_expB.pt'), map_location=device)['model_state_dict'])
pinn_expB.eval()
models['pinn_expB'] = ('pinn', pinn_expB, 'experiments/train_pinn_expB.py', '42 (train)')

# 7. PINN Exp D
pinn_expD = BoundedReparametrizedPINN(log_mean, log_std).to(device)
pinn_expD.load_state_dict(torch.load(str(MODELS / 'pinn_expD.pt'), map_location=device)['model_state_dict'])
pinn_expD.eval()
models['pinn_expD'] = ('pinn', pinn_expD, 'src/train_expD_pinn.py', '42 (train)')

# 8. Solver CN
models['solver_cn'] = ('solver', None, 'src/inverse_mode2.py', 'N/A (deterministic)')

# 9. Data-only MLP
mlp_ckpt = torch.load(str(MODELS / 'mlp_data_only.pt'), map_location=device)
mlp_data_only = DataOnlyMLP(mlp_ckpt['log_alpha_mean'], mlp_ckpt['log_alpha_std']).to(device)
mlp_data_only.load_state_dict(mlp_ckpt['model_state_dict'])
mlp_data_only.eval()
models['mlp_data_only'] = ('mlp', mlp_data_only, 'src/train_data_only_mlp.py', '42 (train)')

# 10. Persistence (trivial baseline)
models['persistence (trivial baseline)'] = ('persistence', None, 'src/data/generate_dataset.py', 'N/A (baseline)')

def run_evaluation():
    records = []

    for split_name, npz_path, mask_fn, test_seed in splits:
        print(f"\nEvaluating split: {split_name}...")
        dataset = HeatEquationDataset(npz_path, log_alpha_mean=log_mean, log_alpha_std=log_std)
        data = np.load(npz_path)
        x_np = data['x']
        t_np = data['t']
        t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing='ij')
        t_flat = torch.tensor(t_mesh, dtype=torch.float32, device=device).view(-1, 1)
        x_flat = torch.tensor(x_mesh, dtype=torch.float32, device=device).view(-1, 1)
        
        # Pre-filter sample indices
        sample_indices = [i for i in range(len(dataset)) if mask_fn(dataset.alphas[i].item())]
        print(f"Number of samples in {split_name}: {len(sample_indices)}")
        
        for model_name, (m_type, model_obj, script_name, model_seed) in models.items():
            rel_l2_list = []
            t0_mae_list = []
            
            with torch.no_grad():
                for idx in sample_indices:
                    x_input, y_target = dataset[idx]
                    y_true = dataset.u[idx].numpy() # (Nt, Nx)
                    alpha_val = dataset.alphas[idx].item()
                    
                    if m_type == 'fno':
                        x_in = x_input.unsqueeze(0).to(device)
                        pred = model_obj(x_in).squeeze(1).squeeze(0).cpu().numpy() # (Nt, Nx)
                    elif m_type in ('pinn', 'mlp'):
                        a_flat = torch.full_like(t_flat, alpha_val)
                        pred_flat = model_obj(x_flat, t_flat, a_flat)
                        pred = pred_flat.view(len(t_np), len(x_np)).cpu().numpy()
                    elif m_type == 'solver':
                        _, _, pred = solve_heat_1d_cn(len(x_np), len(t_np), alpha_val)
                    elif m_type == 'persistence':
                        # Persistence baseline: u(x, t) = u(x, 0) = sin(pi * x)
                        pred = np.tile(np.sin(np.pi * x_np), (len(t_np), 1))
                    
                    diff = pred - y_true
                    rel_l2 = np.linalg.norm(diff) / (np.linalg.norm(y_true) + 1e-12)
                    t0_mae = np.mean(np.abs(diff[0, :]))
                    
                    rel_l2_list.append(rel_l2)
                    t0_mae_list.append(t0_mae)
                    
            med_l2 = float(np.median(rel_l2_list))
            p90_l2 = float(np.percentile(rel_l2_list, 90))
            med_t0 = float(np.median(t0_mae_list))
            p90_t0 = float(np.percentile(t0_mae_list, 90))
            
            print(f"  {model_name:30s} | Med L2: {med_l2:.5f} | P90 L2: {p90_l2:.5f} | Med t0: {med_t0:.6f}")
            
            records.append({
                'model': model_name,
                'split': split_name,
                'samples': len(sample_indices),
                'median_rel_l2': med_l2,
                'p90_rel_l2': p90_l2,
                'median_t0_mae': med_t0,
                'p90_t0_mae': p90_t0,
                'script': script_name,
                'model_seeds': model_seed,
                'test_seed': test_seed
            })

    df_res = pd.DataFrame(records)
    out_csv = str(RESULTS / "experiments_summary.csv")
    df_res.to_csv(out_csv, index=False)
    print(f"\nSaved experiments summary table to: {out_csv}")

if __name__ == '__main__':
    run_evaluation()
