"""D3: Dynamic Range Guard & Bound Pinning Gate.

Routes Mode 3 parameter inversion to Mode 3+ whenever the neural surrogate estimate
lies outside its safe interpolation domain [0.01, 1.0].
Flags 'estimate_at_bound' and 'out_of_range' if:
  (1) The final estimate falls within 0.1 decade of the solver grid bounds [0.001, 10.0]
      (i.e. log10(hat) <= -2.9 or log10(hat) >= 0.9), OR
  (2) The 95% Wald interval touches or crosses the bound (ci_lo <= -3.0 or ci_hi >= 1.0).
Also computes the original 1% tolerance rule for backward compatibility and side-by-side reporting.
"""

import numpy as np

GRID_BOUND_LOW = 0.001   # 10^-3
GRID_BOUND_HIGH = 10.0   # 10^1
BOUND_LOG_LOW = -3.0
BOUND_LOG_HIGH = 1.0

# Original 1% rule thresholds
BOUND_TOL_PCT = 0.01     # 1% tolerance
LOWER_FLAG_THRESHOLD_1PCT = GRID_BOUND_LOW * (1.0 + BOUND_TOL_PCT)    # 0.00101
UPPER_FLAG_THRESHOLD_1PCT = GRID_BOUND_HIGH * (1.0 - BOUND_TOL_PCT)   # 9.90000

# New 0.1 decade rule thresholds
DECADE_MARGIN = 0.10
LOWER_LOG_THRESHOLD_01DEC = BOUND_LOG_LOW + DECADE_MARGIN            # -2.90
UPPER_LOG_THRESHOLD_01DEC = BOUND_LOG_HIGH - DECADE_MARGIN           # +0.90
LOWER_FLAG_THRESHOLD_01DEC = float(10**LOWER_LOG_THRESHOLD_01DEC)    # ~0.0012589
UPPER_FLAG_THRESHOLD_01DEC = float(10**UPPER_LOG_THRESHOLD_01DEC)    # ~7.94328

def check_bound_pinning(alpha_hat, se_log10=None, return_info=False):
    """Check if estimated alpha is at or near solver grid bounds [0.001, 10.0].
    
    Evaluates:
    - Original 1% rule: alpha_hat <= 0.00101 or alpha_hat >= 9.90
    - New rule: within 0.1 decade of grid bound (log10 <= -2.9 or log10 >= 0.9)
                OR 95% Wald CI touches or exceeds bound (ci_lo <= -3.0 or ci_hi >= 1.0).
                
    Parameters
    ----------
    alpha_hat : float
        Estimated parameter value.
    se_log10 : float, optional
        Standard error of log10(alpha_hat) for 95% Wald CI evaluation.
    return_info : bool, default False
        If True, returns (is_at_bound, bound_type, info_dict).
        If False, returns (is_at_bound, bound_type).
        
    Returns
    -------
    is_at_bound : bool
        True if flagged by the new rule (0.1 decade or CI touch).
    bound_type : str
        'lower', 'upper', or 'none'.
    info : dict, optional
        Detailed boolean flags ('flag_1pct', 'flag_01dec', 'flag_ci_touch', 'flag_new').
    """
    # 1% rule
    at_lower_1pct = bool(alpha_hat <= LOWER_FLAG_THRESHOLD_1PCT)
    at_upper_1pct = bool(alpha_hat >= UPPER_FLAG_THRESHOLD_1PCT)
    flag_1pct = bool(at_lower_1pct or at_upper_1pct)
    
    # 0.1 decade rule
    log10_hat = float(np.log10(max(1e-12, alpha_hat)))
    at_lower_01dec = bool(log10_hat <= LOWER_LOG_THRESHOLD_01DEC)
    at_upper_01dec = bool(log10_hat >= UPPER_LOG_THRESHOLD_01DEC)
    flag_01dec = bool(at_lower_01dec or at_upper_01dec)
    
    # 95% interval touches bound
    flag_ci_touch = False
    if se_log10 is not None and not np.isnan(se_log10) and se_log10 > 0:
        ci_lo = log10_hat - 1.96 * se_log10
        ci_hi = log10_hat + 1.96 * se_log10
        if ci_lo <= BOUND_LOG_LOW or ci_hi >= BOUND_LOG_HIGH:
            flag_ci_touch = True
            
    flag_new = bool(flag_01dec or flag_ci_touch)
    
    if at_lower_01dec or (se_log10 is not None and se_log10 > 0 and (log10_hat - 1.96 * se_log10) <= BOUND_LOG_LOW):
        bound_type = 'lower'
    elif at_upper_01dec or (se_log10 is not None and se_log10 > 0 and (log10_hat + 1.96 * se_log10) >= BOUND_LOG_HIGH):
        bound_type = 'upper'
    elif flag_1pct:
        bound_type = 'lower' if at_lower_1pct else 'upper'
    else:
        bound_type = 'none'
        
    info = {
        'flag_1pct': flag_1pct,
        'flag_01dec': flag_01dec,
        'flag_ci_touch': flag_ci_touch,
        'flag_new': flag_new
    }
    
    if return_info:
        return flag_new, bound_type, info
    return flag_new, bound_type


def range_guarded_mode3_inversion(x_s, t_s, y_s, sigma, alpha_true, prec,
                                  eval_m3_fn, eval_m3p_fn, crb_fn=None):
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
    crb_fn : callable, optional
        Cramer-Rao bound calculator to get se_log10.
        
    Returns
    -------
    dict
        Estimation results, routing state, and both 1% and new bound flags.
    """
    # 1. Initial Mode 3 evaluation
    h3, e3, c3 = eval_m3_fn(x_s, t_s, y_s, sigma, alpha_true, prec)
    
    # 2. Dynamic routing rule: if hat_m3 < 0.01 or hat_m3 > 1.0, route to Mode 3+
    routed = bool((h3 < 0.01) or (h3 > 1.0))
    if routed:
        h_final, e_final, c_final = eval_m3p_fn(x_s, t_s, y_s, sigma, alpha_true, h3, prec)
    else:
        h_final, e_final, c_final = h3, e3, c3
        
    # 3. Compute log10 standard error if CRB available
    se_log10 = None
    if crb_fn is not None:
        try:
            crb_val = crb_fn(h_final, t_s, x_s, sigma)
            if crb_val != np.inf and crb_val > 0:
                se_log10 = float(np.sqrt(crb_val) / (h_final * np.log(10)))
        except Exception:
            se_log10 = None
            
    # 4. Check bound pinning on final estimate (both rules)
    is_at_bound, bound_type, b_info = check_bound_pinning(h_final, se_log10=se_log10, return_info=True)
    
    return {

        'alpha_hat': float(h_final),
        'rel_error': float(e_final),
        'in_ci_95': int(c_final),
        'routed_to_m3p': routed,
        'estimate_at_bound': is_at_bound,  # New rule (0.1 decade or CI touch)
        'out_of_range': is_at_bound,
        'flag_1pct': b_info['flag_1pct'],
        'flag_new': b_info['flag_new'],
        'flag_01dec': b_info['flag_01dec'],
        'flag_ci_touch': b_info['flag_ci_touch'],
        'bound_type': bound_type,
        'alpha_m3_initial': float(h3)
    }

