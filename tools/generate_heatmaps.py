try:
    from paths import RESULTS, PLOTS
except ImportError:
    from src.paths import RESULTS, PLOTS
import csv
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def generate_heatmaps():
    os.makedirs('plots', exist_ok=True)
    
    # 1. Load CSV data
    with open(str(RESULTS / 'mode2_pipeline_results_v2.csv'), 'r') as f:
        m2_rows = list(csv.DictReader(f))
    with open(str(RESULTS / 'mode3_pipeline_results_v2.csv'), 'r') as f:
        m3_rows = list(csv.DictReader(f))
    with open(str(RESULTS / 'mode3plus_hybrid_results.csv'), 'r') as f:
        m3p_rows = list(csv.DictReader(f))

    # Grid axes
    alphas = [0.002, 0.003, 0.004, 0.005, 0.008, 0.02, 0.05, 0.1, 0.2, 0.5, 1.5, 2.0, 2.5, 3.0, 4.0]
    alpha_labels = ['0.002\n(Ext)', '0.003', '0.004', '0.005', '0.008', 
                    '0.02', '0.05', '0.1', '0.2', '0.5', 
                    '1.5', '2.0', '2.5', '3.0', '4.0\n(Ext)']
    
    sensor_counts = [5, 10, 20]
    sensor_labels = ['5', '10', '20']
    noise_levels = [0.0, 0.01, 0.05]

    # Helper to build matrix (sensors x alphas)
    def build_matrix(rows, sigma_val, val_key):
        mat = np.zeros((len(sensor_counts), len(alphas)))
        status_mat = np.empty((len(sensor_counts), len(alphas)), dtype=object)
        for i_s, s in enumerate(sensor_counts):
            for i_a, a in enumerate(alphas):
                match = [r for r in rows if float(r['alpha']) == a and int(r['sensors']) == s and float(r['sigma']) == sigma_val]
                if match:
                    r = match[0]
                    val = float(r[val_key])
                    mat[i_s, i_a] = val
                    status_mat[i_s, i_a] = r['status']
                else:
                    mat[i_s, i_a] = np.nan
                    status_mat[i_s, i_a] = 'N/A'
        return mat, status_mat

    # Color norm: LogNorm from 1e-4 (0.01%) to 1.0 (100%)
    norm = mcolors.LogNorm(vmin=1e-4, vmax=1.0)
    cmap = plt.cm.YlOrRd.copy()
    cmap.set_bad('lightgray')

    # Figure 1: 3x3 Grid comparing Mode 2, Mode 3, and Mode 3+ across all noise levels
    fig, axes = plt.subplots(3, 3, figsize=(22, 14), sharex=True, sharey=True)
    plt.subplots_adjust(wspace=0.12, hspace=0.22, top=0.92, bottom=0.08, left=0.06, right=0.90)

    modes_info = [
        ('Mode 2: Crank–Nicolson Spline (≈1.8 ms)', m2_rows, 'med_rel_err'),
        ('Mode 3: FNO Spline (Wide ≤10, ≈1.3 ms)', m3_rows, 'med_wide'),
        ('Ablation: Solver Polish of FNO (≈137 ms)', m3p_rows, 'med_rel_err')
    ]

    for col_idx, (col_title, data_rows, key_name) in enumerate(modes_info):
        for row_idx, sigma in enumerate(noise_levels):
            ax = axes[row_idx, col_idx]
            mat, status_mat = build_matrix(data_rows, sigma, key_name)

            im = ax.imshow(mat, cmap=cmap, norm=norm, aspect='auto', origin='lower')

            # Annotate each cell with formatted value
            for i in range(len(sensor_counts)):
                for j in range(len(alphas)):
                    val = mat[i, j]
                    stat = status_mat[i, j]
                    if np.isnan(val):
                        continue
                    
                    # Formatting text
                    if val < 0.001:
                        txt = f"{val*100:.2f}%"
                    elif val < 0.10:
                        txt = f"{val*100:.1f}%"
                    else:
                        txt = f"{val*100:.0f}%"

                    # Annotation color based on brightness
                    text_color = "white" if val > 0.08 else "black"
                    
                    # Highlight status markers
                    marker = ""
                    if stat == 'Not Identifiable':
                        marker = "\n[NI]"
                        text_color = "red" if val <= 0.08 else "yellow"
                    elif 'bias-dominated' in stat or 'bias-uncorrected' in stat:
                        marker = "\n[BD]"
                        text_color = "blue" if val <= 0.08 else "cyan"

                    ax.text(j, i, txt + marker, ha='center', va='center', 
                            fontsize=7.5, color=text_color, fontweight='bold')

            # Add domain vertical dividers
            # low-alpha boundary: between index 4 (0.008) and 5 (0.02) -> x = 4.5
            # high-alpha boundary: between index 9 (0.5) and 10 (1.5) -> x = 9.5
            ax.axvline(4.5, color='black', linestyle='--', linewidth=1.2, alpha=0.7)
            ax.axvline(9.5, color='black', linestyle='--', linewidth=1.2, alpha=0.7)

            if row_idx == 0:
                ax.set_title(col_title, fontsize=13, fontweight='bold', pad=10)
            if col_idx == 0:
                ax.set_ylabel(rf"$\sigma = {sigma}$" + "\nSensors ($N_s$)", fontsize=11, fontweight='bold')

    # Shared X and Y ticks
    for col_idx in range(3):
        axes[2, col_idx].set_xticks(range(len(alphas)))
        axes[2, col_idx].set_xticklabels(alpha_labels, fontsize=8.5)
        axes[2, col_idx].set_xlabel("True Diffusion Coefficient ($\\alpha$)", fontsize=11, fontweight='bold')

    for row_idx in range(3):
        axes[row_idx, 0].set_yticks(range(len(sensor_counts)))
        axes[row_idx, 0].set_yticklabels(sensor_labels, fontsize=10)

    # Add colorbar
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.70])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label('Median Relative Error $|\\hat{\\alpha} - \\alpha| / \\alpha$', fontsize=12, fontweight='bold')
    cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y*100:.2g}%"))

    # Top Super Title
    fig.suptitle('Inverse Pipeline Parameter Identification Benchmark: Median Relative Error Heatmaps\n'
                 '[Low-α OOD: α < 0.01 | In-Distribution: 0.01 ≤ α ≤ 1.0 | High-α OOD: α > 1.0]  '
                 '[NI: Not Identifiable | BD: Bias-Dominated]',
                 fontsize=15, fontweight='bold', y=0.98)

    heatmap_path = 'plots/inverse_pipeline_error_heatmaps.png'
    plt.savefig(heatmap_path, dpi=300)
    plt.close()
    print(f"Heatmap saved to {heatmap_path}.")

    # Figure 2: Detailed Mode 2 vs Mode 3 Ratio Comparison for noisy regimes (sigma > 0)
    # Exclude sigma=0 since Mode 2 denominator is a numerical discretization floor.
    # Non-identifiable cells are marked [NI] rather than comparing unidentifiable ratios.
    ratio_noise_levels = [0.01, 0.05]
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5), sharey=True)
    plt.subplots_adjust(wspace=0.15, top=0.82, bottom=0.18, left=0.06, right=0.88)

    cmap_ratio = plt.cm.coolwarm.copy()
    cmap_ratio.set_bad('#e0e0e0') # Light gray for non-identifiable cells
    norm_ratio = mcolors.TwoSlopeNorm(vmin=0.2, vcenter=1.0, vmax=5.0)

    for i_sig, sigma in enumerate(ratio_noise_levels):
        ax = axes[i_sig]
        m2_mat, m2_stat = build_matrix(m2_rows, sigma, 'med_rel_err')
        m3_mat, m3_stat = build_matrix(m3_rows, sigma, 'med_wide')

        ratio_mat = np.full((len(sensor_counts), len(alphas)), np.nan)

        for i in range(len(sensor_counts)):
            for j in range(len(alphas)):
                s2 = m2_stat[i, j]
                s3 = m3_stat[i, j]
                # Mark non-identifiable cells instead of comparing their ratios
                if s2 == 'Not Identifiable' or s3 == 'Not Identifiable':
                    ax.text(j, i, "[NI]", ha='center', va='center', fontsize=8, color='#b71c1c', fontweight='bold')
                else:
                    r_val = m3_mat[i, j] / (m2_mat[i, j] + 1e-12)
                    ratio_mat[i, j] = r_val
                    txt = f"{r_val:.1f}x"
                    t_col = "white" if (r_val > 2.5 or r_val < 0.4) else "black"
                    ax.text(j, i, txt, ha='center', va='center', fontsize=8, color=t_col, fontweight='bold')

        im_ratio = ax.imshow(ratio_mat, cmap=cmap_ratio, norm=norm_ratio, aspect='auto', origin='lower')

        ax.axvline(4.5, color='black', linestyle='--', linewidth=1.2, alpha=0.7)
        ax.axvline(9.5, color='black', linestyle='--', linewidth=1.2, alpha=0.7)
        ax.set_title(f"Noise $\\sigma = {sigma}$", fontsize=12, fontweight='bold')
        ax.set_xticks(range(len(alphas)))
        ax.set_xticklabels(alpha_labels, fontsize=8)
        ax.set_xlabel("True Diffusion Coefficient ($\\alpha$)", fontsize=10, fontweight='bold')

    axes[0].set_yticks(range(len(sensor_counts)))
    axes[0].set_yticklabels(sensor_labels, fontsize=10)
    axes[0].set_ylabel("Sensors ($N_s$)", fontsize=11, fontweight='bold')

    cbar_ax2 = fig.add_axes([0.90, 0.20, 0.02, 0.60])
    cbar2 = fig.colorbar(im_ratio, cax=cbar_ax2)
    cbar2.set_label('Error Ratio (Mode 3 / Mode 2)\n[>1.0: Mode 2 more accurate | <1.0: Mode 3 more accurate]', fontsize=10, fontweight='bold')

    fig.suptitle('Error Ratio Heatmap: Mode 3 (FNO) vs. Mode 2 (Crank–Nicolson)\n'
                 '[σ=0 omitted (numerical floor) | [NI] denotes cells where parameter is Not Identifiable]',
                 fontsize=13, fontweight='bold', y=0.96)

    ratio_path = 'plots/mode3_vs_mode2_ratio_heatmaps.png'
    plt.savefig(ratio_path, dpi=300)
    plt.close()
    print(f"Ratio heatmap saved to {ratio_path}.")

if __name__ == '__main__':
    generate_heatmaps()
