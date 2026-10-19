import numpy as np
import scipy.optimize as opt
import matplotlib.pyplot as plt
import os
import time
import scipy.sparse as sp
import scipy.sparse.linalg as spla

def solve_heat_1d_exact(x, t, alpha):
    return np.exp(-alpha * np.pi**2 * t) * np.sin(np.pi * x)

def solve_heat_1d_cn(Nx, Nt, alpha):
    x = np.linspace(0, 1, Nx)
    t = np.linspace(0, 1, Nt)
    dx = x[1] - x[0]
    dt = t[1] - t[0]
    r = alpha * dt / (2 * dx**2)
    main_diag_A = (1 + 2*r) * np.ones(Nx-2)
    off_diag_A = -r * np.ones(Nx-3)
    main_diag_B = (1 - 2*r) * np.ones(Nx-2)
    off_diag_B = r * np.ones(Nx-3)
    A = sp.diags([off_diag_A, main_diag_A, off_diag_A], offsets=[-1, 0, 1], format='csr')
    B = sp.diags([off_diag_B, main_diag_B, off_diag_B], offsets=[-1, 0, 1], format='csr')
    u = np.zeros((Nt, Nx))
    u[0, :] = np.sin(np.pi * x)
    for n in range(0, Nt - 1):
        rhs = B.dot(u[n, 1:-1])
        u[n+1, 1:-1] = spla.spsolve(A, rhs)
        u[n+1, 0] = 0.0
        u[n+1, -1] = 0.0
    return x, t, u

def cramer_rao_bound(alpha, t_sensors, x_sensors, sigma):
    grads = -np.pi**2 * t_sensors * np.exp(-alpha * np.pi**2 * t_sensors) * np.sin(np.pi * x_sensors)
    fisher_info = np.sum(grads**2) / (sigma**2 + 1e-12)
    if fisher_info == 0:
        return np.inf
    return 1.0 / fisher_info

def get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid):
    layouts = []
    for _ in range(num_replications):
        t_log = np.logspace(np.log10(0.01), np.log10(1.0), num_sensors)
        t_idx = [np.argmin(np.abs(t_grid - t)) for t in t_log]
        t_sensors = t_grid[t_idx]
        x_candidates = x_grid[(x_grid >= 0.2) & (x_grid <= 0.8)]
        x_sensors = np.random.choice(x_candidates, size=num_sensors, replace=True)
        layouts.append((t_sensors, x_sensors))
    return layouts

def mode2_loss(log_alpha, t_sensors, x_sensors, y_sensors, x_grid, t_grid):
    alpha = 10**log_alpha[0]
    _, _, u_num = solve_heat_1d_cn(len(x_grid), len(t_grid), alpha)
    loss = 0.0
    for i in range(len(t_sensors)):
        t_idx = np.argmin(np.abs(t_grid - t_sensors[i]))
        x_idx = np.argmin(np.abs(x_grid - x_sensors[i]))
        loss += (u_num[t_idx, x_idx] - y_sensors[i])**2
    return loss / len(t_sensors)

