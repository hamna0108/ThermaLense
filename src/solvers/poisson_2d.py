import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

def solve_poisson_2d_exact(X, Y):
    """
    Computes the exact analytic solution for the 2D Poisson Equation:
    u(x,y) = sin(pi * x) * sin(pi * y)
    with manufactured source f(x,y) = 2 * pi^2 * sin(pi * x) * sin(pi * y).
    """
    return np.sin(np.pi * X) * np.sin(np.pi * Y)

def manufactured_source_2d(X, Y):
    """
    Manufactured source f(x,y) = 2 * pi^2 * sin(pi * x) * sin(pi * y).
    """
    return 2.0 * np.pi**2 * np.sin(np.pi * X) * np.sin(np.pi * Y)

class Poisson2DSolver:
    """
    Fast finite-difference 2D Poisson solver with prefactorized sparse direct solve.
    Solves -nabla^2 u = f on [0, 1]^2 with u = 0 on boundary using standard 5-point stencil.
    """
    def __init__(self, N=64):
        self.N = N
        self.x = np.linspace(0, 1, N)
        self.y = np.linspace(0, 1, N)
        self.X, self.Y = np.meshgrid(self.x, self.y, indexing='ij')
        self.dx = self.x[1] - self.x[0]
        self.dy = self.y[1] - self.y[0]
        self.h = self.dx
        
        self.nx_int = N - 2
        self.ny_int = N - 2
        self.n_int = self.nx_int * self.ny_int
        
        self._build_and_factorize()

    def _build_and_factorize(self):
        cx = -1.0 / self.dx**2
        cy = -1.0 / self.dy**2
        cc = 2.0 / self.dx**2 + 2.0 / self.dy**2
        
        main_diag = np.full(self.n_int, cc)
        off_diag_y = np.full(self.n_int - 1, cy)
        off_diag_y[self.ny_int - 1::self.ny_int] = 0.0
        off_diag_x = np.full(self.n_int - self.ny_int, cx)
        
        self.A = sp.diags(
            [main_diag, off_diag_y, off_diag_y, off_diag_x, off_diag_x],
            [0, 1, -1, self.ny_int, -self.ny_int],
            format='csc'
        )
        self.lu_solve = spla.factorized(self.A)

    def solve(self, f):
        """
        Solve -nabla^2 u = f with u = 0 on boundary.
        f: either callable f(X, Y) or ndarray of shape (N, N).
        Returns:
            u: ndarray of shape (N, N) with u = 0 on boundary.
        """
        if callable(f):
            f_grid = f(self.X, self.Y)
        else:
            f_grid = np.asarray(f)
            if f_grid.shape != (self.N, self.N):
                raise ValueError(f"f array shape {f_grid.shape} must match (N, N) = ({self.N}, {self.N})")
        
        b = f_grid[1:-1, 1:-1].flatten()
        u_int = self.lu_solve(b)
        
        u = np.zeros((self.N, self.N), dtype=np.float64)
        u[1:-1, 1:-1] = u_int.reshape((self.nx_int, self.ny_int))
        return u

    def compute_residual(self, u, f):
        """
        Compute discrete PDE residual r = -nabla_h^2 u - f on interior points.
        Returns:
            r_rel: ||r||_2 / ||f_int||_2
            r_max: max(|r|)
        """
        if callable(f):
            f_grid = f(self.X, self.Y)
        else:
            f_grid = np.asarray(f)
            
        u_int = u[1:-1, 1:-1]
        lap_u = (
            -4.0 * u_int
            + u[2:, 1:-1]
            + u[:-2, 1:-1]
            + u[1:-1, 2:]
            + u[1:-1, :-2]
        ) / (self.h**2)
        
        # -nabla^2 u = - lap_u
        neg_lap = -lap_u
        r = neg_lap - f_grid[1:-1, 1:-1]
        
        f_norm = np.linalg.norm(f_grid[1:-1, 1:-1])
        r_rel = float(np.linalg.norm(r) / (f_norm + 1e-12))
        r_max = float(np.max(np.abs(r)))
        return r_rel, r_max

def solve_poisson_2d_numerical(Nx, Ny):
    """
    Legacy convenience wrapper for manufactured solution solve on Nx x Ny grid.
    """
    solver = Poisson2DSolver(N=Nx)
    u = solver.solve(manufactured_source_2d)
    return solver.X, solver.Y, u

def compute_convergence_study(resolutions=(16, 32, 64, 128)):
    """
    Computes convergence of 5-point stencil against manufactured solution:
    u = sin(pi*x)*sin(pi*y), f = 2*pi^2*sin(pi*x)*sin(pi*y).
    Returns list of dicts with resolution, h, rel_l2, l_inf, observed order.
    """
    results = []
    prev_h = None
    prev_err = None
    
    for N in resolutions:
        solver = Poisson2DSolver(N=N)
        u_exact = solve_poisson_2d_exact(solver.X, solver.Y)
        u_num = solver.solve(manufactured_source_2d)
        
        diff = u_num - u_exact
        rel_l2 = float(np.linalg.norm(diff) / np.linalg.norm(u_exact))
        l_inf = float(np.max(np.abs(diff)))
        h = 1.0 / (N - 1)
        
        if prev_err is not None:
            order = float(np.log(prev_err / rel_l2) / np.log(prev_h / h))
        else:
            order = None
            
        results.append({
            "N": N,
            "h": h,
            "rel_l2": rel_l2,
            "l_inf": l_inf,
            "order": order
        })
        prev_h = h
        prev_err = rel_l2
        
    return results
