"""D2: Goodness-of-Fit Gate (chi2 / dof).

Flags 'model_invalid' when the reduced chi-squared statistic chi2/dof of the fitted model
exceeds the dynamic threshold tau_gof(dof) = chi2.ppf(1 - alpha, dof) / dof (nominal 5% false-alarm rate).
The parameter estimate is preserved and returned, but flagged to prevent silent failures under
unmodeled physics (S4-S7).
Also provides D5 limitation warning detectors for residual autocorrelation (Durbin-Watson, S3)
and heavy-tailed error distributions (excess kurtosis, S2).
"""

import numpy as np
import scipy.stats as stats
from src.solvers.heat_1d import solve_heat_1d_exact

DEFAULT_TAU_GOF = None  # Computes dynamically as chi2.ppf(0.95, dof)/dof

def compute_gof_threshold(dof: int, alpha_level: float = 0.05) -> float:
    """Compute exact chi2/dof decision threshold for nominal false-alarm rate alpha_level.
    
    tau_gof(dof) = chi2.ppf(1 - alpha_level, dof) / dof
    """
    dof_eff = max(1, int(dof))
    return float(stats.chi2.ppf(1.0 - alpha_level, dof_eff) / dof_eff)

def check_durbin_watson_warning(residuals: np.ndarray, dw_threshold: float = 0.88):
    """Check for residual autocorrelation using the Durbin-Watson statistic (D5, S3).
    
    Threshold dw_threshold=0.88 calibrated on healthy runs for <= 5% false-warning rate.
    """
    N = len(residuals)

    if N < 4:
        return False, 2.0
    diff_r = np.diff(residuals)
    denom = np.sum(residuals**2)
    if denom <= 1e-12:
        return False, 2.0
    dw_stat = float(np.sum(diff_r**2) / denom)
    is_warning = bool(dw_stat < dw_threshold or dw_stat > (4.0 - dw_threshold))
    return is_warning, dw_stat

def check_kurtosis_warning(residuals: np.ndarray, thresh_kurt: float = 1.20, thresh_z: float = 2.35):
    """Check for heavy-tailed / contaminated error distribution via kurtosis & standardized outliers (D5, S2)."""
    N = len(residuals)
    if N < 4:
        return False, 0.0, 0.0
    std_r = np.std(residuals, ddof=1)
    if std_r <= 1e-12:
        return False, 0.0, 0.0
    norm_r = (residuals - np.mean(residuals)) / std_r
    excess_kurt = float(np.mean(norm_r**4) - 3.0)
    max_z = float(np.max(np.abs(norm_r)))
    is_warning = bool(excess_kurt > thresh_kurt or max_z > thresh_z)
    return is_warning, excess_kurt, max_z

def evaluate_goodness_of_fit(x_s, t_s, y_s, alpha_hat, sigma, tau_gof=None, u_pred=None, alpha_level=0.05):
    """Evaluate goodness-of-fit statistic chi2/dof against dynamic chi2 threshold.
    
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
    tau_gof : float, optional
        Threshold above which 'model_invalid' is flagged. If None, uses chi2.ppf(1-alpha, dof)/dof.
    u_pred : np.ndarray, optional
        Precomputed forward model predictions. If None, uses solve_heat_1d_exact.
    alpha_level : float, default 0.05
        Nominal significance level for dynamic threshold.
        
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
    
    if tau_gof is None:
        tau_gof = compute_gof_threshold(dof, alpha_level=alpha_level)
    
    if u_pred is None:
        u_pred = solve_heat_1d_exact(x_s, t_s, alpha_hat)
        
    residuals = y_s - u_pred
    rss = float(np.sum(residuals**2))
    
    denom = max(1e-12, (sigma**2) * dof)
    chi2_dof = float(rss / denom)
    model_invalid = bool(chi2_dof > tau_gof)
    
    warn_list = []
    if model_invalid:
        warn_list.append(f"Model invalid: chi2/dof = {chi2_dof:.3f} > threshold {tau_gof:.3f} (dof={dof}).")
        
    # D5 Warning 1: Durbin-Watson autocorrelation check (S3)
    dw_flag, dw_val = check_durbin_watson_warning(residuals)
    if dw_flag:
        warn_list.append(f"Durbin-Watson statistic {dw_val:.2f} indicates residual autocorrelation.")
        
    # D5 Warning 2: Kurtosis / heavy-tailed check (S2)
    kurt_flag, excess_k, max_z = check_kurtosis_warning(residuals)
    if kurt_flag:
        warn_list.append(f"Heavy-tailed residuals detected (excess kurtosis={excess_k:.2f}, max_z={max_z:.2f}).")
        
    return {
        'chi2_dof': chi2_dof,
        'tau_gof': tau_gof,
        'model_invalid': model_invalid,
        'rss': rss,
        'dof': dof,
        'dw_flag': dw_flag,
        'dw_stat': dw_val,
        'kurt_flag': kurt_flag,
        'excess_kurt': excess_k,
        'warnings': warn_list
    }

