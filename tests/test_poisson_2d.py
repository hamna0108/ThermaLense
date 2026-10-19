import os
import numpy as np
import pytest
import matplotlib.pyplot as plt
from src.solvers.poisson_2d import solve_poisson_2d_exact, solve_poisson_2d_numerical

def test_poisson_2d_convergence():
    """
    Test that the numerical solution converges to the exact solution for the 2D Poisson Equation.
    """
    Nx, Ny = 50, 50
    
    # Get numerical solution
    X, Y, u_num = solve_poisson_2d_numerical(Nx, Ny)
    
    # Get exact solution
    u_exact = solve_poisson_2d_exact(X, Y)
    
    # Calculate errors
    l2_error = np.linalg.norm(u_num - u_exact) / np.linalg.norm(u_exact)
    max_error = np.max(np.abs(u_num - u_exact))
    
    print(f"\nRelative L2 error: {l2_error:.6e}")
    print(f"Maximum error: {max_error:.6e}")
    
    # Plotting
    os.makedirs('plots', exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # Exact Solution
    c1 = axes[0].contourf(X, Y, u_exact, levels=50, cmap='viridis')
    axes[0].set_title('Exact Solution')
    axes[0].set_xlabel('x')
    axes[0].set_ylabel('y')
    fig.colorbar(c1, ax=axes[0])
    
    # Numerical Solution
    c2 = axes[1].contourf(X, Y, u_num, levels=50, cmap='viridis')
    axes[1].set_title('Numerical Solution')
    axes[1].set_xlabel('x')
    axes[1].set_ylabel('y')
    fig.colorbar(c2, ax=axes[1])
    
    # Error Map
    c3 = axes[2].contourf(X, Y, np.abs(u_num - u_exact), levels=50, cmap='inferno')
    axes[2].set_title('Absolute Error')
    axes[2].set_xlabel('x')
    axes[2].set_ylabel('y')
    fig.colorbar(c3, ax=axes[2])
    
    # Save the plot before showing
    plt.savefig(os.path.join('plots', 'poisson_2d_convergence.png'), dpi=300)
    plt.close() # Using plt.close() here for testing to avoid hanging pytest, since we saved it.
    
    # Error should be small
    assert l2_error < 1e-3, f"Relative L2 error too high: {l2_error}"
