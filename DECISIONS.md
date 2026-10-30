# Architectural Decisions & Design Rationale

This document records the foundational architectural decisions made across the Digital Twin project, including options explored, the selected approach, technical justification, and empirical verification artifacts. Every reason and number is traceable to active codebase files and stored audit reports.

---

### Decision 1: Forward Neural Surrogate Architecture (Heat Equation)
- **Options Tried:**
  1. *Parametric Physics-Informed Neural Network (PINN):* Evaluated in unconstrained base form (`pinn_base`) and bounded reparametrized form (`pinn_expD`).
  2. *Fourier Neural Operator (FNO-2D):* Evaluated in unconstrained base form (`fno_base`) and bounded reparametrized form (`fno_expD`).
  3. *Plain Data-Only Network (`mlp_data_only`):* 4-layer MLP with identical width/depth to the PINN, trained purely on observed solution fields via MSE regression without physics loss (`src/train_data_only_mlp.py`).
  4. *Classical Crank-Nicolson Solver (`solver_cn`):* Deterministic numerical reference solver (`src/inverse_mode2.py`).
  5. *Persistence (Trivial Baseline):* Static initial condition persistence baseline $u(x, t) = \sin(\pi x)$ (`src/data/generate_dataset.py`).
- **Option Selected:** Both neural models are retained for distinct pipeline roles: Fourier Neural Operator (`fno_base`, unmasked) is selected for Mode 3 fast grid precomputation, real-time spline inversion, and high-precision forward simulation; Bounded PINN (`pinn_expD`) is selected for Mode 1 direct parameter autograd; Classical Crank-Nicolson is selected as the Mode 2 ground-truth numerical standard.
- **Why:**
  - *Empirical Accuracy from `data/results/experiments_summary.csv`:* Neural surrogate trade-off between FNO Base and Reparametrized variants shows that hard initial condition enforcement (Exp C/D) delivers the lowest in-range errors, while unconstrained FNO Base delivers the best out-of-range extrapolation robustness:
    - *Interpolation:* `fno_expC` achieves median relative $L_2$ error of **0.23%** (0.00228, P90: 0.01710) and `fno_expD` achieves **0.31%** (0.00306, P90: 0.01043), outperforming unconstrained `fno_base` at **0.45%** (0.00448, P90: 0.00582), `pinn_expD` at **0.88%** (0.00882, P90: 0.01303), `mlp_data_only` at **2.96%** (0.02960, P90: 0.12895), and persistence at **68.65%** (0.68651).
    - *Low-$\alpha$ OOD Extrapolation ($\alpha \in [0.003, 0.008]$):* `fno_expD` achieves **0.28%** (0.00280, P90: 0.00498) and `fno_base` achieves **0.46%** (0.00455, P90: 0.00561), whereas `fno_expC` achieves **0.59%** (0.00588, P90: 0.01095), `pinn_expD` degrades to **4.08%** (0.04084, P90: 0.05680), `mlp_data_only` to **5.23%** (0.05226), and persistence to **3.20%**.
    - *High-$\alpha$ OOD Extrapolation ($\alpha \in [1.5, 3.0]$):* Out of range, `fno_base` is substantially more robust, achieving **12.8%** (0.12772, P90: 0.20130). In contrast, the rigid boundary envelopes in `fno_expD` and `fno_expC` degrade to **34.6%** (0.34647, P90: 0.53843) and **42.9%** (0.42934, P90: 0.75196) respectively. However, both FNO variants vastly outperform PINNs out of range (`pinn_expD` degrades to **65.6%** [0.65592], `pinn_base` to **112.3%**, `mlp_data_only` to **57.4%**, and persistence to **580.5%**). Classical Crank-Nicolson solver maintains **0.24%** (0.00237).
  - *Operational Rationale for Pipeline Assignment:* Each surrogate is selected according to its distinct architectural role:
    1. *Mode 3 uses FNO (`fno_base`):* Mode 3 relies on FNO for its superior global field accuracy (0.45% in-distribution, 12.8% OOD) and batch tensor evaluation speed (0.67 ms single fit time after 2D field grid precomputation). FNO computes the complete 2D spatio-temporal solution field $[0, 1] \times [0, 1]$ in a single forward pass, eliminating pointwise query loops over $(x, t)$ coordinates. In the sensor observation window ($t \in [0.01, 1.0]$, $x \in [0.2, 0.8]$), FNO achieves 0.00239 MAE, enabling Mode 3 to match the Crank-Nicolson solver within a median parameter error ratio of 1.020.
    2. *Mode 1 uses PINN (`pinn_expD`):* Mode 1 performs inverse parameter estimation by directly differentiating sensor residuals through a frozen neural surrogate to $\alpha$ via autograd ($d\mathcal{L}/d\alpha$). The PINN provides a continuously differentiable analytical function $u_\theta(x, t, \alpha)$ that enables direct backward passes without requiring spatial grid meshing or discrete differentiation.
- **Status:** **Decided; evidence: data/results/experiments_summary.csv**
- **Evidence File:** `data/results/experiments_summary.csv`, `src/eval_final_all.py`, `src/models/fno2d.py`, `src/models/pinn.py`, `src/train_data_only_mlp.py`, `src/run_definitive_pipeline.py`.

---

### Decision 2: Boundary & Initial Condition Enforcement (Ablation Series Exp A–D)
- **Options Tried:**
  1. *Baseline:* Soft-penalty PINN (`pinn_base`) / unconstrained FNO (`fno_base`) with loss terms penalizing boundary/initial condition violations.
  2. *Exp A (Loss Weighting Axis):* Soft-penalty PINN with normalized PDE residual loss scaling $f = (u_t - \alpha u_{xx}) / \alpha$ (`experiments/train_pinn_expA.py`).
  3. *Exp B (Hard Spatiotemporal Reparametrization Axis):* PINN reparametrized with exact initial condition and linear temporal enforcement: $u(x, t) = \sin(\pi x) + x(1-x) \cdot t \cdot N(x, t)$ (`experiments/train_pinn_expB.py`).
  4. *Exp C (FNO Hard Reparametrization Axis):* FNO reparametrized with exact initial condition and linear temporal enforcement on operator output: $u(x, t) = \sin(\pi x) + x(1-x) \cdot t \cdot N(x, t)$ (`experiments/train_expC.py`).
  5. *Exp D (Bounded Reparametrization Axis):* PINN and FNO reparametrized with bounded exponential temporal enforcement: $u(x, t) = \sin(\pi x) + x(1-x)(1 - e^{-5t}) N(x, t)$ (`src/train_expD_pinn.py`, `src/train_expD_fno.py`).
