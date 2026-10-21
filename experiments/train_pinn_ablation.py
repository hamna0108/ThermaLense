"""Week 3/6 PINN Ablation Study for Colab / Local Execution.

====================================================================================================
PRE-REGISTRATION DECLARATION:
1. Purpose: Systematic exploratory ablation study benchmarking single-factor architectural
   and optimization variants around the frozen Exp D PINN baseline (src/train_expD_pinn.py).
2. Base Configuration:
   - Network Size: 4 hidden layers of 64 units each [3, 64, 64, 64, 64, 1] wrapped in
     BoundedReparametrizedPINN: u(x, t, a) = sin(pi*x) + x*(1-x)*(1 - exp(-5t))*N(x, t, a).
   - Boundary & Initial Conditions: Hard-constrained identically by construction.
     No IC loss and no BC loss exist in the loss objective (L_IC = 0, L_BC = 0).
   - Activation: tanh (nn.Tanh()).
   - Collocation Sampling: Uniform pseudorandom over (x, t, log10(a)) with N_f = 20,000 points,
     resampled at every training epoch.
   - Loss Weighting: Pure PDE residual loss L = L_PDE (w_pde = 1.0, w_data = 0.0).
     Because IC and BC are hard-constrained, loss weighting ablates PDE-vs-data weighting only.
   - Optimizer: Adam (lr=1e-3, 1000 epochs) followed by L-BFGS (max 500 iters, strong Wolfe).
   - Schedule: Fixed learning rate (1e-3) during Adam phase.
3. Ablation Factor Structure (One Factor at a Time around Base):
   - Activation: tanh (base) vs GELU vs sin
   - Collocation Sampling: base (resampled uniform) vs fixed (static uniform) vs Sobol vs LHS
   - Loss Weighting: base (pure PDE) vs data_equal (w_data=1.0) vs data_heavy (w_pde=0.1, w_data=1.0)
     vs grad_norm (adaptive gradient-norm balancing between PDE and data)
   - Optimizer: base (Adam + L-BFGS) vs Adam only (1500 epochs)
4. Evaluation Splits & Metrics:
   - Evaluated on test_interpolation.npz and test_ood.npz (low-alpha OOD: alpha < 0.01; high-alpha: alpha > 1.0).
   - Metrics: Median relative L2 error (Interp, Low-alpha OOD, High-alpha OOD), t=0 MAE, train runtime.
5. Pre-registered Decision Rule:
   - NO SELECTION ON TEST SPLITS.
   - If an ablated variant achieves lower test error than the base config, findings are documented
     honestly in the report, but the frozen checkpoint models/pinn_expD.pt is RETAINED and NOT replaced.
====================================================================================================
"""

