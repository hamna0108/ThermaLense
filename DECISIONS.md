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
  - *Construction vs Learned Accuracy ($t = 0$):* By mathematical construction, at $t = 0$ the temporal factor $(1 - e^0) = 0$ in Exp D (and $t = 0$ in Exp B/C), identically collapsing $u(x, 0) \equiv \sin(\pi x)$ down to float precision ($4.79 \times 10^{-8}$ for PINN, $5.06 \times 10^{-8}$ for FNO). Because initial condition error is eliminated by algebraic construction rather than learned optimization, comparing $t=0$ error alone evaluates the mathematical formula, not surrogate accuracy.
  - *Learned Accuracy ($t > 0$ and Full Field):*
    - *PINN Models:* Baseline unconstrained PINN (`pinn_base`) achieves interpolation median relative $L_2$ error of 0.02753 (P90: 0.21474). Exp B achieves 0.00775 (P90: 0.05087). Exp D achieves 0.00882 with a dramatically tighter tail (P90: 0.01303, a $3.9\times$ reduction in 90th-percentile error over Exp B). In Low-$\alpha$ OOD, Exp D achieves 0.04084 vs 0.09631 for base.
    - *FNO Models (Accuracy Trade-off):* The historical apparent degradation of FNO base (0.1655) and FNO Exp C/D (0.1047) was caused entirely by `use_hard_mask=True` in `src/models/fno2d.py`, which zeroed time boundaries ($t=0$ and $t=1$). When evaluated under the correct unmasked configuration (`use_hard_mask=False`):
      - `fno_expC` achieves the lowest interpolation error at **0.23%** (0.00228, P90: 0.01710), with $t=1.0$ MAE of $0.00054$.
      - `fno_expD` achieves **0.31%** (0.00306, P90: 0.01043) on interpolation, the lowest Low-$\alpha$ OOD error at **0.28%** (0.00280), and $t=1.0$ MAE of $0.00096$.
      - `fno_base` achieves **0.45%** (0.00448, P90: 0.00582) on interpolation and **0.46%** (0.00455) on Low-$\alpha$ OOD, but delivers superior High-$\alpha$ OOD robustness at **12.8%** (0.12772) vs 34.6% for Exp D and 42.9% for Exp C. Its unconstrained $t=0$ MAE is already very small ($0.00213$).
      Because `fno_base` avoids high-alpha failure while remaining within 0.15%–0.22% of Exp C/D in-distribution, it is chosen as the standard for Mode 3, while `fno_expD` provides an exact hard-boundary alternative ($0.31\%$ in-range error).
  - *FNO Training Specifications & Budgets:*
    | Model | Training Samples | Epochs | Batch Size | Optimizer / LR Schedule | Dataset Seed |
    | :--- | :--- | :--- | :--- | :--- | :--- |
    | `fno_base` | 1,000 | 100 | 20 (50 steps/epoch) | Adam ($10^{-3}$, decay $10^{-4}$), StepLR(50, 0.5) | 42 |
    | `fno_expC` | 1,000 | 100 | 20 (50 steps/epoch) | Adam ($10^{-3}$, decay $10^{-4}$), StepLR(50, 0.5) | 42 |
    | `fno_expD` | 1,000 | 100 | 20 (50 steps/epoch) | Adam ($10^{-3}$, decay $10^{-4}$), StepLR(50, 0.5) | 42 |

    *Note on Training Budgets:* All three FNO variants (`fno_base`, `fno_expC`, `fno_expD`) share the identical training budget of 1,000 training trajectories from `data/datasets/train.npz` (evaluated on 200 validation trajectories from `val.npz`), 100 epochs, and 5,000 gradient updates. Historical notes referencing "80 samples" reflected early exploratory sub-splits or a 80/20 train/val percentage, whereas all finalized benchmark checkpoints were trained on the complete 1,000-sample dataset.
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
    4. *Timing Honesty Disclosures:* At 64x64 resolution on CPU (`data/results/timing_honesty.json`), the classical sparse direct solver is vastly faster than FNO on CPU: 0.501 ms vs 20.477 ms single-query (40.9x faster), and 0.255 ms vs 5.590 ms batched (21.9x faster). Even rebuilding and re-factorizing the sparse matrix from scratch on every query (10.925 ms) is $\sim 1.9\times$ faster than FNO forward inference latency (CPU, 64x64). GPU inference not measured. (See `data/results/timing_honesty.json`, `data/audits/audit_poisson.txt` Section 6).
- **Status:** **Decided by evidence**
- **Evidence File:** `archive/superseded/train_fno_poisson.py` (lines 14, 31, 52), `src/train_fno_poisson_v2.py` (lines 36–58), `archive/superseded/generate_poisson_dataset.py`, `src/data/generate_poisson_dataset_v2.py`, `data/results/poisson_v2_benchmark_table.csv`, `data/results/timing_honesty.json`, `data/audits/audit_poisson.txt` (Sections 1–7).

---

### Limitations & Reproducibility Notes

1. **FNO Boundary Masking & Inference State (Mode 3 Reproducibility):**
   - *Historical State:* In the pre-cleanup codebase, `FNO2d.__init__` had `use_hard_mask=True` by default, which zeroed all four borders (spatial $x=0, 1$ and temporal $t=0, 1$). Zeroing $t=0$ and $t=1$ is unphysical for time-dependent heat diffusion where $t=0$ is the non-zero initial condition $u_0(x) = \sin(\pi x)$.
   - *Frozen Results Match Unmasked Inference:* Comparing empirical re-evaluations against `data/results/mode3_pipeline_results_v2.csv` on deterministic $\sigma=0$ bias floors shows that frozen Mode 3 results match unmasked inference ($0.0357$ vs $0.0336$ unmasked vs $0.1592$ masked at $\alpha=0.005$; $0.0021$ vs $0.0021$ unmasked vs $0.0078$ masked at $\alpha=0.100$). The $\sigma=0.01$ rows (evaluated over 20 episodes) are inconclusive due to a separate noise stream (e.g. $\alpha=2.5$ is numerically closer to masked in that particular 20-episode sample).
   - *Fix & Safeguards:* The default is explicitly passed everywhere in pipeline scripts, stored in checkpoint metadata, and strictly enforced via regression tests (`tests/test_fno_mask.py`). Final confirmation will be established during the Day-4 one-command pipeline re-run with fixed per-cell seeds.

2. **Global RNG State & Benchmark Noise Dependency:**
   - In earlier evaluation loops, sensor noise streams were drawn sequentially from the global NumPy random state (`np.random`), making individual cell realizations dependent on loop execution order and earlier cell sampling counts.
   - The Day-4 one-command benchmark evaluation must enforce deterministic, independent seeds per cell (e.g., `seed = base_seed + cell_idx`) so each cell's noisy episodes are strictly reproducible in isolation.

3. **Anomaly Detection Cascade Model Mismatch Limitation:**
   - In `src/study_anomaly.py`, synthetic sensor observations for healthy and anomalous runs are generated using the exact series solution (`solve_heat_1d_exact`), and both the baseline and change-point hypotheses are fitted using that same analytic forward solution.
   - *Zero Model Mismatch:* Consequently, this study tests temporal change-point estimation and hypothesis separation under zero model mismatch; it does not evaluate how surrogate approximation errors (such as PINN or FNO surrogate residuals) propagate into false alarm rates or change-point localization errors.