- **Option Selected:** Exp D (Bounded Reparametrization) for PINN (`models/pinn_expD.pt`); Base unmasked FNO (`models/fno2d_heat.pt`) for Mode 3 production pipeline, with Exp D (`models/fno2d_expD.pt`) retained as an exact boundary enforcement baseline.
- **Why:**
  - *Origin of Exact-IC Motivation:* The historical large $t=0$ error that originally motivated the exact-IC reparametrization came entirely from the erroneous boundary mask zeroing the time rows (committed diagnostic plots showed FNO base $t=0$ error artificially clamped at **0.62**; whereas unmasked base FNO achieves $t=0$ error of $\mathbf{\sim 0.0021}$).
  - *PINN Surrogate Selection:* Exp D is kept for the PINN surrogate (`models/pinn_expD.pt`) because unconstrained/soft-penalty PINNs suffer substantial learned boundary errors (soft-IC PINN $t=0$ relative error ranges from **1.4% to 22.0%**, whereas Exp D enforces exact initial and boundary conditions by algebraic construction with median relative $L_2$ error 0.00882 and tight tail P90 0.01303).
  - *FNO Surrogate Selection (Extrapolation vs In-Range Accuracy):* For the FNO, base (unmasked) is selected as the definitive pipeline model because it extrapolates much better to high diffusion rates (**12.8%** at high $\alpha = 2.5$ vs **34.6%** for Exp D and **42.9%** for Exp C). Exp C and Exp D are only slightly better in-range (**0.228%** for Exp C and **0.306%** for Exp D vs **0.448%** for base FNO), meaning the slight in-range gain of reparametrization is heavily outweighed by severe OOD extrapolation breakdown.
  - *FNO Training Specifications, Budgets & Historical Mask State:*
    | Model | Training Samples | Epochs | Batch Size | Optimizer / LR Schedule | Dataset Seed | Training-Time Mask State |
    | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
    | `fno_base` | 1,000 | 100 | 20 (50 steps/epoch) | Adam ($10^{-3}$, decay $10^{-4}$), StepLR(50, 0.5) | 42 | unknown (checkpoint has no flag) |
    | `fno_expC` | 1,000 | 100 | 20 (50 steps/epoch) | Adam ($10^{-3}$, decay $10^{-4}$), StepLR(50, 0.5) | 42 | pre-cleanup default = masked |
    | `fno_expD` | 1,000 | 100 | 20 (50 steps/epoch) | Adam ($10^{-3}$, decay $10^{-4}$), StepLR(50, 0.5) | 42 | pre-cleanup default = masked |

    *Note on Mask State & Validation:* At pre-cleanup training time (`git show pre-cleanup:src/train.py`, `src/train_expC.py`, `src/train_expD_fno.py`), `FNO2d` defaulted to `use_hard_mask=True`. While `fno_base` saved no flag in its checkpoint dictionary (mask state strictly unknown at training time), Exp C and Exp D inherited the masked default. Crucially, all model weights have been validated at unmasked inference (`use_hard_mask=False`) and are verified by unit regression tests (`tests/test_fno_mask.py` and `tests/test_heat_1d.py`). All three share the identical training budget of 1,000 training trajectories from `data/datasets/train.npz` (evaluated on 200 validation trajectories from `val.npz`), 100 epochs, and 5,000 gradient updates. Historical notes referencing "80 samples" reflected early exploratory sub-splits or a 80/20 train/val percentage, whereas all finalized benchmark checkpoints were trained on the complete 1,000-sample dataset.
  - *Coverage of Brief Ablation Axes:*
    - *Covered:* **Loss weighting** is systematically tested in Exp A via normalized residual loss scaling $f = (u_t - \alpha u_{xx}) / \alpha$.
    - *Missing:* **Activation function** variation is missing (standard Tanh activation is fixed across all PINN architectures, and GeLU across all FNOs). **Collocation sampling strategies** are missing (uniform random interior sampling is kept constant across all runs without testing adaptive or residual-based resampling).
- **Status:** **Decided; evidence: data/results/experiments_summary.csv**
- **Evidence File:** `data/results/experiments_summary.csv`, `src/train_expD_pinn.py`, `src/train_expD_fno.py`, `experiments/train_pinn_expA.py`, `experiments/train_pinn_expB.py`, `experiments/train_expC.py`, `plots/t0_error_experiments.png`.

---

### Decision 3: Inverse Parameter Estimation Strategy & Mode 1 Baseline
- **Options Tried:**
  1. *Mode 1:* Direct backpropagation through frozen PINN forward surrogate.
  2. *Mode 2:* Classical Crank-Nicolson finite-difference solver evaluated via 1D CubicSpline in $\log_{10}(\alpha)$ with bounded Brent optimization.
  3. *Mode 3:* Precomputed FNO forward surrogate evaluated via 1D CubicSpline in $\log_{10}(\alpha)$ with bounded Brent optimization.
  4. *Mode 3+ (Hybrid Ablation):* Two-stage pipeline using Mode 3 initial estimate followed by bounded Brent search with live Crank-Nicolson solver polish.
