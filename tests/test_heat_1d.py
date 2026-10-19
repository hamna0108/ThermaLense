import os
import numpy as np
import pytest
import matplotlib.pyplot as plt
from src.solvers.heat_1d import solve_heat_1d_exact, solve_heat_1d_numerical

def test_heat_1d_convergence():
    """
    Test that the numerical solution converges to the exact solution.
    We compute the Relative L2 field error at the final time step t=1.
    """
    Nx = 50
    Nt = 1000
    alpha = 0.1
    
    x, t, u_num = solve_heat_1d_numerical(Nx, Nt, alpha)
    
    # Get numerical solution at final time T=1
    u_num_final = u_num[-1, :]
    
    # Get exact solution at final time T=1
    u_exact_final = solve_heat_1d_exact(x, t[-1], alpha)
    
    # Calculate Relative L2 error
    l2_error = np.linalg.norm(u_num_final - u_exact_final) / np.linalg.norm(u_exact_final)
    
    # Calculate Maximum error
    max_error = np.max(np.abs(u_num_final - u_exact_final))
    
    print(f"\nRelative L2 error at T=1: {l2_error:.6e}")
    print(f"Maximum error at T=1: {max_error:.6e}")
    
    # Plotting
    os.makedirs('plots', exist_ok=True)
    plt.figure(figsize=(8, 6))
    plt.plot(x, u_exact_final, 'k-', label='Exact Solution')
    plt.plot(x, u_num_final, 'r--', label='Numerical Solution')
    plt.title('1D Heat Equation: Exact vs Numerical at T=1')
    plt.xlabel('x')
    plt.ylabel('u(x, T=1)')
    plt.legend()
    plt.grid(True)
    
    # Save the plot before showing
    plt.savefig(os.path.join('plots', 'heat_1d_convergence.png'), dpi=300)
    plt.close()

    
    # Error should be small (expected < 1e-3 for these Nx, Nt)
    assert l2_error < 1e-3, f"Relative L2 error too high: {l2_error}"
