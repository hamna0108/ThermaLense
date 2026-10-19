import torch
import numpy as np
import sys
import os

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
src_dir = os.path.join(base_dir, "src")
exp_dir = os.path.join(base_dir, "experiments")
for p in [base_dir, src_dir, exp_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from paths import MODELS
try:
    from envs.heat_env import HeatEnv
except ImportError:
    HeatEnv = None

from models.fno2d import FNO2d
from train_expD_fno import BoundedReparametrizedFNO2d

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def evaluate_model_t1_99(model_class, path, env, rollout_steps=100):
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
            
            t_tensor = torch.full_like(u_tensor, t * 0.01)
            alpha_tensor = torch.full_like(u_tensor, alpha)
            x_in = torch.cat([u_tensor, t_tensor, alpha_tensor], dim=1)
            u_pred = model(x_in)
            u_tensor = u_pred
            
            if t > 0: # t=1 to 99 (index 1 to 99)
                u_true_tensor = torch.tensor(u_true, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
                abs_err = torch.mean(torch.abs(u_pred - u_true_tensor)).item()
                errors.append(abs_err)
            
    return np.mean(errors)

def main():
    if HeatEnv is None:
        print("Note: HeatEnv is not available in the repository. Skipping live environment rollout.")
        return
    env = HeatEnv(resolution=64)
    print("--- Mean Absolute Error (t=1 to 99) ---")
    
    # FNO variants
    fno_base = evaluate_model_t1_99(FNO2d, str(MODELS / "fno2d_heat.pt"), env)
    fno_expD = evaluate_model_t1_99(BoundedReparametrizedFNO2d, str(MODELS / "fno2d_expD.pt"), env)
    
    print(f"FNO Baseline (t=1-99): {fno_base:.6f}")
    print(f"FNO Exp D (t=1-99):    {fno_expD:.6f}")
    print("-" * 30)

if __name__ == "__main__":
    main()
