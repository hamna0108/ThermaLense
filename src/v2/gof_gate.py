"""D2: Goodness-of-Fit Gate (chi2 / dof).

Flags 'model_invalid' when the reduced chi-squared statistic chi2/dof of the fitted model
exceeds a pre-calibrated threshold tau_gof (calibrated on healthy runs for <= 5% false-alarm rate).
The parameter estimate is preserved and returned, but flagged to prevent silent failures under
unmodeled physics (S4-S7) and correlated measurement error (S3).
"""

import numpy as np
from src.solvers.heat_1d import solve_heat_1d_exact

DEFAULT_TAU_GOF = 1.878  # Calibrated on healthy runs (seed 1300000..1300999) for exactly 5.0% false-alarm rate

def evaluate_goodness_of_fit(x_s, t_s, y_s, alpha_hat, sigma, tau_gof=DEFAULT_TAU_GOF, u_pred=None):
    """Evaluate goodness-of-fit statistic chi2/dof against calibrated threshold.
    
    Parameters
    ----------
    x_s : np.ndarray
        Sensor spatial coordinates.
    t_s : np.ndarray
        Sensor temporal observation points.
    y_s : np.ndarray
        Observed sensor values.
    alpha_hat : float
        Estimated thermal diffusivity.
    sigma : float
        Measurement noise standard deviation (declared or baseline-estimated).
    tau_gof : float, default 1.95
        Threshold above which 'model_invalid' is flagged.
    u_pred : np.ndarray, optional
        Precomputed forward model predictions. If None, uses solve_heat_1d_exact.
        
    Returns
    -------
    dict
        'chi2_dof': float, reduced chi2 statistic
        'tau_gof': float, decision threshold
        'model_invalid': bool, True if chi2_dof > tau_gof
        'rss': float, residual sum of squares
        'dof': int, degrees of freedom
        'warnings': list of str, diagnostic messages
    """
    N = len(y_s)
    dof = max(1, N - 1)
    
    if u_pred is None:
        u_pred = solve_heat_1d_exact(x_s, t_s, alpha_hat)
        
    residuals = y_s - u_pred
    rss = float(np.sum(residuals**2))
    
    denom = max(1e-12, (sigma**2) * dof)
    chi2_dof = float(rss / denom)
    model_invalid = bool(chi2_dof > tau_gof)
    
    warn_list = []
    if model_invalid:
        warn_list.append(f"Model invalid: chi2/dof = {chi2_dof:.3f} > threshold {tau_gof:.3f}.")
        
    # Check Durbin-Watson autocorrelation in residuals (D5 correlated noise indicator)
    if N >= 4:
        diff_r = np.diff(residuals)
        denom_dw = np.sum(residuals**2)
        if denom_dw > 1e-12:
            dw_stat = float(np.sum(diff_r**2) / denom_dw)
            if dw_stat < 1.0 or dw_stat > 3.0:
                warn_list.append(f"Durbin-Watson statistic {dw_stat:.2f} indicates residual autocorrelation.")
                
    return {
        'chi2_dof': chi2_dof,
        'tau_gof': tau_gof,
        'model_invalid': model_invalid,
        'rss': rss,
        'dof': dof,
        'warnings': warn_list
    }