def evaluate_mode2():
    Nx, Nt = 50, 100
    x_grid = np.linspace(0, 1, Nx)
    t_grid = np.linspace(0, 1, Nt)
    
    alphas_to_test = {
        'Interpolation': [0.1, 0.5],
        'Low-alpha OOD': [0.005],
        'High-alpha OOD': [2.5]
    }
    
    sensor_counts = [2, 5, 10, 20]
    noise_levels = [0.0, 0.01, 0.05]
    
    grid_log_alphas = np.linspace(-3, np.log10(4.0), 200)
    num_replications = 200
    
    print("Precomputing grid solutions for Mode 2...")
    t0_pre = time.time()
    grid_u_nums = []
    for la in grid_log_alphas:
        _, _, u_num = solve_heat_1d_cn(len(x_grid), len(t_grid), 10**la)
        grid_u_nums.append(u_num)
    t1_pre = time.time()
    print(f"Precompute time: {t1_pre - t0_pre:.2f} s")
    print("Local refinement in Mode 2 utilizes L-BFGS-B with eps=1e-4 to navigate the finite-difference solver landscape smoothly.")
    
    print(f"{'Split':15s} | {'Alpha':5s} | {'Sensors':7s} | {'Sigma':5s} | {'MedRelErr':10s} | {'Spread(log)':11s} | {'Cov95':6s} | {'Time(s)':7s}")
    print("-" * 95)
    
    global_total_time = 0
    global_num_inversions = 0
    
    for split, alphas in alphas_to_test.items():
        for alpha_true in alphas:
            for num_sensors in sensor_counts:
                layouts = get_sensor_layouts(num_sensors, num_replications, x_grid, t_grid)
                for sigma in noise_levels:
                    
                    alpha_hats = []
                    crbs_log = []
                    coverage_count = 0
                    
                    cell_start_time = time.time()
                    
                    for t_s, x_s in layouts:
                        u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
                        if sigma > 0:
                            noise = np.random.normal(0, sigma, size=num_sensors)
                            y_s = u_exact + noise
                        else:
                            y_s = u_exact
                            
                        crb_true = cramer_rao_bound(alpha_true, t_s, x_s, sigma)
                        crb_std_log = np.sqrt(crb_true) / (alpha_true * np.log(10)) if (crb_true != np.inf and crb_true != 0) else 0.0
                        crbs_log.append(crb_std_log)
                        
                        losses = []
                        for u_num in grid_u_nums:
                            loss = 0.0
                            for i in range(len(t_s)):
                                t_idx = np.argmin(np.abs(t_grid - t_s[i]))
                                x_idx = np.argmin(np.abs(x_grid - x_s[i]))
                                loss += (u_num[t_idx, x_idx] - y_s[i])**2
                            losses.append(loss / len(t_s))
                            
                        best_grid_idx = np.argmin(losses)
                        best_grid_log_alpha = grid_log_alphas[best_grid_idx]
                        
                        res = opt.minimize(
                            mode2_loss, 
                            x0=[best_grid_log_alpha], 
                            args=(t_s, x_s, y_s, x_grid, t_grid),
                            bounds=[(-3.0, np.log10(4.0))],
                            method='L-BFGS-B',
                            options={'eps': 1e-4}
                        )
                        hat = 10**res.x[0]
                        alpha_hats.append(hat)
                        
                        if sigma > 0:
                            crb_hat = cramer_rao_bound(hat, t_s, x_s, sigma)
                            if crb_hat != np.inf and crb_hat != 0:
                                crb_hat_log_std = np.sqrt(crb_hat) / (hat * np.log(10))
                                lower = np.log10(hat) - 1.96 * crb_hat_log_std
                                upper = np.log10(hat) + 1.96 * crb_hat_log_std
                                if lower <= np.log10(alpha_true) <= upper:
                                    coverage_count += 1
                                    
                    cell_end_time = time.time()
                    cell_time = cell_end_time - cell_start_time
                    global_total_time += cell_time
                    global_num_inversions += num_replications
                    
                    alpha_hats = np.array(alpha_hats)
                    log_alpha_hats = np.log10(alpha_hats)
                    
                    median_rel_err = np.median(np.abs(alpha_hats - alpha_true) / alpha_true)
                    spread_log_alpha = np.std(log_alpha_hats)
                    mean_crb = np.mean(crbs_log)
                    
                    bound_low = 10**-3.0
                    bound_high = 4.0
                    frac_clamped = np.mean((np.abs(alpha_hats - bound_low) < 1e-4) | (np.abs(alpha_hats - bound_high) < 1e-4))
                    
                    if sigma == 0:
                        cov_str = "N/A"
                    else:
                        cov_pct = 100.0 * coverage_count / num_replications
                        cov_str = f"{cov_pct:4.1f}%"
                        
                    mean_time = cell_time / num_replications
                    
                    if frac_clamped > 0.5 or (sigma > 0 and spread_log_alpha < 0.5 * mean_crb):
                        print(f"{split:15s} | {alpha_true:5.3f} | {num_sensors:7d} | {sigma:5.2f} | "
                              f"{median_rel_err:10.4f} | {spread_log_alpha:11.4f} | {cov_str:6s} | {mean_time:7.4f} **(Not Identifiable)**", flush=True)
                    else:
                        print(f"{split:15s} | {alpha_true:5.3f} | {num_sensors:7d} | {sigma:5.2f} | "
                              f"{median_rel_err:10.4f} | {spread_log_alpha:11.4f} | {cov_str:6s} | {mean_time:7.4f} (CRB: {mean_crb:.4f})", flush=True)

    print(f"\nAverage wall-clock time per Mode 2 inversion (excluding precompute): {global_total_time / global_num_inversions:.4f} seconds")

    print("\nGenerating comprehensive bias-vs-alpha sweep for sigma=0...")
    alphas_curve = np.linspace(0.003, 4.0, 50)
    bias_curve = []
    
    num_sensors = 20
    sigma = 0.0
    layouts = get_sensor_layouts(num_sensors, 10, x_grid, t_grid) # 10 reps for curve
    for alpha_true in alphas_curve:
        alpha_hats = []
        for t_s, x_s in layouts:
            u_exact = solve_heat_1d_exact(x_s, t_s, alpha_true)
            y_s = u_exact
            
            losses = []
            for u_num in grid_u_nums:
                loss = 0.0
                for i in range(len(t_s)):
                    t_idx = np.argmin(np.abs(t_grid - t_s[i]))
                    x_idx = np.argmin(np.abs(x_grid - x_s[i]))
                    loss += (u_num[t_idx, x_idx] - y_s[i])**2
                losses.append(loss / len(t_s))
                
            best_grid_idx = np.argmin(losses)
            best_grid_log_alpha = grid_log_alphas[best_grid_idx]
            
            res = opt.minimize(
                mode2_loss, 
                x0=[best_grid_log_alpha], 
                args=(t_s, x_s, y_s, x_grid, t_grid),
                bounds=[(-3.0, np.log10(4.0))],
                method='L-BFGS-B',
                options={'eps': 1e-4}
            )
            alpha_hats.append(10**res.x[0])
        mean_hat = np.mean(alpha_hats)
        bias_curve.append(mean_hat - alpha_true)
        print(f"Sweep sigma=0 | True Alpha: {alpha_true:.4f} | Bias: {mean_hat - alpha_true:.6f} | Relative Error: {abs(mean_hat - alpha_true)/alpha_true:.6f}")
        
    plt.figure()
    plt.plot(alphas_curve, bias_curve, marker='o', markersize=3)
    plt.axhline(0, color='r', linestyle='--')
    plt.xlabel('True Alpha')
    plt.ylabel('Bias (Estimated - True)')
    plt.title('Mode 2: Bias vs Alpha (sigma=0, 20 sensors)')
    plt.grid(True)
    plt.savefig('plots/mode2_bias_vs_alpha_sigma0.png')
    plt.close()

if __name__ == '__main__':
    os.makedirs('plots', exist_ok=True)
    evaluate_mode2()