import os
import sys
import time
import json
import hashlib
import argparse
import platform
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Path handling
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
for p in [REPO_ROOT, SRC_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.paths import DATASETS, MODELS, RESULTS
from src.models.pinn import PINN

# -------------------------------------------------------------------------------------------------
# 1. Custom Activations and Reparametrized Architecture
# -------------------------------------------------------------------------------------------------

class SinActivation(nn.Module):
    """Element-wise sine activation function for PINNs."""
    def forward(self, x):
        return torch.sin(x)

class ConfigurablePINN(nn.Module):
    """Configurable Multi-Layer Perceptron supporting custom activation functions."""
    def __init__(self, layers=[3, 64, 64, 64, 64, 1], activation_type='tanh'):
        super().__init__()
        self.layers = nn.ModuleList()
        for i in range(len(layers) - 1):
            self.layers.append(nn.Linear(layers[i], layers[i+1]))
            
        if activation_type.lower() == 'tanh':
            self.activation = nn.Tanh()
        elif activation_type.lower() == 'gelu':
            self.activation = nn.GELU()
        elif activation_type.lower() == 'sin':
            self.activation = SinActivation()
        else:
            raise ValueError(f"Unsupported activation: {activation_type}")
            
    def forward(self, x, t, alpha_scaled):
        inputs = torch.cat([x, t, alpha_scaled], dim=-1)
        out = inputs
        for i in range(len(self.layers) - 1):
            out = self.activation(self.layers[i](out))
        out = self.layers[-1](out)
        return out

class BoundedReparametrizedPINN(nn.Module):
    """Hard-constrained PINN ansatz satisfying IC and Dirichlet BCs identically by construction."""
    def __init__(self, log_alpha_mean, log_alpha_std, activation_type='tanh', layers=[3, 64, 64, 64, 64, 1]):
        super().__init__()
        self.pinn = ConfigurablePINN(layers=layers, activation_type=activation_type)
        self.log_alpha_mean = log_alpha_mean
        self.log_alpha_std = log_alpha_std
        
    def forward(self, x, t, alpha_raw):
        # Scale spatial and temporal coordinates to [-1, 1]
        x_scaled = 2.0 * x - 1.0
        t_scaled = 2.0 * t - 1.0
        
        # Standardize log-diffusivity using precomputed training distribution
        log_alpha = torch.log10(alpha_raw)
        alpha_scaled = (log_alpha - self.log_alpha_mean) / (self.log_alpha_std + 1e-12)
        
        N = self.pinn(x_scaled, t_scaled, alpha_scaled)
        
        # Bounded temporal multiplier: 1 - exp(-5t)
        bounded_t = 1.0 - torch.exp(-t * 5.0)
        
        # Exact boundary & initial condition satisfaction:
        # u(0, t) = sin(0) + 0 = 0
        # u(1, t) = sin(pi) + 0 = 0
        # u(x, 0) = sin(pi*x) + x*(1-x)*(0)*N = sin(pi*x)
        out = torch.sin(np.pi * x) + x * (1.0 - x) * bounded_t * N
        return out

# -------------------------------------------------------------------------------------------------
# 2. PDE Residual and Sampling Utilities
# -------------------------------------------------------------------------------------------------

def compute_pde_loss(model, x, t, alpha_raw):
    """Compute mean squared residual of heat equation: u_t - alpha * u_xx = 0."""
    x = x.clone().detach().requires_grad_(True)
    t = t.clone().detach().requires_grad_(True)
    
    u = model(x, t, alpha_raw)
    
    u_t = torch.autograd.grad(u, t, grad_outputs=torch.ones_like(u), create_graph=True)[0]
    u_x = torch.autograd.grad(u, x, grad_outputs=torch.ones_like(u), create_graph=True)[0]
    u_xx = torch.autograd.grad(u_x, x, grad_outputs=torch.ones_like(u_x), create_graph=True)[0]
    
    f = u_t - alpha_raw * u_xx
    return torch.mean(f**2)

def sample_collocation_points(N, method='base', seed=None, device='cpu'):
    """Sample N collocation points (x, t, alpha_raw) according to specified method."""
    if method == 'base' or method == 'resampled_uniform':
        x = torch.rand(N, 1, device=device)
        t = torch.rand(N, 1, device=device)
        log_alpha = torch.rand(N, 1, device=device) * (-2.0) # [-2, 0] -> alpha in [0.01, 1.0]
        alpha_raw = 10**log_alpha
        return x, t, alpha_raw
        
    elif method == 'sobol':
        sobol = torch.quasirandom.SobolEngine(dimension=3, scramble=True, seed=seed)
        pts = sobol.draw(N).to(device)
        x = pts[:, 0:1]
        t = pts[:, 1:2]
        log_alpha = pts[:, 2:3] * (-2.0)
        alpha_raw = 10**log_alpha
        return x, t, alpha_raw
        
    elif method == 'lhs':
        try:
            from scipy.stats import qmc
            sampler = qmc.LatinHypercube(d=3, seed=seed)
            pts_np = sampler.random(n=N)
        except Exception:
            # Fallback to stratified uniform if qmc unavailable
            pts_np = np.random.RandomState(seed).uniform(0, 1, (N, 3))
        pts = torch.tensor(pts_np, dtype=torch.float32, device=device)
        x = pts[:, 0:1]
        t = pts[:, 1:2]
        log_alpha = pts[:, 2:3] * (-2.0)
        alpha_raw = 10**log_alpha
        return x, t, alpha_raw
        
    else:
        raise ValueError(f"Unknown collocation method: {method}")

def compute_dataset_hash(filepath):
    """Compute SHA-256 checksum of dataset file."""
    if not os.path.exists(filepath):
        return "FILE_NOT_FOUND"
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

# -------------------------------------------------------------------------------------------------
# 3. Model Training & Single-Variant Runner
# -------------------------------------------------------------------------------------------------

def train_single_variant(variant_name, config, seed, device, out_dir, epochs=1000, lbfgs_iters=500, smoke_test=False):
    """Train a single PINN variant under controlled RNG seed."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        
    ckpt_dir = os.path.join(out_dir, "checkpoints")
    os.makedirs(ckpt_dir, exist_ok=True)
    ckpt_path = os.path.join(ckpt_dir, f"pinn_{variant_name}_seed{seed}.pt")
    
    # Load scaling statistics from fno2d_heat.pt or defaults
    fno_path = os.path.join(MODELS, 'fno2d_heat.pt')
    if os.path.exists(fno_path):
        fno_ckpt = torch.load(fno_path, map_location=device, weights_only=False)
        log_alpha_mean = fno_ckpt.get('log_alpha_mean', torch.tensor(-1.0056))
        log_alpha_std = fno_ckpt.get('log_alpha_std', torch.tensor(0.5832))
    else:
        log_alpha_mean = torch.tensor(-1.0056)
        log_alpha_std = torch.tensor(0.5832)
        
    act_type = config.get('activation', 'tanh')
    model = BoundedReparametrizedPINN(log_alpha_mean, log_alpha_std, activation_type=act_type).to(device)
    
    N_f = 2000 if smoke_test else 20000
    actual_epochs = 2 if smoke_test else epochs
    actual_lbfgs_iters = 2 if smoke_test else lbfgs_iters
    
    colloc_method = config.get('collocation', 'base')
    is_fixed_colloc = (colloc_method == 'fixed')
    if is_fixed_colloc:
        fixed_x_f, fixed_t_f, fixed_alpha_f = sample_collocation_points(N_f, method='base', seed=seed, device=device)
        
    # Data loss configuration (if enabled)
    w_pde = config.get('w_pde', 1.0)
    w_data = config.get('w_data', 0.0)
    use_grad_norm = config.get('grad_norm', False)
    
    # Pre-load train data points if data loss is used
    train_data_tensors = None
    if w_data > 0.0 or use_grad_norm:
        train_npz_path = os.path.join(DATASETS, 'train.npz')
        if os.path.exists(train_npz_path):
            d_tr = np.load(train_npz_path)
            u_tr_arr = d_tr['u'] # (1000, 100, 50)
            a_tr_arr = d_tr['alpha']
            x_tr_arr = d_tr['x']
            t_tr_arr = d_tr['t']
            
            # Subsample 2000 fixed measurement points for data loss
            rng_d = np.random.RandomState(seed + 1000)
            sample_eps = rng_d.choice(len(a_tr_arr), size=min(100, len(a_tr_arr)), replace=False)
            d_x_list, d_t_list, d_a_list, d_u_list = [], [], [], []
            for ep_idx in sample_eps:
                t_idx = rng_d.choice(len(t_tr_arr), size=20, replace=False)
                x_idx = rng_d.choice(len(x_tr_arr), size=20, replace=False)
                for ti, xi in zip(t_idx, x_idx):
                    d_x_list.append(x_tr_arr[xi])
                    d_t_list.append(t_tr_arr[ti])
                    d_a_list.append(a_tr_arr[ep_idx])
                    d_u_list.append(u_tr_arr[ep_idx, ti, xi])
            train_data_tensors = (
                torch.tensor(d_x_list, dtype=torch.float32, device=device).unsqueeze(1),
                torch.tensor(d_t_list, dtype=torch.float32, device=device).unsqueeze(1),
                torch.tensor(d_a_list, dtype=torch.float32, device=device).unsqueeze(1),
                torch.tensor(d_u_list, dtype=torch.float32, device=device).unsqueeze(1),
            )
            
    optimizer_type = config.get('optimizer', 'adam_lbfgs')
    adam_epochs = actual_epochs if optimizer_type != 'adam_only' else int(actual_epochs * 1.5)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    t_start = time.time()
    model.train()
    
    for epoch in range(adam_epochs):
        optimizer.zero_grad()
        
        # Collocation sampling
        if is_fixed_colloc:
            x_f, t_f, alpha_f = fixed_x_f, fixed_t_f, fixed_alpha_f
        else:
            x_f, t_f, alpha_f = sample_collocation_points(N_f, method=colloc_method, seed=seed+epoch, device=device)
            
        loss_pde = compute_pde_loss(model, x_f, t_f, alpha_f)
        
        # Data loss computation
        if train_data_tensors is not None:
            d_x, d_t, d_a, d_u = train_data_tensors
            u_pred = model(d_x, d_t, d_a)
            loss_data = torch.mean((u_pred - d_u)**2)
            
            if use_grad_norm:
                # Wang et al. 2021 gradient-norm balancing
                optimizer.zero_grad()
                loss_pde.backward(retain_graph=True)
                grad_pde_norm = torch.sqrt(sum(p.grad.norm()**2 for p in model.parameters() if p.grad is not None))
                
                optimizer.zero_grad()
                loss_data.backward(retain_graph=True)
                grad_data_norm = torch.sqrt(sum(p.grad.norm()**2 for p in model.parameters() if p.grad is not None))
                
                optimizer.zero_grad()
                w_d_adaptive = float(grad_pde_norm / (grad_data_norm + 1e-12))
                loss = loss_pde + w_d_adaptive * loss_data
            else:
                loss = w_pde * loss_pde + w_data * loss_data
        else:
            loss = loss_pde
            
        loss.backward()
        optimizer.step()
        
    # Phase 2: L-BFGS (if configured)
    if optimizer_type == 'adam_lbfgs':
        optimizer_lbfgs = torch.optim.LBFGS(model.parameters(), max_iter=actual_lbfgs_iters, line_search_fn="strong_wolfe")
        def closure():
            optimizer_lbfgs.zero_grad()
            if is_fixed_colloc:
                x_c, t_c, a_c = fixed_x_f, fixed_t_f, fixed_alpha_f
            else:
                x_c, t_c, a_c = sample_collocation_points(N_f, method=colloc_method, seed=seed+9999, device=device)
            l_pde = compute_pde_loss(model, x_c, t_c, a_c)
            l_tot = l_pde
            if train_data_tensors is not None and w_data > 0.0:
                d_x, d_t, d_a, d_u = train_data_tensors
                l_dat = torch.mean((model(d_x, d_t, d_a) - d_u)**2)
                l_tot = w_pde * l_pde + w_data * l_dat
            l_tot.backward()
            return l_tot
            
        optimizer_lbfgs.step(closure)
        
    train_time = round(time.time() - t_start, 2)
    
    # Save checkpoint
    torch.save({
        'variant': variant_name,
        'config': config,
        'seed': seed,
        'train_time_sec': train_time,
        'model_state_dict': model.state_dict(),
        'log_alpha_mean': log_alpha_mean,
        'log_alpha_std': log_alpha_std
    }, ckpt_path)
    
    return model, train_time, ckpt_path

# -------------------------------------------------------------------------------------------------
# 4. Standard Evaluation on Exp D Splits
# -------------------------------------------------------------------------------------------------

def evaluate_pinn_model(model, device):
    """Evaluate PINN on test_interpolation.npz and test_ood.npz matching Exp D metrics."""
    model.eval()
    
    # 1. Test Interpolation
    interp_path = os.path.join(DATASETS, 'test_interpolation.npz')
    d_in = np.load(interp_path)
    x_np = d_in['x']
    t_np = d_in['t']
    u_in = d_in['u']
    a_in = d_in['alpha']
    
    tm, xm = np.meshgrid(t_np, x_np, indexing='ij')
    t_flat = torch.tensor(tm, dtype=torch.float32, device=device).view(-1, 1)
    x_flat = torch.tensor(xm, dtype=torch.float32, device=device).view(-1, 1)
    
    interp_rel_l2 = []
    t0_mae_list = []
    
    with torch.no_grad():
        for i in range(len(a_in)):
            alpha_val = float(a_in[i])
            a_flat = torch.full_like(t_flat, alpha_val)
            pred = model(x_flat, t_flat, a_flat).view(len(t_np), len(x_np)).cpu().numpy()
            target = u_in[i]
            
            rel_err = float(np.linalg.norm(pred - target) / (np.linalg.norm(target) + 1e-12))
            interp_rel_l2.append(rel_err)
            
            # t=0 MAE
            t0_mae = float(np.mean(np.abs(pred[0, :] - target[0, :])))
            t0_mae_list.append(t0_mae)
            
    # 2. Test OOD (Low-alpha and High-alpha)
    ood_path = os.path.join(DATASETS, 'test_ood.npz')
    d_ood = np.load(ood_path)
    u_ood = d_ood['u']
    a_ood = d_ood['alpha']
    
    low_rel_l2 = []
    high_rel_l2 = []
    
    with torch.no_grad():
        for i in range(len(a_ood)):
            alpha_val = float(a_ood[i])
            a_flat = torch.full_like(t_flat, alpha_val)
            pred = model(x_flat, t_flat, a_flat).view(len(t_np), len(x_np)).cpu().numpy()
            target = u_ood[i]
            
            rel_err = float(np.linalg.norm(pred - target) / (np.linalg.norm(target) + 1e-12))
            if alpha_val < 0.01:
                low_rel_l2.append(rel_err)
            elif alpha_val > 1.0:
                high_rel_l2.append(rel_err)
                
    return {
        'interp_rel_l2_median': float(np.median(interp_rel_l2)),
        'low_alpha_ood_rel_l2_median': float(np.median(low_rel_l2)) if low_rel_l2 else 0.0,
        'high_alpha_ood_rel_l2_median': float(np.median(high_rel_l2)) if high_rel_l2 else 0.0,
        't0_mae_median': float(np.median(t0_mae_list))
    }

# -------------------------------------------------------------------------------------------------
# 5. Main Ablation Orchestrator
# -------------------------------------------------------------------------------------------------

def run_ablation_study(args):
    device = torch.device(args.device if (args.device == 'cpu' or torch.cuda.is_available()) else 'cpu')
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    
    print("=" * 105)
    print("EXPERIMENT G: PINN SINGLE-FACTOR ABLATION STUDY (Exp D Architecture)")
    print(f"Device: {device} | Output Directory: {out_dir}")
    print("=" * 105)
    
    # 1. Dataset Verification & SHA-256 Hashes
    dataset_files = ["train.npz", "val.npz", "test_interpolation.npz", "test_ood.npz"]
    dataset_hashes = {f: compute_dataset_hash(os.path.join(DATASETS, f)) for f in dataset_files}
    
    # 2. Write System & Experiment Manifest
    manifest = {
        'study_name': 'PINN Single-Factor Ablation Study',
        'execution_date': time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        'device_name': torch.cuda.get_device_name(0) if device.type == 'cuda' else platform.processor(),
        'platform_system': platform.system(),
        'platform_release': platform.release(),
        'python_version': platform.python_version(),
        'torch_version': torch.__version__,
        'numpy_version': np.__version__,
        'cuda_available': torch.cuda.is_available(),
        'cuda_version': torch.version.cuda if torch.cuda.is_available() else 'N/A',
        'dataset_sha256': dataset_hashes,
        'pre_registration_rule': (
            "No selection on test splits; even if an ablated variant beats base, "
            "it is reported for transparency but models/pinn_expD.pt is retained."
        )
    }
    manifest_path = os.path.join(out_dir, "pinn_ablation_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    print(f"[Manifest] Saved system metadata to: {manifest_path}")
    
    # 3. Define Ablation Variants around Base
    # Base: activation=tanh, collocation=base, loss=pure_pde, optimizer=adam_lbfgs
    variants = {
        # Base Configuration
        'base': {'activation': 'tanh', 'collocation': 'base', 'w_pde': 1.0, 'w_data': 0.0, 'optimizer': 'adam_lbfgs'},
        
        # 1. Activation Ablation
        'activation_gelu': {'activation': 'gelu', 'collocation': 'base', 'w_pde': 1.0, 'w_data': 0.0, 'optimizer': 'adam_lbfgs'},
        'activation_sin':  {'activation': 'sin',  'collocation': 'base', 'w_pde': 1.0, 'w_data': 0.0, 'optimizer': 'adam_lbfgs'},
        
        # 2. Collocation Sampling Ablation
        'collocation_fixed': {'activation': 'tanh', 'collocation': 'fixed', 'w_pde': 1.0, 'w_data': 0.0, 'optimizer': 'adam_lbfgs'},
        'collocation_sobol': {'activation': 'tanh', 'collocation': 'sobol', 'w_pde': 1.0, 'w_data': 0.0, 'optimizer': 'adam_lbfgs'},
        'collocation_lhs':   {'activation': 'tanh', 'collocation': 'lhs',   'w_pde': 1.0, 'w_data': 0.0, 'optimizer': 'adam_lbfgs'},
        
        # 3. Loss Weighting Ablation (PDE vs Data, as IC/BC is hard-constrained)
        'loss_data_equal': {'activation': 'tanh', 'collocation': 'base', 'w_pde': 1.0, 'w_data': 1.0, 'optimizer': 'adam_lbfgs'},
        'loss_data_heavy': {'activation': 'tanh', 'collocation': 'base', 'w_pde': 0.1, 'w_data': 1.0, 'optimizer': 'adam_lbfgs'},
        'loss_grad_norm':  {'activation': 'tanh', 'collocation': 'base', 'w_pde': 1.0, 'w_data': 1.0, 'grad_norm': True, 'optimizer': 'adam_lbfgs'},
        
        # 4. Optimizer Ablation
        'optim_adam_only': {'activation': 'tanh', 'collocation': 'base', 'w_pde': 1.0, 'w_data': 0.0, 'optimizer': 'adam_only'},
    }
    
    # Filter variants if user requested specific ones
    if args.variants != 'all':
        req = [v.strip() for v in args.variants.split(',')]
        variants = {k: v for k, v in variants.items() if k in req}
        
    seeds = [int(s.strip()) for s in args.seeds.split(',')]
    
    # Summary CSV path
    summary_csv_path = os.path.join(out_dir, "pinn_ablation_summary.csv")
    metrics_json_path = os.path.join(out_dir, "pinn_ablation_metrics.json")
    
    results_list = []
    if args.resume and os.path.exists(summary_csv_path):
        df_existing = pd.read_csv(summary_csv_path)
        results_list = df_existing.to_dict('records')
        print(f"[Resume] Loaded {len(results_list)} existing runs from {summary_csv_path}")
        
    completed_keys = {(r['variant'], int(r['seed'])) for r in results_list}
    
    # 4. Evaluate Frozen Baseline Checkpoint first (Reference Row)
    frozen_pinn_path = os.path.join(MODELS, 'pinn_expD.pt')
    if os.path.exists(frozen_pinn_path) and ('frozen_expD', 42) not in completed_keys:
        print("\n--- Evaluating Frozen Baseline Checkpoint (models/pinn_expD.pt) ---")
        f_ckpt = torch.load(frozen_pinn_path, map_location=device, weights_only=False)
        m_frozen = BoundedReparametrizedPINN(f_ckpt['log_alpha_mean'], f_ckpt['log_alpha_std']).to(device)
        m_frozen.load_state_dict(f_ckpt['model_state_dict'])
        m_frozen_eval = evaluate_pinn_model(m_frozen, device)
        
        ref_row = {
            'variant': 'frozen_expD',
            'axis': 'frozen_reference',
            'seed': 42,
            'activation': 'tanh',
            'collocation': 'base',
            'loss_weighting': 'pure_pde',
            'optimizer': 'adam_lbfgs',
            'interp_rel_l2_median': m_frozen_eval['interp_rel_l2_median'],
            'low_alpha_ood_rel_l2_median': m_frozen_eval['low_alpha_ood_rel_l2_median'],
            'high_alpha_ood_rel_l2_median': m_frozen_eval['high_alpha_ood_rel_l2_median'],
            't0_mae_median': m_frozen_eval['t0_mae_median'],
            'train_time_sec': 0.0,
            'status': 'FROZEN_BASELINE_RETAINED'
        }
        results_list.append(ref_row)
        print(f"  Frozen: Interp L2={ref_row['interp_rel_l2_median']:.6f} | Low-a={ref_row['low_alpha_ood_rel_l2_median']:.6f} | High-a={ref_row['high_alpha_ood_rel_l2_median']:.6f} | t0={ref_row['t0_mae_median']:.6f}")
        
    # 5. Execute Training Loop across Variants and Seeds
    total_runs = len(variants) * len(seeds)
    run_idx = 0
    
    for v_name, v_cfg in variants.items():
        # Determine ablation axis
        if v_name == 'base':
            axis = 'base'
        elif 'activation' in v_name:
            axis = 'activation'
        elif 'collocation' in v_name:
            axis = 'collocation'
        elif 'loss' in v_name:
            axis = 'loss_weighting'
        elif 'optim' in v_name:
            axis = 'optimizer'
        else:
            axis = 'custom'
            
        for s in seeds:
            run_idx += 1
            if (v_name, s) in completed_keys:
                print(f"[{run_idx}/{total_runs}] Skipping completed: {v_name} (seed {s})")
                continue
                
            print(f"\n[{run_idx}/{total_runs}] Training Variant: {v_name} | Seed: {s} | Axis: {axis}")
            print(f"  Config: {v_cfg}")
            
            try:
                model, train_time, ckpt_path = train_single_variant(
                    v_name, v_cfg, s, device, out_dir,
                    epochs=args.epochs, lbfgs_iters=args.lbfgs_iters,
                    smoke_test=args.smoke_test
                )
                
                # Evaluation
                eval_metrics = evaluate_pinn_model(model, device)
                
                row = {
                    'variant': v_name,
                    'axis': axis,
                    'seed': s,
                    'activation': v_cfg.get('activation', 'tanh'),
                    'collocation': v_cfg.get('collocation', 'base'),
                    'loss_weighting': 'grad_norm' if v_cfg.get('grad_norm', False) else f"pde_{v_cfg.get('w_pde', 1.0)}_data_{v_cfg.get('w_data', 0.0)}",
                    'optimizer': v_cfg.get('optimizer', 'adam_lbfgs'),
                    'interp_rel_l2_median': eval_metrics['interp_rel_l2_median'],
                    'low_alpha_ood_rel_l2_median': eval_metrics['low_alpha_ood_rel_l2_median'],
                    'high_alpha_ood_rel_l2_median': eval_metrics['high_alpha_ood_rel_l2_median'],
                    't0_mae_median': eval_metrics['t0_mae_median'],
                    'train_time_sec': train_time,
                    'status': 'EVALUATED'
                }
                results_list.append(row)
                completed_keys.add((v_name, s))
                
                # Checkpoint status
                print(f"  Results: Interp={row['interp_rel_l2_median']:.6f} | Low-a={row['low_alpha_ood_rel_l2_median']:.6f} | High-a={row['high_alpha_ood_rel_l2_median']:.6f} | Time={train_time}s")
                
                # Save incremental results to CSV & JSON
                df_out = pd.DataFrame(results_list)
                df_out.to_csv(summary_csv_path, index=False)
                with open(metrics_json_path, 'w', encoding='utf-8') as f:
                    json.dump(results_list, f, indent=2)
                    
            except Exception as e:
                print(f"ERROR on {v_name} seed {s}: {e}")
                import traceback
                traceback.print_exc()
                
    print("\n" + "=" * 105)
    print("PINN ABLATION STUDY RUN COMPLETE")
    print(f"Saved Summary Table: {summary_csv_path}")
    print(f"Saved Metrics JSON:  {metrics_json_path}")
    print(f"Saved System Manifest:{manifest_path}")
    print("=" * 105)

# -------------------------------------------------------------------------------------------------
# 6. CLI Argument Parsing
# -------------------------------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="PINN Single-Factor Ablation Study Runner")
    parser.add_argument("--device", type=str, default="cuda", help="Computation device ('cuda' or 'cpu')")
    parser.add_argument("--seed", type=int, default=None, help="Run single specific seed")
    parser.add_argument("--seeds", type=str, default="42,43,44", help="Comma-separated list of seeds")
    parser.add_argument("--out-dir", type=str, default=os.path.join(RESULTS, "pinn_ablation"), help="Output directory")
    parser.add_argument("--resume", action="store_true", help="Resume from existing summary CSV")
    parser.add_argument("--epochs", type=int, default=1000, help="Adam training epochs (default: 1000)")
    parser.add_argument("--lbfgs-iters", type=int, default=500, help="L-BFGS max iterations (default: 500)")
    parser.add_argument("--variants", type=str, default="all", help="Comma-separated variants to run, or 'all'")
    parser.add_argument("--smoke-test", action="store_true", help="Fast 2-epoch run for verification")
    args = parser.parse_args()
    
    if args.seed is not None:
        args.seeds = str(args.seed)
    return args

if __name__ == '__main__':
    run_ablation_study(parse_args())
