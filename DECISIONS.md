# Architectural Decisions & Design Rationale

This document records the foundational architectural decisions made across the Digital Twin project, including options explored, the selected approach, technical justification, and empirical verification artifacts. Every reason and number is traceable to active codebase files and stored audit reports.

---

### Decision 1: Forward Neural Surrogate Architecture (Heat Equation)
- **Options Tried:**
  1. Pointwise parametric Physics-Informed Neural Network (PINN) trained with soft boundary and PDE residual losses.
  2. Fourier Neural Operator (FNO-2D) mapping parameter $\alpha$ and coordinate grids directly to solution fields.
- **Option Selected:** Fourier Neural Operator (FNO-2D) for digital twin surrogate; Bounded PINN (Exp D) retained as an alternative benchmark baseline.
- **Why:** FNO evaluates full 2D spatiotemporal fields $[0, 1] \times [0, 1]$ in a single forward pass, eliminating pointwise $(x, t)$ MLP query loops.
- **Not verified:** Pointwise batch latency multiplier and aggregate relative $L_2$ error ratio on interpolation splits are not stored in a summary audit table (qualitative rollout comparison visualized in `plots/full_rollout_abs_error_comparison.png`).
- **Status:** **Decided by evidence**
- **Evidence File:** `plots/full_rollout_abs_error_comparison.png`, `src/eval_final_all.py`, `src/models/fno2d.py`, `src/models/pinn.py`.

---

### Decision 2: Boundary & Initial Condition Enforcement (Ablation Series Exp A–D)
- **Options Tried:**
  1. *Baseline:* Unconstrained neural network with penalty weights in loss objective.
  2. *Exp A:* Soft-penalty PINN with tuning of PDE vs BC loss balancing.
  3. *Exp B:* Spatial boundary reparametrization $u(x, t) = \sin(\pi x) + x(1-x) N(x, t)$.
  4. *Exp C:* Spatial boundary reparametrization on FNO Fourier modes.
  5. *Exp D:* Bounded temporal and spatial reparametrization $u(x, t) = \sin(\pi x) + x(1-x)(1 - e^{-5t}) N(x, t)$.
- **Option Selected:** Exp D (Bounded Reparametrization).
- **Why:** By mathematical construction, at $t = 0$ the temporal factor $(1 - e^0) = 0$, enforcing $u(x, 0) = \sin(\pi x)$ (exact initial conditions), while at boundaries $x \in \{0, 1\}$ the factor $x(1 - x) = 0$ and $\sin(0) = \sin(\pi) = 0$, enforcing $u(0, t) = u(1, t) = 0$ for all $t \ge 0$.
- **Not verified:** Aggregate numerical $t=0$ MAE across the full OOD test split is plotted in `plots/t0_error_experiments.png` rather than stored in a tabular text file.
- **Status:** **Decided by evidence**
- **Evidence File:** `src/eval_final_all.py` (lines 44–46), `src/train_expD_pinn.py`, `src/train_expD_fno.py`, `experiments/diagnostics_exp.py`, `plots/t0_error_experiments.png`.

---

### Decision 3: Inverse Parameter Estimation Strategy & Mode 1 Baseline
- **Options Tried:**
  1. *Mode 1:* Direct backpropagation through frozen PINN forward surrogate.
  2. *Mode 2:* Classical Crank-Nicolson finite-difference solver with spline interpolation and L-BFGS-B optimization.
  3. *Mode 3:* Autograd through precomputed FNO surrogate with spline interpolation.
  4. *Mode 3+ (Hybrid Ablation):* Two-stage pipeline using Mode 3 initial estimate followed by Crank-Nicolson Solver Polish.
