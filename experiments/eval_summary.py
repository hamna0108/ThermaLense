import torch
import numpy as np
import sys
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(base_dir, "src")
exp_dir = os.path.dirname(os.path.abspath(__file__))
for p in [base_dir, src_dir, exp_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from paths import MODELS, EXP_MODELS
try:
    from envs.heat_env import HeatEnv
except ImportError:
    HeatEnv = None

from models.fno2d import FNO2d
from models.pinn import PINN
from train_expC import ReparametrizedFNO2d as HardConstraintFNO2d
from train_pinn_expB import ReparametrizedPINN
from train_expD_fno import BoundedReparametrizedFNO2d
from train_expD_pinn import BoundedReparametrizedPINN

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def evaluate_model(model_class, path, env, rollout_steps=100, is_fno=True):
    if not os.path.exists(path):
        return float('nan')
    model = model_class().to(device)
    model.load_state_dict(torch.load(path, map_location=device))
    model.eval()
    
    alpha = 5.0
    u = env.reset(alpha=alpha)
    u_tensor = torch.tensor(u, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
    
    errors = []
    
    with torch.no_grad():
        for t in range(rollout_steps):
            u_true = env.step()
            
            if is_fno:
                t_tensor = torch.full_like(u_tensor, t * 0.01)
                alpha_tensor = torch.full_like(u_tensor, alpha)
                x_in = torch.cat([u_tensor, t_tensor, alpha_tensor], dim=1)
                u_pred = model(x_in)
                u_tensor = u_pred
            else:
                x_grid = torch.linspace(0, 1, env.resolution).to(device)
                y_grid = torch.linspace(0, 1, env.resolution).to(device)
                grid_x, grid_y = torch.meshgrid(x_grid, y_grid, indexing='ij')
                
                t_tensor = torch.full_like(grid_x, t * 0.01)
                alpha_tensor = torch.full_like(grid_x, alpha)
                
                x_in = torch.stack([grid_x.flatten(), grid_y.flatten(), t_tensor.flatten(), alpha_tensor.flatten()], dim=1)
                u_pred = model(x_in).reshape(1, 1, env.resolution, env.resolution)
            
            u_true_tensor = torch.tensor(u_true, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
            abs_err = torch.mean(torch.abs(u_pred - u_true_tensor)).item()
            errors.append(abs_err)
            
    return np.median(errors)

def main():
    if HeatEnv is None:
        print("Note: HeatEnv is not available in the repository. Skipping live environment rollout.")
        return
    env = HeatEnv(resolution=64)
    print("--- Median Absolute Error Summary ---")
    
    # FNO variants
    fno_base = evaluate_model(FNO2d, str(MODELS / "fno2d_heat.pt"), env, is_fno=True)
    fno_expC = evaluate_model(HardConstraintFNO2d, str(EXP_MODELS / "fno2d_expC.pt"), env, is_fno=True)
    fno_expD = evaluate_model(BoundedReparametrizedFNO2d, str(MODELS / "fno2d_expD.pt"), env, is_fno=True)
    
    print("FNO Baseline: {:.6f}".format(fno_base))
    print("FNO Exp C:    {:.6f}".format(fno_expC))
    print("FNO Exp D:    {:.6f}".format(fno_expD))
    print("-" * 30)
    
    # PINN variants
    pinn_base = evaluate_model(PINN, str(EXP_MODELS / "pinn_heat.pt"), env, is_fno=False)
    pinn_expB = evaluate_model(ReparametrizedPINN, str(EXP_MODELS / "pinn_expB.pt"), env, is_fno=False)
    pinn_expD = evaluate_model(BoundedReparametrizedPINN, str(MODELS / "pinn_expD.pt"), env, is_fno=False)
    
    print("PINN Baseline: {:.6f}".format(pinn_base))
    print("PINN Exp B:    {:.6f}".format(pinn_expB))
    print("PINN Exp D:    {:.6f}".format(pinn_expD))

if __name__ == "__main__":
    main()