- **Option Selected:** Mode 2 as gold standard; Mode 3 for rapid real-time inversion; Mode 3+ (Solver Polish) for deployable twins. Mode 1 is kept as a baseline, but not recommended for deployment.
- **Why:**
  - *Mode 1 Performance:* In-range ($\alpha \in \{0.02, 0.1\}$), Mode 1 matches or beats Mode 2 in 6 of 8 cells with median relative error 0.0404–0.0737 (error ratios 0.48x–0.98x; the 0.48x cell reflects inductive shrinkage toward typical values, spread/CRB = 0.63). However, out-of-range at $\alpha = 2.5$, Mode 1 degrades severely to 16.8%–28.0% error (median relative error 0.2199), which is $3.28\times\text{--}20.19\times$ worse than the classical solver (Mode 2 solver error 0.8%–8.6%). Furthermore, the classical solver is $\sim 4\times$ faster per single fit ($\sim 1.69$ ms vs $\sim 7.03$ ms for Mode 1 PINN surrogate, median wall time ratio 4.06x). (See `data/audits/audit_pinn_report.txt` Sections 3 & 4, `data/results/mode1_pinn_summary.csv`).
  - *Mode 2 & Mode 3 Performance:* In the production pipeline (`src/run_definitive_pipeline.py`), Mode 2 precomputes Crank-Nicolson solutions on a 350-point grid spanning $\log_{10}(\alpha) \in [-3.0, 1.0]$, evaluates sensor measurements via 1D `CubicSpline` over $\log_{10}(\alpha)$, and optimizes using scalar bounded Brent search (`scipy.optimize.minimize_scalar(..., bounds=(-3.0, 1.0), method='bounded')`). It achieves mean single fit time of 1.85 ms with mean Wald coverage of 93.6% (16 of 120 cells under 90%). Mode 3 precomputes FNO forward solutions on the same 350-point grid, evaluates via `CubicSpline` in $\log_{10}(\alpha)$, and optimizes via bounded Brent search. It delivers 0.67 ms mean single fit time with near-solver accuracy (error ratio vs Mode 2 at $\sigma=0.05, \alpha \ge 0.02$ is median 1.020; mean coverage 88.2%). (Note: autograd through FNO via L-BFGS-B was explored in `src/inverse_mode3.py`, but the production benchmark in `src/run_definitive_pipeline.py` uses precomputed spline evaluation). Mode 3+ solver polish takes the Mode 3 initial estimate $\hat{\alpha}_0$ and executes bounded 1D Brent search with live Crank-Nicolson solves within $\pm 0.3$ decades (`scipy.optimize.minimize_scalar(cn_objective, bounds=(la_0 - 0.3, la_0 + 0.3), method='bounded')`), achieving 94.0% coverage (8 of 90 cells under 90%) and median $|diff|/error$ of 0.0002 vs standalone Mode 2 (fit time 137.12 ms). (See `data/audits/audit_report.txt` Sections 3, 4, 5, 6, `src/run_hybrid_benchmark.py` lines 320–328).
- **Status:** **Kept as baseline, not recommended for deployment** (Mode 1); **Decided by evidence** (Modes 2, 3, 3+).
- **Evidence File:** `data/results/mode1_pinn_summary.csv`, `data/audits/audit_pinn_report.txt` (Sections 3 & 4), `data/audits/audit_report.txt` (Sections 1, 3, 4, 5, 6), `data/results/mode2_pipeline_results_v2.csv`, `data/results/mode3_pipeline_results_v2.csv`, `data/results/mode3plus_hybrid_results.csv`, `src/run_definitive_pipeline.py`, `src/run_hybrid_benchmark.py`.

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
  4. *Oracle-Grid GLR Testing:* Evaluating GLR only at synthetic training grid times ($t_c \in \{0.1, 0.25, 0.5\}$, $m \in \{0.5, 2.0\}$).
- **Option Selected:** Model-selection cascade (fit both F and C hypotheses, choose lower BIC) with baseline-informed parameter anchoring, evaluated across off-grid change-points ($t_c \in \{0.15, 0.35, 0.70\}$, $m \in \{0.7, 1.5, 3.0\}$).
- **Why:**
  - *C-First Cascade:* On the dev set, naive C-first testing caused Class F recall to collapse to 32.1% with 57.1% of faulty episodes falsely absorbed into Class C ($F \to C = 57.1\%$), while healthy false alarm rate on H rose to 8.6%. The fix is a model-selection cascade (fit both F and C, choose lower BIC), which restores Class F recall to 79.7%, slashes $F \to C$ leakage to 5.2%, and reduces healthy FAR on H to 3.8% (and FAR on A to 1.6%). (See `data/audits/audit_anomaly.txt` Section 3 lines 76–101).
  - *stuck_last_good Sensor Fault:* Dropped as a separate fault type because it duplicated `stuck_const` (identical frozen sensor reading behavior). Consolidated into a single authentic stuck sensor type (sensor stuck at mid-range constant 0.5000), evaluated across 80 episodes per primary cell (800 Class F episodes total across the factorial design). (See `data/audits/audit_anomaly.txt` Section 4 lines 140–145).
  - *Unanchored GLR Detector:* At high noise ($\sigma = 0.05$), estimating baseline diffusion $\alpha_0$ simultaneously from the same window containing the jump causes nuisance-parameter absorption (null fit shifts toward $\alpha_1$). On the dev set at $\sigma = 0.05$:
    - For $N=10$: Unanchored detector recall is 12.5%, Semi-Oracle power is 36.7%, and Baseline-Informed recall reaches 62.1% (+49.6% gain from baseline anchoring; Oracle LRT power is 75.6%).
    - For $N=20$: Unanchored detector recall is 36.7%, Semi-Oracle power is 57.1%, and Baseline-Informed recall reaches 69.6% (+32.9% gain from baseline anchoring; Oracle LRT power is 85.5%). (See `data/audits/audit_anomaly.txt` Section 3 lines 110–125).
    - Fresh test set recall for baseline-informed cascade: $N=10, \sigma=0.01 \to 94.0\%$ (Oracle Power 99.7%); $N=10, \sigma=0.05 \to 51.0\%$ (Oracle Power 74.1%); $N=20, \sigma=0.01 \to 92.0\%$ (Oracle Power 99.9%); $N=20, \sigma=0.05 \to 59.0\%$ (Oracle Power 83.1%). (See `data/audits/audit_anomaly.txt` Section 5 lines 180–201).
  - *Oracle-Grid GLR Testing:* Evaluating change-point detection on synthetic on-grid times ($t_c \in \{0.1, 0.25, 0.5\}$, $m \in \{0.5, 2.0\}$) gives an artificial grid-matching advantage. Continuous 2D GLR evaluated on off-grid change-points ($t_c \in \{0.15, 0.35, 0.70\}$, $m \in \{0.7, 1.5, 3.0\}$) proves the detector generalizes without grid-matching bias, outperforming the rigid BIC tree across all 4 primary cells: $N=10, \sigma=0.01 \to +11.1\%$ delta; $N=10, \sigma=0.05 \to +15.0\%$ delta; $N=20, \sigma=0.01 \to +8.3\%$ delta; $N=20, \sigma=0.05 \to +16.1\%$ delta. (See `src/study_anomaly.py` lines 483–484 & 638–641, `data/audits/audit_anomaly.txt` Section 6 lines 203–218).
  - *Healthy False Alarm Rate (FAR) Ceiling Non-Compliance:* On the fresh evaluation test set (3,200 episodes across 4 primary cells, `data/results/anomaly_frozen_final_tables.json` Table 1), overall healthy FAR is **6.5% [5.0, 8.4]**. It does **NOT** meet a 5.0% ceiling.
  - *Baseline Window Length Calibration and Operational Requirement:* The detector is calibrated with $k=20$ baseline readings (yielding 5.62% FAR [4.23, 7.44] on healthy controls). Under window truncations, $k=12$ gives 8.5% FAR [6.76, 10.64], and $k \le 5$ degrades severely to $>15\%$ FAR ($k=5 \to 15.88\%$ [13.51, 18.57], $k=3 \to 23.25\%$ [20.45, 26.30]; see `data/results/anomaly_baseline_robustness_new_fresh_summary.csv`). Therefore, minimum supported baseline = 20 readings (the service must warn or refuse below that).
