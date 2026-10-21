"""V2 Pipeline Integration & High-Level Module Wrappers.

Integrates D1-D5 improvements on top of frozen modules without modifying any frozen code:
- D1: Sigma estimation from baseline (for Wald CI and Anomaly thresholds)
- D2: Goodness-of-fit chi2/dof gate flagging 'model_invalid'
- D3: Mode 3 range guard routing to Mode 3+ and bound pinning flag
- D4: Declared physics parameter inversion (u0, BC, source)
- D5: Operational limitations & warning flags
"""

import numpy as np
from src.solvers.heat_1d import solve_heat_1d_exact
from src.v2.sigma_estimator import estimate_sigma_from_baseline
from src.v2.gof_gate import evaluate_goodness_of_fit, DEFAULT_TAU_GOF
from src.v2.range_guard import range_guarded_mode3_inversion, check_bound_pinning
from src.v2.declared_physics import invert_with_declared_physics

def evaluate_v2_parameter_inversion(x_s, t_s, y_s, sigma_declared, alpha_true, prec,
                                    eval_m2_fn=None, eval_m3_fn=None, eval_m3p_fn=None,
                                    baseline_data=None, declared_physics=None,
                                    use_range_guard=True, tau_gof=DEFAULT_TAU_GOF):
    """Execute V2 parameter inversion integrating D1, D2, D3, D4, and D5.
    
    Parameters
    ----------
    x_s, t_s, y_s : np.ndarray
        Operational sensor observations.
    sigma_declared : float or None
        Declared noise sigma. If None or misspecified, estimated from baseline_data (D1).
    alpha_true : float
        Ground truth parameter for benchmarking.
    prec : dict
        Precomputed surrogate lookup tables.
    baseline_data : tuple of (x_b, t_b, y_b), optional
        Healthy baseline measurements (k >= 20) for D1 sigma estimation.
    declared_physics : dict, optional
        Declared physics inputs for D4: 'u0_fn', 'bc_fn', 'source_fn', 'alpha_fn'.
    use_range_guard : bool, default True
        Enable D3 range guard for Mode 3 routing.
    tau_gof : float
        Goodness-of-fit threshold for D2.
        
    Returns
    -------
    dict
        V2 estimation results, flags, and diagnostic warnings.
    """
    warnings_list = []
    
    # -------------------------------------------------------------
    # D1: Baseline Sigma Estimation
    # -------------------------------------------------------------
    if baseline_data is not None:
        xb, tb, yb = baseline_data
        sig_info = estimate_sigma_from_baseline(xb, tb, yb, min_readings=20, allow_fewer=True)
        effective_sigma = sig_info['sigma_hat']
        warnings_list.extend(sig_info['warnings'])
    else:
        effective_sigma = sigma_declared if sigma_declared is not None else 0.01
        
    # -------------------------------------------------------------
    # D4: Declared Physics Inversion (if declared)
    # -------------------------------------------------------------
    if declared_physics is not None:
        u0_fn = declared_physics.get('u0_fn', None)
        bc_fn = declared_physics.get('bc_fn', None)
        source_fn = declared_physics.get('source_fn', None)
        alpha_fn = declared_physics.get('alpha_fn', None)
        
        res_d4 = invert_with_declared_physics(x_s, t_s, y_s, effective_sigma,
                                             alpha_true=alpha_true,
                                             u0_fn=u0_fn, bc_fn=bc_fn,
                                             source_fn=source_fn, alpha_fn=alpha_fn)
        hat_alpha = res_d4['alpha_hat']
        rel_err = res_d4['rel_error']
        in_ci = res_d4['in_ci_95']
        chi2_dof = res_d4['chi2_dof']
        routed = False
        is_at_bound, bound_type = check_bound_pinning(hat_alpha)
        
        gof_res = evaluate_goodness_of_fit(x_s, t_s, y_s, hat_alpha, effective_sigma, tau_gof=tau_gof)
        model_invalid = gof_res['model_invalid']
        warnings_list.extend(gof_res['warnings'])
        
        return {
            'alpha_hat': hat_alpha,
            'rel_error': rel_err,
            'in_ci_95': in_ci,
            'effective_sigma': effective_sigma,
            'chi2_dof': chi2_dof,
            'model_invalid': model_invalid,
            'routed_to_m3p': routed,
            'estimate_at_bound': is_at_bound,
            'out_of_range': is_at_bound,
            'bound_type': bound_type,
            'mode_used': 'Declared Physics General CN',
            'warnings': warnings_list
        }
        
    # -------------------------------------------------------------
    # D3: Range Guard Mode 3 Inversion
    # -------------------------------------------------------------
    if use_range_guard and eval_m3_fn is not None and eval_m3p_fn is not None:
        rg_res = range_guarded_mode3_inversion(x_s, t_s, y_s, effective_sigma,
                                              alpha_true, prec, eval_m3_fn, eval_m3p_fn)
        hat_alpha = rg_res['alpha_hat']
        rel_err = rg_res['rel_error']
        in_ci = rg_res['in_ci_95']
        routed = rg_res['routed_to_m3p']
        is_at_bound = rg_res['estimate_at_bound']
        bound_type = rg_res['bound_type']
        mode_used = 'Mode 3+ (routed)' if routed else 'Mode 3 (in-range)'
    elif eval_m2_fn is not None:
        hat_alpha, rel_err, in_ci = eval_m2_fn(x_s, t_s, y_s, effective_sigma, alpha_true, prec)
        routed = False
        is_at_bound, bound_type = check_bound_pinning(hat_alpha)
        mode_used = 'Mode 2'
    else:
        raise ValueError("No evaluation function provided.")
        
    # -------------------------------------------------------------
    # D2: Goodness-of-Fit Gate (chi2 / dof)
    # -------------------------------------------------------------
    gof_res = evaluate_goodness_of_fit(x_s, t_s, y_s, hat_alpha, effective_sigma, tau_gof=tau_gof)
    model_invalid = gof_res['model_invalid']
    chi2_dof = gof_res['chi2_dof']
    warnings_list.extend(gof_res['warnings'])
    
    return {
        'alpha_hat': hat_alpha,
        'rel_error': rel_err,
        'in_ci_95': in_ci,
        'effective_sigma': effective_sigma,
        'chi2_dof': chi2_dof,
        'model_invalid': model_invalid,
        'routed_to_m3p': routed,
        'estimate_at_bound': is_at_bound,
        'out_of_range': is_at_bound,
        'bound_type': bound_type,
        'mode_used': mode_used,
        'warnings': warnings_list
    }
