"""D3: Dynamic Range Guard & Bound Pinning Gate.

Routes Mode 3 parameter inversion to Mode 3+ whenever the neural surrogate estimate
lies outside its safe interpolation domain [0.01, 1.0].
Flags 'estimate_at_bound' and 'out_of_range' if the final estimate falls within 1% of the
solver grid bounds [0.001, 10.0], intercepting unidentifiable or super-grid regimes (S12).
"""

import numpy as np

GRID_BOUND_LOW = 0.001   # 10^-3
GRID_BOUND_HIGH = 10.0   # 10^1
BOUND_TOL_PCT = 0.01     # 1% tolerance

LOWER_FLAG_THRESHOLD = GRID_BOUND_LOW * (1.0 + BOUND_TOL_PCT)    # 0.00101
UPPER_FLAG_THRESHOLD = GRID_BOUND_HIGH * (1.0 - BOUND_TOL_PCT)   # 9.90000

def check_bound_pinning(alpha_hat):
    """Check if estimated alpha is within 1% of solver grid bounds [0.001, 10.0]."""
    at_lower = (alpha_hat <= LOWER_FLAG_THRESHOLD)
    at_upper = (alpha_hat >= UPPER_FLAG_THRESHOLD)
    is_at_bound = bool(at_lower or at_upper)
    bound_type = 'lower' if at_lower else ('upper' if at_upper else 'none')
    return is_at_bound, bound_type

def range_guarded_mode3_inversion(x_s, t_s, y_s, sigma, alpha_true, prec,
                                  eval_m3_fn, eval_m3p_fn):
    """Execute Mode 3 with dynamic routing to Mode 3+ outside [0.01, 1.0] and bound flagging.
    
    Parameters
    ----------
    x_s, t_s, y_s : np.ndarray
        Sensor measurements.
    sigma : float
        Noise level.
    alpha_true : float
        Ground truth parameter (for evaluation scoring).
    prec : dict
        Precomputed solver tables.
    eval_m3_fn : callable
        Frozen Mode 3 evaluation function.
    eval_m3p_fn : callable
        Frozen Mode 3+ evaluation function.
        
    Returns
    -------
    dict
        'alpha_hat': final parameter estimate
        'rel_error': relative error
        'in_ci_95': 95% Wald CI coverage
        'routed_to_m3p': bool, True if routed to Mode 3+
        'estimate_at_bound': bool, True if within 1% of bound
        'out_of_range': bool, True if flagged out of range
        'bound_type': 'lower', 'upper', or 'none'
    """
    # 1. Initial Mode 3 evaluation
    h3, e3, c3 = eval_m3_fn(x_s, t_s, y_s, sigma, alpha_true, prec)
    
    # 2. Dynamic routing rule: if hat_m3 < 0.01 or hat_m3 > 1.0, route to Mode 3+
    routed = bool((h3 < 0.01) or (h3 > 1.0))
    if routed:
        h_final, e_final, c_final = eval_m3p_fn(x_s, t_s, y_s, sigma, alpha_true, h3, prec)
    else:
        h_final, e_final, c_final = h3, e3, c3
        
    # 3. Check bound pinning on final estimate
    is_at_bound, bound_type = check_bound_pinning(h_final)
    
    return {
        'alpha_hat': float(h_final),
        'rel_error': float(e_final),
        'in_ci_95': int(c_final),
        'routed_to_m3p': routed,
        'estimate_at_bound': is_at_bound,
        'out_of_range': is_at_bound,
        'bound_type': bound_type,
        'alpha_m3_initial': float(h3)
    }