- **Status:** **Decided by evidence**
- **Evidence File:** `data/audits/audit_anomaly.txt` (Sections 3, 4, 5, 6), `data/results/anomaly_summary.csv`, `data/raw/anomaly_raw.csv`, `src/study_anomaly.py`, `data/results/anomaly_frozen_final_tables.json`, `data/results/anomaly_baseline_robustness_new_fresh_summary.csv`.

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
    4. *Timing Honesty Disclosures:* At 64x64 resolution on CPU (`data/results/timing_honesty.json`), the classical sparse direct solver is vastly faster than FNO on CPU: 0.501 ms vs 20.477 ms single-query (40.9x faster), and 0.255 ms vs 5.590 ms batched (21.9x faster). Even rebuilding and re-factorizing the sparse matrix from scratch on every query (10.925 ms) is $\sim 1.9\times$ faster than FNO forward inference latency (CPU, 64x64). GPU inference not measured. (See `data/results/timing_honesty.json`, `data/audits/audit_poisson.txt` Section 6).
- **Status:** **Decided by evidence**
- **Evidence File:** `archive/superseded/train_fno_poisson.py` (lines 14, 31, 52), `src/train_fno_poisson_v2.py` (lines 36–58), `archive/superseded/generate_poisson_dataset.py`, `src/data/generate_poisson_dataset_v2.py`, `data/results/poisson_v2_benchmark_table.csv`, `data/results/timing_honesty.json`, `data/audits/audit_poisson.txt` (Sections 1–7).

---

### Decision 7: Poisson Round 2: v2 Frozen
- **Options Tried:**
  1. *Poisson v2 (Frozen Baseline):* FNO-2D (`modes1=12, modes2=12`, width 32, 4 layers, 1,188,353 complex/scalar tensor elements / 2,368,001 real float parameters; previously misstated as modes 16, ~466k params) trained on Poisson v2 dataset with $L_2 + 0.1 H^1$ loss.
  2. *Poisson v3 (Colab 5-Seed Retraining Study):* FNO-2D retrained across 5 seeds (42, 43, 44, 45, 46) on GPU (Tesla T4) with extended training budget (up to 300 epochs, patience 25, delta 1e-4) to test whether scaling training epochs and testing seed sensitivity unlocks $\ge 2\times$ error reduction on validation/interpolation and closes OOD failure modes.
- **Option Selected:** Poisson v2 frozen (`models/fno2d_poisson_v2.pt` retained as official final model; v3 rejected).
- **Why:**
  - *Pre-Registered Acceptance Rule:* Fixed strictly before launching the Colab v3 run: v3 is accepted if and only if (1) Validation median relative $L_2$ error achieves $\ge 2.0\times$ improvement over v2 ($v_2 / v_3 \ge 2.0$, requiring val median $\le 0.01673$), AND (2) all 4 OOD split medians (`test_ood_narrow`, `test_ood_count`, `test_ood_boundary`, `test_ood_highmodes`) are no worse than v2.
  - *Outcome & Rejection:*
    - *Validation/Interpolation Improvement:* The mean of medians across the 5 seeds achieved val median 0.02750 (improvement factor $0.03346 / 0.02750 = 1.216\times$) and interpolation median 0.02703 ($1.237\times$), falling well short of the $2.0\times$ pre-registered bar.
    - *OOD Generalization:* While the 4 OOD medians were on average better than v2 (narrow: 0.0792 vs 0.0900; count: 0.0221 vs 0.0277; boundary: 0.0834 vs 0.1418; highmodes: 0.5247 vs 0.8042), the failure to hit the required $2\times$ validation threshold led to strict rejection.
  - *Large Seed Spread (~6x–7x):* Model performance exhibits substantial seed sensitivity across identical training configurations:
    - On validation: min 0.00681, max 0.04119 ($\mathbf{6.05\times}$ spread).
    - On test interpolation: min 0.00631, max 0.04251 ($\mathbf{6.74\times}$ spread).
    - Selecting the single best seed (seed 46, which reached 0.0063 on interpolation) after inspecting test set outcomes would be post-hoc cherry-picking; evaluating across the full 5-seed cohort reflects true expected performance.
  - *Persistent High-Modes Generalization Failure:* High-frequency harmonic modes ($m, n \in \{5..8\}$) remain a severe failure mode across all seeds, with median relative errors between $37.3\%$ and $59.2\%$ (p90 error $62.3\%\text{--}101.1\%$, max error up to $171.5\%$). Because wavenumbers $5\text{--}8$ lie well inside the 12 retained Fourier modes (`modes1=12, modes2=12`; note heat 1D retained 16 modes), this is not a spectral truncation cutoff, but a fundamental out-of-distribution wavenumber generalization failure: the model was trained exclusively on low wavenumbers ($m, n \in \{1..4\}$) and fails to generalize to unseen higher frequencies despite extended training.
  - *Reproducibility Note on GPU Non-Determinism:* Re-running the identical 5 seeds on the GPU yielded different numbers (interp mean 0.0247 in an initial unrecorded run vs 0.0270 in the official recorded run; seed range 0.0061–0.0365 vs 0.0063–0.0425). Due to non-deterministic CUDA atomic operations and cuFFT execution kernels, GPU runs are not bit-reproducible; consequently, all conclusions are stated with seed spread rather than single-point estimates.
- **Status:** **Decided by evidence; v2 frozen, v3 rejected**
- **Evidence File:** `data/results/poisson_fno_v3/fno_v3_acceptance_report.json`, `data/results/poisson_fno_v3/fno_v3_manifest.json`, `data/results/poisson_fno_v3_per_seed.csv`, `data/results/poisson_fno_v3/split_analysis.json`, `data/results/poisson_fno_v3/dataset_checksums.json`.

---

