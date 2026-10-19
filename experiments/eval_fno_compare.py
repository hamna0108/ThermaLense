import sys, os
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_dir = os.path.join(base_dir, "src")
exp_dir = os.path.abspath(os.path.dirname(__file__))
for p in [base_dir, src_dir, exp_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from paths import DATASETS, MODELS
import torch
import numpy as np
from torch.utils.data import DataLoader

from data.dataset import HeatEquationDataset
from models.fno2d import FNO2d
from train_expD_fno import BoundedReparametrizedFNO2d

def get_errors_for_model(model_class, model_name, dataloader, device, is_expD=False):
    model_path = str(MODELS / model_name)
    checkpoint = torch.load(model_path, map_location=device)
    
    if is_expD:
        model = model_class().to(device)
    else:
        model = model_class(modes1=16, modes2=12, width=32).to(device)
    
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    abs_errors = []
    
    with torch.no_grad():
        for x, y in dataloader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            
            if out.dim() == 4:
                out = out.squeeze(1)
            if y.dim() == 4:
                y = y.squeeze(1)
                
            diff_norms = torch.norm(out - y, 2, dim=2)
            abs_errors.append(diff_norms.cpu().numpy())
            
    abs_errors = np.concatenate(abs_errors, axis=0)
    
    # average across test set
    mean_abs_err_per_t = np.mean(abs_errors, axis=0)
    # average for t=1 to 99
    mean_abs_t1_99 = np.mean(mean_abs_err_per_t[1:])
    return mean_abs_t1_99

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    checkpoint = torch.load(str(MODELS / 'fno2d_heat.pt'), map_location=device)
    test_ood_dataset = HeatEquationDataset(str(DATASETS / 'test_ood.npz'), 
                                           log_alpha_mean=checkpoint['log_alpha_mean'], 
                                           log_alpha_std=checkpoint['log_alpha_std'])
    
    test_ood_loader = DataLoader(test_ood_dataset, batch_size=20, shuffle=False)
    
    err_base = get_errors_for_model(FNO2d, 'fno2d_heat.pt', test_ood_loader, device, is_expD=False)
    err_expD = get_errors_for_model(BoundedReparametrizedFNO2d, 'fno2d_expD.pt', test_ood_loader, device, is_expD=True)
    
    print(f"FNO Baseline MAE (t=1-99): {err_base:.6f}")
    print(f"FNO Exp D MAE (t=1-99):    {err_expD:.6f}")

if __name__ == '__main__':
    main()
