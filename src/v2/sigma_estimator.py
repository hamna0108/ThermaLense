"""D1: Baseline Noise Sigma Estimation & D5 Limitation Warnings.

Estimates observation noise standard deviation sigma from k >= 20 healthy baseline readings.
The estimated sigma is then supplied to Wald confidence intervals and anomaly GLR/BIC
decision thresholds when sigma is undeclared or misspecified.
Also provides D5 limitation check for parameter drift during the baseline window (S13).
"""

import warnings
import numpy as np
import scipy.stats as stats
import scipy.optimize as opt
from src.solvers.heat_1d import solve_heat_1d_exact

BOUND_LOG_LOW = -3.0
BOUND_LOG_HIGH = 1.0

def check_baseline_drift_warning(t_b: np.ndarray, residuals: np.ndarray, alpha_level: float = 0.05):
    """Check for systematic parameter drift during baseline window via residual trend regression (D5, S13).
    
    Tests if the linear regression slope of residuals against baseline time t_b has a statistically
    significant t-statistic (|t| > t_crit at df = k - 2).
    """
    k = len(t_b)
    if k < 6:
        return False, 0.0, 0.0
    t_mean = np.mean(t_b)
    r_mean = np.mean(residuals)
    s_tt = np.sum((t_b - t_mean)**2)
    if s_tt <= 1e-12:
        return False, 0.0, 0.0
    s_tr = np.sum((t_b - t_mean) * (residuals - r_mean))
    slope = s_tr / s_tt
    r_fit = r_mean + slope * (t_b - t_mean)
    rss_reg = np.sum((residuals - r_fit)**2)
    dof_reg = max(1, k - 2)
    se_slope = np.sqrt((rss_reg / dof_reg) / s_tt)
    if se_slope <= 1e-12:
        return False, 0.0, 0.0
    t_stat = float(slope / se_slope)
    t_crit = float(stats.t.ppf(1.0 - alpha_level / 2.0, dof_reg))
    is_drift = bool(abs(t_stat) > t_crit)
    return is_drift, t_stat, float(slope)

def estimate_sigma_from_baseline(x_b, t_b, y_b, min_readings=20, allow_fewer=False):
    """Estimate measurement noise standard deviation from k baseline readings.
    
    Parameters
    ----------
    x_b : np.ndarray
        Spatial coordinates of baseline sensors.
    t_b : np.ndarray
        Temporal observation points of baseline sensors.
    y_b : np.ndarray
        Observed baseline values.
    min_readings : int, default 20
        Minimum supported baseline readings (calibrated standard).
    allow_fewer : bool, default False
        If True, issues warning instead of raising exception when k < min_readings.
        
    Returns
    -------
    dict
        'sigma_hat': float, estimated noise std
        'alpha_base': float, estimated baseline diffusivity
        'dof': int, residual degrees of freedom (k - 1)
        'drift_flag': bool, True if baseline parameter drift detected
        'warnings': list of str, any diagnostic warning messages
    """
    k = len(y_b)
    warn_list = []
    
    # D5 Limitation Check: Baseline readings count
    if k < min_readings:
        msg = f"Baseline readings k={k} < {min_readings}. Service policy requires k >= {min_readings} for stable variance estimation."
        if not allow_fewer:
            raise ValueError(f"Service Refused: {msg}")
        else:
            warnings.warn(msg)
            warn_list.append(msg)
            
    # Fit baseline diffusivity alpha_base
    def rss_obj(la):
        pred = solve_heat_1d_exact(x_b, t_b, 10**la)
        return np.sum((pred - y_b)**2)
        
    res = opt.minimize_scalar(rss_obj, bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
    hat_alpha_base = float(10**res.x)
    
    # Compute residuals and unbiased sample variance
    pred_base = solve_heat_1d_exact(x_b, t_b, hat_alpha_base)
    residuals = y_b - pred_base
    dof = max(1, k - 1)
    hat_variance = float(np.sum(residuals**2) / dof)
    hat_sigma = float(np.sqrt(max(1e-12, hat_variance)))
    
    # D5 Limitation Check: Heavy-tailed noise (excess kurtosis)
    if k >= 8:
        std_r = np.std(residuals, ddof=1)
        if std_r > 1e-12:
            norm_r = (residuals - np.mean(residuals)) / std_r
            kurt = float(np.mean(norm_r**4) - 3.0)
            if kurt > 2.0:
                warn_list.append(f"Excess kurtosis ({kurt:.2f} > 2.0) detected: possible heavy-tailed noise.")
                
    # D5 Limitation Check: Correlated noise (lag-1 residual autocorrelation)
    if k >= 8:
        r_centered = residuals - np.mean(residuals)
        denom = np.sum(r_centered**2)
        if denom > 1e-12:
            r1 = np.sum(r_centered[:-1] * r_centered[1:]) / denom
            if abs(r1) > 0.40:
                warn_list.append(f"High residual lag-1 autocorrelation ({r1:.2f}) detected: possible correlated noise.")
                
    # D5 Limitation Check: Baseline parameter drift (S13)
    drift_flag, t_drift, slope_drift = check_baseline_drift_warning(t_b, residuals)
    if drift_flag:
        warn_list.append(f"Baseline drift detected (residual slope t-stat={t_drift:.2f}, slope={slope_drift:.4f}): parameter may be non-stationary.")
        
    return {
        'sigma_hat': hat_sigma,
        'alpha_base': hat_alpha_base,
        'dof': dof,
        'rss_base': float(np.sum(residuals**2)),
        'drift_flag': drift_flag,
        'drift_t_stat': t_drift,
        'warnings': warn_list
    }


