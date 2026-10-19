import os
import sys
import time
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import torch
import numpy as np
from src.models.pinn_poisson import HardPINNPoisson

def train_pinn_single_source(n_collocation=1000, adam_epochs=600, lbfgs_iters=60, seed=42):
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    os.makedirs("models", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    model = HardPINNPoisson(hidden_layers=[50, 50, 50, 50])
    
    # Collocation coordinates in (0, 1)^2
    xy_coords = torch.rand(n_collocation, 2)
    
    t0 = time.time()
    
    # 1. Adam Stage
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=adam_epochs, eta_min=1e-4)
    
    for epoch in range(adam_epochs):
        optimizer.zero_grad()
        xy = xy_coords.clone().requires_grad_(True)
        f_vals = 2.0 * np.pi**2 * torch.sin(np.pi * xy[:, 0:1]) * torch.sin(np.pi * xy[:, 1:2])
        residual, _ = model.compute_residual(xy, f_vals)
        loss = torch.mean(residual**2)
        loss.backward()
        optimizer.step()
        scheduler.step()
        
    adam_time = time.time() - t0
    
    # 2. L-BFGS Stage
    lbfgs = torch.optim.LBFGS(
        model.parameters(),
        max_iter=lbfgs_iters,
        tolerance_grad=1e-8,
        tolerance_change=1e-12,
        history_size=50,
        line_search_fn="strong_wolfe"
    )
    
    def closure():
        lbfgs.zero_grad()
        xy = xy_coords.clone().requires_grad_(True)
        f_vals = 2.0 * np.pi**2 * torch.sin(np.pi * xy[:, 0:1]) * torch.sin(np.pi * xy[:, 1:2])
        residual, _ = model.compute_residual(xy, f_vals)
        loss = torch.mean(residual**2)
        loss.backward()
        return loss
        
    lbfgs.step(closure)
    total_train_time = time.time() - t0
    
    # Evaluation on 64x64 evaluation grid
    N_eval = 64
    x_g = np.linspace(0, 1, N_eval)
    y_g = np.linspace(0, 1, N_eval)
    X, Y = np.meshgrid(x_g, y_g, indexing="ij")
    grid_coords = torch.tensor(
        np.stack([X.flatten(), Y.flatten()], axis=1),
        dtype=torch.float32
    )
    
    model.eval()
    with torch.no_grad():
        u_pred = model(grid_coords).cpu().numpy().reshape(N_eval, N_eval)
        
    u_exact = np.sin(np.pi * X) * np.sin(np.pi * Y)
    
    diff = u_pred - u_exact
    rel_l2 = float(np.linalg.norm(diff) / np.linalg.norm(u_exact))
    max_err = float(np.max(np.abs(diff)))
    
    # Check boundary condition satisfaction
    bc_err = float(max(
        np.max(np.abs(u_pred[0, :])),
        np.max(np.abs(u_pred[-1, :])),
        np.max(np.abs(u_pred[:, 0])),
        np.max(np.abs(u_pred[:, -1]))
    ))
    
    # Discrete residual on grid
    h = 1.0 / (N_eval - 1)
    u_int = u_pred[1:-1, 1:-1]
    lap_u = (
        -4.0 * u_int
        + u_pred[2:, 1:-1]
        + u_pred[:-2, 1:-1]
        + u_pred[1:-1, 2:]
        + u_pred[1:-1, :-2]
    ) / (h**2)
    f_grid = 2.0 * np.pi**2 * np.sin(np.pi * X) * np.sin(np.pi * Y)
    grid_res = -lap_u - f_grid[1:-1, 1:-1]
    rel_pde_res = float(np.linalg.norm(grid_res) / np.linalg.norm(f_grid[1:-1, 1:-1]))
    
    metrics = {
        "source": "manufactured",
        "formula": "2*pi^2*sin(pi*x)*sin(pi*y)",
        "exact_solution": "sin(pi*x)*sin(pi*y)",
        "rel_l2_error": rel_l2,
        "max_abs_error": max_err,
        "bc_violation_max": bc_err,
        "pde_residual_rel": rel_pde_res,
        "training_time_sec": total_train_time,
        "adam_time_sec": adam_time,
        "n_collocation": n_collocation,
        "adam_epochs": adam_epochs,
        "lbfgs_iters": lbfgs_iters
    }
    
    # Save model and metrics
    torch.save(model.state_dict(), "models/pinn_poisson.pt")
    with open("data/pinn_poisson_summary.json", "w") as f:
        json.dump(metrics, f, indent=2)
        
    print(f"PINN Training complete in {total_train_time:.2f}s!")
    print(f"  Rel L2 Error   : {rel_l2:.4e}")
    print(f"  Max Error      : {max_err:.4e}")
    print(f"  BC Violation   : {bc_err:.4e} (strictly 0 by construction)")
    print(f"  Grid PDE Res   : {rel_pde_res:.4e}")
    return metrics

if __name__ == "__main__":
    train_pinn_single_source()
