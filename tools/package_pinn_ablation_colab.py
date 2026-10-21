"""Package PINN Ablation Study for Google Colab Execution.

Creates:
1. pinn_ablation_colab_package.zip containing all code, dependencies, and evaluation datasets.
2. run_pinn_ablation_colab.ipynb: Ready-to-run Jupyter Notebook with step-by-step cells.
"""

import os
import sys
import zipfile
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def create_colab_package():
    zip_path = os.path.join(REPO_ROOT, "pinn_ablation_colab_package.zip")
    
    files_to_pack = [
        # Source code
        "src/models/pinn.py",
        "src/paths.py",
        "src/__init__.py",
        "experiments/train_pinn_ablation.py",
        # Frozen baseline for reference
        "models/pinn_expD.pt",
        # Required datasets for training data-loss variants and evaluation
        "data/datasets/train.npz",
        "data/datasets/test_interpolation.npz",
        "data/datasets/test_ood.npz"
    ]
    
    print(f"Creating {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel_path in files_to_pack:
            full_path = os.path.join(REPO_ROOT, rel_path)
            if os.path.exists(full_path):
                z.write(full_path, rel_path)
                sz_mb = os.path.getsize(full_path) / 1024 / 1024
                print(f"  Added: {rel_path} ({sz_mb:.2f} MB)")
            else:
                print(f"  WARNING: Missing {rel_path}")
                
    total_sz_mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"\n[Success] Created {zip_path} ({total_sz_mb:.2f} MB)")
    
    # Create the Colab notebook
    nb_path = os.path.join(REPO_ROOT, "run_pinn_ablation_colab.ipynb")
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# PINN Single-Factor Ablation Study (Colab GPU Runner)\n",
                    "\n",
                    "This notebook executes the systematic single-factor PINN ablation study around the frozen Exp D baseline.\n",
                    "\n",
                    "### Ablation Matrix (3 seeds: 42, 43, 44 each):\n",
                    "1. **Activation:** `tanh` (base) vs `GELU` vs `sin`\n",
                    "2. **Collocation:** `base` (resampled uniform) vs `fixed` (static uniform) vs `sobol` vs `lhs`\n",
                    "3. **Loss Weighting:** `base` (pure PDE) vs `data_equal` (PDE + data) vs `data_heavy` vs `grad_norm` (dynamic GradNorm balancing)\n",
                    "4. **Optimizer:** `base` (Adam + L-BFGS) vs `adam_only` (Adam 1500 epochs)\n",
                    "\n",
                    "### Prerequisites:\n",
                    "1. In Google Colab menu: **Runtime -> Change runtime type -> GPU (T4 or better)**.\n",
                    "2. Have `pinn_ablation_colab_package.zip` ready on your computer."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 1: Check GPU availability\n",
                    "!nvidia-smi"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 2: Upload and extract pinn_ablation_colab_package.zip\n",
                    "import os, zipfile\n",
                    "from google.colab import files\n",
                    "\n",
                    "if not os.path.exists('pinn_ablation_colab_package.zip'):\n",
                    "    print('Please select and upload pinn_ablation_colab_package.zip from your computer:')\n",
                    "    uploaded = files.upload()\n",
                    "\n",
                    "print('Extracting package...')\n",
                    "with zipfile.ZipFile('pinn_ablation_colab_package.zip', 'r') as z:\n",
                    "    z.extractall('.')\n",
                    "print('Package extracted successfully!')\n",
                    "!ls -lh data/datasets/"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 3: Fast 2-epoch smoke test to verify GPU, autograd, Sobol, LHS, GradNorm\n",
                    "!python experiments/train_pinn_ablation.py --device cuda --smoke-test --out-dir /tmp/pinn_smoke"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 4: Run full PINN ablation study (all 12 configurations x 3 seeds = 36 runs)\n",
                    "# Results are incrementally saved to data/results/pinn_ablation/ with resume support.\n",
                    "!python experiments/train_pinn_ablation.py --device cuda --seeds 42,43,44 --epochs 1000 --lbfgs-iters 500 --out-dir data/results/pinn_ablation --resume"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 5: Display summary table\n",
                    "import pandas as pd\n",
                    "df = pd.read_csv('data/results/pinn_ablation/pinn_ablation_summary.csv')\n",
                    "print(df.to_string())\n",
                    "\n",
                    "# Group by variant (mean across seeds)\n",
                    "summary_tbl = df.groupby(['axis', 'variant'])[['interp_rel_l2_median', 'low_alpha_ood_rel_l2_median', 'high_alpha_ood_rel_l2_median', 't0_mae_median', 'train_time_sec']].mean()\n",
                    "print('\\n=== MEAN METRICS ACROSS SEEDS (42, 43, 44) ===')\n",
                    "print(summary_tbl.to_string())"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 6: Create downloadable ZIP archive of all results, checkpoints, and curves\n",
                    "!zip -r pinn_ablation_results.zip data/results/pinn_ablation/\n",
                    "print('Results successfully packaged into pinn_ablation_results.zip!')\n",
                    "from google.colab import files\n",
                    "files.download('pinn_ablation_results.zip')"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 7 (Optional): Backup to Google Drive\n",
                    "try:\n",
                    "    from google.colab import drive\n",
                    "    drive.mount('/content/drive')\n",
                    "    !mkdir -p /content/drive/MyDrive/Digital_Twin_Ablation/\n",
                    "    !cp -r data/results/pinn_ablation /content/drive/MyDrive/Digital_Twin_Ablation/\n",
                    "    print('Backed up results to Google Drive successfully!')\n",
                    "except Exception as e:\n",
                    "    print('Google Drive backup skipped:', e)"
                ]
            }
        ],
        "metadata": {
            "accelerator": "GPU",
            "colab": {
                "provenance": []
            },
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }
    
    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=2)
    print(f"[Success] Created {nb_path}")

if __name__ == '__main__':
    create_colab_package()
