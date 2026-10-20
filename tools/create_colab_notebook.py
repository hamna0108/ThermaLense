import json

nb = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Stage 2 Round 2: FNO v3 Multi-Seed Colab Training\n",
                "\n",
                "This notebook trains the **FNO v3** operator (width 64, modes 16, hard boundary mask) on the 2D Poisson v2 dataset across **5 seeds** (`42, 43, 44, 45, 46`) using GPU acceleration.\n",
                "\n",
                "### Steps:\n",
                "1. **Ensure GPU is active:** Check that `Runtime -> Change runtime type` is set to **T4 GPU**.\n",
                "2. Run Cell 1 to verify GPU.\n",
                "3. Run Cell 2 to upload and extract `fno_v3_colab_package.zip`.\n",
                "4. Run Cell 3 to execute the training and evaluation script.\n",
                "5. Run Cell 4 to view the acceptance verdict and download the results.\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Step 1: Check GPU availability\n",
                "!nvidia-smi\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Step 2: Upload and extract fno_v3_colab_package.zip\n",
                "import os, zipfile\n",
                "from google.colab import files\n",
                "\n",
                "if not os.path.exists('fno_v3_colab_package.zip'):\n",
                "    print('Please select and upload fno_v3_colab_package.zip from your computer:')\n",
                "    uploaded = files.upload()\n",
                "\n",
                "print('Extracting package...')\n",
                "with zipfile.ZipFile('fno_v3_colab_package.zip', 'r') as z:\n",
                "    z.extractall('.')\n",
                "print('Extraction complete!')\n",
                "!ls src/\n",
                "!ls data/datasets/\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Step 3: Train FNO v3 across 5 seeds on GPU\n",
                "!python src/train_fno_poisson_v3.py --seeds 42 43 44 45 46 --device cuda --out-dir models/fno_v3 --epochs 300 --patience 25\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Step 4: Display Acceptance Decision & Multi-Seed Results\n",
                "import json\n",
                "report_path = 'models/fno_v3/fno_v3_acceptance_report.json'\n",
                "if os.path.exists(report_path):\n",
                "    with open(report_path) as f:\n",
                "        rep = json.load(f)\n",
                "    print('==================================================')\n",
                "    print('ACCEPTANCE DECISION VERDICT:')\n",
                "    print(rep['acceptance_verdict'])\n",
                "    print('==================================================')\n",
                "    print('\\nMulti-Seed Spread Summary:')\n",
                "    print(json.dumps(rep['spread_summary'], indent=2))\n",
                "else:\n",
                "    print('Report file not found. Ensure training completed.')\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Step 5: Download the trained models and reports back to your PC\n",
                "!zip -r fno_v3_results.zip models/fno_v3/\n",
                "files.download('fno_v3_results.zip')\n"
            ]
        }
    ],
    "metadata": {
        "accelerator": "GPU",
        "colab": {
            "provenance": []
        },
        "kernelspec": {
            "display_name": "Python 3",
            "name": "python3"
        },
        "language_info": {
            "name": "python"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 0
}

with open("run_fno_v3_colab.ipynb", "w") as f:
    json.dump(nb, f, indent=2)

print("Created run_fno_v3_colab.ipynb successfully!")