### Decision 8: Heat FNO Multi-Seed Retraining Study & Frozen Checkpoint Retention
- **Options Tried:**
  1. *Frozen Baseline Checkpoint (`models/fno2d_heat.pt`):* Initial model with unmasked inference (`use_hard_mask=False`).
  2. *5-Seed Retraining Cohort (`data/results/heat_fno_seeds/`, seeds 42, 43, 44, 45, 46):* Evaluated on test interpolation, low-$\alpha$ OOD, high-$\alpha$ OOD, and deterministic Mode 3 $\sigma=0$ bias floors at $\alpha \in \{0.005, 0.100, 2.500\}$.
- **Option Selected:** Retain frozen `models/fno2d_heat.pt`. No retrained candidate replaces it.
- **Why:**
  - *Candidate Replacement Rule (Written AFTER Seed Results were Seen):* A replacement candidate must be no worse than the frozen baseline at **BOTH** the $\alpha = 0.005$ and $\alpha = 2.5$ deterministic bias floors (`data/results/heat_fno_seeds_summary.csv`):
    - At $\alpha = 0.005$, frozen bias floor relative error is **17.86%** (`0.178556`). Seed 42 degrades to **23.52%** (`0.235184`, worse than frozen).
    - At $\alpha = 2.500$, frozen bias floor relative error is **5.94%** (`0.059421`). Seed 43 degrades to **13.02%** (`0.130197`), Seed 44 degrades to **16.17%** (`0.161689`), Seed 45 degrades to **13.25%** (`0.132470`), and Seed 46 degrades to **11.31%** (`0.113087`), all substantially worse than frozen (up to $2.7\times$ higher error).
    - Consequently, **NOT A SINGLE SEED** satisfies the criterion of being no worse at both ends of the parameter range.
    - *Transparency Disclosure:* This replacement rule was written **AFTER** the seed results were seen (post-hoc selection criterion).
  - *Operational Deployment Domain for Mode 3 vs Mode 3+:*
    - Mode 3 alone is **not recommended** outside $\alpha \in [0.01, 1.0]$. At extreme diffusions ($\alpha = 0.005$ and $\alpha \ge 2.5$), neural surrogate extrapolation error creates persistent parameter estimation bias floors of 5.9% to 23.5% (`data/results/heat_fno_seeds_summary.csv` rows: frozen $\alpha=0.005 \to 0.178556$; seed 44 $\alpha=2.5 \to 0.161689$).
    - Inside $\alpha \in [0.01, 1.0]$ (specifically at $\alpha = 0.1$), all seeds achieve $< 1.2\%$ bias floor error (e.g. Seed 42 reaches 0.044%, Seed 44 reaches 0.27%, frozen reaches 1.17%).
    - For general deployment across wide parameter domains, **Mode 3+ (Hybrid with live Crank-Nicolson solver polish)** is the verified deployable mode, reducing surrogate bias floors and delivering 94.0% coverage across evaluated noise regimes with 8/90 cells < 90% (`data/results/mode3plus_hybrid_results.csv`, `data/results/heat_fno_seeds_summary.csv`). However, stress testing reveals that Mode 3+ fails identically to Mode 2 in Scenario 12 (extreme diffusivity outside the forward solver grid or information-limited regime where signal drops below noise floor).
- **Status:** **Decided by evidence; frozen fno2d_heat.pt retained**
- **Evidence File:** `data/results/heat_fno_seeds_summary.csv`, `data/results/heat_fno_seeds/heat_fno_seeds_stability_summary.json`, `data/results/heat_fno_seeds/metrics_heat_frozen.json`, `metrics_heat_seed*.json`.

---

### Decision 9: Physics-Informed Neural Network Single-Factor Ablation & Collocation Hypothesis (Task G)
- **Options Tried:**
  1. *Activation Function:* `tanh` (base) vs `GELU` vs `sin`.
  2. *Collocation Sampling:* `base` (uniform pseudorandom resampled every epoch) vs `fixed` (uniform pseudorandom fixed across all epochs) vs `sobol` (Sobol quasi-random low-discrepancy sequence) vs `lhs` (Latin Hypercube Sampling).
  3. *Loss Formulation:* `pure_pde` (base, $w_{\text{pde}}=1.0, w_{\text{data}}=0.0$) vs `data_equal` ($w_{\text{pde}}=1.0, w_{\text{data}}=1.0$) vs `data_heavy` ($w_{\text{pde}}=0.1, w_{\text{data}}=1.0$) vs `grad_norm` (adaptive gradient-norm balancing).
  4. *Optimizer:* `adam_lbfgs` (base, Adam 1000 epochs + L-BFGS 500 iterations) vs `adam_only` (Adam 1500 epochs).
- **Option Selected:** Retain frozen baseline `models/pinn_expD.pt` (`tanh`, `base` resampled collocation, `pure_pde`, `adam_lbfgs`) as pre-registered in `experiments/train_pinn_ablation.py`. No retrained candidate replaces the frozen baseline.
- **Why:**
  - *Pre-Registered Protocol:* To guard against post-hoc selection and test split cherry-picking, the study protocol explicitly pre-registered: "If an ablated variant achieves lower test error than the base config, findings are documented honestly in the report, but the frozen checkpoint `models/pinn_expD.pt` is RETAINED and NOT replaced."
  - *Empirical Findings (`data/results/pinn_ablation/pinn_ablation_summary.csv`):*
    - *Activation:* `gelu` achieves median interpolation relative $L_2$ error of 0.00609 and low-$\alpha$ OOD of 0.00324, outperforming `tanh` (0.00799 / 0.04258), while `sin` achieves 0.00753 / 0.04250.
    - *Collocation:* Static/structured collocation sampling achieves order-of-magnitude reductions in median relative $L_2$ error: `collocation_fixed` achieves 0.000438 on interpolation and 0.003406 on low-$\alpha$ OOD; `collocation_sobol` achieves 0.000411 / 0.002297; `collocation_lhs` achieves 0.000436 / 0.002920, all vastly outperforming dynamic resampling (`base`: 0.007987 / 0.042582).
    - *Loss Weighting:* Pure PDE residual loss remains competitive (0.007987) with data-assisted weighting (0.006396 for `data_equal`, 0.005945 for `data_heavy`, 0.004132 for `grad_norm`).
    - *Optimizer:* Adam + L-BFGS achieves comparable interpolation error (0.007987 vs 0.005103 for `adam_only`) while converging faster in wall-clock time (13.85 s vs 20.73 s).
  - *Collocation Explanation as an UNVERIFIED Hypothesis:*
    - In dynamic resampling (`base`), resampling collocation coordinates at every Adam epoch and L-BFGS step perturbs the loss landscape under the optimizer. In contrast, fixed static collocation presents a deterministic, static objective surface.
    - *UNVERIFIED Hypothesis:* It is hypothesized that fixed collocation coordinates allow the second-order L-BFGS quasi-Newton optimizer to construct stable, non-stochastic curvature history approximations and execute exact line searches down into narrow quadratic basins without stochastic gradient jitter, whereas dynamic coordinate resampling constantly shifts the loss landscape and disrupts quasi-Newton Hessian updates. This explanation remains an **UNVERIFIED hypothesis** and has not been conclusively proven through ablation of L-BFGS memory history or line-search step dynamics.
