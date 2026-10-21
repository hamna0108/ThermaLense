"""Unit Tests for Week 6 V2 Modules (src/v2/).

Tests D1 (sigma estimation & k<20 refusal), D2 (goodness-of-fit gating),
D3 (range guard routing & bound flagging), and D4 (declared physics inversion).
"""

import pytest
import numpy as np
from src.solvers.heat_1d import solve_heat_1d_exact
from src.v2.sigma_estimator import estimate_sigma_from_baseline
from src.v2.gof_gate import evaluate_goodness_of_fit, DEFAULT_TAU_GOF
from src.v2.range_guard import check_bound_pinning
from src.v2.declared_physics import invert_with_declared_physics

def test_d1_sigma_estimation():
    rng = np.random.RandomState(42)
    alpha_true = 0.100
    sigma_true = 0.05
    k = 20
    tb = np.linspace(0.01, 0.5, k)
    xb = rng.uniform(0.2, 0.8, k)
    yb = solve_heat_1d_exact(xb, tb, alpha_true) + rng.normal(0, sigma_true, k)
    
    res = estimate_sigma_from_baseline(xb, tb, yb, min_readings=20)
    assert 0.035 <= res['sigma_hat'] <= 0.065
    assert res['dof'] == 19
    assert abs(res['alpha_base'] - alpha_true) < 0.03

def test_d1_k_less_than_20_refusal():
    rng = np.random.RandomState(42)
    tb = np.linspace(0.01, 0.5, 12)
    xb = rng.uniform(0.2, 0.8, 12)
    yb = solve_heat_1d_exact(xb, tb, 0.1) + rng.normal(0, 0.01, 12)
    
    # Should raise ValueError when allow_fewer=False
    with pytest.raises(ValueError, match="Service Refused"):
        estimate_sigma_from_baseline(xb, tb, yb, min_readings=20, allow_fewer=False)
        
    # Should issue warning when allow_fewer=True
    with pytest.warns(UserWarning, match="k=12 < 20"):
        res = estimate_sigma_from_baseline(xb, tb, yb, min_readings=20, allow_fewer=True)
        assert len(res['warnings']) > 0

def test_d2_goodness_of_fit_healthy_vs_invalid():
    rng = np.random.RandomState(42)
    N = 10
    t_s = np.logspace(np.log10(0.01), 0, N)
    x_s = rng.uniform(0.2, 0.8, N)
    alpha_true = 0.100
    sigma = 0.01
    
    # Healthy case
    y_healthy = solve_heat_1d_exact(x_s, t_s, alpha_true) + rng.normal(0, sigma, N)
    gof_healthy = evaluate_goodness_of_fit(x_s, t_s, y_healthy, alpha_true, sigma, tau_gof=DEFAULT_TAU_GOF)
    assert gof_healthy['chi2_dof'] < DEFAULT_TAU_GOF
    assert not gof_healthy['model_invalid']
    
    # Unmodeled physics case (corrupted by large constant offset)
    y_invalid = y_healthy + 0.10
    gof_invalid = evaluate_goodness_of_fit(x_s, t_s, y_invalid, alpha_true, sigma, tau_gof=DEFAULT_TAU_GOF)
    assert gof_invalid['chi2_dof'] > DEFAULT_TAU_GOF
    assert gof_invalid['model_invalid']

def test_d3_range_guard_bound_flagging():
    # Grid bound is [0.001, 10.0]
    # At bound within 1%
    assert check_bound_pinning(0.00100)[0] is True
    assert check_bound_pinning(0.00101)[0] is True
    assert check_bound_pinning(0.00105)[0] is False
    assert check_bound_pinning(0.100)[0] is False
    assert check_bound_pinning(5.0)[0] is False
    assert check_bound_pinning(9.85)[0] is False
    assert check_bound_pinning(9.90)[0] is True
    assert check_bound_pinning(9.999)[0] is True

def test_d4_declared_physics_inversion():
    rng = np.random.RandomState(42)
    N = 10
    t_s = np.logspace(np.log10(0.01), 0, N)
    x_s = rng.uniform(0.2, 0.8, N)
    alpha_true = 0.100
    sigma = 0.01
    
    # Custom IC: sin(2 pi x)
    u0_custom = lambda x: np.sin(2.0 * np.pi * x)
    res_d4 = invert_with_declared_physics(x_s, t_s,
                                         # Synthetic data from same IC
                                         y_s=np.sin(2.0*np.pi*x_s)*np.exp(-alpha_true*(2*np.pi)**2 * t_s) + rng.normal(0, sigma, N),
                                         sigma=sigma,
                                         alpha_true=alpha_true,
                                         u0_fn=u0_custom,
                                         Nx=51, Nt=201)
    assert res_d4['rel_error'] < 0.05
    assert res_d4['chi2_dof'] < 2.0
