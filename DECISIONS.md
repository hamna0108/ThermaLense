# Architectural Decisions & Design Rationale

This document records the foundational architectural decisions made across the Digital Twin project, including options explored, the selected approach, technical justification, and empirical verification artifacts.

---

### Decision 1: Forward Neural Surrogate Architecture (Heat Equation)
- **Options Tried:**
  1. Pointwise parametric Physics-Informed Neural Network (PINN) trained with soft boundary and PDE residual losses.
  2. Fourier Neural Operator (FNO-2D) mapping parameter $\alpha$ and coordinate grids directly to solution fields.
- **Option Selected:** Fourier Neural Operator (FNO-2D) for digital twin surrogate; Bounded PINN (Exp D) as an alternative benchmark baseline.
- **Why:** FNO processes full spatiotemporal fields in a single forward pass, providing $>100\times$ faster batch evaluation latency than point-by-point MLP queries, while yielding $5\times$ lower relative $L_2$ error in interpolation splits.
- **Evidence File:** `plots/full_rollout_abs_error_comparison.png`, `data/mode3_pipeline_results_v2.csv`, `src/eval_final_all.py`.

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
- **Evidence File:** `src/eval_final_all.py`, `plots/t0_error_experiments.png`, `data/mode1_pinn_summary.csv`.

---

### Decision 3: Inverse Parameter Estimation Strategy
- **Options Tried:**
  1. *Mode 1:* Direct backpropagation through frozen PINN forward surrogate.
  2. *Mode 2:* Classical Crank-Nicolson finite-difference solver with spline interpolation and L-BFGS-B optimization.
  3. *Mode 3:* Autograd through precomputed FNO surrogate with spline interpolation.
  4. *Mode 3+ (Ablation):* Hybrid two-stage pipeline using Mode 3 for fast initial estimate followed by Crank-Nicolson Solver Polish.
- **Option Selected:** Mode 2 as the gold-standard classical solver; Mode 3 for rapid real-time estimation; Mode 3+ (Solver Polish) for deployable high-precision digital twins.
- **Why:** Mode 3 provides sub-millisecond execution ($<1.5$ ms) with near-optimal Cramér-Rao efficiency in the nominal parameter range $\alpha \in [0.05, 0.5]$, but exhibits spurious local minima for extreme $\alpha$. Mode 3+ polish eliminates boundary bias and matches classical solver precision at a fraction of standalone Mode 2 cost.
- **Evidence File:** `data/mode2_pipeline_results_v2.csv`, `data/mode3_pipeline_results_v2.csv`, `data/mode3plus_hybrid_results.csv`, `plots/inverse_pipeline_error_heatmaps.png`, `data/audit_report.txt`.

---

### Decision 4: Sensor Placement Strategy (Task A)
- **Options Tried:**
  1. Uniform temporal placement.
  2. Logarithmically spaced temporal placement.
  3. Random sampling.
  4. Concentrated placement at optimal time $t^*$.
  5. Two-stage adaptive placement (preliminary probe + focused clustering).
- **Option Selected:** Two-stage adaptive placement and logarithmic temporal distribution.
- **Why:** For large $\alpha$, heat decays rapidly, concentrating Fisher information at small $t$; for small $\alpha$, information accumulates over longer horizons. A single fixed uniform layout fails across disparate diffusion regimes. The two-stage adaptive strategy achieves estimator spread within $1.1\times$ of the Cramér-Rao lower bound across all cells.
- **Evidence File:** `data/sensor_placement_summary.csv`, `data/audit_sensor_placement.txt`, `data/raw/sensor_placement_raw.csv`.

---

### Decision 5: Anomaly Detection Architecture
- **Options Tried:**
  1. Simple thresholding on single-point sensor residual norm.
  2. Unsupervised PCA / autoencoder reconstruction error.
  3. Physics-informed multi-feature rule ensemble ($\chi^2$ goodness-of-fit, $z_{\max}$, fraction beyond $3\sigma$, leave-one-out cross validation, early vs late residual drift, Mode 3 vs Mode 2 divergence).
- **Option Selected:** Calibrated 7-feature rule ensemble with BIC model selection penalty.
- **Why:** Physical regime changes (wrong governing equation) produce global, temporally correlated residual growth, whereas sensor faults (dead sensors, bias, noise bursts) produce isolated, spatially localized deviations. The rule ensemble cleanly discriminates physical anomalies from sensor failure with $>95\%$ precision and recall.
- **Evidence File:** `data/audit_anomaly.txt`, `data/anomaly_summary.csv`, `data/raw/anomaly_raw.csv`.

---

### Decision 6: 2D Poisson Operator Formulation & Baseline Honesty
- **Options Tried:**
  1. Vanilla FNO-2D without explicit boundary constraints.
  2. Hard zero-boundary masked FNO-2D ($u_{x,y} = 0$ on $\partial\Omega$).
  3. Dual Linear Ridge Regression operator baseline ($u = G f$).
  4. Classical Sparse Direct Factorization (LU solver).
- **Option Selected:** Hard-zero masked FNO-2D paired with explicit baseline honesty disclosures.
- **Why:** Zero-boundary masking forces boundary error to exactly $0.0$. At $64\times 64$ resolution on CPU, the classical sparse direct solver is vastly faster ($0.53$ ms vs $23.3$ ms for FNO) and exact with zero parameters. Neural operators are disclosed honestly as solutions for parametric generalization and GPU batch throughput, not single-query CPU acceleration over classical linear solvers.
- **Evidence File:** `data/poisson_v2_benchmark_table.csv`, `data/timing_honesty.json`, `data/audit_poisson.txt`.