- **Status:** **Decided by evidence; pre-registered frozen checkpoint models/pinn_expD.pt retained**
- **Evidence File:** `experiments/train_pinn_ablation.py`, `data/results/pinn_ablation/pinn_ablation_summary.csv`, `tools/package_pinn_ablation_colab.py`, `run_pinn_ablation_colab.ipynb`.

---

### Decision 10: Digital Twin Service Policy: Frozen Models, Offline Training, and Direct Runtime (No Docker Build)
- **Options Tried:**
  1. *Online Retraining Service:* Allowing API clients to trigger neural surrogate retraining or fine-tuning dynamically inside HTTP request handlers.
  2. *Container-Only Deployment Requirement:* Enforcing mandatory Docker daemon and multi-stage container build for local execution and integration testing.
  3. *Production Service Architecture:* Deploying a FastAPI REST service (`service/app.py`) serving strictly frozen neural weights and precomputed surrogate splines trained offline, executing directly in a native Python environment with zero runtime retraining and without requiring a local Docker build.
- **Option Selected:** Frozen models, offline training, and direct native Python execution (Option 3). A production Dockerfile (`Dockerfile`, `.dockerignore`) is provided for containerized environments, but local execution and verification do NOT require Docker build.
- **Why:**
  - *Frozen Model Invariance & Latency Guarantees:* Online retraining in service request loops introduces non-deterministic model drift, memory exhaustion, CUDA/CPU thread contention, and unbounded latency spikes. Inverting PDE parameters via Mode 3 / Mode 3+ requires predictable, deterministic execution (Mode 3 fast surrogate fit: ~0.7 ms/fit; Mode 3+ CN polish nominal latency for default case with $N=10$ log-spaced sensors $t \in [0.01, 1.0]$, $x \in [0.2, 0.8]$, $\alpha=0.10, \sigma=0.01$: ~58.4 ms service endpoint / ~49.3 ms direct CN polish; 138.8 ms mean over all 135 cells incl. stiff OOD from `data/results/mode3plus_hybrid_results.csv`). For field generation at 101×201 resolution on host CPU, measured latencies are: classical numerical solver 7.3–18.6 ms (p50: 7.3 ms, p95: 18.0–18.6 ms) vs FNO neural operator surrogate 134–166 ms (p50: 134–144 ms, p95: 145–166 ms); in 2D Poisson, sparse LU solves in 0.50 ms vs FNO 20.5 ms. State plainly: FNO is NOT faster than the solver for field generation here; its value is the surrogate grid inside inversion (Mode 3 ~0.7 ms/fit). Serving strictly frozen checkpoints (`models/fno2d_heat.pt`, `models/fno2d_poisson_v2.pt`, `models/pinn_expD.pt`) guarantees bit-level reproducibility and predictable runtime behavior.
  - *Offline Training Segregation:* All neural operator and PINN training procedures (`src/train_fno_poisson_v2.py`, `src/train_expD_pinn.py`, `experiments/train_pinn_ablation.py`) are strictly decoupled into offline batch training scripts. The production service application (`service/app.py`) loads weights at startup via FastAPI `lifespan` handler and exposes inference-only routes (`/v1/estimate`, `/v1/diagnose`, `/v1/placement`, `/v1/field`, `/v1/poisson`).
  - *Direct Runtime vs Docker Build Policy:* The project environment operates on native Windows / Linux Python 3.10+ environments with direct `uvicorn service.app:app` execution. Requiring Docker build on local machines imposes heavy virtualization overhead, requires Hyper-V / WSL2 daemon setup, and slows down automated test execution (`tests/test_service.py`). While `Dockerfile` is provided for cloud and Kubernetes deployments, the system policy specifies that local test suites, verification runners (`evaluation.run_all`), and automated end-to-end evaluations run directly against native Python without Docker build dependencies.
- **Status:** **Decided by architecture and service design policy**
- **Evidence File:** `service/app.py`, `service/models.py`, `service/metrics.py`, `Dockerfile`, `.dockerignore`, `requirements-service.txt`, `tests/test_service.py`, `evaluation/run_all.py`.

---

### Decision 11: Real-World Unit Normalisation as a Backend Wrapper Layer
- **Options Tried:**
  1. *Retraining on Dimensional Scales:* Retraining neural operator surrogates (FNO, PINN) across continuous dimensional parameter spaces with variable physical lengths $L$, durations $T$, and arbitrary temperature scales.
  2. *Frontend Client-Side Normalisation:* Scaling sensor coordinates and readings in client-side JavaScript before sending JSON requests to the API.
  3. *Declarative Backend Normalisation Wrapper Layer:* Serving frozen dimensionless models as-is, wrapping endpoints (`/v1/estimate` and `/v1/diagnose`) with an affine space-time-temperature transformation layer that accepts optional physical parameters ($L$, $T$, $T_{\text{boundary}}$, $T_{\text{peak}}$, $\sigma$), validates physical consistency, normalizes to canonical dimensionless variables ($x_{\text{norm}} = x/L$, $t_{\text{norm}} = t/T$, $u = (T_{\text{reading}} - T_{\text{boundary}})/(T_{\text{peak}} - T_{\text{boundary}})$, $\sigma_u = \sigma / |T_{\text{peak}} - T_{\text{boundary}}|$), invokes the frozen numerical/neural pipeline, converts results back ($\alpha_{\text{real}} = \hat{\alpha} \cdot L^2/T$, scaling confidence bounds likewise), and echoes normalization constants and normalized alpha in the response.
