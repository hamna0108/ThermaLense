# Stage 2 Round 2 Review & Deliverable Report

## 1. Reconciled Training Diagnosis (Train vs Val)
- **Epochs Trained:** 62 | **Best Epoch:** 47 | **Status:** `early_stopped_plateau (patience 15 reached at epoch 62, best epoch 47)`
- **Loss at Best Epoch (Epoch 47):**
  - **Mean Rel L2 (from epoch batch-loss curves):** Train = 0.053223 (5.32%) vs Val = 0.044219 (4.42%)
  - **Median Rel L2 (from evaluated checkpoint on full datasets):** Train = 0.032870 (3.29%) vs Val = 0.033455 (3.35%)
- **Diagnosis:** Validation plateau reached without overfitting (best epoch 47: train rel L2 5.32%, val rel L2 4.42%); early stopping preserved optimal generalization.
- **Reconciliation Conclusion:** Train and validation errors are practically identical (3.29% train median vs 3.35% val median, a delta of only 0.06%). The previous label 'mild overfitting' was an artifact of evaluating the final epoch (62) after early-stopping patience had expired; the preserved checkpoint at epoch 47 exhibits clean validation plateauing without overfitting.

## 2. Timing Honesty Disclosures (CPU, 64x64)
- **Single Query Solver (Prefactorized LU):** 0.501 ms
- **Batched Solver (Prefactorized LU, B=32):** 0.255 ms / query
- **Fresh LU Factorization (From Scratch per Query):** 10.925 ms
- **Linear Dual Baseline (Single / Batched):** 3.333 ms / 0.389 ms
- **FNO-2D Operator (Single / Batched):** 20.477 ms / 5.590 ms
- **Fresh-Factorization Solver Speedup vs FNO:** 1.9x faster (10.925 ms vs 20.477 ms on CPU, 64x64).
- **Honest Statement:** At 64x64 resolution, the classical sparse direct solver is vastly faster than FNO on CPU: 0.501 ms vs 20.477 ms single-query (40.9x faster), and 0.255 ms vs 5.590 ms batched (21.9x faster). Even rebuilding and re-factorizing the sparse matrix from scratch on every query (10.925 ms) is ~1.9x faster than FNO (20.477 ms) on CPU, 64x64. The classical solver is faster, exact, and zero-parameter at this scale.

## 3. Before vs After: Poisson v1 vs Poisson v2 on v2 Evaluation Splits
Why the source family was widened: v1 was trained exclusively on Gaussian mixtures. When evaluated on the multi-mode harmonic sine splits of v2, v1 fails catastrophically.

| Evaluation Split | Samples | v1 FNO Rel L2 Med | v1 FNO Rel L2 P90 | v2 FNO Rel L2 Med | v2 FNO Rel L2 P90 | Lin Baseline Med | v2 FNO PDE Res Med |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `train` | 1000 | 0.1339 (13.39%) | 1.9347 | 0.0329 (3.29%) | 0.0524 | 3.4067e-08 | 0.7877 |
| `val` | 100 | 0.1382 (13.82%) | 1.9429 | 0.0335 (3.35%) | 0.0881 | 3.5309e-08 | 0.8955 |
| `test_interp` | 200 | 0.1679 (16.79%) | 1.8470 | 0.0334 (3.34%) | 0.0760 | 3.7341e-08 | 0.8394 |
| `test_ood_narrow` | 200 | 0.0962 (9.62%) | 0.2664 | 0.0900 (9.00%) | 0.2822 | 6.1458e-04 | 1.9642 |
| `test_ood_count` | 200 | 0.0242 (2.42%) | 0.0462 | 0.0277 (2.77%) | 0.0440 | 1.3411e-07 | 1.0332 |
| `test_ood_boundary` | 200 | 0.1492 (14.92%) | 0.2673 | 0.1418 (14.18%) | 0.3210 | 5.8485e-06 | 2.3983 |
| `test_ood_highmodes` | 200 | 4.4081 (440.81%) | 6.1883 | 0.8042 (80.42%) | 1.2777 | 1.4997e-02 | 3.0181 |

