# Experiments Directory

This directory contains standalone, runnable ablation studies and baseline evaluations conducted during project development.

## Running Experiment Modules

All experiments import dependencies from the core library (`src/`) and can be executed as Python modules directly from the repository root:

```bash
# Evaluate full rollout error comparison across models
python -m experiments.eval_full_rollout

# Run ablation diagnostic on initial condition error
python -m experiments.diagnostics_exp

# Train Exp A (soft-penalty PINN)
python -m experiments.train_pinn_expA

# Train Exp B (reparametrized PINN)
python -m experiments.train_pinn_expB

# Train Exp C (reparametrized FNO)
python -m experiments.train_expC

# Train base parametric PINN
python -m experiments.train_pinn

# Evaluate FNO out-of-distribution generalization
python -m experiments.eval_fno_compare

# Summarize errors across all heat ablation models
python -m experiments.eval_summary
```

## Structure
- `models/`: Checkpoints produced by and evaluated in experiment ablations (`pinn_expA.pt`, `pinn_expB.pt`, `fno2d_expC.pt`, `pinn_heat.pt`).
- `train_*.py`: Training scripts for model variants.
- `eval_*.py`: Quantitative rollout and generalization evaluation routines.
- `diagnostics*.py`: Analytical diagnostic scripts for initial condition and boundary behavior.
