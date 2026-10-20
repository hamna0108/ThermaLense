import os
import zipfile
import json

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    zip_path = os.path.join(base_dir, "heat_fno_seeds_colab_package.zip")
    
    files_to_pack = [
        # Source code
        "src/models/fno2d.py",
        "src/data/dataset.py",
        "src/solvers/heat_1d.py",
        "src/paths.py",
        "src/__init__.py",
        "experiments/train_heat_fno_seeds.py",
        # Frozen baseline for comparison
        "models/fno2d_heat.pt",
        # Heat datasets
        "data/datasets/train.npz",
        "data/datasets/val.npz",
        "data/datasets/test_interpolation.npz",
        "data/datasets/test_ood.npz"
    ]
    
    print(f"Creating {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel_path in files_to_pack:
            full_path = os.path.join(base_dir, rel_path)
            if os.path.exists(full_path):
                z.write(full_path, rel_path)
                print(f"  Added: {rel_path} ({os.path.getsize(full_path):,} bytes)")
            else:
                print(f"  WARNING: Missing {rel_path}")
                
    print(f"Package created successfully! Size: {os.path.getsize(zip_path) / 1024 / 1024:.2f} MB")
    
    # Also create the ready-to-run Jupyter Notebook
    nb_path = os.path.join(base_dir, "run_heat_fno_seeds_colab.ipynb")
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# 1D Heat FNO Multi-Seed Stability Study (Colab GPU Runner)\n",
                    "\n",
                    "This notebook runs the 5-seed stability study (`seeds 42, 43, 44, 45, 46`) on GPU (T4/V100/A100) and compares results directly against the frozen `models/fno2d_heat.pt`.\n",
                    "\n",
                    "### Prerequisites:\n",
                    "1. Set Runtime: **Runtime -> Change runtime type -> T4 GPU** (or any GPU).\n",
                    "2. Have `heat_fno_seeds_colab_package.zip` ready on your computer."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 1: Verify GPU\n",
                    "!nvidia-smi"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 2: Mount Google Drive (to automatically save results)\n",
                    "from google.colab import drive\n",
                    "import os\n",
                    "\n",
                    "drive.mount('/content/drive')\n",
                    "drive_out_dir = '/content/drive/MyDrive/heat_fno_seeds_results'\n",
                    "os.makedirs(drive_out_dir, exist_ok=True)\n",
                    "print('Google Drive connected! Results will be copied to:', drive_out_dir)"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 3: Upload and Extract package\n",
                    "from google.colab import files\n",
                    "import zipfile\n",
                    "\n",
                    "if not os.path.exists('data/datasets/train.npz'):\n",
                    "    print('Please select and upload heat_fno_seeds_colab_package.zip:')\n",
                    "    uploaded = files.upload()\n",
                    "    for fn in uploaded.keys():\n",
                    "        if fn.endswith('.zip'):\n",
                    "            print(f'Extracting {fn}...')\n",
                    "            with zipfile.ZipFile(fn, 'r') as z:\n",
                    "                z.extractall('.')\n",
                    "            print('Extraction complete!')\n",
                    "\n",
                    "!ls -lh data/datasets/"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 4: Run the 5-seed training and stability evaluation\n",
                    "!python experiments/train_heat_fno_seeds.py \\\n",
                    "    --seeds 42 43 44 45 46 \\\n",
                    "    --device cuda \\\n",
                    "    --out-dir models/fno_heat_seeds \\\n",
                    "    --epochs 100 \\\n",
                    "    --batch-size 20 \\\n",
                    "    --resume"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Step 5: Save results to Google Drive & Create Download Zip\n",
                    "!cp -r models/fno_heat_seeds/* /content/drive/MyDrive/heat_fno_seeds_results/\n",
                    "!zip -r heat_fno_seeds_results.zip models/fno_heat_seeds/\n",
                    "print('Results synced to Drive and packaged into heat_fno_seeds_results.zip!')\n",
                    "\n",
                    "# Trigger browser download\n",
                    "from google.colab import files\n",
                    "files.download('heat_fno_seeds_results.zip')"
                ]
            }
        ],
        "metadata": {
            "accelerator": "GPU",
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }
    
    with open(nb_path, "w") as f:
        json.dump(nb, f, indent=2)
    print(f"Created notebook at {nb_path}")

if __name__ == "__main__":
    main()
