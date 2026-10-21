"""Unit Tests for Week 6 V2 Modules (src/v2/).

Tests D1 (sigma estimation & k<20 refusal & drift check),
D2 (dynamic chi2/dof goodness-of-fit gating, DW, kurtosis),
D3 (range guard routing & 0.1 decade / CI bound flagging),
and D4 (declared physics inversion with splu).
"""

import pytest
import numpy as np
from src.solvers.heat_1d import solve_heat_1d_exact
from src.v2.sigma_estimator import estimate_sigma_from_baseline, check_baseline_drift_warning
from src.v2.gof_gate import evaluate_goodness_of_fit, compute_gof_threshold, DEFAULT_TAU_GOF
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
    assert not res['drift_flag']

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

def test_d2_dynamic_threshold_computation():
    # Dynamic threshold: chi2.ppf(0.95, dof)/dof
    assert abs(compute_gof_threshold(4, 0.05) - 2.3719) < 0.01   # N=5, dof=4
    assert abs(compute_gof_threshold(9, 0.05) - 1.8799) < 0.01   # N=10, dof=9
    assert abs(compute_gof_threshold(19, 0.05) - 1.5865) < 0.01  # N=20, dof=19

def test_d2_goodness_of_fit_healthy_vs_invalid():
    rng = np.random.RandomState(42)
    N = 10
    t_s = np.logspace(np.log10(0.01), 0, N)
    x_s = rng.uniform(0.2, 0.8, N)
    alpha_true = 0.100
    sigma = 0.01
    
    # Healthy case (dynamic threshold default)
    y_healthy = solve_heat_1d_exact(x_s, t_s, alpha_true) + rng.normal(0, sigma, N)
    gof_healthy = evaluate_goodness_of_fit(x_s, t_s, y_healthy, alpha_true, sigma)
    assert gof_healthy['chi2_dof'] < gof_healthy['tau_gof']
    assert not gof_healthy['model_invalid']
    assert gof_healthy['dof'] == 9
    assert abs(gof_healthy['tau_gof'] - 1.88) < 0.02
    
    # Unmodeled physics case (corrupted by large constant offset)
    y_invalid = y_healthy + 0.10
    gof_invalid = evaluate_goodness_of_fit(x_s, t_s, y_invalid, alpha_true, sigma)
    assert gof_invalid['chi2_dof'] > gof_invalid['tau_gof']
    assert gof_invalid['model_invalid']

def test_d3_range_guard_bound_flagging():
    # Grid bound is [0.001, 10.0] (log10 in [-3.0, 1.0])
    # 2-tuple return for backward compatibility
    is_at_b, btype = check_bound_pinning(0.00100)
    assert is_at_b is True
    assert btype == 'lower'
    
    # 1% rule checks with return_info=True:
    # 0.00100 -> lower
    is_at_b, btype, info = check_bound_pinning(0.00100, return_info=True)
    assert is_at_b is True and info['flag_1pct'] is True and info['flag_01dec'] is True
    
    # 0.00120 -> outside 1% rule (0.00101), but inside 0.1 decade (10^-2.9 ~ 0.001259)
    is_at_b, btype, info = check_bound_pinning(0.00120, return_info=True)
    assert info['flag_1pct'] is False
    assert info['flag_01dec'] is True
    assert is_at_b is True
    
    # 0.100 (in-grid interior) -> False for both
    is_at_b, btype, info = check_bound_pinning(0.100, return_info=True)
    assert is_at_b is False and info['flag_1pct'] is False and info['flag_01dec'] is False
    
    # 95% Wald CI touching bound check:
    # hat = 0.002, se_log10 = 0.20 -> log10(0.002) = -2.699. ci_lo = -2.699 - 1.96*0.2 = -3.091 <= -3.0
    is_at_b, btype, info = check_bound_pinning(0.002, se_log10=0.20, return_info=True)
    assert info['flag_ci_touch'] is True
    assert is_at_b is True
    
    # Upper bound: 8.5 -> outside 1% rule (9.90), but within 0.1 decade (10^0.9 ~ 7.94)
    is_at_b, btype, info = check_bound_pinning(8.5, return_info=True)
    assert info['flag_1pct'] is False
    assert info['flag_01dec'] is True
    assert is_at_b is True


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

