import os
import numpy as np
from tqdm import tqdm
import argparse
import sys

# Add parent directory to path to import src
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.solvers.heat_1d import solve_heat_1d_numerical

def generate_dataset(num_samples, alpha_range, alpha_dist='log-uniform', Nx=50, Nt_sim=5000, Nt_save=100, seed=42):
    """
    Generates a dataset for the 1D heat equation by varying alpha.
    """
    rng = np.random.default_rng(seed)
    if alpha_dist == 'log-uniform':
        alphas = np.exp(rng.uniform(np.log(alpha_range[0]), np.log(alpha_range[1]), num_samples))
    elif alpha_dist == 'uniform':
        alphas = rng.uniform(alpha_range[0], alpha_range[1], num_samples)
    else:
        raise ValueError("Invalid distribution")

    # Pre-allocate output arrays
    U = np.zeros((num_samples, Nt_save, Nx))
    
    # Generate data
    for i in tqdm(range(num_samples), desc=f"Generating {num_samples} samples ({alpha_dist})"):
        alpha = alphas[i]
        x, t, u = solve_heat_1d_numerical(Nx, Nt_sim, alpha)
        
        # Subsample time to save space
        idx = np.linspace(0, Nt_sim - 1, Nt_save, dtype=int)
        U[i] = u[idx, :]
        
    t_save = t[idx]
    return alphas, x, t_save, U

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out_dir', type=str, default='data/interim')
    args = parser.parse_args()
    
    # Use absolute path for output dir based on script location
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    out_dir = os.path.join(base_dir, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Training Set (alpha in [0.01, 1.0])
    print("Generating Training Set...")
    a_tr, x, t, u_tr = generate_dataset(1000, [0.01, 1.0], 'log-uniform', seed=42)
    np.savez_compressed(os.path.join(out_dir, 'train.npz'), alpha=a_tr, x=x, t=t, u=u_tr)
    
    # 2. Validation Set (alpha in [0.01, 1.0])
    print("Generating Validation Set...")
    a_val, _, _, u_val = generate_dataset(200, [0.01, 1.0], 'log-uniform', seed=43)
    np.savez_compressed(os.path.join(out_dir, 'val.npz'), alpha=a_val, x=x, t=t, u=u_val)
    
    # 3. Test Set - Interpolation (alpha in [0.01, 1.0])
    print("Generating Test Set (Interpolation)...")
    a_test_in, _, _, u_test_in = generate_dataset(200, [0.01, 1.0], 'log-uniform', seed=44)
    np.savez_compressed(os.path.join(out_dir, 'test_interpolation.npz'), alpha=a_test_in, x=x, t=t, u=u_test_in)
    
    # 4. Test Set - OOD Extrapolation (alpha < 0.01 or alpha > 1.0)
    print("Generating Test Set (OOD)...")
    rng_ood = np.random.default_rng(45)
    # Half below, half above
    a_low = rng_ood.uniform(0.003, 0.008, 100)
    a_high = rng_ood.uniform(1.5, 3.0, 100)
    a_ood = np.concatenate([a_low, a_high])
    rng_ood.shuffle(a_ood)
    
    U_ood = np.zeros((200, 100, 50))
    for i in tqdm(range(200), desc="Generating OOD samples"):
        alpha = a_ood[i]
        # For alpha > 1, we need smaller dt. alpha=3.0 -> r = 3.0 * dt / dx^2 <= 0.5
        # dt <= 0.5 * (1/49)^2 / 3.0 = 0.0000694. Nt = 1/dt = 14400.
        # Let's use Nt_sim=20000 for OOD to guarantee stability up to alpha=3.0
        _, _, u = solve_heat_1d_numerical(50, 20000, alpha)
        idx = np.linspace(0, 19999, 100, dtype=int)
        U_ood[i] = u[idx, :]
        
    np.savez_compressed(os.path.join(out_dir, 'test_ood.npz'), alpha=a_ood, x=x, t=t, u=U_ood)
    print("Dataset generation complete!")

if __name__ == '__main__':
    main()