- **Option Selected:** Declarative Backend Normalisation Wrapper Layer (Option 3). Frozen model weights (`models/`) and benchmark tables (`data/results/`) remain strictly bit-for-bit unchanged.
- **Why:**
  - *Mathematical Isomorphism of the Heat Equation:* The dimensional 1D unsteady heat conduction equation is $\frac{\partial T}{\partial t} = \alpha_{\text{real}} \frac{\partial^2 T}{\partial x^2}$ on $x \in [0, L], t \in [0, T]$ with boundary conditions $T(0, t) = T(L, t) = T_b$ and initial distribution $T(x, 0) = T_b + (T_p - T_b) u_0(x/L)$. Substituting dimensionless space $\tilde{x} = x/L$, dimensionless time $\tilde{t} = t/T$, and normalized temperature $u = (T - T_b)/(T_p - T_b)$ yields $\frac{\partial u}{\partial \tilde{t}} = \left(\alpha_{\text{real}} \frac{T}{L^2}\right) \frac{\partial^2 u}{\partial \tilde{x}^2} = \hat{\alpha} \frac{\partial^2 u}{\partial \tilde{x}^2}$. Because the linear parabolic PDE is scale-invariant, the dimensionless system is isomorphic to the canonical unit problem on $[0, 1] \times [0, 1]$. Retraining neural surrogates on dimensional data would introduce surrogate generalization errors and invalidate verified benchmark tables, whereas the wrapper layer preserves 100% of the verified benchmark accuracy (94.0% Wald coverage) with zero model drift.
  - *Never Deriving Constants from Readings:* Normalization constants must be explicitly provided by the user or client. The service strictly refuses to infer $L, T, T_b, T_p$ from sample extrema ($\min/\max$ of readings), as noise fluctuations, discrete sensor spacing, or boundary sensor absence would introduce systematic calibration bias into diffusivity estimation.
  - *Affine-Invariance & Unit Consistency:* Any affine transformation on temperature (e.g. Celsius to Fahrenheit: $T \to 1.8 T + 32$, $\sigma \to 1.8 \sigma$) cancels analytically in $u = (T - T_b)/(T_p - T_b)$ and $\sigma_u = \sigma / |T_p - T_b|$, guaranteeing identical dimensionless optimization objectives and identical normalized diffusivity estimates $\hat{\alpha}$.
  - *Clear Error Handling & Non-Silent Unit Validation:* Inputs are strictly checked: $T_p \neq T_b$ (rejects division by zero), positions $\in [0, L]$, times $\in [0, T]$. If normalized readings fall far outside $[-0.5, 1.5]$ (such as Kelvin readings mixed with Celsius boundary specifications), the backend emits a clear warning (`"These readings don't look like cooling from your stated start. Check units or values."`) and never silently converts or guesses unit conventions.
  - *Empirical Recovery & Preset Benchmark:*
    - Synthetic recovery tests across multiple physical configurations (including cooling and heating cases with $T_p < T_b$) prove exact recovery of $\alpha_{\text{real}}$ within 95% Wald confidence intervals.
    - Preset "Bar heated evenly, ends at room temperature" (constant initial condition $u_0(x) = 1.0$) was evaluated across 200 uncherry-picked random seeds prior to shipping: achieved **97.0% coverage** (194/200), **+0.063% mean relative bias**, and **0.924% median relative error**, confirming it meets production deployment standards.
- **Status:** **Decided by architecture and physics invariance; frozen models and benchmark tables unchanged.**
- **Evidence File:** `service/app.py`, `service/models.py`, `tests/test_service.py`, `scratch/test_preset_constant_u0.py`.

---

### Decision 12: Bar Profiles Reference Library (Storage, Security, and Single-Lab Operation)
- **Options Tried:**
  1. *Browser localStorage Only:* Storing references in client-side browser storage (thermalens-v13). Simple and zero backend state, but tied to an individual browser profile, fragile under browser cache clearing, and cannot be shared across laboratory workstations.
  2. *Relational Database with User Authentication:* Deploying PostgreSQL/SQLite with user accounts, sessions, and passwords. Heavily over-engineered for plant laboratory workbench use; introduces database migrations, schema overhead, connection pooling, and credential administration.
  3. *Server-Side Plain Files in `data/profiles/` (No Login, Single-Lab Workbench):* Storing profiles as paired plain files (`{id}.json` for metadata and setup constants, `{id}.csv` for sensor readings) on the local filesystem. Profile IDs are strictly server-generated UUIDv4 strings (display names are metadata only). Hard security constraints: max 50 profiles total, max 5,000 readings per profile, max 1 MB payload size, strict physical bounds ($x \in [0, L], t \in (0, T]$, finite numbers). Save-time validation checks reference runs against normal heat diffusion and autocorrelation, warning users on unclean baselines.
- **Option Selected:** Server-Side Plain Files in `data/profiles/` (Option 3).
- **Why:**
  - *Single-Lab Operational Model:* Designed for physical plant technicians and laboratory operators on a dedicated lab workstation or private local intranet. The service intentionally operates without user authentication or login; it is **NOT designed or intended for untrusted multi-tenant public cloud hosting**.
  - *Security by Design:* Path traversal attacks (e.g., `../../etc/passwd` or absolute path injection) are completely eliminated by rejecting any non-UUID string with a plain HTTP 422. Filesystem operations strictly concatenate `PROFILES_DIR / f"{uuid_str}.json"`. Denial of service is prevented by enforcing hard limits (50 profiles, 5,000 rows, 1 MB).
  - *Save-Time Quality Guard:* When saving or importing, readings are run through the baseline sigma estimator and 3-model BIC fit (`estimate_sigma_from_baseline`, `fit_three_models_bic_detailed`). If non-conforming, it triggers an amber honesty warning: *"This doesn't look like a clean normal run. Save anyway?"* with measured normal heat spread and noise, preventing accidental contamination of reference libraries while allowing intentional bypass (`force=true`).
  - *Limits of Demo Scenarios:*
    - The standard demo scenarios (Healthy, Factor 2.5 Anomaly, Stuck Sensor, +5 °C Bias, Jump at 35 s) are extreme, clear-cut illustrative cases designed for operational demonstration, not benchmark sensitivity limits.
    - Change-time error is exactly 0.00 s in clear-cut demos because the GLR candidate grid `np.arange(0.05, 0.75, 0.05)` has 5.0 s steps for $T=100$ s, and 35.0 s (0.35) coincides exactly with a discrete candidate point. It does not represent continuous timing accuracy, which is bounded by the discrete grid spacing ($\pm 2.5$ s).
    - Under harder conditions (evaluated across 20 uncherry-picked random seeds): weak sensor offset (~3$\sigma$ = +1.5 °C) is detected only 35% of the time (7/20; 12/20 buried in normal noise); a subtle heat spread change (factor 1.3) triggers GLR temporal shift detection (19/20 as Class C, 1 as Class F) rather than pure stationary anomalous diffusion (Class A).
