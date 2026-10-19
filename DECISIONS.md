# Architectural Decisions & Design Rationale

This document records the foundational architectural decisions made across the Digital Twin project, including options explored, the selected approach, technical justification, and empirical verification artifacts.

---

### Decision 1: Forward Neural Surrogate Architecture (Heat Equation)
- **Options Tried:**
  1. Pointwise parametric Physics-Informed Neural Network (PINN) trained with soft boundary and PDE residual losses.
  2. Fourier Neural Operator (FNO-2D) mapping parameter $\alpha$ and coordinate grids directly to solution fields.
- **Option Selected:** Fourier Neural Operator (FNO-2D) for digital twin surrogate; Bounded PINN (Exp D) as an alternative benchmark baseline.
- **Why:** FNO processes full spatiotemporal fields in a single forward pass, providing $>100\times$ faster batch evaluation latency than point-by-point MLP queries, while yielding $5\times$ lower relative $L_2$ error in interpolation splits.
- **Status:** **Decided by evidence**
- **Evidence File:** `plots/full_rollout_abs_error_comparison.png`, `data/results/mode3_pipeline_results_v2.csv`, `src/eval_final_all.py`.

---

### Decision 2: Boundary & Initial Condition Enforcement (Ablation Series Exp A–D)
- **Options Tried:**
  1. *Baseline:* Unconstrained neural network with penalty weights in loss objective.
  2. *Exp A:* Soft-penalty PINN with tuning of PDE vs BC loss balancing.
  3. *Exp B:* Spatial boundary reparametrization $u(x, t) = \sin(\pi x) + x(1-x) N(x, t)$.
  4. *Exp C:* Hard boundary constraint on FNO Fourier modes.
  5. *Exp D:* Bounded temporal and spatial reparametrization $u(x, t) = \sin(\pi x) + x(1-x)(1 - e^{-5t}) N(x, t)$.
- **Option Selected:** Exp D (Bounded Reparametrization).
- **Why:** Standard FNO and PINNs exhibit significant error spikes at $t=0$ and non-zero boundary leakage. The bounded reparametrization strictly forces zero boundary violation for all $t$ and enforces exact initial conditions at $t=0$ by construction ($1 - e^0 = 0$).
- **Status:** **Decided by evidence**
- **Evidence File:** `src/eval_final_all.py`, `plots/t0_error_experiments.png`, `data/results/mode1_pinn_summary.csv`.

---

### Decision 3: Inverse Parameter Estimation Strategy & Mode 1 Retirement
- **Options Tried:**
  1. *Mode 1:* Direct backpropagation through frozen PINN forward surrogate.
  2. *Mode 2:* Classical Crank-Nicolson finite-difference solver with spline interpolation and L-BFGS-B optimization.
  3. *Mode 3:* Autograd through precomputed FNO surrogate with spline interpolation.
  4. *Mode 3+ (Ablation):* Hybrid two-stage pipeline using Mode 3 for fast initial estimate followed by Crank-Nicolson Solver Polish.
- **Option Selected:** Mode 2 as gold standard; Mode 3 for rapid real-time inversion; Mode 3+ (Solver Polish) for deployable twins. Mode 1 retired.
- **Why:** Mode 1 PINN surrogate inversion is competitive only within narrow interpolation ($\alpha \in [0.02, 0.1]$), but degrades catastrophically out-of-range ($\alpha = 2.5$, $16.8\text{--}28.0\%$ error; $3.3\times\text{--}20.2\times$ worse than classical solver) while running $4\times$ slower (~$7.0$ ms vs ~$1.8$ ms). Mode 3 provides sub-millisecond execution ($<1.5$ ms) with near-optimal Cramér-Rao efficiency, and Mode 3+ polish eliminates boundary bias at a fraction of standalone Mode 2 cost.
- **Status:** **Decided by evidence**
- **Evidence File:** `data/results/mode2_pipeline_results_v2.csv`, `data/results/mode3_pipeline_results_v2.csv`, `data/results/mode3plus_hybrid_results.csv`, `data/results/mode1_pinn_summary.csv`, `data/audits/audit_report.txt`, `data/audits/audit_pinn_report.txt`.

---

### Decision 4: Sensor Placement Strategy (Task A)
- **Options Tried:**
  1. Uniform temporal placement across $t \in [0, 1]$.
  2. Logarithmically spaced temporal placement.
  3. Random sampling.
  4. Concentrated placement at optimal time $t^*$.
  5. Two-stage adaptive placement (preliminary probe + Fisher-information-weighted clustering).
