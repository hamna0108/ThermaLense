"""D4: Declared Physics Parameter Inversion Wrapper.

Accepts optional declared physics inputs:
- u0_fn: custom initial spatial temperature distribution u_0(x)
- bc_fn: custom boundary conditions (bc0(t), bc1(t))
- source_fn: volumetric heat source rate s(x, t)
- alpha_fn: spatially varying diffusivity field alpha(x)

Directly executes live bounded-Brent optimization over alpha using the verified
generalized Crank-Nicolson numerical PDE solver with zero precomputed grid constraint.
"""

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import scipy.optimize as opt
from scipy.interpolate import CubicSpline

BOUND_LOG_LOW = -3.0
BOUND_LOG_HIGH = 1.0

def solve_heat_1d_general(Nx=101, Nt=501, alpha=0.1, u0_fn=None, bc_fn=None, source_fn=None, alpha_fn=None):
    """Generalized Crank-Nicolson solver for arbitrary ICs, BCs, source terms, and variable diffusivity."""
    x = np.linspace(0, 1, Nx)
    t = np.linspace(0, 1, Nt)
    dx = x[1] - x[0]
    dt = t[1] - t[0]
    
    if alpha_fn is not None:
        a_nodes = alpha_fn(x)
    elif np.isscalar(alpha):
        a_nodes = np.full(Nx, alpha)
    else:
        a_nodes = alpha
        
    u = np.zeros((Nt, Nx))
    if u0_fn is not None:
        u[0, :] = u0_fn(x)
    else:
        u[0, :] = np.sin(np.pi * x)
        
    N_int = Nx - 2
    a_half = 0.5 * (a_nodes[:-1] + a_nodes[1:])
    r_half = a_half * dt / (2.0 * dx**2)
    
    main_A = 1.0 + r_half[:N_int] + r_half[1:N_int+1]
    lower_A = -r_half[1:N_int]
    upper_A = -r_half[1:N_int]
    
    main_B = 1.0 - (r_half[:N_int] + r_half[1:N_int+1])
    lower_B = r_half[1:N_int]
    upper_B = r_half[1:N_int]
    
    A = sp.diags([lower_A, main_A, upper_A], offsets=[-1, 0, 1], shape=(N_int, N_int), format='csc')
    B = sp.diags([lower_B, main_B, upper_B], offsets=[-1, 0, 1], shape=(N_int, N_int), format='csr')
    lu_A = spla.splu(A)
    
    for n in range(Nt - 1):
        tn = t[n]
        tn1 = t[n+1]
        
        if bc_fn is not None:
            bc0_n, bc1_n = bc_fn(tn)
            bc0_n1, bc1_n1 = bc_fn(tn1)
        else:
            bc0_n, bc1_n = 0.0, 0.0
            bc0_n1, bc1_n1 = 0.0, 0.0
            
        u[n, 0] = bc0_n
        u[n, -1] = bc1_n
        u[n+1, 0] = bc0_n1
        u[n+1, -1] = bc1_n1
        
        rhs = B.dot(u[n, 1:-1])
        rhs[0] += r_half[0] * (bc0_n + bc0_n1)
        rhs[-1] += r_half[-1] * (bc1_n + bc1_n1)
        
        if source_fn is not None:
            s_n = source_fn(x[1:-1], tn)
            s_n1 = source_fn(x[1:-1], tn1)
            rhs += 0.5 * dt * (s_n + s_n1)
            
        u[n+1, 1:-1] = lu_A.solve(rhs)
        
    return x, t, u

def invert_with_declared_physics(x_s, t_s, y_s, sigma, alpha_true=0.1,
                                 u0_fn=None, bc_fn=None, source_fn=None, alpha_fn=None,
                                 Nx=101, Nt=501):
    """Perform live parameter inversion with declared physics models.
    
    Parameters
    ----------
    x_s, t_s, y_s : np.ndarray
        Sensor measurements.
    sigma : float
        Noise level for likelihood and CI.
    alpha_true : float
        Ground truth parameter (for validation scoring).
    u0_fn : callable, optional
        Custom initial condition function u0(x).
    bc_fn : callable, optional
        Custom boundary function bc(t) returning (bc0, bc1).
    source_fn : callable, optional
        Custom volumetric source term s(x, t).
    alpha_fn : callable, optional
        Custom variable diffusivity field alpha(x).
    Nx, Nt : int
        Grid discretization points.
        
    Returns
    -------
    dict
        'alpha_hat': estimated diffusivity
        'rel_error': relative parameter error
        'in_ci_95': Wald coverage indicator (0 or 1)
        'chi2_dof': reduced chi2 of the fit
        'crb': numerical Cramér-Rao lower bound
    """
    xg = np.linspace(0, 1, Nx)
    tg = np.linspace(0, 1, Nt)
    x_idx = np.array([np.argmin(np.abs(xg - x)) for x in x_s])
    t_idx = np.array([np.argmin(np.abs(tg - t)) for t in t_s])
    
    def obj(la):
        a_val = float(10**la)
        _, _, u_grid = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=a_val,
                                            u0_fn=u0_fn, bc_fn=bc_fn,
                                            source_fn=source_fn, alpha_fn=alpha_fn)
        pred = u_grid[t_idx, x_idx]
        return float(np.mean((pred - y_s)**2))
        
    res = opt.minimize_scalar(obj, bounds=(BOUND_LOG_LOW, BOUND_LOG_HIGH), method='bounded')
    hat_alpha = float(10**res.x)
    rel_err = float(abs(hat_alpha - alpha_true) / max(1e-5, alpha_true))
    
    # Forward prediction at optimal alpha
    _, _, u_opt = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=hat_alpha,
                                        u0_fn=u0_fn, bc_fn=bc_fn,
                                        source_fn=source_fn, alpha_fn=alpha_fn)
    y_opt = u_opt[t_idx, x_idx]
    residuals = y_s - y_opt
    dof = max(1, len(y_s) - 1)
    chi2_dof = float(np.sum(residuals**2) / (max(1e-12, (sigma**2) * dof)))
    
    # Numerical sensitivity du/dalpha for Fisher Information / CRB
    eps = 0.005 * hat_alpha
    _, _, u_plus = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=hat_alpha + eps,
                                         u0_fn=u0_fn, bc_fn=bc_fn,
                                         source_fn=source_fn, alpha_fn=alpha_fn)
    _, _, u_minus = solve_heat_1d_general(Nx=Nx, Nt=Nt, alpha=max(1e-4, hat_alpha - eps),
                                          u0_fn=u0_fn, bc_fn=bc_fn,
                                          source_fn=source_fn, alpha_fn=alpha_fn)
    du_da = (u_plus[t_idx, x_idx] - u_minus[t_idx, x_idx]) / (2.0 * eps)
    fi = float(np.sum((du_da**2) / (sigma**2 + 1e-12)))
    crb = float(1.0 / fi) if fi > 1e-15 else np.inf
    
    in_ci = 0
    if crb != np.inf and crb > 0:
        se = np.sqrt(crb) / (hat_alpha * np.log(10))
        if np.log10(hat_alpha) - 1.96 * se <= np.log10(alpha_true) <= np.log10(hat_alpha) + 1.96 * se:
            in_ci = 1
            
    return {
        'alpha_hat': hat_alpha,
        'rel_error': rel_err,
        'in_ci_95': in_ci,
        'chi2_dof': chi2_dof,
        'crb': crb
    }
