import numpy as np

def solve_heat_1d_exact(x, t, alpha=0.1):
    """
    Computes the exact analytic solution: u(x,t) = e^(-alpha * pi^2 * t) * sin(pi * x)
    """
    return np.exp(-alpha * np.pi**2 * t) * np.sin(np.pi * x)

def solve_heat_1d_numerical(Nx, Nt, alpha=0.1):
    """
    Solves the 1D heat equation using Forward-Time Central-Space (FTCS) finite difference.
    Domain: x in [0, 1], t in [0, 1]
    """
    x = np.linspace(0, 1, Nx)
    t = np.linspace(0, 1, Nt)
    dx = x[1] - x[0]
    dt = t[1] - t[0]
    
    # CFL stability check
    r = alpha * dt / (dx**2)
    if r > 0.5:
        raise ValueError(f"Stability condition violated: r = {r:.4f} > 0.5. Increase Nt or decrease Nx.")
        
    u = np.zeros((Nt, Nx))
    
    # Initial Condition: u(x,0) = sin(pi * x)
    u[0, :] = np.sin(np.pi * x)
    
    for n in range(0, Nt - 1):
        # Update interior points
        u[n+1, 1:-1] = u[n, 1:-1] + r * (u[n, 2:] - 2*u[n, 1:-1] + u[n, :-2])
        # Enforce boundary conditions
        u[n+1, 0] = 0.0
        u[n+1, -1] = 0.0
        
    return x, t, u
