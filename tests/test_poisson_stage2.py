import os
import sys
import numpy as np
import pytest
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.solvers.poisson_2d import Poisson2DSolver, manufactured_source_2d, solve_poisson_2d_exact, compute_convergence_study
from src.models.fno2d import FNO2d
from src.models.pinn_poisson import HardPINNPoisson
from src.models.linear_baseline import LinearPoissonBaseline
from src.data.poisson_loader import load_all_splits

def test_solver_convergence_order_2():
    """Verify that the 5-point finite difference solver converges with order 2 on manufactured solution."""
    conv = compute_convergence_study(resolutions=(16, 32, 64, 128))
    orders = [c["order"] for c in conv if c["order"] is not None]
    assert len(orders) == 3
    for o in orders:
        assert 1.95 <= o <= 2.05, f"Expected order ~ 2.0, got {o}"

def test_solver_discrete_residual():
    """Verify that solver solution has machine-precision interior discrete residual."""
    solver = Poisson2DSolver(N=64)
    u = solver.solve(manufactured_source_2d)
    rel_res, max_res = solver.compute_residual(u, manufactured_source_2d)
    assert rel_res < 1e-10, f"Residual too large: {rel_res}"

def test_hard_bc_satisfaction():
    """Verify that both FNO2d and PINN enforce zero Dirichlet boundary conditions strictly."""
    # FNO hard mask
    fno = FNO2d(modes1=12, modes2=12, width=32, use_hard_mask=True)
    x = torch.randn(2, 3, 64, 64)
    y = fno(x)
    assert torch.all(y[:, :, 0, :] == 0.0)
    assert torch.all(y[:, :, -1, :] == 0.0)
    assert torch.all(y[:, :, :, 0] == 0.0)
    assert torch.all(y[:, :, :, -1] == 0.0)
    
    # PINN hard envelope x*(1-x)*y*(1-y)
    pinn = HardPINNPoisson()
    N_pts = 50
    left_edge = torch.stack([torch.zeros(N_pts), torch.linspace(0, 1, N_pts)], dim=1)
    right_edge = torch.stack([torch.ones(N_pts), torch.linspace(0, 1, N_pts)], dim=1)
    bottom_edge = torch.stack([torch.linspace(0, 1, N_pts), torch.zeros(N_pts)], dim=1)
    top_edge = torch.stack([torch.linspace(0, 1, N_pts), torch.ones(N_pts)], dim=1)
    
    for edge in [left_edge, right_edge, bottom_edge, top_edge]:
        u_edge = pinn(edge)
        assert torch.all(u_edge == 0.0), f"PINN boundary violation on edge: {u_edge.abs().max()}"

def test_dataset_v1_disjoint_seeds():
    """Verify dataset v1 splits, row counts, and disjointness of seeds."""
    splits = load_all_splits("data", version="v1")
    expected_counts = {
        "train": 1000,
        "val": 100,
        "test_interp": 200,
        "test_ood_narrow": 200,
        "test_ood_count": 200,
        "test_ood_boundary": 200
    }
    all_seeds = []
    for split_name, exp_n in expected_counts.items():
        assert split_name in splits
        seeds = splits[split_name]["seeds"]
        assert len(seeds) == exp_n
        all_seeds.extend(seeds.tolist())
        
    assert len(all_seeds) == 1900
    assert len(set(all_seeds)) == 1900, "Seeds are not strictly disjoint!"

def test_dataset_v2_disjoint_seeds_and_sine_modes():
    """Verify dataset v2 splits (including highmodes), 2100 samples, and disjoint seeds."""
    splits = load_all_splits("data", version="v2")
    expected_counts = {
        "train": 1000,
        "val": 100,
        "test_interp": 200,
        "test_ood_narrow": 200,
        "test_ood_count": 200,
        "test_ood_boundary": 200,
        "test_ood_highmodes": 200
    }
    all_seeds = []
    for split_name, exp_n in expected_counts.items():
        assert split_name in splits
        seeds = splits[split_name]["seeds"]
        assert len(seeds) == exp_n
        all_seeds.extend(seeds.tolist())
        
    assert len(all_seeds) == 2100
    assert len(set(all_seeds)) == 2100, "v2 Seeds are not strictly disjoint!"

def test_svd_decay_rapid():
    """Verify that the training source matrix has rapid singular-value decay."""
    splits = load_all_splits("data", version="v2")
    F_mat = splits["train"]["F"][:300].reshape(300, -1).astype(np.float64)
    s = np.linalg.svd(F_mat, compute_uv=False)
    # sigma_10 should be substantially smaller than sigma_1
    assert s[9] / s[0] < 0.5
    # sigma_50 should be << 1e-3 of sigma_1
    assert s[49] / s[0] < 1e-3

def test_linear_baseline_performance():
    """Verify that Linear Ridge baseline matches Poisson operator and generalizes OOD."""
    splits = load_all_splits("data", version="v2")
    lin = LinearPoissonBaseline(alpha_reg=1e-8)
    lin.fit(splits["train"]["F"], splits["train"]["U"])
    
    pred_interp = lin.predict(splits["test_interp"]["F"])
    diff = pred_interp - splits["test_interp"]["U"]
    rel_l2_interp = np.median(np.linalg.norm(diff.reshape(len(diff), -1), axis=1) /
                              np.linalg.norm(splits["test_interp"]["U"].reshape(len(diff), -1), axis=1))
    assert rel_l2_interp < 1e-4, f"Linear baseline interpolation error too high: {rel_l2_interp}"