- **Option Selected:** Mode 2 as gold standard; Mode 3 for rapid real-time inversion; Mode 3+ (Solver Polish) for deployable twins. Mode 1 is kept as a baseline, but not recommended for deployment.
- **Why:**
  - *Mode 1 Performance:* In-range ($\alpha \in \{0.02, 0.1\}$), Mode 1 matches or beats Mode 2 in 6 of 8 cells with median relative error 0.0404–0.0737 (error ratios 0.48x–0.98x; the 0.48x cell reflects inductive shrinkage toward typical values, spread/CRB = 0.63). However, out-of-range at $\alpha = 2.5$, Mode 1 degrades severely to 16.8%–28.0% error (median relative error 0.2199), which is $3.28\times\text{--}20.19\times$ worse than the classical solver (Mode 2 solver error 0.8%–8.6%). Furthermore, the classical solver is $\sim 4\times$ faster per single fit ($\sim 1.69$ ms vs $\sim 7.03$ ms for Mode 1 PINN surrogate, median wall time ratio 4.06x). (See `data/audits/audit_pinn_report.txt` Sections 3 & 4, `data/results/mode1_pinn_summary.csv`).
  - *Mode 2 & Mode 3 Performance:* Mode 2 achieves mean single fit time of 1.85 ms with mean Wald coverage of 93.6% (16 of 120 cells under 90%). Mode 3 delivers 0.67 ms mean single fit time with near-solver accuracy (error ratio vs Mode 2 at $\sigma=0.05, \alpha \ge 0.02$ is median 1.020; mean coverage 88.2%). Mode 3+ solver polish eliminates FNO boundary bias, achieving 94.0% coverage (8 of 90 cells under 90%) and median $|diff|/error$ of 0.0002 vs standalone Mode 2 (fit time 137.12 ms). (See `data/audits/audit_report.txt` Sections 3, 4, 5, 6).
- **Status:** **Kept as baseline, not recommended for deployment** (Mode 1); **Decided by evidence** (Modes 2, 3, 3+).
- **Evidence File:** `data/results/mode1_pinn_summary.csv`, `data/audits/audit_pinn_report.txt` (Sections 3 & 4), `data/audits/audit_report.txt` (Sections 1, 3, 4, 5, 6), `data/results/mode2_pipeline_results_v2.csv`, `data/results/mode3_pipeline_results_v2.csv`, `data/results/mode3plus_hybrid_results.csv`.

---

### Decision 4: Sensor Placement Strategy (Task A)
- **Options Tried:**
  1. *Log-spaced temporal placement* across $t \in [0, 1]$ (reference static heuristic).
  2. *Uniform temporal placement* across $t \in [0, 1]$.
  3. *Early-heavy temporal placement*.
  4. *Late-heavy temporal placement*.
  5. *Information-weighted temporal placement* (oracle alpha).
  6. *All-at-t-star temporal placement* (oracle alpha).
  7. *Two-stage deployable adaptive placement* (preliminary probe + Fisher-information-weighted clustering).
- **Option Selected:** Two-stage deployable adaptive placement as recommended deployment strategy, evaluated against log-spaced as the reference static heuristic and information-weighted as the oracle upper bound.
- **Why:**
  - *Overall Performance (12 cells):* Log-spaced static placement achieves median relative error 0.0673 (median CRB_rel = 0.0967, spread/CRB = 1.01). The two-stage deployable design achieves median relative error 0.0474 (median CRB_rel = 0.0669, spread/CRB = 1.02), yielding a 29.6% error reduction over log-spaced ($(0.0673 - 0.0474)/0.0673 = 29.6\%$). Information-weighted oracle placement achieves 0.0414 (median CRB_rel = 0.0596), and all-at-t-star oracle achieves 0.0362. (See `data/audits/audit_sensor_placement.txt` Section 3).
  - *Primary Cell Comparison ($N=10, \sigma=0.01$):* Two-stage adaptive design achieves consistent $+31.0\%$ to $+34.7\%$ error reductions over log-spaced reference:
    - $\alpha = 0.005$: log-spaced 0.0984 $\to$ two-stage 0.0642 (+34.7% gain; oracle info-wt 0.0546; all-at-t* 0.0427).
    - $\alpha = 0.100$: log-spaced 0.0122 $\to$ two-stage 0.0082 (+33.2% gain; oracle info-wt 0.0058; all-at-t* 0.0052).
    - $\alpha = 2.500$: log-spaced 0.0112 $\to$ two-stage 0.0077 (+31.0% gain; oracle info-wt 0.0068; all-at-t* 0.0054). (See `data/audits/audit_sensor_placement.txt` Section 4).
  - *Uniform Design Failure Mode:* At fast diffusion decay ($\alpha = 2.5, N=10, \sigma=0.01$), uniform placement error degrades to 0.0280 (CRB_rel = 0.0405) compared to 0.0112 for log-spaced and 0.0077 for two-stage. (See `data/audits/audit_sensor_placement.txt` Section 7).
  - *Timing:* Static single fit time is 0.301 ms; two-stage adaptive single fit time is 1.229 ms (includes 2 fits + adaptive design computation). (See `data/audits/audit_sensor_placement.txt` Section 6).
