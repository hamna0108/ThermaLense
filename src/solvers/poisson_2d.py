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
    Solves -nabla^2 u = f on [x_min, x_max] x [y_min, y_max] with u = 0 on boundary using standard 5-point stencil.
    Supports arbitrary resolutions (Nx, Ny).
    """
    def __init__(self, N=64, Nx=None, Ny=None, domain_x=(0.0, 1.0), domain_y=(0.0, 1.0)):
        self.N = N
        self.Nx = Nx if Nx is not None else N
        self.Ny = Ny if Ny is not None else N
        self.x = np.linspace(domain_x[0], domain_x[1], self.Nx)
        self.y = np.linspace(domain_y[0], domain_y[1], self.Ny)
        self.X, self.Y = np.meshgrid(self.x, self.y, indexing='ij')
        self.dx = self.x[1] - self.x[0]
        self.dy = self.y[1] - self.y[0]
        self.h = self.dx
        
        self.nx_int = self.Nx - 2
        self.ny_int = self.Ny - 2
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

    def solve(self, f, bc=None):
        """
        Solve -nabla^2 u = f with specified boundary conditions.
        f: either callable f(X, Y) or ndarray of shape (Nx, Ny).
        bc: optional dict specifying boundary conditions on edges:
            {'x_min': ..., 'x_max': ..., 'y_min': ..., 'y_max': ...}
            Each edge can specify {'type': 'dirichlet'|'neumann', 'value': ...}.
            If bc is None, defaults to zero Dirichlet on all boundaries.
        Returns:
            u: ndarray of shape (Nx, Ny) satisfying discrete PDE and boundary conditions.
        """
        if callable(f):
            f_grid = f(self.X, self.Y)
        else:
            f_grid = np.asarray(f)
            if f_grid.shape != (self.Nx, self.Ny):
                raise ValueError(f"f array shape {f_grid.shape} must match (Nx, Ny) = ({self.Nx}, {self.Ny})")
        
        if bc is None or not bc:
            b = f_grid[1:-1, 1:-1].flatten()
            u_int = self.lu_solve(b)
            u = np.zeros((self.Nx, self.Ny), dtype=np.float64)
            u[1:-1, 1:-1] = u_int.reshape((self.nx_int, self.ny_int))
            return u

        def _get_bc(key, default_type='dirichlet', default_val=0.0):
            spec = bc.get(key, {})
            if isinstance(spec, dict):
                return str(spec.get('type', default_type)).lower(), spec.get('value', default_val)
            if isinstance(spec, (tuple, list)):
                return str(spec[0]).lower(), spec[1]
            return default_type, float(spec)

        l_type, l_val = _get_bc('x_min', 'dirichlet', 0.0)
        r_type, r_val = _get_bc('x_max', 'dirichlet', 0.0)
        b_type, b_val = _get_bc('y_min', 'dirichlet', 0.0)
        t_type, t_val = _get_bc('y_max', 'dirichlet', 0.0)

        def _eval_bc(val, coords):
            if callable(val):
                return np.asarray(val(coords), dtype=float)
            elif isinstance(val, (int, float)):
                return np.full_like(coords, float(val), dtype=float)
            else:
                return np.asarray(val, dtype=float)

        g_left = _eval_bc(l_val, self.y)
        g_right = _eval_bc(r_val, self.y)
        g_bottom = _eval_bc(b_val, self.x)
        g_top = _eval_bc(t_val, self.x)

        # 1. All-Dirichlet case (including arbitrary non-zero and unequal edges)
        if l_type == 'dirichlet' and r_type == 'dirichlet' and b_type == 'dirichlet' and t_type == 'dirichlet':
            rhs = f_grid[1:-1, 1:-1].copy()
            rhs[0, :] += g_left[1:-1] / (self.dx**2)
            rhs[-1, :] += g_right[1:-1] / (self.dx**2)
            rhs[:, 0] += g_bottom[1:-1] / (self.dy**2)
            rhs[:, -1] += g_top[1:-1] / (self.dy**2)

            u_int = self.lu_solve(rhs.flatten())
            u = np.zeros((self.Nx, self.Ny), dtype=np.float64)
            u[1:-1, 1:-1] = u_int.reshape((self.nx_int, self.ny_int))
            u[0, :] = g_left
            u[-1, :] = g_right
            u[:, 0] = g_bottom
            u[:, -1] = g_top
            return u

        # 2. Neumann on x-edges, Dirichlet on y-edges
        elif l_type == 'neumann' and r_type == 'neumann' and b_type == 'dirichlet' and t_type == 'dirichlet':
            N_unk = self.Nx * self.ny_int
            A_mat = sp.lil_matrix((N_unk, N_unk), dtype=float)
            rhs = np.zeros(N_unk, dtype=float)

            for i in range(self.Nx):
                for j_int in range(self.ny_int):
                    j = j_int + 1
                    k = i * self.ny_int + j_int
                    rhs[k] = f_grid[i, j]

                    if j_int == 0:
                        rhs[k] += g_bottom[i] / (self.dy**2)
                    if j_int == self.ny_int - 1:
                        rhs[k] += g_top[i] / (self.dy**2)

                    diag_val = 2.0 / (self.dy**2) + 2.0 / (self.dx**2)
                    A_mat[k, k] = diag_val

                    if j_int > 0:
                        A_mat[k, k - 1] = -1.0 / (self.dy**2)
                    if j_int < self.ny_int - 1:
                        A_mat[k, k + 1] = -1.0 / (self.dy**2)

                    if i == 0:
                        A_mat[k, (i + 1) * self.ny_int + j_int] = -2.0 / (self.dx**2)
                        rhs[k] -= 2.0 * g_left[j] / self.dx
                    elif i == self.Nx - 1:
                        A_mat[k, (i - 1) * self.ny_int + j_int] = -2.0 / (self.dx**2)
                        rhs[k] += 2.0 * g_right[j] / self.dx
                    else:
                        A_mat[k, (i - 1) * self.ny_int + j_int] = -1.0 / (self.dx**2)
                        A_mat[k, (i + 1) * self.ny_int + j_int] = -1.0 / (self.dx**2)

            u_sol = spla.spsolve(A_mat.tocsc(), rhs)
            u = np.zeros((self.Nx, self.Ny), dtype=np.float64)
            u[:, 1:-1] = u_sol.reshape((self.Nx, self.ny_int))
            u[:, 0] = g_bottom
            u[:, -1] = g_top
            return u

        else:
            raise NotImplementedError(f"Unsupported 2D boundary combination: x=({l_type}, {r_type}), y=({b_type}, {t_type})")

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