- **Option Selected:** Two-stage adaptive placement and logarithmic temporal distribution. Uniform dropped.
- **Why:** For large $\alpha$, heat decays rapidly, concentrating Fisher information at small $t$; for small $\alpha$, information accumulates over longer horizons. A single fixed uniform layout fails across disparate diffusion regimes. The two-stage adaptive strategy achieves estimator spread within $1.1\times$ of the Cramér-Rao lower bound across all cells.
- **Status:** **Decided by evidence**
- **Evidence File:** `data/results/sensor_placement_summary.csv`, `data/audits/audit_sensor_placement.txt`, `data/raw/sensor_placement_raw.csv`.

---

### Decision 5: Anomaly Cascade Order & Sensor Fault Disambiguation
- **Options Tried:**
  1. *C-First Cascade:* Testing physical change-points (Class C) before sensor faults (Class F).
  2. *Single-Sensor Stuck-at-Last-Good Heuristic:* Classifying freezing sensors via scalar residual thresholding.
  3. *Oracle-Grid GLR Testing:* Evaluating GLR only at synthetic training grid times ($t_c \in \{0.2, 0.4, 0.6, 0.8\}$).
  4. *Unanchored Joint-Estimation GLR:* Jointly estimating $\alpha_0$ and jump $\Delta\alpha$ from the test window.
- **Option Selected:** F-First Model-Selection Cascade with Leave-One-Out (LOO) spatial isolation, continuous off-grid GLR evaluation, and baseline-informed parameter anchoring.
- **Why:**
  - *C-First Dropped:* Evaluating Class C first caused localized sensor faults to trigger false physical alarms ($F \to C$ error $>25\%$). F-first cascade reduces strong fault leakage to $<10\%$.
  - *Stuck-at-Last-Good Disambiguation:* Freezing sensors diverge dynamically, mimicking physical shifts. LOO ratio cleanly isolates the deviation to a single channel ($k=1$), preventing false Class C flags.
  - *Oracle-Grid Dropped:* Continuous 2D GLR evaluated on off-grid physical change-points ($t_c \in \{0.15, 0.35, 0.70\}$, $m \in \{0.7, 1.5, 3.0\}$) proves the detector generalizes without grid-matching bias.
  - *Unanchored GLR Dropped:* Joint estimation under high noise ($\sigma=0.05$) suffers nuisance-parameter absorption (Class C recall drops to $37\%$). Anchoring $\alpha_0$ via a healthy baseline window surges recall back to $58\text{--}70\%$, recovering the gap to Neyman-Pearson Oracle power.
- **Status:** **Decided by evidence**
- **Evidence File:** `data/audits/audit_anomaly.txt` (Sections 3, 4, 5, 6), `data/results/anomaly_summary.csv`, `data/raw/anomaly_raw.csv`.

---

### Decision 6: 2D Poisson Operator Formulation & Baseline Honesty (v1 vs v2)
- **Options Tried:**
  1. *Poisson v1:* Vanilla FNO-2D without explicit boundary constraints; overlapping seeds with heat dataset.
  2. *Poisson v2:* Hard zero-boundary masked FNO-2D ($u_{x,y} = 0$ on $\partial\Omega$), strictly disjoint seeds (100000..600199), and verified second-order 5-point stencil solver ($O(h^2)$).
  3. *Linear Ridge Regression Operator Baseline:* Dual linear operator ($u = G f$).
  4. *Classical Sparse Direct Factorization:* Scipy sparse LU prefactorization.
- **Option Selected:** Poisson v2 with hard zero-boundary masking, paired with full baseline honesty disclosures.
- **Why:** Zero-boundary masking forces boundary violation to exactly $0.0$ by construction (vs $>10^{-2}$ in v1). Disjoint seed generation eliminates any split leakage. Timing benchmarks disclose that prefactorized classical sparse LU on CPU ($0.53$ ms) is vastly faster than neural operators ($23.3$ ms), clarifying that FNO's value lies in GPU batch throughput and parametric generalization, not single-solve CPU speedup.
- **Status:** **Decided by evidence**
- **Evidence File:** `data/results/poisson_v2_benchmark_table.csv`, `data/results/timing_honesty.json`, `data/audits/audit_poisson.txt` (Sections 1–7).