- **Status:** **Decided by evidence**
- **Evidence File:** `data/results/sensor_placement_summary.csv`, `data/audits/audit_sensor_placement.txt` (Sections 3, 4, 5, 6, 7).

---

### Decision 5: Anomaly Cascade Order, Fault Consolidation & Change-Point Estimation
- **Options Tried:**
  1. *C-First Cascade:* Testing physical change-points (Class C) before sensor faults (Class F).
  2. *stuck_last_good:* Evaluated as a separate fault type from `stuck_const`.
  3. *Unanchored Joint-Estimation GLR Detector:* Estimating $\alpha_0$ and jump factor $m$ simultaneously from the jump window under test.
  4. *Oracle-Grid GLR Testing:* Evaluating GLR only at synthetic training grid times ($t_c \in \{0.2, 0.4, 0.6, 0.8\}$).
- **Option Selected:** Model-selection cascade (fit both F and C hypotheses, choose lower BIC) with baseline-informed parameter anchoring, evaluated across off-grid change-points ($t_c \in \{0.15, 0.35, 0.70\}$, $m \in \{0.7, 1.5, 3.0\}$).
- **Why:**
  - *C-First Cascade:* On the dev set, naive C-first testing caused Class F recall to collapse to 32.1% with 57.1% of faulty episodes falsely absorbed into Class C ($F \to C = 57.1\%$), while healthy false alarm rate on H rose to 8.6%. The fix is a model-selection cascade (fit both F and C, choose lower BIC), which restores Class F recall to 79.7%, slashes $F \to C$ leakage to 5.2%, and reduces healthy FAR on H to 3.8% (and FAR on A to 1.6%). (See `data/audits/audit_anomaly.txt` Section 3 lines 76–101).
  - *stuck_last_good Sensor Fault:* Dropped as a separate fault type because it duplicated `stuck_const` (identical frozen sensor reading behavior). Consolidated into a single authentic stuck sensor type (sensor stuck at mid-range constant 0.5000), evaluated across 80 episodes per primary cell (800 Class F episodes total across the factorial design). (See `data/audits/audit_anomaly.txt` Section 4 lines 140–145).
  - *Unanchored GLR Detector:* At high noise ($\sigma = 0.05$), estimating baseline diffusion $\alpha_0$ simultaneously from the same window containing the jump causes nuisance-parameter absorption (null fit shifts toward $\alpha_1$). On the dev set at $\sigma = 0.05$:
    - For $N=10$: Unanchored detector recall is 12.5%, Semi-Oracle power is 36.7%, and Baseline-Informed recall reaches 62.1% (+49.6% gain from baseline anchoring; Oracle LRT power is 75.6%).
    - For $N=20$: Unanchored detector recall is 36.7%, Semi-Oracle power is 57.1%, and Baseline-Informed recall reaches 69.6% (+32.9% gain from baseline anchoring; Oracle LRT power is 85.5%). (See `data/audits/audit_anomaly.txt` Section 3 lines 110–125).
    - Fresh test set recall for baseline-informed cascade: $N=10, \sigma=0.01 \to 94.0\%$ (Oracle Power 99.7%); $N=10, \sigma=0.05 \to 51.0\%$ (Oracle Power 74.1%); $N=20, \sigma=0.01 \to 92.0\%$ (Oracle Power 99.9%); $N=20, \sigma=0.05 \to 59.0\%$ (Oracle Power 83.1%). (See `data/audits/audit_anomaly.txt` Section 5 lines 180–201).
  - *Oracle-Grid GLR Testing:* Continuous 2D GLR evaluated on off-grid change-points ($t_c \in \{0.15, 0.35, 0.70\}$, $m \in \{0.7, 1.5, 3.0\}$) outperforms the rigid BIC tree across all 4 primary cells without grid-matching bias: $N=10, \sigma=0.01 \to +11.1\%$ delta; $N=10, \sigma=0.05 \to +15.0\%$ delta; $N=20, \sigma=0.01 \to +8.3\%$ delta; $N=20, \sigma=0.05 \to +16.1\%$ delta. (See `src/study_anomaly.py` lines 638–640, `data/audits/audit_anomaly.txt` Section 6 lines 203–218).