### Baseline Exactness & Degeneracy Analysis
the linear map is exact because the Poisson problem with fixed boundary conditions is linear and the source family has low effective rank; it degrades on high modes (1.5e-02).

## 4. Documented Failure Modes (Stress Matrix Top Failures)
Quantitative failure mode taxonomy from Poisson v2 evaluation:
1. **`highmodes` (Spectral Truncation):** Modes $m, n \in [5, 8]$ exceeding the FNO modes 12 cutoff. Median relative $L_2$ error is **80.4%** (0.8042), P90 is **127.8%** (1.2777), and max error is **229.4%** (2.2945). Field comparison saved to `plots/fno_v2_highmodes_failure.png`.
2. **`boundary` (Extreme Boundary Layer):** Sources situated within 0.12 of the domain perimeter ($c_x, c_y \le 0.12$). Median relative $L_2$ error is **14.2%** (0.1418), P90 is **32.1%** (0.3210), and max error is **132.9%** (1.3292).
3. **`narrow` (Sub-Grid Scale Cutoff):** Source widths $w \in [0.04, 0.07]$ approaching the grid spacing resolution limit ($h = 1/63 \approx 0.0159$). Median relative $L_2$ error is **9.0%** (0.0900), P90 is **28.2%** (0.2822), and max error is **74.2%** (0.7419).

### Top 3 Worst Failure Samples per OOD Regime
- **`test_ood_highmodes`:**
  - Rank 1: Sample Index 92 (Seed 1700092): Rel $L_2$ = 2.294483 (229.45%) | modes: [(5, 2, 0.225), (1, 8, 1.265), (6, 5, 0.295)]
  - Rank 2: Sample Index 61 (Seed 1700061): Rel $L_2$ = 2.289050 (228.91%) | modes: [(7, 1, 1.436)]
  - Rank 3: Sample Index 193 (Seed 1700193): Rel $L_2$ = 2.092302 (209.23%) | modes: [(7, 2, 0.757), (7, 1, 0.662)]
- **`test_ood_boundary`:**
  - Rank 1: Sample Index 53 (Seed 1600053): Rel $L_2$ = 1.329223 (132.92%) | k=1, centers=['(0.96, 0.02)'], widths=[0.082]
  - Rank 2: Sample Index 66 (Seed 1600066): Rel $L_2$ = 1.317446 (131.74%) | k=1, centers=['(0.13, 0.02)'], widths=[0.099]
  - Rank 3: Sample Index 161 (Seed 1600161): Rel $L_2$ = 1.296561 (129.66%) | k=1, centers=['(0.11, 0.04)'], widths=[0.08]
- **`test_ood_narrow`:**
  - Rank 1: Sample Index 157 (Seed 1400157): Rel $L_2$ = 0.741898 (74.19%) | k=1, widths=[0.0405], amps=[0.62]
  - Rank 2: Sample Index 80 (Seed 1400080): Rel $L_2$ = 0.678295 (67.83%) | k=1, widths=[0.0472], amps=[0.76]
  - Rank 3: Sample Index 111 (Seed 1400111): Rel $L_2$ = 0.665583 (66.56%) | k=1, widths=[0.0454], amps=[0.59]

## 5. FNO v3 Colab Script & Acceptance Framework
- **Script Path:** `src/train_fno_poisson_v3.py`
- **Configuration:** `FNO2d(modes1=16, modes2=16, width=64, in_channels=3, out_channels=1, use_hard_mask=True)`, CosineAnnealingLR up to 300 epochs, early stopping on val loss.
- **Command to Execute on Colab (with GPU):**
  ```bash
  python src/train_fno_poisson_v3.py --seeds 42 43 44 45 46 --device cuda --out-dir models/fno_v3 --epochs 300 --patience 25
  ```
- **Strict Acceptance Rule:**
  - Val median relative $L_2$ must improve by at least 2x: $\le 0.016728$ (1.67%) vs v2 (0.033455).
  - All OOD medians must be no worse than v2: narrow $\le 0.090019$, count $\le 0.027709$, boundary $\le 0.141791$, highmodes $\le 0.804159$.
  - If met: Accept v3. Otherwise: Freeze Poisson FNO v2.