- **Status:** **Decided by service architecture and physical operational requirements; frozen models and benchmark tables unchanged.**
- **Evidence File:** `service/profiles.py`, `service/app.py`, `service/models.py`, `tests/test_profiles.py`, `tools/eval_demo_scenarios_20seeds.py`.

---

### Decision 13: Operator Diagnosis Verdict Clarification, Detector Single-Reading Scope, and Operational Limits (thermalens-v17)
- **Context & Operational Feedback:**
  Operator feedback identified four areas of potential confusion in the Diagnosis and Operational Limits interfaces:
  1. *Reading vs Sensor Confusion:* Flagging "Sensor 3" implied the physical instrument channel was defective for the entire duration of the test, whereas the mathematical detector uses a point leave-one-out model that identifies a single corrupted reading.
  2. *Single-Reading Scope Clarity:* The detector was not clearly distinguished from a persistent stuck-sensor detector.
  3. *Plain Language Operational Limits:* The Limits page lacked plain, direct statements of the empirical failure modes identified in stress testing and demo evaluations.
  4. *Benchmark vs Demo Separation:* On the Evidence page, the 7 demo scenario outcomes (which include harder cases such as 30% shifts and 3σ offsets) were not positioned directly alongside the official 800-run Monte Carlo statistical benchmark.
- **Updates Made (Text-Only; Zero Model, Threshold, or Frozen Weight Changes):**
  1. *Verdict F Wording:* Replaced `One sensor looks faulty: Sensor 3` with `Reading #3 looks faulty (position 0.03 m, time 4.6 s)` while retaining the possible causes (`Possible causes: stuck, offset or wrong scale.`). The hand-off button is renamed from `Estimate without sensor 3` to `Estimate without reading 3`.
  2. *Detector Scope Statement:* Added explicit scope line in the "Show details" disclosure: *"The detector is built for one or two isolated bad readings, not a sensor that is wrong for the whole test."*
  3. *Limits Page Plain Additions:* Documented plainly:
     - (a) Small shifts in heat spread (e.g. 30%) are usually misread as a mid-test change (19/20 in our demo test).
     - (b) Weak offsets (about 3 sigma) are found about 35% of the time.
     - (c) Change times are located only on a 5 s grid between 5 s and 70 s of a 100 s test, and changes outside that window cannot be located.
     - (d) Fault model = one or two corrupted readings, not a stuck sensor over time.
     - (e) Reference run must be healthy.
  4. *Evidence Page Side-by-Side Presentation:* Positioned the 7-scenario demo table directly next to the Real Benchmark Table (800 Monte Carlo runs across N=10, σ=0.01) in a 2-column `.grid-2` layout, labeled prominently with the badge `demo cases, not benchmark accuracy`.
  5. *Chart Anti-Collision Resolution:* Added curve grouping for symmetric positions (`x=0.03, 0.07m`) and vertical separation of labels (upper above line, lower below line), confirming 0 label collisions at 1440px and 390px viewports.
- **Status:** **Text-only documentation, HTML, and UI polish; frozen models, thresholds, and benchmark tables unchanged.**
- **Evidence File:** `service/static/app.js`, `service/static/index.html`, `tests/test_playwright_diagnose.py`, `tests/test_playwright_shared_tabs.py`, `docs/ui_screenshots/diagnose_chart_1440px.png`, `docs/ui_screenshots/diagnose_chart_390px.png`.

---

### Limitations & Reproducibility Notes

1. **FNO Boundary Masking & Inference State (Mode 3 Reproducibility):**
   - *Historical State:* In the pre-cleanup codebase, `FNO2d.__init__` had `use_hard_mask=True` by default, which zeroed all four borders (spatial $x=0, 1$ and temporal $t=0, 1$). Zeroing $t=0$ and $t=1$ is unphysical for time-dependent heat diffusion where $t=0$ is the non-zero initial condition $u_0(x) = \sin(\pi x)$.
   - *Frozen Results Match Unmasked Inference:* Comparing empirical re-evaluations against `data/results/mode3_pipeline_results_v2.csv` on deterministic $\sigma=0$ bias floors shows that frozen Mode 3 results match unmasked inference ($0.0357$ vs $0.0336$ unmasked vs $0.1592$ masked at $\alpha=0.005$; $0.0021$ vs $0.0021$ unmasked vs $0.0078$ masked at $\alpha=0.100$). The $\sigma=0.01$ rows (evaluated over 20 episodes) are inconclusive due to a separate noise stream (e.g. $\alpha=2.5$ is numerically closer to masked in that particular 20-episode sample).
   - *Fix & Safeguards:* The default is explicitly passed everywhere in pipeline scripts, stored in checkpoint metadata, and strictly enforced via regression tests (`tests/test_fno_mask.py`). Final confirmation will be established during the Day-4 one-command pipeline re-run with fixed per-cell seeds.

2. **Global RNG State & Benchmark Noise Dependency:**
   - In earlier evaluation loops, sensor noise streams were drawn sequentially from the global NumPy random state (`np.random`), making individual cell realizations dependent on loop execution order and earlier cell sampling counts.
   - The Day-4 one-command benchmark evaluation must enforce deterministic, independent seeds per cell (e.g., `seed = base_seed + cell_idx`) so each cell's noisy episodes are strictly reproducible in isolation.

3. **Anomaly Detection Cascade Model Mismatch & Surrogate Scope Limitation:**
   - In `src/study_anomaly.py`, synthetic sensor observations for healthy and anomalous runs are generated using the exact series solution (`solve_heat_1d_exact`), and both the baseline and change-point hypotheses are fitted using that same analytic forward solution.
   - *Zero Model Mismatch:* Consequently, the anomaly module generates data with the same exact solver it fits with (zero model mismatch) and does not use the FNO surrogate in the online cascade detection loop.
   - *Stress Matrix Coverage:* This operational separation is deliberate and covered by the stress matrix: the forward surrogate approximation errors, parameter bias floors, and OOD generalization failure modes are independently audited in the inverse benchmark stress matrix (Modes 2, 3, and 3+), while the anomaly cascade isolates temporal change-point detection and hypothesis separation under controlled physical perturbations. Future online digital twin deployments must propagate surrogate residuals into the GLR threshold calibration.