- **Status:** **Decided by evidence**
- **Evidence File:** `data/audits/audit_anomaly.txt` (Sections 3, 4, 5, 6), `data/results/anomaly_summary.csv`, `data/raw/anomaly_raw.csv`, `src/study_anomaly.py`.

---

### Decision 6: 2D Poisson Operator Formulation & Baseline Honesty (v1 vs v2)
- **Options Tried:**
  1. *Poisson v1:* FNO-2D trained with hard zero-boundary mask on pure Gaussian mixture sources (`sample_gaussian_source`), 15 epochs, relative $L_2$ loss only, overlapping seeds with heat datasets.
  2. *Poisson v2:* FNO-2D trained with hard zero-boundary mask on a 50/50 mixture of Gaussian and 2D sine mode sources (`sample_sine_mode_source`), up to 150 epochs, combined $L_2 + \beta_{H1} H^1$ Sobolev loss ($\beta_{H1} = 0.1$), dedicated highmodes split, strictly disjoint seeds (100000..600199).
  3. *Linear Ridge Regression Operator Baseline:* Dual linear operator ($u = G f$).
  4. *Classical Sparse Direct Factorization:* Scipy sparse LU solver (`scipy.sparse.linalg.splu`).
- **Option Selected:** Poisson v2 with full baseline honesty disclosures.
- **Why:**
  - *Boundary Constraint Verification:* Both v1 and v2 used hard zero-boundary masking (`use_hard_mask=True` in `archive/superseded/train_fno_poisson.py` line 31 and `src/train_fno_poisson_v2.py`). There was no boundary constraint omission in v1.
  - *True Differences between v1 and v2:*
    1. *Source Family:* v1 trained exclusively on Gaussian mixtures (`sample_gaussian_source`); v2 trained on a 50/50 mixture of Gaussian mixtures and 2D harmonic sine modes (`sample_sine_mode_source` where $f(x, y) = \sum_k a_k (m_k^2 + n_k^2) \pi^2 \sin(m_k \pi x) \sin(n_k \pi y)$ with $m, n \in \{1..4\}$).
    2. *Splits & Seeds:* v1 used 6 splits with seed overlap against earlier heat datasets (seeds 100000..200099); v2 introduced a dedicated 7th split `test_ood_highmodes` ($m, n \in \{5..8\}$) and strictly disjoint seeds across all splits (100000..600199).
    3. *Loss Formulation & Epochs:* v1 trained for a fixed 15 epochs using relative $L_2$ loss; v2 trained for up to 150 epochs using combined $L_2 + \beta_{H1} H^1$ Sobolev semi-norm loss ($\beta_{H1} = 0.1$) with early stopping (patience 15) and CosineAnnealing.
    4. *Timing Honesty Disclosures:* CPU timing benchmarks reveal that prefactorized classical sparse LU on CPU takes 0.53 ms, whereas FNO-2D takes 23.3 ms on CPU ($44\times$ slower on CPU single-eval). This proves that neural operators do not provide single-solve CPU acceleration over classical factorized solvers, but provide value in parametric GPU batch inference. (See `data/results/timing_honesty.json`, `data/audits/audit_poisson.txt` Section 6).
- **Status:** **Decided by evidence**
- **Evidence File:** `archive/superseded/train_fno_poisson.py` (lines 14, 31, 52), `src/train_fno_poisson_v2.py` (lines 36–58), `archive/superseded/generate_poisson_dataset.py`, `src/data/generate_poisson_dataset_v2.py`, `data/results/poisson_v2_benchmark_table.csv`, `data/results/timing_honesty.json`, `data/audits/audit_poisson.txt` (Sections 1–7).
