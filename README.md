# Neural PDE Digital Twin: Physics-Informed Operator Learning

A production-grade, mathematically verified digital twin platform combining classical numerical solvers with neural operators (FNO-2D) and physics-informed neural networks (PINN) for transient and steady-state partial differential equations.

---

## Final Core Pipeline (10 Key Components)

The final, verified digital twin system comprises the following core modules in `src/`:

1. **`src/solvers/heat_1d.py`**: High-precision Crank-Nicolson finite-difference solver for 1D transient heat diffusion.
2. **`src/solvers/poisson_2d.py`**: Fast sparse LU direct solver for 2D Poisson boundary value problems.
3. **`src/models/fno2d.py`**: Fourier Neural Operator (FNO-2D) with optional zero-boundary hard masking.
4. **`src/train.py`**: Trains the official 1D Heat FNO forward surrogate (`models/fno2d_heat.pt`).
5. **`src/run_definitive_pipeline.py`**: Runs the definitive inverse benchmark evaluating Mode 2 (Crank-Nicolson Spline) and Mode 3 (FNO Spline).
6. **`src/run_hybrid_benchmark.py`**: Runs Mode 3+ (Solver Polish ablation) combining FNO initialization with fine solver convergence.
7. **`src/study_sensor_placement.py`**: Task A: Evaluates 7 spatial-temporal sensor placement strategies against the Cramér-Rao lower bound.
8. **`src/study_pinn_inverse.py`**: Task B: Evaluates Mode 1 frozen PINN surrogate parameter inversion.
9. **`src/study_anomaly.py`**: Evaluates 7-feature anomaly detection discriminating physical regime drift from sensor faults.
10. **`src/eval_poisson_v2.py`**: Comprehensive 2D Poisson evaluation comparing FNO and Linear baseline across 7 test splits.

---

## Quickstart & Execution Guide

### 1. Run Regression Tests
Verify system physics, stencil convergence orders, and model integrity:
```bash
pytest tests
```

### 2. Run Forward Surrogate Training
Train the core 1D heat and 2D Poisson surrogates:
```bash
python src/train.py
python src/train_fno_poisson_v2.py
```

### 3. Run Inverse Parameter Estimation Pipelines
Run the definitive inverse benchmarks:
```bash
# Mode 2 (Crank-Nicolson) and Mode 3 (FNO Spline)
python src/run_definitive_pipeline.py

# Mode 3+ Hybrid Solver Polish ablation
python src/run_hybrid_benchmark.py
```

### 4. Run Core Audits & Verifications
Run independent audit scripts checking results against stored baselines:
```bash
python src/audit_inverse.py
python src/audit_sensor_placement.py
python src/audit_pinn_inverse.py
python src/audit_anomaly.py
python src/audit_poisson.py
```

---

## Repository Architecture
- `src/`: Final library, forward models, inverse pipelines, studies, and audit verifications.
- `data/`: Final datasets, simulation replications, benchmark CSVs, and audit reports.
- `models/`: Production neural network checkpoints and fitted linear baseline parameters.
- `plots/`: Diagnostic curves, loss landscapes, and 3x3 error heatmaps.
- `experiments/`: Ablation studies (Exp A–D), PINN variants, and rollout diagnostics (see `experiments/README.md`).
- `tools/`: Post-processing table generators and markdown export utilities.
- `archive/`: Historical superseded code, v1 Poisson benchmarks, and scratch extraction files (see `archive/INDEX.md`).
- `docs/`: Project brief specifications and system architecture documents.
- `reports/`: Audit plans and reorganization reports (`reports/cleanup_plan.md`).
- `EXPERIMENTS.md`: Complete register of all ablation studies, inputs, and outputs.
- `DECISIONS.md`: Design rationale records (options tried $\to$ chosen $\to$ evidence).
- `run_manifest.json`: Canonical metadata manifest tracking all simulation seeds and artifact paths.
