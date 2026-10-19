import numpy as np
import os
import matplotlib.pyplot as plt
import json

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
data_dir = os.path.join(base_dir, 'data/interim')
plot_dir = os.path.join(base_dir, 'plots')
os.makedirs(plot_dir, exist_ok=True)

splits = ['train', 'val', 'test_interpolation', 'test_ood']
data = {}
for split in splits:
    data[split] = np.load(os.path.join(data_dir, f"{split}.npz"))

report = {}

# 1. Split counts and sizes
report['counts'] = {s: data[s]['alpha'].shape[0] for s in splits}
report['total_samples'] = sum(report['counts'].values())

# 2. Alpha ranges
report['alpha_ranges'] = {}
for s in splits:
    alphas = data[s]['alpha']
    report['alpha_ranges'][s] = {
        'min': float(np.min(alphas)),
        'max': float(np.max(alphas))
    }

plt.figure(figsize=(10, 6))
for s in splits:
    plt.hist(data[s]['alpha'], bins=30, alpha=0.5, label=s)
plt.xscale('log')
plt.title('Alpha Distribution across Splits')
plt.xlabel('Alpha')
plt.ylabel('Count')
plt.legend()
plt.savefig(os.path.join(plot_dir, 'alpha_histogram.png'), dpi=300)
plt.close()

# 3. No leakage
report['leakage'] = {}
a_train = set(data['train']['alpha'])
a_val = set(data['val']['alpha'])
a_test_in = set(data['test_interpolation']['alpha'])
a_test_ood = set(data['test_ood']['alpha'])
report['leakage']['train_val'] = len(a_train.intersection(a_val))
report['leakage']['train_test_in'] = len(a_train.intersection(a_test_in))
report['leakage']['train_test_ood'] = len(a_train.intersection(a_test_ood))
report['leakage']['val_test_in'] = len(a_val.intersection(a_test_in))

# 4. Boundary/initial conditions fixed
report['bc_ic_check'] = True
for s in splits:
    u = data[s]['u']
    x = data[s]['x']
    # IC check
    ic_expected = np.sin(np.pi * x)
    ic_diff = np.max(np.abs(u[:, 0, :] - ic_expected))
    if ic_diff > 1e-5: report['bc_ic_check'] = False
    # BC check
    bc_left = np.max(np.abs(u[:, :, 0]))
    bc_right = np.max(np.abs(u[:, :, -1]))
    if bc_left > 1e-5 or bc_right > 1e-5: report['bc_ic_check'] = False

# 5. Solver correctness
alphas = data['test_interpolation']['alpha']
idx = np.argmin(np.abs(alphas - 0.1))
a_closest = alphas[idx]
u_closest = data['test_interpolation']['u'][idx]
t_closest = data['test_interpolation']['t']
x_closest = data['test_interpolation']['x']

def solve_heat_1d_exact(x, t, alpha):
    return np.exp(-alpha * np.pi**2 * t) * np.sin(np.pi * x)

u_exact_final = solve_heat_1d_exact(x_closest, t_closest[-1], a_closest)
l2_error = np.linalg.norm(u_closest[-1] - u_exact_final) / np.linalg.norm(u_exact_final)
report['solver_correctness'] = {
    'alpha_used': float(a_closest),
    'l2_error_at_T': float(l2_error)
}

# 6. Sanity on arrays
report['sanity'] = {}
for s in splits:
    u = data[s]['u']
    has_nan = bool(np.isnan(u).any())
    has_inf = bool(np.isinf(u).any())
    report['sanity'][s] = {
        'shape': list(u.shape),
        'has_nan': has_nan,
        'has_inf': has_inf
    }

# 7. Reproducibility
with open(os.path.join(base_dir, 'src/data/generate_dataset.py'), 'r') as f:
    content = f.read()
report['reproducibility'] = 'np.random.seed(42)' in content

print(json.dumps(report, indent=4))
